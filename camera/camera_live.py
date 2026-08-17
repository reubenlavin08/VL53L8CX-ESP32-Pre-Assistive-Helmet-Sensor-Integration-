#!/usr/bin/env python3
"""
camera_live.py - live viewer for the HBV-1716WA with a mode toggle + brightness readout.

Built during Phase-2 bring-up because MJPEG 1080p was returning all-black frames
while YUY2 640x480 returned (dim but real) data - this lets us watch both live.

Keys:  m = toggle MJPG 1920x1080  <->  YUY2 640x480
       s = save snapshot to camera/snapshots/
       q / Esc = quit

The green HUD shows mean/max pixel brightness. max ~= 0 means no light is
reaching the sensor (lens covered) or the mode is broken; a real scene in
room light should read mean 60-140.
"""
import os
import sys
import time

import cv2

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1

# MJPG 1280x720 is THE working mode on this unit and the one we calibrate at.
# MJPG 1920x1080 is deliberately absent: this module's firmware declares uncompressed
# bitrates in its MJPEG descriptors, so 1080p never gets bandwidth and streams an
# all-zero payload (ffmpeg fails identically - it is not an OpenCV bug).
# See docs/datasheets/camera/HBV-1716WA-VERIFIED-SPECS.md
MODES = [
    ("MJPG", 1280, 720),
    ("YUY2", 640, 480),
]


def fourcc_str(v):
    v = int(v)
    return "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))


def open_mode(mode_i):
    name, w, h = MODES[mode_i]
    cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*name))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


mode_i = 0
cap = open_mode(mode_i)
if cap is None:
    print(f"Could not open camera index {INDEX}")
    raise SystemExit(1)

os.makedirs(SAVE_DIR, exist_ok=True)
cv2.namedWindow("helmet camera - live", cv2.WINDOW_NORMAL)
cv2.resizeWindow("helmet camera - live", 960, 540)

n, t0, frames, fps = 0, time.time(), 0, 0.0
peak_sharp = 0.0
while True:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.05)
        continue

    frames += 1
    dt = time.time() - t0
    if dt >= 1.0:
        fps, frames, t0 = frames / dt, 0, time.time()

    mean, mx = frame.mean(), int(frame.max())

    # Focus aid: variance of the Laplacian over the CENTRE box only. Higher = sharper.
    # Centre-only because the centre ~90 deg is the region that must be optically correct
    # (it is the two ToF sensors' combined FoV) and the fisheye edges are soft regardless.
    gh, gw = frame.shape[0], frame.shape[1]
    cy0, cy1 = int(gh * 0.30), int(gh * 0.70)
    cx0, cx1 = int(gw * 0.30), int(gw * 0.70)
    centre = cv2.cvtColor(frame[cy0:cy1, cx0:cx1], cv2.COLOR_BGR2GRAY)
    sharp = cv2.Laplacian(centre, cv2.CV_64F).var()
    peak_sharp = max(peak_sharp, sharp)

    shown = frame if frame.shape[1] <= 1280 else cv2.resize(frame, (1280, 720))
    sh, sw = shown.shape[0], shown.shape[1]
    cv2.rectangle(shown, (int(sw * 0.30), int(sh * 0.30)),
                  (int(sw * 0.70), int(sh * 0.70)), (0, 200, 255), 2)

    label = (f"{fourcc_str(cap.get(cv2.CAP_PROP_FOURCC))} "
             f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} "
             f"~{fps:.0f}fps   mean={mean:.1f} max={mx}")
    cv2.putText(shown, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(shown, f"SHARPNESS {sharp:7.0f}   best so far {peak_sharp:7.0f}",
                (12, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    # sharpness bar, scaled against the best value seen this session
    bar = int(280 * min(1.0, sharp / peak_sharp)) if peak_sharp > 0 else 0
    cv2.rectangle(shown, (12, 74), (292, 90), (60, 60, 60), -1)
    cv2.rectangle(shown, (12, 74), (12 + bar, 90), (0, 255, 255), -1)
    cv2.putText(shown, "[m]ode  [s]ave  [r]eset peak  [q]uit",
                (12, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.imshow("helmet camera - live", shown)

    k = cv2.waitKey(1) & 0xFF
    if k in (ord("q"), 27):
        break
    if k == ord("m"):
        cap.release()
        mode_i = (mode_i + 1) % len(MODES)
        cap = open_mode(mode_i)
        peak_sharp = 0.0
    if k == ord("r"):
        peak_sharp = 0.0
    if k == ord("s"):
        p = os.path.join(SAVE_DIR, f"snap_{n:03d}.jpg")
        cv2.imwrite(p, frame)
        print("saved", p)
        n += 1

cap.release()
cv2.destroyAllWindows()
