"""ToF<->camera calibration capture, with live quality feedback + auto-capture.

    python camera/tof_calib_capture.py --port COM9 --cam 1 --sensor A

ONE WINDOW: camera on the left (checkerboard overlay), ToF grids on the right,
each zone coloured by how far it sits from the best-fit plane.

WHY RESIDUALS AND NOT DISTANCES: the failure that ruins calibration data is a
zone slipping off the edge of the board and ranging the wall behind it. Raw
distances hide that -- 780 vs 810 mm looks unremarkable. Residual from the
fitted plane makes it obvious: on-board zones sit within a few mm, an
off-board zone is out by hundreds.

AUTO-CAPTURE: you need both hands on the board, so there is nothing to press.
A pose is taken automatically when ALL of:
    - the checkerboard is detected
    - the selected sensor has every zone on-plane
    - the board has been held still for HOLD_S seconds
    - the pose is meaningfully DIFFERENT from every pose already captured
It beeps on capture. SPACE still forces one manually; Q quits.

The novelty test is the important one: it stops you collecting ten near-identical
poses, which look like ten measurements but constrain translation like one.

Requires the tof_pin_test firmware (streams "GRID:A,d0,..,d15" lines).
"""
import argparse
import collections
import json
import pathlib
import threading
import time

import cv2
import numpy as np
import serial

try:
    import winsound
    def beep(ok=True):
        winsound.Beep(1400 if ok else 400, 120)
except ImportError:
    def beep(ok=True):
        print("\a", end="", flush=True)

SIDE = 4
NZ = SIDE * SIDE
FOV_DEG = 45.0                  # VL53L8CX full FOV per axis  [DS14161 Table 2]
AVG_FRAMES = 30                 # ToF frames averaged per pose. At the firmware's
                                # 10 Hz that is a 3 s hold. With ~5.8 mm frame-to-
                                # frame jitter, 30 frames -> ~1 mm on the plane fit,
                                # far better than needed; more just makes the hold
                                # unpleasant. Total averaging TIME is what matters,
                                # not the frame count or the ranging rate.
PLANE_TOL_MM = 40.0             # residual from the CURVED fit above this
                                # = the zone has missed the board entirely
BOARD = (8, 11)                 # inner corners
SQUARE_MM = 19.6                # from calibration_720p.txt -- NOT 20.0

MIN_DIST_MM = 0.0               # default OFF: no cover glass on this pod, so the
                                # UM3109 3.2 sub-60cm crosstalk warning (which is
                                # scoped to a protective window) should not apply.
                                # Board coverage beats the margin: at 600 mm the ToF
                                # field is ~50 cm across, wider than the board.
                                # Distance IS recorded per pose, so the dome can be
                                # regressed against range afterwards -- if crosstalk
                                # were really the cause, the bow would grow as the
                                # board gets closer. Override with --min-dist.
MAX_DOME_MM = 12.0              # reject a visibly bowed board
HOLD_S = 1.2                    # how long the board must be still
STILL_ROT_DEG = 1.5             # movement below this counts as "still"
STILL_TRANS_MM = 8.0
NOVEL_ROT_DEG = 12.0            # a new pose must differ by this much...
NOVEL_TRANS_MM = 80.0           # ...in rotation OR translation

OUT = pathlib.Path(__file__).parent / "tof_calib_poses"

latest = {"A": None, "B": None}
lock = threading.Lock()
running = True


def zone_rays(side=SIDE, fov=FOV_DEG):
    """Per-zone direction vector, sensor frame: +X right, +Y down, +Z forward.

    NOT unit vectors. The VL53L8CX reports the PERPENDICULAR (Z) distance for a
    zone, not the slant range along the zone's ray -- verified 2026-08-16 against
    23 planar poses: treating it as slant gave 12.02 mm plane rms and a -36 mm
    false dome; treating it as perpendicular gives 3.83 mm rms and -2.9 mm bow,
    i.e. pure noise. So the 3D point is

        p = z * [tan(az), tan(el), 1]

    and multiplying by a UNIT ray instead pulls the outer zones inward, which
    looks exactly like a bowed calibration target. It cost a full capture run.
    """
    step = fov / side
    ang = np.deg2rad((np.arange(side) - (side - 1) / 2.0) * step)
    t = np.tan(ang)
    d = np.zeros((side, side, 3))
    for r in range(side):
        for c in range(side):
            d[r, c] = [t[c], t[r], 1.0]
    return d


