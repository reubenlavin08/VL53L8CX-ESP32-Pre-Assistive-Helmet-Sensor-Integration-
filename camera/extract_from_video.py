#!/usr/bin/env python3
"""
extract_from_video.py - pull good calibration frames out of a recorded video.

You wave the board in front of the camera while ffmpeg records. This then walks
the video offline, finds every frame where the full checkerboard is detected,
and keeps a spread of them: it rejects frames whose board sits in nearly the same
place as one already kept, so the result covers the whole image instead of 200
near-identical views of the centre.

Offline means nothing is racing a live preview - detection can take as long as it
likes on every frame.

Usage:  python camera/extract_from_video.py [video_path] [max_frames]
Writes: camera/calib_shots/calib_###.png
Then:   python camera/calibrate_fisheye.py
"""
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calib_shots")
VIDEO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "calib_video.mkv")
MAX_FRAMES = int(sys.argv[2]) if len(sys.argv) > 2 else 30

BOARD = (8, 11)
# Reject a new frame if the board centre is within this many px of a kept one AND
# the board covers a similar area - i.e. it is basically the same viewpoint.
MIN_CENTRE_DIST = 90.0
MIN_AREA_RATIO = 0.75
# Reject frames where the board is too small to localise corners accurately.
# Measured on a real recording: a letter-size board on this 140 deg lens gives
# 1.3-7.4% fill at normal arm's-length distances, so 8% rejected everything.
# 3% ~= 20 px per square, which is workable. Bigger is still better.
MIN_FILL = 0.03
# Reject motion-blurred views - blurred corners are exactly what inflates RMS.
MIN_SHARP = 300.0

FIND_FLAGS = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE

if not os.path.exists(VIDEO):
    raise SystemExit(f"No video at {VIDEO}")

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.startswith("calib_") and f.endswith(".png"):
        os.remove(os.path.join(OUT, f))

cap = cv2.VideoCapture(VIDEO)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"video: {VIDEO}  frames: {total}")

kept = []          # (centre_xy, area)
saved = 0
idx = 0
detected = 0
too_small = 0
blurry = 0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    idx += 1
    if idx % 2:                      # every 3rd frame is plenty at 30 fps
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, BOARD, FIND_FLAGS)
    if not found:
        continue
    detected += 1

    c = corners.reshape(-1, 2)
    centre = np.array([c[:, 0].mean(), c[:, 1].mean()])
    area = float(np.ptp(c[:, 0]) * np.ptp(c[:, 1]))

    fill = area / float(frame.shape[0] * frame.shape[1])
    if fill < MIN_FILL:
        too_small += 1
        continue

    # sharpness measured over the board region only
    x0, x1 = int(max(0, c[:, 0].min())), int(c[:, 0].max())
    y0, y1 = int(max(0, c[:, 1].min())), int(c[:, 1].max())
    crop = gray[y0:y1, x0:x1]
    if crop.size == 0 or cv2.Laplacian(crop, cv2.CV_64F).var() < MIN_SHARP:
        blurry += 1
        continue

    novel = True
    for kc, ka in kept:
        if (np.linalg.norm(centre - kc) < MIN_CENTRE_DIST
                and min(area, ka) / max(area, ka) > MIN_AREA_RATIO):
            novel = False
            break
    if not novel:
        continue

    p = os.path.join(OUT, f"calib_{saved:03d}.png")
    cv2.imwrite(p, frame)
    kept.append((centre, area))
    saved += 1
    print(f"  kept {os.path.basename(p)}  centre=({centre[0]:.0f},{centre[1]:.0f})  "
          f"fills {area/(frame.shape[0]*frame.shape[1])*100:.1f}%")
    if saved >= MAX_FRAMES:
        break

cap.release()
print(f"\nscanned {idx} frames, board detected in {detected}, "
      f"rejected {too_small} too-small + {blurry} blurry, kept {saved} distinct views")
if too_small > detected * 0.5:
    print("*** Most views were too small. HOLD THE BOARD MUCH CLOSER - it should fill")
    print("*** roughly a third to a half of the frame, not a small patch in the middle.")

if saved:
    # crude coverage report over a 3x3 grid, same idea as the live tool had
    fw, fh = 1280, 720
    grid = np.zeros((3, 3), int)
    for (cx, cy), _ in kept:
        grid[min(2, int(cy / fh * 3)), min(2, int(cx / fw * 3))] += 1
    print("\ncoverage (3x3 across the frame):")
    for row in grid:
        print("   " + "  ".join(f"{v:2d}" for v in row))
    empty = int((grid == 0).sum())
    if empty:
        print(f"WARNING: {empty} of 9 regions have no views - the fisheye distortion")
        print("         terms will be poorly determined there. Record more, moving the")
        print("         board into the frame edges and corners.")

if saved < 10:
    print("\nToo few views. Record again: keep the WHOLE board in shot, well lit,")
    print("no glare, and tilt it 30-45 degrees in varied directions.")
else:
    print("\nNext: python camera/calibrate_fisheye.py")
