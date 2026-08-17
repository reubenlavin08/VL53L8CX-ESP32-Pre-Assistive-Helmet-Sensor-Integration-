#!/usr/bin/env python3
"""
capture_calib.py - collect checkerboard images for fisheye calibration.

WHAT CALIBRATION IS DOING (read once, it makes the procedure make sense)
We know the board's real geometry exactly: a flat grid of 20 mm squares. So for
every photo, OpenCV can ask "where must the camera have been, and what must the
lens do to light, for this known flat grid to land on those particular pixels?"
One photo has too many unknowns. Many photos, of the SAME board seen from DIFFERENT
angles and distances, over-constrain the problem until only one lens model fits
them all. That model is K (focal length + optical centre) and D (how the lens bends
light outward). This is Zhang's method.

WHY TILTING IS REQUIRED, NOT A PROBLEM
Held flat-on and square to the camera, "small board up close" and "big board far
away" produce nearly identical images - the focal length and the distance trade
off against each other and cannot be separated. Tilting breaks that tie: a tilted
plane produces perspective foreshortening whose exact shape depends on focal
length alone. So tilt is what makes the answer unique. Flat-on images are the
useless ones.

WHAT THIS SCRIPT ADDS
It tracks WHERE in the frame you have already photographed the board and refuses
to count near-duplicates, so you end up with genuinely varied views covering the
whole frame - centre AND edges AND corners. Edge coverage is what pins down the
fisheye distortion terms; without it the model is guessing out there.

HOW TO USE
1. Print camera/checkerboard_8x11_20mm.pdf at 100%, verify the 100 mm ruler,
   glue it to something rigid and flat. Flatness matters more than print quality.
2. Run this. Hold the board up and move it around. Green overlay = detected.
3. AUTO-capture fires when the board is detected, held still, and occupies a
   screen region you have not already covered. Press SPACE to force a capture.
4. Fill all 9 cells of the coverage grid, and get some steep tilts in. Aim for
   >= 20 keepers. Then press q.
5. Run: python camera/calibrate_fisheye.py

Keys: SPACE force-capture   d delete last   r reset all   q finish
"""
import os
import queue
import sys
import threading
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "calib_shots")
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1

BOARD = (8, 11)        # INNER corners (cols, rows) - matches the generated PDF
# MEASURED, not nominal: the PDF's 100 mm verification bar printed at 98 mm,
# so the printer scaled everything by 0.98 -> 20.0 * 0.98 = 19.6 mm squares.
SQUARE_MM = 19.6
FOURCC, W, H = "MJPG", 1280, 720   # 1080p is unusable on this module - see VERIFIED-SPECS
TARGET = 20            # minimum keepers before calibrating
STILL_PX = 5.0         # mean corner motion below this counts as "held still" (handheld)
GRID = 3               # coverage grid is GRID x GRID cells
# 1 = detect at native 1280x720. Downscaling was a premature optimisation: the real
# causes of the freezes were a console stuck in QuickEdit select-mode and DirectShow
# frame-queue backup, both fixed elsewhere. Native res detects most reliably.
DETECT_DIV = 1

# No CALIB_CB_FAST_CHECK: it bails early on frames it guesses have no board and
# causes misses on tilted / partially-lit boards, which are exactly the views we want.
FIND_FLAGS = (cv2.CALIB_CB_ADAPTIVE_THRESH |
              cv2.CALIB_CB_NORMALIZE_IMAGE)
SUBPIX = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
# Looser criteria for the live preview only - fewer iterations, coarser tolerance.
SUBPIX_FAST = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 0.05)


def open_cam():
    cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*FOURCC))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