RAYS = zone_rays()


def analyse(grid):
    """grid: SIDExSIDE mm, -1 invalid -> (pts, residuals_mm, rms, valid, dome_mm).

    Fits PLANE + CURVATURE, and reports residuals from that curved surface --
    not from a flat plane. This matters: with a bowed board (or any radial
    distance bias) the corner zones sit ~14 mm off a flat plane while being
    perfectly ON the board, so a flat-plane test flags them as off-board. A zone
    that has genuinely missed the edge and is ranging the wall behind is out by
    HUNDREDS of mm and still stands out against the curved fit.

    dome_mm is reported separately: it is the board-flatness measurement, and it
    must not be conflated with the on/off-board test.

    The fit is iterated with outlier rejection so one bad zone cannot drag the
    surface onto itself and hide.
    """
    valid = (grid > 0).copy()
    res = np.full((SIDE, SIDE), np.nan)
    if valid.sum() < 6:
        return None, res, np.nan, valid, np.nan

    pts_all = RAYS * grid[:, :, None]
    keep = valid.copy()
    dome = np.nan
    for _ in range(3):
        pts = pts_all[keep]
        if len(pts) < 6:
            break
        c = pts.mean(axis=0)
        _, _, vh = np.linalg.svd(pts - c)
        q_all = pts_all[valid] - c
        u, w = q_all @ vh[0], q_all @ vh[1]
        z = q_all @ vh[-1]
        qk = pts_all[keep] - c
        uk, wk, zk = qk @ vh[0], qk @ vh[1], qk @ vh[-1]
        A = np.column_stack([np.ones_like(uk), uk, wk, uk * uk + wk * wk])
        try:
            co, *_ = np.linalg.lstsq(A, zk, rcond=None)
        except np.linalg.LinAlgError:
            break
        pred = co[0] + co[1] * u + co[2] * w + co[3] * (u * u + w * w)
        r = z - pred
        res[valid] = r
        dome = float(co[3] * (uk * uk + wk * wk).max())
        bad = np.abs(r) > PLANE_TOL_MM
        newkeep = valid.copy()
        newkeep[valid] = ~bad
        if newkeep.sum() < 6 or (newkeep == keep).all():
            break
        keep = newkeep

    rr = res[valid]
    rms = float(np.sqrt(np.nanmean(rr ** 2))) if rr.size else np.nan
    return pts_all[valid], res, rms, valid, dome


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
                vals = np.array([int(v) for v in p[1:]], float).reshape(SIDE, SIDE)
            except ValueError:
                continue
            with lock:
                latest[p[0]] = vals
    sp.close()


