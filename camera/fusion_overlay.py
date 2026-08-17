"""LIVE FUSION OVERLAY -- project both ToF sensors' zone grids onto the camera image.

    python camera/fusion_overlay.py --port COM9 --cam 1

The Stage-4 deliverable and the final Stage-3 diagnostic in one tool. Each valid
zone is drawn TWO ways, because the 2026-08-16 diagnosis showed a zone has two
distinct geometries:

  FRUSTUM QUAD  (geometric 45 deg bounds)  -- where the zone can DETECT. A small
      object reported by this zone can be anywhere inside this quad. Filled with
      a depth colour, outlined per sensor (A cyan / B yellow).
  CENTROID DOT  (effective ~34 deg table)  -- where an EXTENDED surface's reported
      distance actually belongs. The VCSEL illumination rolls off across outer
      zones (43.4 deg at 75% power, DS14161 2.3), so the signal-weighted centroid
      sits INSIDE the geometric centre. Fitted jointly from both sensors'
      calibration data (solved_joint.json); A and B agreed on it to ~1 deg.

DESIGN DECISIONS (from the 2026-08-16 research pass -- sources in DEVLOG):
  - Overlay on the RAW fisheye frame, never undistorted: rectifying a 120 deg
    lens magnifies the periphery, exactly where errors need judging.
  - Quad edges are SUBDIVIDED (5 points/edge) before projection: the fisheye
    maps straight 3D edges to curves; a 4-corner polygon lies by several px at
    45-60 deg off-axis, which reads as a phantom calibration error.
  - All boundary points of all zones are projected in ONE cv2.fisheye.projectPoints
    call. p_cam is computed by hand (R @ p + t) and rvec=tvec=0 passed, because
    points must be filtered for z_cam > 50 mm first: cv2's fisheye model is blind
    to the sign of z (opencv#22620) and happily projects points BEHIND the camera
    to plausible in-frame pixels.
  - Same z for all 4 corners of a quad (frontoparallel patch). Wrong at depth
    edges -- deliberately: a quad that shears/floats marks a zone whose return is
    ambiguous.
  - Latest-sample sync only. Fine for static/slow scenes, which is what the
    diagnostic is for. Head-speed motion needs firmware timestamps + IMU
    de-rotation (logged as future work) -- at 200 deg/s the 75 ms ToF latency is
    ~160 px of misalignment, dwarfing everything else.

Error-shape cheat sheet (what a systematic offset on screen means):
  uniform shift, same at all depths .......... rotation R wrong
  uniform shift, shrinks with distance ....... translation t (or depth bias)
  grows with angle from a SENSOR's centre .... zone-angle table wrong
  grows with angle from IMAGE centre ......... fisheye intrinsics (ruled out
                                               2026-08-16 to <0.1 deg)
Parallax is real and expected: a correct overlay MUST shift ~4 deg between a
board at 0.5 m and one at 4 m. If the overlay never moves with depth, t is
being ignored (units, or R/t order).

Keys:  q quit   s save PNG to camera/snapshots/   m toggle joint/CAD extrinsics
       c toggle centroid dots   t toggle per-zone distance text
"""
import argparse
import json
import pathlib
import threading
import time

import cv2
import numpy as np
import serial

SIDE = 4
NZ = SIDE * SIDE
FOV_DEG = 45.0                  # geometric, edge-to-edge (DS14161 2.2, tripod-verified)
MIN_Z_CAM = 50.0                # cull points this close to / behind the camera, mm
EDGE_SUBDIV = 5                 # points per quad edge before fisheye projection
DEPTH_NEAR, DEPTH_FAR = 200.0, 2500.0     # colour ramp range, mm
ROOT = pathlib.Path(__file__).resolve().parent.parent

latest = {"A": None, "B": None}
stamp = {"A": 0.0, "B": 0.0}
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
                stamp[p[0]] = time.monotonic()
    sp.close()


def zone_boundary_tans():
    """(SIDE,SIDE,P,2) tan(az),tan(el) of each zone's subdivided boundary ring.

    Geometric bounds: zone edges every FOV/SIDE deg, uniform in ANGLE. ST's own
    table is closer to tangent-uniform, but the two differ by <0.4 deg -- below
    the sensor's spec -- and angle-uniform is what the whole calibration chain
    used. Consistency beats a sub-noise refinement.
    """
    e = np.deg2rad((np.arange(SIDE + 1) - SIDE / 2.0) * (FOV_DEG / SIDE))
    ring = []
    for r in range(SIDE):
        for c in range(SIDE):
            a0, a1 = e[c], e[c + 1]
            b0, b1 = e[r], e[r + 1]
            s = np.linspace(0, 1, EDGE_SUBDIV, endpoint=False)
            top = np.stack([a0 + (a1 - a0) * s, np.full_like(s, b0)], 1)
            rgt = np.stack([np.full_like(s, a1), b0 + (b1 - b0) * s], 1)
            bot = np.stack([a1 - (a1 - a0) * s, np.full_like(s, b1)], 1)
            lft = np.stack([np.full_like(s, a0), b1 - (b1 - b0) * s], 1)
            ring.append(np.tan(np.vstack([top, rgt, bot, lft])))
    return np.array(ring).reshape(SIDE, SIDE, -1, 2)


def depth_color(z):
    """near = red, far = blue, clamped."""
    f = np.clip((z - DEPTH_NEAR) / (DEPTH_FAR - DEPTH_NEAR), 0, 1)
    return (int(255 * f), 64, int(255 * (1 - f)))          # BGR


