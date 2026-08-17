#!/usr/bin/env python3
"""
camera_focus.py - focus + lock the HBV-1716WA lens before calibration.

WHY THIS EXISTS
The lens is a threaded barrel with NO lock screw. Camera calibration measures the
lens's optical geometry, so if the barrel rotates afterwards the calibration is
void. Procedure: focus it once, tape it, never touch it again.

HOW TO JUDGE FOCUS - read this, it is the whole point of the tool
Judge with your EYES on the 1:1 magnified inset (top-right). The numeric score is
a TIEBREAKER between two settings that look equally sharp, never the arbiter.

Why the number alone lies: it measures high-frequency detail, and sensor NOISE is
high-frequency too. With auto-exposure/auto-gain running, a darker or hotter frame
gets noisier and scores HIGHER while actually looking worse. Hence:
  - this script LOCKS exposure and gain (press 'a' to toggle back to auto),
  - the score is normalised by image brightness to blunt what leaks through,
  - and it shows you real pixels at 1:1 so your eye can do the deciding.

Keys
  1:1 inset is always on (top-right corner).
  [ ]   shrink / grow the measurement box
  a     toggle auto-exposure lock (locked by default - keep it locked while focusing)
  - =   exposure down / up (only when locked)
  r     reset the peak-score memory
  s     save a snapshot to camera/snapshots/
  q/Esc quit

See docs/datasheets/camera/HBV-1716WA-VERIFIED-SPECS.md.
Sensor stays inside its stable-image band up to 50 C (OV2710 datasheet Table 8-2);
if the board is too hot to hold a finger on, let it cool - heat adds noise.
"""
import os
import sys
import time

import cv2
import numpy as np

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 1
WIN = "helmet camera - FOCUS"

# The mode we capture and calibrate at. 1920x1080 is unusable on this module
# (firmware declares uncompressed bitrates in its MJPEG descriptors -> the stream
# never gets bandwidth). See the VERIFIED-SPECS doc.
FOURCC, W, H = "MJPG", 1280, 720

INSET = 320          # size of the 1:1 magnified inset, px
box_frac = 0.25      # half-width of the measurement box as a fraction of the frame
locked = True
exposure = -6        # DSHOW exposure is log2 seconds; -6 = 1/64 s


def open_cam():
    cap = cv2.VideoCapture(INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*FOURCC))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def apply_exposure(cap):
    """0.25 = manual, 0.75 = auto - the DSHOW convention."""
    if locked:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
        cap.set(cv2.CAP_PROP_EXPOSURE, exposure)
    else:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)


def score(gray):
    """Brightness-normalised Tenengrad (mean squared Sobel gradient).

    Tenengrad tracks edge energy rather than raw pixel variance, so it is less
    swayed by film-grain noise than variance-of-Laplacian. Dividing by mean
    intensity removes the 'brighter frame scores higher' bias. It is still only
    a tiebreaker - trust the 1:1 inset.
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    m = float(gray.mean())
    return float((gx * gx + gy * gy).mean()) / max(m * m, 1.0) * 1000.0


cap = open_cam()
if cap is None:
    print(f"Could not open camera index {INDEX}. Is another program holding it?")
    raise SystemExit(1)
apply_exposure(cap)

os.makedirs(SAVE_DIR, exist_ok=True)
cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
cv2.resizeWindow(WIN, 1280, 720)

peak, smooth, n = 0.0, None, 0
print(__doc__)

while True:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.05)
        continue

    fh, fw = frame.shape[:2]
    cx, cy = fw // 2, fh // 2
    bw, bh = int(fw * box_frac), int(fh * box_frac)
    box = frame[cy - bh:cy + bh, cx - bw:cx + bw]
    gray = cv2.cvtColor(box, cv2.COLOR_BGR2GRAY)

    s = score(gray)
    smooth = s if smooth is None else 0.8 * smooth + 0.2 * s   # damp the jitter
    peak = max(peak, smooth)

    shown = frame.copy()
    cv2.rectangle(shown, (cx - bw, cy - bh), (cx + bw, cy + bh), (0, 200, 255), 2)

    # --- 1:1 magnified inset: real pixels, no resampling. Judge focus HERE. ---
    h2 = INSET // 2
    ix0, iy0 = max(0, cx - h2), max(0, cy - h2)
    crop = frame[iy0:iy0 + INSET, ix0:ix0 + INSET]
    if crop.shape[0] == INSET and crop.shape[1] == INSET:
        shown[10:10 + INSET, fw - INSET - 10:fw - 10] = crop
        cv2.rectangle(shown, (fw - INSET - 10, 10), (fw - 10, 10 + INSET), (0, 255, 255), 2)
        cv2.putText(shown, "1:1 - JUDGE HERE", (fw - INSET - 10, INSET + 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

    br = float(gray.mean())
    warn = "" if 40 < br < 210 else "  <-- ADJUST EXPOSURE"
    cv2.putText(shown, f"{FOURCC} {fw}x{fh}   brightness {br:5.1f}{warn}",
                (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
    cv2.putText(shown, f"score {smooth:7.1f}   peak {peak:7.1f}   ({100*smooth/peak:3.0f}% of peak)"
                if peak > 0 else f"score {smooth:7.1f}",
                (12, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)
    bar = int(300 * min(1.0, smooth / peak)) if peak > 0 else 0
    cv2.rectangle(shown, (12, 72), (312, 88), (60, 60, 60), -1)
    cv2.rectangle(shown, (12, 72), (12 + bar, 88), (0, 255, 255), -1)
    cv2.putText(shown, f"exposure {'LOCKED ' + str(exposure) if locked else 'AUTO (unlock=bad for focusing)'}",
                (12, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 255, 0) if locked else (0, 140, 255), 2)
    cv2.putText(shown, "[ ] box   a auto-exp   - = exposure   r reset peak   s save   q quit",
                (12, fh - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

    cv2.imshow(WIN, shown)
    k = cv2.waitKey(1) & 0xFF
    if k in (ord("q"), 27):
        break
    elif k == ord("r"):
        peak, smooth = 0.0, None
    elif k == ord("["):
        box_frac = max(0.06, box_frac - 0.03); peak, smooth = 0.0, None
    elif k == ord("]"):
        box_frac = min(0.48, box_frac + 0.03); peak, smooth = 0.0, None
    elif k == ord("a"):
        locked = not locked; apply_exposure(cap); peak, smooth = 0.0, None
    elif k == ord("-") and locked:
        exposure -= 1; apply_exposure(cap); peak, smooth = 0.0, None
    elif k in (ord("="), ord("+")) and locked:
        exposure += 1; apply_exposure(cap); peak, smooth = 0.0, None
    elif k == ord("s"):
        p = os.path.join(SAVE_DIR, f"focus_{n:03d}.jpg")
        cv2.imwrite(p, frame)
        print("saved", p, f"(score {smooth:.1f})")
        n += 1

cap.release()
cv2.destroyAllWindows()
