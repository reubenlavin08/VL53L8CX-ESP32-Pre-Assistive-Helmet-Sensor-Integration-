"""
VL53L8CX tuning measurement script.

Captures N frames of paired DATA:/SIGMA: lines from the ESP32 firmware over
serial, computes per-zone statistics (mean distance, our measured standard
deviation across frames, valid yield, mean sensor-reported sigma_mm), and
writes both a stdout summary + a CSV log row per zone per run.

The CSV accumulates across runs — one file is your full experiment log.

Usage:
    python measure.py --port COM12 --baud 115200 \\
                      --frames 200 \\
                      --config "baseline-15hz-8x8" \\
                      --csv measurements.csv
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import serial


TOTAL_ZONES = 64
INVALID_DISTANCE_MM = 4000   # firmware sentinel for filtered zones


def parse_data_line(line):
    if not line.startswith("DATA:"):
        return None
    try:
        values = [int(v) for v in line[5:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=int)


def parse_sigma_line(line):
    if not line.startswith("SIGMA:"):
        return None
    try:
        values = [int(v) for v in line[6:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=int)


def capture_frames(port, baud, n_frames):
    """Read paired DATA:/SIGMA: lines until we have n_frames complete pairs."""
    distances = []
    sigmas = []

    with serial.Serial(port, baud, timeout=2) as ser:
        ser.reset_input_buffer()
        current_data = None
        captured = 0

        print(f"Capturing {n_frames} frames from {port}@{baud}...")
        while captured < n_frames:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            data = parse_data_line(line)
            sigma = parse_sigma_line(line)

            if data is not None:
                current_data = data
            elif sigma is not None and current_data is not None:
                distances.append(current_data)
                sigmas.append(sigma)
                current_data = None
                captured += 1
                if captured % 20 == 0 or captured == n_frames:
                    print(f"  {captured}/{n_frames}")

    return np.array(distances), np.array(sigmas)


def compute_stats(distances, sigmas):
    """
    distances: (n_frames, 64) ints, INVALID_DISTANCE_MM = filtered zone
    sigmas:    (n_frames, 64) ints, sensor-reported range_sigma_mm
    Returns a list of 64 per-zone dicts.
    """
    n_frames, n_zones = distances.shape
    out = []

    for z in range(n_zones):
        zone_d = distances[:, z]
        zone_s = sigmas[:, z]
        valid = zone_d != INVALID_DISTANCE_MM
        n_valid = int(valid.sum())
        yld = n_valid / n_frames

        if n_valid >= 2:
            mean_d = float(zone_d[valid].mean())
            our_sigma = float(zone_d[valid].std(ddof=1))      # sample std
            mean_ssig = float(zone_s[valid].mean())
        else:
            mean_d = our_sigma = mean_ssig = float("nan")

        out.append({
            "zone": z,
            "n_total": n_frames,
            "n_valid": n_valid,
            "mean_mm": mean_d,
            "our_sigma_mm": our_sigma,
            "valid_yield": yld,
            "mean_sensor_sigma_mm": mean_ssig,
        })

    return out


def print_summary(config, results):
    valid_rows = [r for r in results if not np.isnan(r["our_sigma_mm"])]
    if not valid_rows:
        print(f"\n{config}  |  NO VALID ZONES — check wiring / mode")
        return

    our_sigmas      = [r["our_sigma_mm"]         for r in valid_rows]
    sensor_sigmas   = [r["mean_sensor_sigma_mm"] for r in valid_rows]
    overall_yield   = float(np.mean([r["valid_yield"] for r in results]))

    print()
    print(f"  {config}")
    print(f"    median (our σ across zones)     = {np.median(our_sigmas):7.2f} mm")
    print(f"    median (sensor sigma_mm)        = {np.median(sensor_sigmas):7.2f} mm")
    print(f"    overall valid yield             = {overall_yield * 100:6.1f} %")
    print(f"    zones reporting / total         = {len(valid_rows)} / {TOTAL_ZONES}")


def write_csv(csv_path, config, results):
    path = Path(csv_path)
    write_header = not path.exists()
    ts = datetime.now().isoformat(timespec="seconds")

    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "timestamp", "config", "zone",
                "n_total", "n_valid",
                "mean_mm", "our_sigma_mm",
                "valid_yield", "mean_sensor_sigma_mm",
            ])
        for r in results:
            w.writerow([
                ts, config, r["zone"],
                r["n_total"], r["n_valid"],
                f"{r['mean_mm']:.2f}"             if not np.isnan(r['mean_mm']) else "",
                f"{r['our_sigma_mm']:.2f}"        if not np.isnan(r['our_sigma_mm']) else "",
                f"{r['valid_yield']:.3f}",
                f"{r['mean_sensor_sigma_mm']:.2f}" if not np.isnan(r['mean_sensor_sigma_mm']) else "",
            ])


def main():
    p = argparse.ArgumentParser(description="VL53L8CX tuning measurement (precision-only).")
    p.add_argument("--port",    default="COM12")
    p.add_argument("--baud",    type=int, default=115200)
    p.add_argument("--frames",  type=int, default=200)
    p.add_argument("--config",  required=True, help="label for this run, e.g. 'baseline-15hz-8x8'")
    p.add_argument("--csv",     default="measurements.csv")
    args = p.parse_args()

    distances, sigmas = capture_frames(args.port, args.baud, args.frames)
    results = compute_stats(distances, sigmas)
    print_summary(args.config, results)
    write_csv(args.csv, args.config, results)
    print(f"\n  CSV row(s) appended to: {Path(args.csv).resolve()}")


if __name__ == "__main__":
    main()
