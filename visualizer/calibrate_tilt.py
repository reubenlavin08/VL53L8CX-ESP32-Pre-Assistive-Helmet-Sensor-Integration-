"""
Solve for the sensor's mount pitch angle from a wall-stare capture.

Given:
  - A raw-frames CSV (200 frames x 64 zones x distance/sigma/status)
  - Known horizontal distance H from sensor to a flat vertical wall
  - Known sensor height (irrelevant to pitch fit, just logged)

The sensor's optical axis pitches DOWN by some angle theta. Each row r in the
rotated body-frame grid has a fixed elevation offset from the optical axis:
  alpha_r = (r - 3.5) * 5.625 deg     for an 8x8 grid (row 0 = top, row 7 = bottom)

A ray's true elevation below horizontal = alpha_r + theta.
Slant distance to a vertical wall at horizontal H:
  D(r, theta) = H / cos(alpha_r + theta)

We fit theta by minimizing sum_r (D_measured(r) - D(r, theta))^2 across rows.
Middle columns only (col 2..5) to avoid horizontal-angle slant on the edges.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar


CSV    = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("raw_frames/wall-tilt-calib-h185cm-d81cm_20260525-113330.csv")
H_MM   = float(sys.argv[2]) if len(sys.argv) > 2 else 813.0          # horizontal distance to wall (mm)
H_SENS = float(sys.argv[3]) if len(sys.argv) > 3 else 1854.0         # sensor height (mm, logged only)
SIDE   = 8
DEG_PER_ZONE = 45.0 / SIDE                                            # 5.625 deg

print(f"Loading: {CSV}")
print(f"Geometry: wall at H = {H_MM:.0f} mm horizontal, sensor at height {H_SENS:.0f} mm")
print()

df = pd.read_csv(CSV)
n_frames = len(df)
print(f"Frames: {n_frames}")

# Extract distance grid: shape (n_frames, 64), masked invalid -> NaN
dist_cols = [f"dist_z{z}" for z in range(SIDE * SIDE)]
D = df[dist_cols].values.astype(float)
D[D >= 4000] = np.nan

# Per-zone mean across frames, reshape to (row, col)
zone_mean = np.nanmean(D, axis=0).reshape(SIDE, SIDE)

# Per-row mean using middle columns only (cols 2-5), so horizontal-angle slant doesn't pollute
MID_COLS = [2, 3, 4, 5]
row_means = np.nanmean(zone_mean[:, MID_COLS], axis=1)

print("Per-zone mean distance (mm) -- full grid:")
print(np.round(zone_mean, 0).astype(int))
print()
print("Per-row mean distance (middle 4 cols only), mm:")
for r in range(SIDE):
    alpha_r_deg = (r - (SIDE - 1) / 2.0) * DEG_PER_ZONE
    print(f"  row {r}: alpha_offset = {alpha_r_deg:+6.2f} deg, mean = {row_means[r]:7.1f} mm")
print()

# Predicted slant distance for a given pitch theta (degrees, positive = down)
def predicted_per_row(theta_deg):
    pred = np.zeros(SIDE)
    for r in range(SIDE):
        alpha_r = (r - (SIDE - 1) / 2.0) * DEG_PER_ZONE
        true_elev = np.radians(alpha_r + theta_deg)
        pred[r] = H_MM / np.cos(true_elev)
    return pred

# SSE between measured and predicted, over rows with valid data
def sse(theta_deg):
    pred = predicted_per_row(theta_deg)
    valid = ~np.isnan(row_means)
    return float(np.sum((row_means[valid] - pred[valid]) ** 2))

# Search over plausible pitch range: -30 to +30 degrees
result = minimize_scalar(sse, bounds=(-30.0, 30.0), method="bounded",
                         options={"xatol": 1e-3})
theta_fit = float(result.x)
sse_fit   = float(result.fun)

print(f"=== FIT RESULT ===")
print(f"  Sensor pitch (positive = pointing DOWN from horizontal): {theta_fit:+.2f} deg")
print(f"  SSE at fit: {sse_fit:.1f} mm^2  (RMS per row: {(sse_fit / SIDE) ** 0.5:.2f} mm)")
print()

print("Measured vs predicted per row:")
pred_fit = predicted_per_row(theta_fit)
print(f"  {'row':>4}  {'alpha':>8}  {'measured':>10}  {'predicted':>11}  {'residual':>10}")
for r in range(SIDE):
    alpha_r = (r - (SIDE - 1) / 2.0) * DEG_PER_ZONE
    print(f"  {r:>4}  {alpha_r:+7.2f}  {row_means[r]:>9.1f}  {pred_fit[r]:>10.1f}  {row_means[r] - pred_fit[r]:>+9.1f}")
