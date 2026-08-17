#!/usr/bin/env python3
"""
record_calib.py - record a calibration video WITH a live preview and a countdown.

ffmpeg holds the camera exclusively, so you cannot record with ffmpeg and preview
with something else at the same time. This does both from one capture: shows the
live frame and writes it to an MJPG .avi.

No checkerboard detection happens here at all - that is done offline afterwards by
extract_from_video.py, so nothing in this loop can stall.

  10 second countdown -> get the board up
  90 second recording -> move the board around, tilting

Keys: q / Esc = stop early
Then: python camera\\extract_from_video.py camera\\calib_video.avi
"""
import os
import queue
import threading
import time

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "calib_video.avi")
INDEX = 1
W, H, FPS = 1280, 720, 30
COUNTDOWN = 10
DURATION = 90

cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS, FPS)
if not cap.isOpened():
    raise SystemExit("could not open camera")

writer = cv2.VideoWriter(OUT, cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))

# Write on a worker thread so encoding never stalls the preview loop.
wq = queue.Queue(maxsize=120)


def writer_worker():
    while True:
        f = wq.get()
        if f is None:
            break
        writer.write(f)


threading.Thread(target=writer_worker, daemon=True).start()

WIN = "RECORDING - move the board around"
cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN, 1280, 720)

# The first attempt failed (RMS 5.5 px) because the board filled under 2% of the
# frame in every view. BIG is the single most important instruction here.
TIPS = [
    "HOLD IT CLOSE - board should fill 1/3 to 1/2 the frame",
    "TILT it 30-45 deg - flat-on is useless",
    "centre, then EDGES, then CORNERS",
    "pause ~1s each pose, avoid blur",
    "keep the WHOLE board visible, and BIG",
]

t0 = time.time()
recording = False
rec_start = None

while True:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.02)
        continue

    now = time.time()
    shown = frame.copy()
    h, w = shown.shape[:2]

    for i in (1, 2):
        cv2.line(shown, (w * i // 3, 0), (w * i // 3, h), (70, 70, 70), 1)
        cv2.line(shown, (0, h * i // 3), (w, h * i // 3), (70, 70, 70), 1)

    if not recording:
        left = COUNTDOWN - (now - t0)
        if left <= 0:
            recording, rec_start = True, now
        else:
            cv2.putText(shown, f"{int(left) + 1}", (w // 2 - 70, h // 2 + 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 6.0, (0, 200, 255), 12)
            cv2.putText(shown, "GET THE BOARD UP", (w // 2 - 300, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 200, 255), 4)
    if recording:
        el = now - rec_start
        if el >= DURATION:
            break
        try:
            wq.put_nowait(frame)
        except queue.Full:
            pass
        cv2.circle(shown, (40, 44), 16, (0, 0, 255), -1)
        cv2.putText(shown, f"REC  {int(DURATION - el):3d}s left", (70, 56),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 255), 3)
        bar = int((w - 40) * el / DURATION)
        cv2.rectangle(shown, (20, h - 26), (20 + bar, h - 12), (0, 0, 255), -1)
        cv2.putText(shown, TIPS[int(el // 18) % len(TIPS)], (20, h - 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

    cv2.imshow(WIN, shown)
    if (cv2.waitKey(1) & 0xFF) in (ord("q"), 27):
        break

wq.put(None)
time.sleep(1.0)
cap.release()
writer.release()
cv2.destroyAllWindows()