class Reader(threading.Thread):
    """Drain the camera at full speed on its own thread and keep only the LATEST frame.

    Without this, any frame the main loop is slow to process (corner detection is
    the expensive bit) leaves frames queued in DirectShow. The queue grows, every
    read() hands back an older frame, and the preview appears to freeze while
    actually showing the past. Keeping a single-slot 'latest' buffer means a slow
    loop drops frames instead of falling behind.
    """

    def __init__(self, cap):
        super().__init__(daemon=True)
        self.cap, self.latest, self.lock, self.stop = cap, None, threading.Lock(), False

    def run(self):
        while not self.stop:
            ok, f = self.cap.read()
            if ok:
                with self.lock:
                    self.latest = f
            else:
                time.sleep(0.01)

    def get(self):
        with self.lock:
            return None if self.latest is None else self.latest.copy()


def saver_worker(q):
    """Write PNGs off the main thread - encoding a 1280x720 PNG costs ~200 ms."""
    while True:
        item = q.get()
        if item is None:
            break
        path, img = item
        cv2.imwrite(path, img)
        print("saved", os.path.basename(path))


cap = open_cam()
if cap is None:
    print(f"Could not open camera index {INDEX}. Is another program holding it?")
    raise SystemExit(1)

os.makedirs(OUT_DIR, exist_ok=True)
for f in os.listdir(OUT_DIR):                      # start clean
    if f.startswith("calib_") and f.endswith(".png"):
        os.remove(os.path.join(OUT_DIR, f))

cv2.namedWindow("calibration capture", cv2.WINDOW_NORMAL)
cv2.resizeWindow("calibration capture", 1280, 720)
print(__doc__)

reader = Reader(cap)
reader.start()
save_q = queue.Queue()
threading.Thread(target=saver_worker, args=(save_q,), daemon=True).start()

covered = np.zeros((GRID, GRID), dtype=int)
saved, prev_corners, last_shot = [], None, 0.0
flash = 0.0
msg = ""
loop_t0, loop_frames, loop_fps = time.time(), 0, 0.0