def load_extrinsics():
    """(joint, cad): each {'A': (R, t), 'B': (R, t)} plus the effective table."""
    cad_j = json.loads((ROOT / "cad" / "extrinsics_measured.json").read_text())
    cad = {}
    for s, key in (("A", "tof_right"), ("B", "tof_left")):
        pri = cad_j["transforms_tof_to_camera"][key]
        cad[s] = (np.array(pri["R"], float), np.array(pri["t_mm"], float))
    joint = None
    eff = None
    jp = ROOT / "camera" / "tof_calib_poses" / "solved_joint.json"
    if jp.exists():
        j = json.loads(jp.read_text())
        joint = {"A": (np.array(j["sensor_A_tof_right"]["R"]), np.array(j["sensor_A_tof_right"]["t_mm"])),
                 "B": (np.array(j["sensor_B_tof_left"]["R"]), np.array(j["sensor_B_tof_left"]["t_mm"]))}
        eff = (np.array(j["effective_tan_x"], float), np.array(j["effective_tan_y"], float))
    return joint, cad, eff


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--cam", type=int, default=1)
    args = ap.parse_args()

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K = cal["K"]
    D = cal["D"].reshape(4, 1)          # fisheye projectPoints requires (4,1)

    joint, cadex, eff = load_extrinsics()
    use_joint = joint is not None
    if not use_joint:
        print("solved_joint.json not found -- CAD extrinsics only ('m' disabled)")
    ring = zone_boundary_tans()          # (4,4,P,2)
    P = ring.shape[2]
    if eff is None:
        # fall back to geometric centres for the dots
        t45 = np.tan(np.deg2rad((np.arange(SIDE) - 1.5) * (FOV_DEG / SIDE)))
        eff = (t45, t45)

    threading.Thread(target=reader, args=(args.port, args.baud), daemon=True).start()
    cap = cv2.VideoCapture(args.cam, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        running = False
        raise SystemExit(f"cannot open camera {args.cam}")

    outline = {"A": (255, 220, 80), "B": (60, 230, 230)}    # BGR: A cyan-ish, B yellow
    show_dots, show_text = True, False
    snapdir = ROOT / "camera" / "snapshots"
    snapdir.mkdir(exist_ok=True)
    nsnap = 0

    while running:
        ok, frame = cap.read()
        if not ok:
            continue
        ex = joint if (use_joint and joint) else cadex
        fill = frame.copy()
        lines = []          # (pixels Px2 int, sensor, z) deferred outline draws
        dots = []
        now = time.monotonic()

        for S in ("A", "B"):
            with lock:
                g = None if latest[S] is None else latest[S].copy()
                age = now - stamp[S]
            if g is None or age > 1.0:
                continue
            R, t = ex[S]
            valid = g > 0
            if not valid.any():
                continue
            # every boundary point of every valid zone, one batch
            zs, quads = [], []
            for r in range(SIDE):
                for c in range(SIDE):
                    if not valid[r, c]:
                        continue
                    z = g[r, c]
                    tan_ae = ring[r, c]                       # (P,2)
                    pts = np.column_stack([tan_ae[:, 0] * z, tan_ae[:, 1] * z,
                                           np.full(P, z)])
                    zs.append(z)
                    quads.append(pts)
                    # effective-centroid dot
                    pd = np.array([eff[0][c] * z, eff[1][r] * z, z])
                    quads.append(pd[None, :])
            allp = np.vstack(quads) @ R.T + t                 # camera frame
            proj = np.full((len(allp), 2), np.nan)
            front = allp[:, 2] > MIN_Z_CAM                    # opencv#22620 guard
            if front.any():
                uv, _ = cv2.fisheye.projectPoints(
                    allp[front].reshape(1, -1, 3).astype(np.float64),
                    np.zeros(3), np.zeros(3), K, D)
                proj[front] = uv.reshape(-1, 2)
            i = 0
            for z in zs:
                quad = proj[i:i + P]; dot = proj[i + P]; i += P + 1
                if np.isnan(quad).any():
                    continue
                q = quad.astype(np.int32)
                cv2.fillPoly(fill, [q], depth_color(z))
                lines.append((q, S, z))
                if not np.isnan(dot).any():
                    dots.append((dot.astype(int), S))

        view = cv2.addWeighted(fill, 0.30, frame, 0.70, 0)
        for q, S, z in lines:
            cv2.polylines(view, [q], True, outline[S], 1, cv2.LINE_AA)
            if show_text:
                cx, cy = q.mean(0).astype(int)
                cv2.putText(view, f"{z:.0f}", (cx - 18, cy + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                            cv2.LINE_AA)
        if show_dots:
            for d, S in dots:
                cv2.circle(view, tuple(d), 3, outline[S], -1, cv2.LINE_AA)

        mode = "JOINT calib" if (use_joint and joint) else "CAD prior"
        cv2.putText(view, f"{mode}   A quads cyan / B yellow   dot=surface centroid",
                    (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (240, 240, 240), 2,
                    cv2.LINE_AA)
        with lock:
            ages = {s: now - stamp[s] if stamp[s] else 99 for s in "AB"}
        cv2.putText(view, f"ToF age  A {ages['A']:.1f}s  B {ages['B']:.1f}s",
                    (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (160, 220, 160) if max(ages.values()) < 0.5 else (60, 140, 255),
                    1, cv2.LINE_AA)

        cv2.imshow("ToF-camera fusion overlay", view)
        k = cv2.waitKey(1) & 0xFF
        if k == ord("q"):
            break
        elif k == ord("m") and joint is not None:
            use_joint = not use_joint
        elif k == ord("c"):
            show_dots = not show_dots
        elif k == ord("t"):
            show_text = not show_text
        elif k == ord("s"):
            p = snapdir / f"fusion_{nsnap:03d}.png"
            cv2.imwrite(str(p), view)
            print(f"saved {p}")
            nsnap += 1

    running = False
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