def draw_panel(name, subtitle, grid, wanted, cell=88, pad=34):
    """Grid panel coloured by plane residual. Green on-plane, red off."""
    w = SIDE * cell
    img = np.full((w + pad, w, 3), 28, np.uint8)
    tc = (255, 255, 120) if wanted else (200, 200, 200)
    cv2.putText(img, name + ("   <= CALIBRATING" if wanted else ""), (8, 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.46, tc, 1, cv2.LINE_AA)
    cv2.putText(img, subtitle, (8, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                (150, 150, 150), 1, cv2.LINE_AA)

    if grid is None:
        cv2.putText(img, "no data", (w // 2 - 40, w // 2 + pad),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (90, 90, 90), 1, cv2.LINE_AA)
        return img, np.nan, 0, False

    _, res, rms, valid, dome = analyse(grid)
    nbad = 0
    for r in range(SIDE):
        for c in range(SIDE):
            x, y = c * cell, r * cell + pad
            if not valid[r, c]:
                col, txt, sub = (55, 55, 55), "--", "invalid"
            else:
                e = abs(res[r, c])
                if e > PLANE_TOL_MM:
                    col, nbad = (40, 40, 210), nbad + 1
                elif e > PLANE_TOL_MM / 3:
                    col = (40, 165, 220)
                else:
                    col = (60, 165, 60)
                txt, sub = f"{int(grid[r, c])}", f"{res[r, c]:+.0f}"
            cv2.rectangle(img, (x + 2, y + 2), (x + cell - 2, y + cell - 2), col, -1)
            cv2.putText(img, txt, (x + 9, y + cell // 2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.52, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(img, sub, (x + 9, y + cell // 2 + 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.38, (225, 225, 225), 1, cv2.LINE_AA)

    nvalid = int(valid.sum())
    flat = abs(dome) < MAX_DOME_MM if np.isfinite(dome) else False
    ok = (nbad == 0) and (nvalid == NZ) and flat
    stat = "OK" if ok else (f"{nbad} off-plane" if nbad else
                            (f"{NZ-nvalid} invalid" if nvalid < NZ else "BOWED"))
    cv2.putText(img, f"{nvalid}/{NZ}  rms {rms:4.1f}  bow {dome:+5.1f}mm  {stat}",
                (8, w + pad - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                (60, 220, 60) if ok else (60, 200, 240), 1, cv2.LINE_AA)
    return img, rms, nvalid, ok


def pose_delta(a, b):
    """(rotation deg, translation mm) between two (rvec, tvec) poses."""
    Ra, _ = cv2.Rodrigues(a[0])
    Rb, _ = cv2.Rodrigues(b[0])
    ang = np.degrees(np.arccos(np.clip((np.trace(Ra.T @ Rb) - 1) / 2, -1, 1)))
    return float(ang), float(np.linalg.norm(a[1] - b[1]))


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cam", type=int, default=1)
    ap.add_argument("--sensor", default="A", choices=["A", "B", "both"],
                    help="which sensor must be fully on-board to allow capture")
    ap.add_argument("--no-auto", action="store_true", help="SPACE only")
    ap.add_argument("--min-dist", type=float, default=MIN_DIST_MM,
                    help="block capture closer than this (mm); 0 = off")
    ap.add_argument("--calib", default=str(pathlib.Path(__file__).parent
                                           / "calibration_720p.npz"))
    args = ap.parse_args()

    cal = np.load(args.calib)
    K, D = cal["K"], cal["D"]
    print(f"intrinsics fx={K[0,0]:.1f} cx={K[0,2]:.1f} rms={cal['rms']:.4f}px")
    print(f"calibrating sensor: {args.sensor}")

    objp = np.zeros((BOARD[0] * BOARD[1], 1, 3), np.float32)
    objp[:, 0, :2] = np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2) * SQUARE_MM

    threading.Thread(target=reader, args=(args.port, args.baud), daemon=True).start()

    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        running = False
        raise SystemExit(f"cannot open camera {args.cam}")

    OUT.mkdir(exist_ok=True)
    poses = []
    hist = collections.deque(maxlen=40)      # (t, rvec, tvec) for stillness
    tick = 0
    last_found = (False, None)
    steady_since = None

    def solve(corners, scale):
        und = cv2.fisheye.undistortPoints(corners * scale, K, D)
        ok, rvec, tvec = cv2.solvePnP(objp, und, np.eye(3), None)
        return (rvec, tvec) if ok else None

    def capture(frame, why):
        g2 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        f2, c2 = cv2.findChessboardCorners(g2, BOARD, cv2.CALIB_CB_ADAPTIVE_THRESH)
        if not f2:
            print("  board lost at full res - skipped")
            beep(False)
            return False
        c2 = cv2.cornerSubPix(g2, c2, (11, 11), (-1, -1),
                              (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                               30, 0.001))
        pr = solve(c2, 1.0)
        if pr is None:
            print("  solvePnP failed - skipped")
            beep(False)
            return False
        rvec, tvec = pr

        acc = {"A": [], "B": []}
        t0 = time.time()
        while max(len(acc["A"]), len(acc["B"])) < AVG_FRAMES and time.time() - t0 < 15:
            with lock:
                for n_ in ("A", "B"):
                    if latest[n_] is not None:
                        acc[n_].append(latest[n_].copy())
            time.sleep(0.02)

        rec = {"index": len(poses), "why": why,
               "board_dist_mm": float(np.linalg.norm(tvec)),
               "rvec": rvec.ravel().tolist(), "tvec": tvec.ravel().tolist()}
        for n_ in ("A", "B"):
            if not acc[n_]:
                continue
            st = np.stack(acc[n_])
            st[st <= 0] = np.nan
            with np.errstate(invalid="ignore"):
                mean = np.nanmean(st, axis=0)
                nval = np.sum(~np.isnan(st), axis=0)
            rec[n_] = {"mean_mm": np.nan_to_num(mean, nan=-1).tolist(),
                       "valid_count": nval.tolist(),
                       "n_frames": len(acc[n_])}
        poses.append(rec)
        (OUT / "poses.json").write_text(json.dumps(poses, indent=1))
        cv2.imwrite(str(OUT / f"pose_{rec['index']:02d}.png"), frame)
        print(f"  POSE {rec['index']} saved  ({why})  board at "
              f"{np.linalg.norm(tvec):.0f}mm")
        beep(True)
        return True

    print("\nHold the board still in a new orientation - it captures itself.")
    print("SPACE forces a capture, Q quits.\n")

    while running:
        ok_f, frame = cap.read()
        if not ok_f:
            continue
        tick += 1

        if tick % 3 == 0:
            small = cv2.resize(frame, None, fx=0.5, fy=0.5)
            g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            last_found = cv2.findChessboardCorners(
                g, BOARD, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK)
        found, corners = last_found

        pose_now = solve(corners, 2.0) if found else None
        if pose_now is not None:
            hist.append((time.time(), pose_now[0], pose_now[1]))
        else:
            hist.clear()

        # ── still? compare oldest sample within the hold window to newest ──
        still = False
        if len(hist) > 4:
            tnow = hist[-1][0]
            old = next((h for h in hist if tnow - h[0] <= HOLD_S), None)
            if old is not None and tnow - old[0] >= HOLD_S * 0.8:
                dr, dt = pose_delta((old[1], old[2]), (hist[-1][1], hist[-1][2]))
                still = dr < STILL_ROT_DEG and dt < STILL_TRANS_MM

        with lock:
            gA = None if latest["A"] is None else latest["A"].copy()
            gB = None if latest["B"] is None else latest["B"].copy()

        pA, rmsA, nA, okA = draw_panel("SENSOR A  (wearer LEFT)",
                                       "pins 6/7/4  -> CAD tof_right", gA,
                                       args.sensor in ("A", "both"))
        pB, rmsB, nB, okB = draw_panel("SENSOR B  (wearer RIGHT)",
                                       "pins 15/16/5 -> CAD tof_left", gB,
                                       args.sensor in ("B", "both"))
        sensor_ok = {"A": okA, "B": okB, "both": okA and okB}[args.sensor]

        # ── novel? must differ from every pose already captured ──
        novel, why = True, "manual"
        if pose_now is not None:
            for p in poses:
                dr, dt = pose_delta((np.array(p["rvec"]).reshape(3, 1),
                                     np.array(p["tvec"]).reshape(3, 1)), pose_now)
                if dr < NOVEL_ROT_DEG and dt < NOVEL_TRANS_MM:
                    novel = False
                    break

        right = np.vstack([pA, pB])
        h = right.shape[0]
        left = cv2.resize(frame, (int(frame.shape[1] * h / frame.shape[0]), h))
        if found:
            sc = left.shape[1] / frame.shape[1]
            cv2.drawChessboardCorners(left, BOARD, corners * 2 * sc, True)

        dist = np.linalg.norm(pose_now[1]) if pose_now is not None else 0.0
        far_enough = dist >= args.min_dist
        if not found:
            msg, col = "no checkerboard", (60, 60, 230)
        elif not far_enough:
            msg, col = f"TOO CLOSE {dist:.0f}mm - need >{args.min_dist:.0f}", (60, 60, 230)
        elif not sensor_ok:
            msg, col = f"sensor {args.sensor}: zones off the board", (60, 160, 240)
        elif not novel:
            msg, col = "too similar to a captured pose - tilt it more", (60, 200, 240)
        elif not still:
            msg, col = "HOLD STILL...", (60, 220, 220)
        else:
            msg, col = "CAPTURING", (60, 240, 60)
        cv2.putText(left, msg, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.85, col, 2,
                    cv2.LINE_AA)
        cv2.putText(left, f"poses: {len(poses)}   sensor {args.sensor}   "
                    f"board {dist:.0f}mm",
                    (12, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (235, 235, 235), 1,
                    cv2.LINE_AA)

        cv2.imshow("ToF/camera calibration capture", np.hstack([left, right]))

        auto_ok = ((not args.no_auto) and found and far_enough and sensor_ok
                   and still and novel)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        if k == ord(" ") or auto_ok:
            if capture(frame, "auto" if auto_ok else "manual"):
                hist.clear()
                time.sleep(0.6)      # let go / move on before re-arming

    running = False
    cap.release()
    cv2.destroyAllWindows()
    print(f"\n{len(poses)} poses -> {OUT/'poses.json'}")


if __name__ == "__main__":
    main()
