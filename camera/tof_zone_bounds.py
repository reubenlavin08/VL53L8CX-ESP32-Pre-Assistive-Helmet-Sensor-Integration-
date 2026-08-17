"""Bound each ToF zone's angle using the CHECKERBOARD as a probe of known extent.

    python camera/tof_zone_bounds.py --port COM9 --cam 1 --sensor A

WHY THIS AND NOT BLOB TRACKING: motion differencing tracked the whole arm while
the ToF reported the hand, so the pairs were mismatched and the measured column
azimuths came out non-monotonic. Bright-blob tracking then failed because the
camera's auto-exposure stops down for a torch. The checkerboard avoids both: cv2
detects it reliably, and solvePnP gives its exact 3D pose, so its angular extent
in the ToF frame is KNOWN rather than estimated.

THE LOGIC is interval intersection, not fitting:
    for each frame, the board occupies azimuths [lo, hi] as seen from the ToF
    a zone that DETECTS the board must have its centre inside  [lo-w/2, hi+w/2]
    a zone that MISSES it must have its centre outside         [lo+w/2, hi-w/2]
Accumulating those constraints boxes in every zone's true angle. No model of the
field is assumed, so it cannot be biased toward either hypothesis -- which is the
whole point, since the fitted 34 deg and the datasheet 45 deg differ by ~4 deg
per column and that is well inside what this can resolve.

Parallax is handled: the board's pose is transformed into the ToF frame before
the angles are taken, so the 37 mm camera-to-ToF offset does not leak in.
"""
import argparse
import json
import pathlib
import threading

import cv2
import numpy as np
import serial

SIDE = 4
NZ = SIDE * SIDE
BOARD = (8, 11)
SQUARE_MM = 20.0        # freshly printed at 100%. The calibration file used 19.6
                        # (that print came out ~2% small) -- override with
                        # --square-mm if a ruler across 10 squares disagrees.
