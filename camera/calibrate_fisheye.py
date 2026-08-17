#!/usr/bin/env python3
"""
calibrate_fisheye.py - fit the lens model to the captured checkerboard images.

WHAT COMES OUT
  K - the camera matrix. Its four useful numbers are fx, fy (focal length measured
      in PIXELS) and cx, cy (where the optical axis actually hits the sensor - the
      true image centre, which is never exactly width/2, height/2).
  D - four fisheye distortion coefficients k1..k4 describing how the lens bends a
      straight line outward.
Together they let us convert "a direction in 3D space" <-> "a pixel", which is the
one operation the whole ToF-camera fusion depends on.

WHY cv2.fisheye AND NOT THE NORMAL MODEL
The standard pinhole model (cv2.calibrateCamera) assumes a ray at angle theta lands
at distance f*tan(theta) from centre. At 140 degrees tan(theta) explodes and the fit
fails or gets badly biased. The fisheye / Kannala-Brandt model uses theta itself as
the base and adds four odd-power correction terms, which stays well-behaved right
out to the edge. Rule of thumb: above about 120 degrees, use fisheye.

READING THE RESULT
RMS reprojection error = take each detected corner, predict where the fitted model
says it should be, measure the gap in pixels, RMS them all.
  < 0.5 px  good, use it
  0.5-1.0   usable, more/steadier views would improve it
  > 1.0     something is off: board not flat, focus changed, blurry frames,
            or a bad image dragging the fit
Per-image errors are printed so a single bad frame is easy to spot and delete.

Usage:  python camera/calibrate_fisheye.py
Writes: camera/calibration_720p.npz  (K, D, image_size, rms, board, square_mm)
        camera/calibration_720p.txt  (human-readable, includes the measured FOV)
        camera/undistort_preview.jpg (before/after, to eyeball straight lines)
"""
import glob
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "calib_shots")
NPZ = os.path.join(HERE, "calibration_720p.npz")
TXT = os.path.join(HERE, "calibration_720p.txt")
PREVIEW = os.path.join(HERE, "undistort_preview.jpg")

BOARD = (8, 11)        # inner corners, must match capture_calib.py / the PDF
# MEASURED: the printed 100 mm verification bar came out at 98 mm, so the printer
# scaled by 0.98 -> squares are 20.0 * 0.98 = 19.6 mm.
# (A uniform scale error like this does NOT affect K or D - it only rescales the
# per-image translation vectors - but Stage 3 needs real millimetres, so fix it here.)
SQUARE_MM = 19.6

SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
CALIB_TERM = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)
FLAGS = (cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
         cv2.fisheye.CALIB_FIX_SKEW)

# One object-point set: the board's corners in millimetres, z = 0 (it is flat).
objp = np.zeros((1, BOARD[0] * BOARD[1], 3), np.float64)
objp[0, :, :2] = np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2) * SQUARE_MM

files = sorted(glob.glob(os.path.join(SHOTS, "calib_*.png")))
if not files:
    raise SystemExit(f"No images in {SHOTS}. Run capture_calib.py first.")

objpoints, imgpoints, used, size = [], [], [], None
print(f"Scanning {len(files)} images for the {BOARD[0]}x{BOARD[1]} corner grid...")
for f in files:
    img = cv2.imread(f)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if size is None:
        size = gray.shape[::-1]
    ok, corners = cv2.findChessboardCorners(
        gray, BOARD, cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        print(f"  skip (no board): {os.path.basename(f)}")
        continue
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), SUBPIX)
    objpoints.append(objp.copy())
    imgpoints.append(corners.reshape(1, -1, 2).astype(np.float64))
    used.append(f)

print(f"{len(used)} usable images.")
if len(used) < 8:
    raise SystemExit("Need at least ~8 (ideally 20+). Capture more, vary tilt and position.")

K = np.zeros((3, 3))
D = np.zeros((4, 1))

