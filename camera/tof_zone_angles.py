"""Measure each ToF zone's true angular position, using the CAMERA as the ruler.

    python camera/tof_zone_angles.py --port COM9 --cam 1 --sensor A

WHY: the planar calibration wants a ~34 deg field where the datasheet says 45,
and every model variant I tried is degenerate (FOV trades against distance
offset and against apex offset, all fitting within 0.5 mm rms of each other).
Tape-measure tests are impractical to do accurately by hand. But the camera is
calibrated to 0.30 px, so a PIXEL IS AN ANGLE -- an instrument we already trust.

WHAT IT DOES: you wave a hand (or any object) in front of the pod. Each frame:
  - the ToF says which ZONE the object is in, and how far away it is
  - the camera says which PIXEL it is at, found by frame differencing
Hundreds of those pairs give every zone a measured angle.

THE PARALLAX TRAP: camera and ToF sit ~37 mm apart, which is 4.2 deg at 500 mm.
Reading the zone angle straight off the camera would bake in an error of exactly
the size we are hunting. So the object's camera ray is intersected with the
ToF's measured depth plane to recover its true position in the TOF frame:

    p_cam = s * u                          (u = unit ray from the pixel)
    p_tof = R^-1 (s*u - t)                 (R,t from the calibration)
    solve s such that p_tof.z == z_reported
    zone angle = atan2(p_tof.x, p_tof.z)

R only needs to be roughly right, and it is: every model variant agreed on it
to within 1.6-2.3 deg of the independent CAD measurement.

Needs the tof_pin_test firmware with TARGET_ORDER_CLOSEST so the near object
wins over the background.
"""
import argparse
import json
import pathlib
import threading
import collections

import cv2
import numpy as np
import serial

SIDE = 4
NZ = SIDE * SIDE
NEAR_MM = 120.0        # how much nearer than background counts as "the object"
# Track a BRIGHT SMALL blob (a phone torch), not motion. Frame differencing gave
# the centroid of the whole moving ARM while the ToF reported the nearest point,
# the HAND -- so every pair was mismatched and the measured column azimuths came
# out non-monotonic. A torch is unambiguous, small enough to sit in one or two
# zones, and leaves the arm irrelevant because the arm is not bright.
# ADAPTIVE, not a fixed level: the camera's auto-exposure stops down for a torch,
# so an absolute threshold of 245 never triggers. Track relative to the frame's
# own maximum instead.
BRIGHT_MARGIN = 25      # accept pixels within this of the frame's brightest
BRIGHT_FLOOR = 150      # ...but never call something dim "bright"
AREA_MIN, AREA_MAX = 15, 40000
ROOT = pathlib.Path(__file__).resolve().parent.parent

latest = {"A": None, "B": None}
lock = threading.Lock()
running = True


