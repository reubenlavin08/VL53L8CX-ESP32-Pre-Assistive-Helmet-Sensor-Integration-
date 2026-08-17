#!/usr/bin/env python3
"""
shoot.py - dead simple snapshot tool for calibration images.

Deliberately dumb: show the camera, save a full-resolution PNG when you press
SPACE. No checkerboard detection in the live loop, no threads doing clever
things, nothing that can stall. Corner detection happens later, offline, in
calibrate_fisheye.py - which is the standard, boring, reliable part.

Take ~25 shots of the checkerboard: move it around the whole frame (centre,
edges, all four corners) and TILT it 30-45 degrees in different directions each
time. Vary the distance too. Flat-on square-to-the-camera shots are the useless
ones - see GLOSSARY.md.

Keys:  SPACE = save    d = delete last    q / Esc = quit
Then:  python camera\\calibrate_fisheye.py
"""
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calib_shots")
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1

cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
cap.set(cv2.CAP_PROP_FPS, 30)
if not cap.isOpened():
    raise SystemExit(f"Could not open camera index {INDEX}")

os.makedirs(OUT, exist_ok=True)
shots = sorted(f for f in os.listdir(OUT) if f.startswith("calib_"))
n = len(shots)

cv2.namedWindow("shoot - SPACE to save", cv2.WINDOW_NORMAL)
cv2.resizeWindow("shoot - SPACE to save", 1280, 720)

while True:
    ok, frame = cap.read()
    if not ok:
        continue
    shown = frame.copy()
    h, w = shown.shape[:2]
    # thirds guide, so you can see which part of the frame you have covered
    for i in (1, 2):
        cv2.line(shown, (w * i // 3, 0), (w * i // 3, h), (70, 70, 70), 1)
        cv2.line(shown, (0, h * i // 3), (w, h * i // 3), (70, 70, 70), 1)
    cv2.putText(shown, f"{n} saved   (aim for 25)", (14, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
    cv2.putText(shown, "SPACE = save    d = delete last    q = quit", (14, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.imshow("shoot - SPACE to save", shown)

    k = cv2.waitKey(1) & 0xFF
    if k in (ord("q"), 27):
        break
    if k == 32:
        p = os.path.join(OUT, f"calib_{n:03d}.png")
        cv2.imwrite(p, frame)
        n += 1
        # flash so you know it landed
        cv2.rectangle(shown, (0, 0), (w - 1, h - 1), (0, 255, 0), 20)
        cv2.imshow("shoot - SPACE to save", shown)
        cv2.waitKey(60)
    if k == ord("d") and n > 0:
        n -= 1
        p = os.path.join(OUT, f"calib_{n:03d}.png")
        if os.path.exists(p):
            os.remove(p)

cap.release()
cv2.destroyAllWindows()