# CALIB_CHECK_COND throws on a single degenerate image and names its index, so we
# drop that image and retry rather than failing outright.
while True:
    try:
        rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
            objpoints, imgpoints, size, K, D,
            flags=FLAGS | cv2.fisheye.CALIB_CHECK_COND, criteria=CALIB_TERM)
        break
    except cv2.error as e:
        s = str(e)
        idx = None
        if "CALIB_CHECK_COND" in s and "input array" in s:
            try:
                idx = int(s.split("input array")[1].split()[0])
            except Exception:
                idx = None
        if idx is None or idx >= len(objpoints):
            print("Retrying without CALIB_CHECK_COND...")
            rms, K, D, rvecs, tvecs = cv2.fisheye.calibrate(
                objpoints, imgpoints, size, K, D, flags=FLAGS, criteria=CALIB_TERM)
            break
        print(f"  dropping degenerate image {os.path.basename(used[idx])}")
        for lst in (objpoints, imgpoints, used):
            lst.pop(idx)
        if len(used) < 8:
            raise SystemExit("Too many images dropped. Recapture.")

# ---- per-image error, so a single bad frame is visible ----
errs = []
for i in range(len(objpoints)):
    proj, _ = cv2.fisheye.projectPoints(objpoints[i], rvecs[i], tvecs[i], K, D)
    e = float(np.linalg.norm(imgpoints[i].reshape(-1, 2) - proj.reshape(-1, 2), axis=1).mean())
    errs.append(e)

fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
w, h = size
# Measured FOV from the fitted model: map the extreme pixel back to an angle.
# The Kannala-Brandt model is angle-based, so undistortPoints gives the true ray.
def fov_deg(px, py, ccx, ccy):
    pts = np.array([[[px, py]]], dtype=np.float64)
    und = cv2.fisheye.undistortPoints(pts, K, D)
    return float(np.degrees(np.arctan(np.linalg.norm(und[0, 0]))))

hfov = fov_deg(w - 1, h / 2.0, cx, cy) + fov_deg(0, h / 2.0, cx, cy)
vfov = fov_deg(w / 2.0, 0, cx, cy) + fov_deg(w / 2.0, h - 1, cx, cy)
dfov = fov_deg(w - 1, h - 1, cx, cy) + fov_deg(0, 0, cx, cy)

verdict = ("GOOD - use it" if rms < 0.5 else
           "USABLE - more/steadier views would help" if rms < 1.0 else
           "POOR - check board flatness, focus, and blurry frames")

report = f"""HBV-1716WA fisheye calibration  ({w}x{h}, MJPG)
images used : {len(used)}
board       : {BOARD[0]}x{BOARD[1]} inner corners, {SQUARE_MM:g} mm squares
RMS reprojection error : {rms:.4f} px   -> {verdict}

K =
{np.array2string(K, precision=4, suppress_small=True)}

D (k1..k4) =
{np.array2string(D.ravel(), precision=6, suppress_small=True)}

fx = {fx:.3f} px    fy = {fy:.3f} px
cx = {cx:.3f} px    cy = {cy:.3f} px      (frame centre would be {w/2:.1f}, {h/2:.1f})

MEASURED field of view (this replaces the extrapolated ~109/67 guess):
  horizontal {hfov:6.2f} deg
  vertical   {vfov:6.2f} deg
  diagonal   {dfov:6.2f} deg   (box claims 140 deg diagonal)

per-image mean error (px):
""" + "\n".join(f"  {e:6.3f}  {os.path.basename(f)}" for e, f in
                sorted(zip(errs, used), reverse=True))

print("\n" + report)
with open(TXT, "w") as fh:
    fh.write(report + "\n")
np.savez(NPZ, K=K, D=D, image_size=np.array(size), rms=rms,
         board=np.array(BOARD), square_mm=SQUARE_MM)

# ---- visual check: straight lines should come out straight ----
img = cv2.imread(used[len(used) // 2])
newK = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(K, D, size, np.eye(3), balance=0.5)
m1, m2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), newK, size, cv2.CV_16SC2)
und = cv2.remap(img, m1, m2, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
pair = np.hstack([img, und])
cv2.putText(pair, "RAW (fisheye)", (14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
cv2.putText(pair, "UNDISTORTED - board edges should be straight",
            (w + 14, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
cv2.imwrite(PREVIEW, pair)

print(f"\nwrote {NPZ}\nwrote {TXT}\nwrote {PREVIEW}")
print("\nNOTE: we do NOT undistort for fusion - the preview is only a sanity check.")
print("Fusion keeps the raw fisheye frame and projects ToF zones into it with")
print("cv2.fisheye.projectPoints, which wastes no field of view and resamples nothing.")