NEAR_MM = 100.0          # board must read this much nearer than the background
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
    ap.add_argument("--square-mm", type=float, default=SQUARE_MM)
    args = ap.parse_args()
    sq = args.square_mm
    print(f"checkerboard square size: {sq} mm")

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K, D = cal["K"], cal["D"]
    cad = json.loads((ROOT / "cad" / "extrinsics_measured.json").read_text())
    key = {"A": "tof_right", "B": "tof_left"}[args.sensor]
    pri = cad["transforms_tof_to_camera"][key]
    R = np.array(pri["R"], float)
    t = np.array(pri["t_mm"], float)
    Rinv = R.T

    objp = np.zeros((BOARD[0] * BOARD[1], 1, 3), np.float32)
    objp[:, 0, :2] = np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2) * sq

    threading.Thread(target=reader, args=(args.port, args.baud), daemon=True).start()
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        running = False
        raise SystemExit(f"cannot open camera {args.cam}")

    # VOTING, not hard intersection. Intersecting windows is brittle: one
    # misdetected frame permanently rules out the true angle, and over hundreds
    # of frames that is near-certain -- it collapsed every column to empty. A
    # histogram tolerates outliers and converges on the consistent answer.
    BINS = np.arange(-35.0, 35.001, 0.5)
    vote = np.zeros((SIDE, SIDE, len(BINS)))
    hits = np.zeros((SIDE, SIDE), int)
    nframes = 0
    raw = []                      # per-frame record, so re-analysis needs no recapture
    print("\nHold the CHECKERBOARD in front of one sensor and move it slowly around")
    print("the field -- left, right, up, down, near, far. Q quits and saves.\n")

    while running:
        ok, frame = cap.read()
        if not ok:
            continue
        small = cv2.resize(frame, None, fx=0.5, fy=0.5)
        g0 = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(
            g0, BOARD, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK)

        view = frame.copy()
        info = "no checkerboard"
        if found:
            und = cv2.fisheye.undistortPoints(corners * 2, K, D)
            okp, rvec, tvec = cv2.solvePnP(objp, und, np.eye(3), None)
            if okp:
                Rb, _ = cv2.Rodrigues(rvec)
                pts_cam = (objp[:, 0, :] @ Rb.T) + tvec.ravel()
                pts_tof = (pts_cam - t) @ Rinv.T
                az = np.degrees(np.arctan2(pts_tof[:, 0], pts_tof[:, 2]))
                el = np.degrees(np.arctan2(pts_tof[:, 1], pts_tof[:, 2]))
                a_lo, a_hi = float(az.min()), float(az.max())
                zb = float(np.median(pts_tof[:, 2]))

                with lock:
                    grid = None if latest[args.sensor] is None else latest[args.sensor].copy()
                if grid is not None and zb > 100:
                    v = grid > 0
                    if v.sum() >= 6:
                        bgd = float(np.median(grid[v]))
                        # zones seeing something at the board's depth
                        on = v & (np.abs(grid - zb) < 120.0) & (grid < bgd - NEAR_MM + 100.0)
                        if on.any():
                            nframes += 1
                            hits += on
                            raw.append({"a_lo": a_lo, "a_hi": a_hi, "z": zb,
                                        "on": on.astype(int).tolist(),
                                        "valid": v.astype(int).tolist()})
                            inside = (BINS >= a_lo - 6.0) & (BINS <= a_hi + 6.0)
                            core = (BINS >= a_lo + 6.0) & (BINS <= a_hi - 6.0)
                            for rr in range(SIDE):
                                for cc in range(SIDE):
                                    if on[rr, cc]:
                                        vote[rr, cc, inside] += 1.0
                                    elif v[rr, cc] and (a_hi - a_lo) > 10.0:
                                        vote[rr, cc, core] -= 1.0
                            info = (f"board az [{a_lo:+.1f},{a_hi:+.1f}] deg  "
                                    f"z {zb:.0f}mm  zones on {int(on.sum())}")
                cv2.drawChessboardCorners(view, BOARD, corners * 2, True)

        cv2.putText(view, info, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (240, 240, 240), 2, cv2.LINE_AA)
        cv2.putText(view, f"frames used: {nframes}", (12, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        y = 96
        for c in range(SIDE):
            n = int(hits[:, c].sum())
            vc = vote[:, c, :].sum(axis=0)
            if n > 3 and vc.max() > 0:
                pk = float(BINS[int(np.argmax(vc))])
                cv2.putText(view, f"col c{c}: peak {pk:+6.2f} deg   n={n}",
                            (12, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (140, 230, 140), 2, cv2.LINE_AA)
                y += 26
        cv2.putText(view, "datasheet 45 -> -16.9 -5.6 +5.6 +16.9", (12, 676),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 220, 140), 1, cv2.LINE_AA)
        cv2.putText(view, "solver  34.2 -> -12.8 -4.3 +4.3 +12.8", (12, 700),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (140, 180, 255), 1, cv2.LINE_AA)

        cv2.imshow("ToF zone angle bounds (checkerboard probe)", view)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

    running = False
    cap.release()
    cv2.destroyAllWindows()

    # Save the raw frames FIRST, before any analysis can throw. A previous run
    # collected 2573 good frames and lost every one of them to a crash in the
    # reporting code -- the capture is expensive, the analysis is not.
    outdir = ROOT / "camera" / "tof_calib_poses"
    outdir.mkdir(exist_ok=True)
    (outdir / f"zone_raw_{args.sensor}.json").write_text(json.dumps(raw))
    print(f"\nraw: {len(raw)} frames -> zone_raw_{args.sensor}.json")

    print(f"\n=== azimuth peaks from {nframes} frames ===")
    ds = [-16.88, -5.63, 5.63, 16.88]
    sv = [-12.84, -4.28, 4.28, 12.84]
    print("  column   measured    datasheet45   solver34.2   closer to")
    out = {}
    for c in range(SIDE):
        n = int(hits[:, c].sum())
        vc = vote[:, c, :].sum(axis=0)
        if n <= 3 or vc.max() <= 0:
            print(f"  c{c}     (insufficient data, n={n})")
            continue
        pk = float(BINS[int(np.argmax(vc))])
        out[f"c{c}"] = {"peak_deg": pk, "n": n}
        which = "DATASHEET" if abs(pk - ds[c]) < abs(pk - sv[c]) else "solver"
        print(f"  c{c}    {pk:+8.2f}     {ds[c]:+8.2f}     {sv[c]:+8.2f}    {which}")
    if out:
        (outdir / f"zone_bounds_{args.sensor}.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
