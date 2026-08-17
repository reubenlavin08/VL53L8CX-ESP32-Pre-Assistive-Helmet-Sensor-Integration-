"""BALL-MOUNT LEVELING TOOL -- live bubble level driven by the helmet's IMU.

    python visualizer/mount_level.py --port COM9

The pod hangs on a ball camera mount, so its attitude relative to the helmet
drifts every time the mount is bumped or re-clamped. The IMU board is flat and
square on the pod base, so pod pitch/roll = IMU pitch/roll directly -- which
makes leveling a two-minute job:

  1. Put the helmet on dead level (on your head looking at the horizon, or on
     a flat table).
  2. Watch the bubble; adjust the ball mount until the dot sits in the ring.
  3. GREEN + "level" = the camera boresight is at its designed 22.5 deg down
     and the ToF pair is square. Lock the ball.

Uses visualizer/imu_mount_cal.json for axis labels when present (so "nose up"
means nose up); without it the bubble still works, the labels may just be
rotated -- adjust, watch, learn the mapping in five seconds.
"""
import argparse
import json
import pathlib
import time

import cv2
import numpy as np
import serial

HERE = pathlib.Path(__file__).resolve().parent
TOL_DEG = 1.0            # "level" threshold


def quat_to_R(w, x, y, z):
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()
    sp = serial.Serial(args.port, args.baud, timeout=1)

    Rm = np.eye(3)
    mc = HERE / "imu_mount_cal.json"
    if mc.exists():
        Rm = np.array(json.loads(mc.read_text())["R_chip_to_helmet"], float)
        print("axis labels from imu_mount_cal.json")
    else:
        print("no mount cal -- bubble works, axis labels may be rotated")

    S = 560
    said_level = False
    was_level_t = 0.0
    while True:
        line = sp.readline().decode("utf-8", "replace").strip()
        if not line.startswith("Q:"):
            continue
        try:
            w, x, y, z = [float(v) for v in line[2:].split(",")[:4]]
        except ValueError:
            continue
        Rw = quat_to_R(w, x, y, z) @ Rm.T        # helmet -> world
        fwd = Rw @ np.array([0, 1, 0])
        rgt = Rw @ np.array([1, 0, 0])
        pitch = np.degrees(np.arcsin(np.clip(-fwd[2], -1, 1)))
        roll = np.degrees(np.arcsin(np.clip(-rgt[2], -1, 1)))
        level = abs(pitch) < TOL_DEG and abs(roll) < TOL_DEG

        img = np.full((S, S, 3), 24, np.uint8)
        c = S // 2
        scale = (S / 2 - 40) / 15.0              # +-15 deg full deflection
        for r_deg in (1, 5, 10, 15):
            cv2.circle(img, (c, c), int(r_deg * scale), (70, 70, 70), 1, cv2.LINE_AA)
        cv2.line(img, (c, 20), (c, S - 20), (70, 70, 70), 1)
        cv2.line(img, (20, c), (S - 20, c), (70, 70, 70), 1)
        bx = int(c + np.clip(roll, -15, 15) * scale)
        by = int(c + np.clip(pitch, -15, 15) * scale)   # nose-down = dot down
        col = (80, 255, 120) if level else (60, 140, 255)
        cv2.circle(img, (bx, by), 14, col, -1, cv2.LINE_AA)
        cv2.circle(img, (c, c), int(TOL_DEG * scale) + 14, col, 2, cv2.LINE_AA)
        cv2.putText(img, f"pitch {pitch:+5.1f}", (16, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2, cv2.LINE_AA)
        cv2.putText(img, f"roll  {roll:+5.1f}", (16, 66),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2, cv2.LINE_AA)
        cv2.putText(img, "LEVEL - lock the ball" if level else
                    "adjust the ball mount", (16, S - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, col, 2, cv2.LINE_AA)
        cv2.imshow("ball-mount level", img)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

        # one spoken confirmation after holding level for 1.5 s
        now = time.monotonic()
        if level:
            if not was_level_t:
                was_level_t = now
            if not said_level and now - was_level_t > 1.5:
                said_level = True
                try:
                    import pyttsx3
                    e = pyttsx3.init(); e.setProperty("rate", 220)
                    e.say("level, lock it"); e.runAndWait(); e.stop()
                except Exception:
                    pass
        else:
            was_level_t = 0.0
            said_level = False

    sp.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
