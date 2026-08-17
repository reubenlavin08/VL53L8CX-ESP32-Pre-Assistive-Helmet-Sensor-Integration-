"""IMU MOUNT CALIBRATION -- find the fixed rotation between the BNO085 chip
frame and the HELMET frame, from two poses. Run interactively:

    python visualizer/imu_mount_cal.py --port COM9

WHY TWO POSES AND WHY GRAVITY: the game rotation vector is mag-free, so its
yaw reference is arbitrary at every boot -- but gravity is not. Holding the
helmet in two known attitudes gives two known helmet-frame directions for the
measured gravity vector, which pins down the full 3-DOF mounting rotation
(level pose fixes two axes, nose-down fixes the third).

HELMET FRAME (matches the fusion docs): X = wearer's right, Y = forward,
Z = up. The result is saved to visualizer/imu_mount_cal.json as a rotation
matrix R_chip_to_helmet, plus a live verification mode so you can SEE that
pitch/roll/yaw respond correctly before trusting it.
"""
import argparse
import json
import pathlib
import time

import numpy as np
import serial

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "imu_mount_cal.json"


def quat_to_R(w, x, y, z):
    """chip -> world rotation from a unit quaternion."""
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def read_quats(sp, seconds, label):
    """Average the chip-frame DOWN direction over `seconds` of Q: lines."""
    downs = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        line = sp.readline().decode("utf-8", "replace").strip()
        if not line.startswith("Q:"):
            continue
        try:
            w, x, y, z = [float(v) for v in line[2:].split(",")[:4]]
        except ValueError:
            continue
        R = quat_to_R(w, x, y, z)          # chip -> world
        downs.append(R.T @ np.array([0.0, 0.0, -1.0]))   # world-down in chip frame
    if len(downs) < 10:
        raise SystemExit(f"only {len(downs)} samples during '{label}' -- is the IMU streaming?")
    d = np.mean(downs, axis=0)
    d /= np.linalg.norm(d)
    spread = np.degrees(np.mean([np.arccos(np.clip(v @ d, -1, 1)) for v in downs]))
    print(f"  {label}: {len(downs)} samples, spread {spread:.2f} deg "
          f"{'(HOLD STILLER and redo if > 2)' if spread > 2 else 'OK'}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()
    sp = serial.Serial(args.port, args.baud, timeout=1)

    print(__doc__)
    print("STEP 1/2 -- hold the helmet LEVEL, the way it sits on a head looking at")
    print("the horizon. Keep it still. Press Enter when ready...")
    input()
    print("  sampling 4 s -- keep still...")
    d_level = read_quats(sp, 4.0, "level")

    print("\nSTEP 2/2 -- now pitch the helmet NOSE-DOWN about 90 degrees, like the")
    print("wearer is looking straight at their feet. Keep it still. Enter when ready...")
    input()
    print("  sampling 4 s -- keep still...")
    d_nose = read_quats(sp, 4.0, "nose-down")

    ang = np.degrees(np.arccos(np.clip(d_level @ d_nose, -1, 1)))
    print(f"\n  angle between poses: {ang:.1f} deg (want roughly 90; 60-120 is usable)")
    if ang < 30:
        raise SystemExit("poses too similar -- redo with a real nose-down tilt")

    # level: helmet down (-Z) is where gravity points  -> chip d_level = helmet -Z
    # nose-down: helmet forward (+Y) points at the ground -> chip d_nose ~ helmet +Y
    z_h = -d_level
    y_h = d_nose - (d_nose @ z_h) * z_h        # remove any residual Z component
    y_h /= np.linalg.norm(y_h)
    x_h = np.cross(y_h, z_h)                   # right = forward x up
    R = np.vstack([x_h, y_h, z_h])             # rows: chip vec -> helmet components

    # SNAP to the nearest cardinal orientation. The IMU board is mounted flat
    # and square on the pod's base plate (user, 2026-08-17), so the true
    # mounting is one of the 24 axis-aligned rotations; the measured deviation
    # from it is the mounting/holding error, not signal.
    from itertools import permutations, product
    best, bt = None, -9
    for perm in permutations(range(3)):
        for signs in product([1, -1], repeat=3):
            C = np.zeros((3, 3))
            for i in range(3):
                C[i, perm[i]] = signs[i]
            if np.linalg.det(C) < 0.5:
                continue
            t = np.trace(C.T @ R)
            if t > bt:
                bt, best = t, C
    dev = np.degrees(np.arccos(np.clip((bt - 1) / 2, -1, 1)))
    print("\nmeasured R_chip_to_helmet:")
    print(np.array_str(R, precision=4, suppress_small=True))
    print(f"\nsnapped to cardinal mount (deviation {dev:.1f} deg -- this is your"
          f" mounting+holding error{'; fine' if dev < 8 else '; REDO if you held it sloppily'}):")
    print(np.array_str(best, precision=0, suppress_small=True))
    OUT.write_text(json.dumps({
        "what": "rows map a chip-frame vector to helmet frame (X right, Y fwd, Z up)",
        "date": time.strftime("%Y-%m-%d %H:%M"),
        "R_chip_to_helmet": best.tolist(),
        "R_measured": R.tolist(),
        "snap_deviation_deg": float(dev),
        "pose_angle_deg": float(ang),
    }, indent=1))
    print(f"\nsaved {OUT} (using the SNAPPED matrix)")

    print("\nLIVE VERIFICATION -- move the helmet and check the numbers make sense:")
    print("  pitch: nose-down = positive     roll: right-ear-down = positive")
    print("  yaw: relative to boot, left turn = positive. Ctrl+C to finish.\n")
    try:
        while True:
            line = sp.readline().decode("utf-8", "replace").strip()
            if not line.startswith("Q:"):
                continue
            try:
                w, x, y, z = [float(v) for v in line[2:].split(",")[:4]]
            except ValueError:
                continue
            Rw = quat_to_R(w, x, y, z) @ R.T   # helmet -> world
            fwd = Rw @ np.array([0, 1, 0])
            rgt = Rw @ np.array([1, 0, 0])
            pitch = np.degrees(np.arcsin(np.clip(-fwd[2], -1, 1)))
            roll = np.degrees(np.arcsin(np.clip(-rgt[2], -1, 1)))
            yaw = np.degrees(np.arctan2(-fwd[0], fwd[1]))
            print(f"\r  pitch {pitch:+7.1f}   roll {roll:+7.1f}   yaw {yaw:+7.1f}   ",
                  end="", flush=True)
    except KeyboardInterrupt:
        print("\ndone.")
    sp.close()


if __name__ == "__main__":
    main()
