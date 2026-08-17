#!/usr/bin/env python3
"""
camera_check.py - Phase 2 camera bring-up for the assistive helmet.

Plug in the HBV-1716WA (OV2710) over USB and run this to confirm it
enumerates, pull a live UVC feed, verify the MJPEG 1080p mode, and grab
snapshots. NO linear algebra required - this is pure "does the camera
see?" plumbing. Calibration / intrinsics (the matrix stuff) come later
in Module 5; you do NOT need them to get a picture.

Notes baked in from our datasheet research (docs/camera-and-multisensor-layout.md):
  - OV2710 does 1080p @ 30 ONLY in MJPEG. YUY2 is capped ~640x480.
  - The "140 deg" on the box is the DIAGONAL FOV -> ~109H x 67V (calibrate to confirm).

Usage (from the repo root):
    python camera/camera_check.py            # auto-probe, open best guess
    python camera/camera_check.py 1          # force camera index 1
Keys in the live window:  s = save snapshot,  q / Esc = quit
"""
import sys, os, time
import cv2

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")


def fourcc_str(v):
    v = int(v)
    return "".join(chr((v >> (8 * i)) & 0xFF) for i in range(4))


def open_cam(index):
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        return None
    # ask for MJPG 1080p30 - OV2710's only path to full resolution
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    cap.set(cv2.CAP_PROP_FPS, 30)
    return cap


def probe():
    print("Probing camera indices 0..3 (your laptop's built-in webcam is usually 0)...")
    found = []
    for i in range(4):
        cap = open_cam(i)
        if cap is None:
            print(f"  [{i}] (nothing)")
            continue
        ok, _ = cap.read()
        if ok:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cc = fourcc_str(cap.get(cv2.CAP_PROP_FOURCC))
            print(f"  [{i}] OK   {w}x{h} @ {fps:.0f}fps  fourcc={cc}")
            found.append((i, w, h))
        else:
            print(f"  [{i}] opened but returned no frame")
        cap.release()
    return found


def live(index):
    cap = open_cam(index)
    if cap is None or not cap.isOpened():
        print(f"Could not open camera index {index}. Check USB cable / Device Manager > Cameras.")
        return
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cc = fourcc_str(cap.get(cv2.CAP_PROP_FOURCC))
    print(f"\nLive on index {index}: {w}x{h} fourcc={cc}")
    if cc != "MJPG":
        print("  (note: not MJPG - if resolution is stuck at 640x480 that's the YUY2 cap)")
    print("  s = save snapshot    q / Esc = quit")
    os.makedirs(SAVE_DIR, exist_ok=True)
    n, t0, frames, fps = 0, time.time(), 0, 0.0
    while True:
        ok, frame = cap.read()
        if not ok:
            print("frame grab failed")
            break
        frames += 1
        dt = time.time() - t0
        if dt >= 1.0:
            fps = frames / dt
            frames, t0 = 0, time.time()
        cv2.putText(frame, f"{w}x{h}  ~{fps:.0f}fps   [s]ave  [q]uit",
                    (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("helmet camera - bring-up", frame)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("s"):
            p = os.path.join(SAVE_DIR, f"snap_{n:03d}.jpg")
            cv2.imwrite(p, frame)
            print("saved", p)
            n += 1
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    print(__doc__)
    if len(sys.argv) > 1:
        live(int(sys.argv[1]))
    else:
        found = probe()
        pick = next((i for i, _, _ in found if i != 0), None)  # prefer external over built-in 0
        if pick is None and found:
            pick = found[0][0]
        if pick is None:
            print("\nNo camera found. Is it plugged in? Check Device Manager > Cameras.")
        else:
            print(f"\nOpening index {pick} live. Override with: python camera/camera_check.py <index>")
            live(pick)