while True:
    frame = reader.get()
    if frame is None:
        time.sleep(0.03)
        continue
    fh, fw = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect on a QUARTER-SIZE image (about 16x less work - corner detection is by
    # far the slowest thing in this loop), then scale the corners back up and refine
    # them against the FULL-RES image. The saved PNGs are always full resolution and
    # calibrate_fisheye.py re-detects from scratch, so this costs nothing in
    # calibration quality - only preview speed.
    small = cv2.resize(gray, (fw // DETECT_DIV, fh // DETECT_DIV), interpolation=cv2.INTER_AREA)
    found, corners = cv2.findChessboardCorners(small, BOARD, FIND_FLAGS)
    if found:
        corners = corners * float(DETECT_DIV)

    shown = frame.copy()
    still, cell = False, None

    if found:
        # Refine on a downscaled-but-not-tiny image: full-res cornerSubPix over 88
        # corners with an 11x11 window is itself a visible cost in the preview loop.
        # Final accuracy comes from calibrate_fisheye.py, which redoes this properly
        # on the saved full-resolution PNGs.
        corners = cv2.cornerSubPix(gray, corners, (7, 7), (-1, -1), SUBPIX_FAST)
        cv2.drawChessboardCorners(shown, BOARD, corners, found)

        c = corners.reshape(-1, 2)
        cx, cy = float(c[:, 0].mean()), float(c[:, 1].mean())
        cell = (min(GRID - 1, int(cy / fh * GRID)), min(GRID - 1, int(cx / fw * GRID)))

        if prev_corners is not None and prev_corners.shape == corners.shape:
            still = float(np.linalg.norm(c - prev_corners.reshape(-1, 2), axis=1).mean()) < STILL_PX
        prev_corners = corners.copy()

        # how much of the frame the board spans - a proxy for distance variety
        span = (c[:, 0].ptp() * c[:, 1].ptp()) / float(fw * fh)
        cv2.putText(shown, f"board fills {span*100:4.1f}% of frame",
                    (12, fh - 46), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)
    else:
        prev_corners = None

    # ---- auto-capture: detected + still + this cell still needs views ----
    now = time.time()
    auto = (found and still and cell is not None
            and covered[cell] < 3 and (now - last_shot) > 1.0)

    # Say out loud WHY it is not firing - otherwise "nothing happens" is unreadable.
    if not found:
        reason = "no board seen - fill more of the frame, more light, less glare"
    elif not still:
        reason = "moving - hold it steady for a moment"
    elif cell is not None and covered[cell] >= 3:
        reason = "this area already has 3 shots - move the board elsewhere"
    elif (now - last_shot) <= 1.0:
        reason = "cooling down..."
    else:
        reason = "capturing"

    key = cv2.waitKey(1) & 0xFF
    force = (key == 32 and found)

    if auto or force:
        p = os.path.join(OUT_DIR, f"calib_{len(saved):03d}.png")
        save_q.put((p, frame.copy()))          # encode on the worker thread
        saved.append(p)
        if cell is not None:
            covered[cell] += 1
        last_shot, flash = now, now

    # ---------------- overlay ----------------
    for i in range(1, GRID):
        cv2.line(shown, (fw * i // GRID, 0), (fw * i // GRID, fh), (70, 70, 70), 1)
        cv2.line(shown, (0, fh * i // GRID), (fw, fh * i // GRID), (70, 70, 70), 1)
    for r in range(GRID):
        for cc in range(GRID):
            x0, y0 = fw * cc // GRID, fh * r // GRID
            n = covered[r, cc]
            col = (0, 200, 0) if n >= 2 else ((0, 200, 255) if n == 1 else (0, 0, 220))
            cv2.rectangle(shown, (x0 + 6, y0 + 6), (x0 + 40, y0 + 34), col, -1)
            cv2.putText(shown, str(n), (x0 + 16, y0 + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    loop_frames += 1
    if now - loop_t0 >= 1.0:
        loop_fps = loop_frames / (now - loop_t0)
        loop_frames, loop_t0 = 0, now

    status = "BOARD FOUND" if found else "NO BOARD"
    scol = (0, 255, 0) if found else (0, 0, 255)
    cv2.putText(shown, status, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, scol, 2)
    cv2.putText(shown, f"{loop_fps:4.1f} fps", (fw - 130, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    cv2.putText(shown, reason, (12, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (0, 255, 0) if reason == "capturing" else (0, 200, 255), 2)
    cv2.putText(shown, "SPACE = capture now", (12, 88),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    done = int((covered >= 2).sum())
    cv2.putText(shown, f"captured {len(saved)}/{TARGET}   cells covered {done}/9",
                (12, fh - 78), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 255, 0) if (len(saved) >= TARGET and done == 9) else (0, 255, 255), 2)
    cv2.putText(shown, "vary TILT and DISTANCE - flat-on views are the useless ones",
                (12, fh - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)
    if time.time() - flash < 0.35:
        cv2.rectangle(shown, (0, 0), (fw - 1, fh - 1), (0, 255, 0), 12)

    cv2.imshow("calibration capture", shown)

    if key in (ord("q"), 27):
        break
    elif key == ord("d") and saved:
        p = saved.pop()
        if os.path.exists(p):
            os.remove(p)
        print("deleted last")
    elif key == ord("r"):
        for p in saved:
            if os.path.exists(p):
                os.remove(p)
        saved, covered = [], np.zeros((GRID, GRID), dtype=int)
        print("reset")

reader.stop = True
save_q.put(None)
time.sleep(0.6)                 # let queued PNGs finish encoding
cap.release()
cv2.destroyAllWindows()
print(f"\n{len(saved)} images in {OUT_DIR}")
print(f"cells with >=2 views: {int((covered >= 2).sum())}/9")
if len(saved) < TARGET or (covered >= 2).sum() < 9:
    print("WARNING: thin coverage. More views, especially at the frame edges,")
    print("         make the fisheye distortion terms much better determined.")
print("Next: python camera/calibrate_fisheye.py")