def reader(port, baud):
    global running
    try:
        sp = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"serial: {e}")
        running = False
        return
    buf = b""
    while running:
        try:
            buf += sp.read(sp.in_waiting or 1)
        except Exception:
            break
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            s = line.decode("utf-8", "replace").strip()
            if not s.startswith("GRID:"):
                continue
            p = s[5:].split(",")
            if len(p) != NZ + 1:
                continue
            try:
                v = np.array([int(x) for x in p[1:]], float).reshape(SIDE, SIDE)
            except ValueError:
                continue
            with lock:
                latest[p[0]] = v
    sp.close()


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cam", type=int, default=1)
    ap.add_argument("--sensor", default="A", choices=["A", "B"])
    args = ap.parse_args()

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K, D = cal["K"], cal["D"]
    cad = json.loads((ROOT / "cad" / "extrinsics_measured.json").read_text())
    key = {"A": "tof_right", "B": "tof_left"}[args.sensor]
    pri = cad["transforms_tof_to_camera"][key]
    R = np.array(pri["R"], float)
    t = np.array(pri["t_mm"], float)
    Rinv = R.T
    print(f"sensor {args.sensor} -> {key};  |t| = {np.linalg.norm(t):.1f} mm "
          f"(parallax matters, it is solved out)")

    threading.Thread(target=reader, args=(args.port, args.baud), daemon=True).start()
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        running = False
        raise SystemExit(f"cannot open camera {args.cam}")

    samples = collections.defaultdict(list)     # (r,c) -> [(az_deg, el_deg)]
    print("\nWave a hand around in front of the pod. Q quits and saves.\n")

    while running:
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gmax = int(gray.max())
        lvl = max(BRIGHT_FLOOR, gmax - BRIGHT_MARGIN)
        _, th = cv2.threshold(gray, lvl, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        px = None
        cand = [c for c in cnts if AREA_MIN < cv2.contourArea(c) < AREA_MAX]
        if cand:
            c = max(cand, key=cv2.contourArea)
            M = cv2.moments(c)
            if M["m00"]:
                px = (M["m10"] / M["m00"], M["m01"] / M["m00"])

        with lock:
            g = None if latest[args.sensor] is None else latest[args.sensor].copy()

        zone, zmm = None, None
        if g is not None:
            v = g > 0
            if v.sum() >= 6:
                bgd = float(np.median(g[v]))
                near = v & (g < bgd - NEAR_MM)
                if 0 < near.sum() <= 4:      # unambiguous: a small target
                    gm = np.where(near, g, np.inf)
                    zone = np.unravel_index(np.argmin(gm), gm.shape)
                    zmm = float(g[zone])

        view = frame.copy()
        if px is not None and zone is not None and zmm and zmm > 50:
            # pixel -> unit ray in camera frame (fisheye model)
            u = cv2.fisheye.undistortPoints(
                np.array([[[px[0], px[1]]]], np.float64), K, D)[0, 0]
            u = np.array([u[0], u[1], 1.0])
            u /= np.linalg.norm(u)
            # solve s so the point's depth in the TOF frame equals the reported z
            a = Rinv[2] @ u
            b = Rinv[2] @ t
            if abs(a) > 1e-9:
                s = (zmm + b) / a
                if 50 < s < 4000:
                    p_tof = Rinv @ (s * u - t)
                    if p_tof[2] > 1:
                        az = np.degrees(np.arctan2(p_tof[0], p_tof[2]))
                        el = np.degrees(np.arctan2(p_tof[1], p_tof[2]))
                        samples[zone].append((az, el))
            cv2.circle(view, (int(px[0]), int(px[1])), 14, (0, 230, 255), 3)
            cv2.putText(view, f"zone r{zone[0]}c{zone[1]}  {zmm:.0f}mm",
                        (int(px[0]) + 20, int(px[1])), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 230, 255), 2, cv2.LINE_AA)

        # live detector diagnostics + the mask itself, so a failure is visible
        areas = sorted((cv2.contourArea(c) for c in cnts), reverse=True)[:3]
        cv2.putText(view, f"frame max {gmax}  thresh {lvl}  blobs {len(cnts)} "
                    f"areas {[int(a) for a in areas]}", (12, 660),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        m = cv2.resize(th, (256, 144))
        view[8:152, view.shape[1]-264:view.shape[1]-8] = cv2.cvtColor(m, cv2.COLOR_GRAY2BGR)
        cv2.rectangle(view, (view.shape[1]-264, 8), (view.shape[1]-8, 152), (90, 90, 90), 1)
        if px is None:
            cv2.putText(view, "NO TARGET LOCKED - white blob should appear in the mask (top right)",
                        (12, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 160, 255), 2,
                        cv2.LINE_AA)
        n = sum(len(v) for v in samples.values())
        cv2.putText(view, f"samples: {n}   zones hit: {len(samples)}/16",
                    (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2,
                    cv2.LINE_AA)

        # live per-column azimuth means
        y = 66
        for c in range(SIDE):
            az = [a for (r, cc), lst in samples.items() if cc == c for a, e in lst]
            if len(az) >= 5:
                cv2.putText(view, f"col c{c}: {np.median(az):+6.2f} deg  (n={len(az)})",
                            (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                            (140, 230, 140), 2, cv2.LINE_AA)
                y += 26
        cv2.putText(view, "datasheet 45 -> col centres -16.9 -5.6 +5.6 +16.9",
                    (12, 700), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 220, 140), 1,
                    cv2.LINE_AA)
        cv2.putText(view, "solver  34.2 -> col centres -12.8 -4.3 +4.3 +12.8",
                    (12, 676), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 180, 255), 1,
                    cv2.LINE_AA)

        cv2.imshow("ToF zone angle measurement", view)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

    running = False
    cap.release()
    cv2.destroyAllWindows()

    print("\n=== measured zone angles ===")
    print("  zone    n     azimuth      elevation")
    out = {}
    for (r, c), lst in sorted(samples.items()):
        if len(lst) < 5:
            continue
        a = np.array(lst)
        out[f"r{r}c{c}"] = {"n": len(lst),
                            "az_deg": float(np.median(a[:, 0])),
                            "el_deg": float(np.median(a[:, 1]))}
        print(f"  r{r}c{c}  {len(lst):4d}   {np.median(a[:,0]):+7.2f}     "
              f"{np.median(a[:,1]):+7.2f}")
    if out:
        for c in range(SIDE):
            az = [v["az_deg"] for k, v in out.items() if k.endswith(f"c{c}")]
            if az:
                print(f"  column c{c} median azimuth: {np.median(az):+7.2f} deg")
        p = ROOT / "camera" / "tof_calib_poses" / f"zone_angles_{args.sensor}.json"
        p.write_text(json.dumps(out, indent=1))
        print(f"\nwrote {p}")
        print("\ncompare: datasheet 45 -> +/-16.88, +/-5.63"
              "      solver 34.2 -> +/-12.84, +/-4.28")


if __name__ == "__main__":
    main()
