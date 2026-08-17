"""Solve ToF->camera extrinsics from captured planar-target poses.

    python camera/tof_calib_solve.py --sensor A

METHOD. Each pose gives the same physical plane described twice:
  - camera: solvePnP on the checkerboard -> plane (n_cam, d_cam) in camera frame
  - ToF   : 16 zone distances -> 3D points in ToF frame
Every ToF point must land ON the camera's plane once transformed. Minimise the
point-to-plane distance over all poses and all zones.

    residual = dot(n_cam, R @ p_tof + t) - d_cam            [mm]

WHY THE FOV IS A FREE PARAMETER. The zone ray directions depend on the ToF's
angular field, and the datasheet's nominal 45 deg produced a strongly
radially-symmetric residual (corners -14 mm, centre +14 mm, edges ~0) that no
choice of R,t can absorb -- it is a lens-model error, not a pose error. Fitting
plane RMS alone cannot recover the FOV (as FOV->0 the rays become parallel, the
points collapse onto a line, and any plane fits: degenerate). Anchoring against
the CAMERA's plane removes that degeneracy and makes FOV observable.

Initialised from the CAD prior in cad/extrinsics_measured.json, which is also
what tells you whether the answer is sane rather than merely converged.
"""
import argparse
import json
import pathlib

import cv2
import numpy as np
from scipy.optimize import least_squares

ROOT = pathlib.Path(__file__).resolve().parent.parent
POSES = ROOT / "camera" / "tof_calib_poses" / "poses.json"
CAD = ROOT / "cad" / "extrinsics_measured.json"
SIDE = 4

# sensor A is the wearer's LEFT, which is CAD tof_right  (sensor_identity block)
SENSOR_TO_CAD = {"A": "tof_right", "B": "tof_left"}


def zone_rays(fov_x_deg, fov_y_deg, side=SIDE):
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
    tx = np.tan(np.deg2rad((np.arange(side) - (side - 1) / 2.0) * (fov_x_deg / side)))
    ty = np.tan(np.deg2rad((np.arange(side) - (side - 1) / 2.0) * (fov_y_deg / side)))
    d = np.zeros((side, side, 3))
    for r in range(side):
        for c in range(side):
            d[r, c] = [tx[c], ty[r], 1.0]
    return d


def load(sensor):
    P = json.loads(POSES.read_text())
    out = []
    for p in P:
        if sensor not in p:
            continue
        Rb, _ = cv2.Rodrigues(np.array(p["rvec"], float))
        t = np.array(p["tvec"], float).ravel()
        n = Rb[:, 2]                       # board plane normal, camera frame
        if n @ t > 0:                      # orient toward the camera
            n = -n
        out.append({"n": n, "d": float(n @ t),
                    "g": np.array(p[sensor]["mean_mm"], float),
                    "i": p["index"]})
    return out


def residuals(x, poses, fit_fov):
    rvec, t = x[0:3], x[3:6]
    fx, fy = (x[6], x[7]) if fit_fov else (45.0, 45.0)
    R, _ = cv2.Rodrigues(rvec)
    rays = zone_rays(fx, fy)
    out = []
    for p in poses:
        v = p["g"] > 0
        pts = rays[v] * p["g"][v][:, None]        # ToF frame
        pc = pts @ R.T + t                        # camera frame
        out.append(pc @ p["n"] - p["d"])          # point-to-plane, mm
    return np.concatenate(out)


def report(name, x, poses, fit_fov, prior_R, prior_t):
    r = residuals(x, poses, fit_fov)
    R, _ = cv2.Rodrigues(x[0:3])
    t = x[3:6]
    fx, fy = (x[6], x[7]) if fit_fov else (45.0, 45.0)
    dR = R @ prior_R.T
    ang = np.degrees(np.arccos(np.clip((np.trace(dR) - 1) / 2, -1, 1)))
    print(f"\n=== {name} ===")
    print(f"  rms residual   {np.sqrt((r**2).mean()):8.2f} mm     "
          f"max {np.abs(r).max():.1f} mm")
    if fit_fov:
        print(f"  fitted FOV     {fx:8.2f} x {fy:.2f} deg   (datasheet 45.00)")
    print(f"  t (mm)         [{t[0]:+8.2f} {t[1]:+8.2f} {t[2]:+8.2f}]")
    print(f"  CAD prior t    [{prior_t[0]:+8.2f} {prior_t[1]:+8.2f} {prior_t[2]:+8.2f}]"
          f"   delta {np.linalg.norm(t - prior_t):.2f} mm")
    print(f"  rotation vs CAD prior: {ang:.3f} deg")
    return np.sqrt((r ** 2).mean()), ang, t, R, (fx, fy)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sensor", default="A", choices=["A", "B"])
    ap.add_argument("--save", action="store_true", help="write result JSON")
    args = ap.parse_args()

    poses = load(args.sensor)
    cad = json.loads(CAD.read_text())
    key = SENSOR_TO_CAD[args.sensor]
    pri = cad["transforms_tof_to_camera"][key]
    prior_R = np.array(pri["R"], float)
    prior_t = np.array(pri["t_mm"], float)

    print(f"sensor {args.sensor}  ->  CAD {key}   ({len(poses)} poses, "
          f"{sum((p['g']>0).sum() for p in poses)} zone measurements)")
    print(f"initialised from the CAD prior")

    x0 = np.concatenate([cv2.Rodrigues(prior_R)[0].ravel(), prior_t])

    # 1) pose only, datasheet FOV — the baseline
    s1 = least_squares(residuals, x0, args=(poses, False), method="lm")
    r1 = report("R,t only  (FOV fixed at 45 deg)", s1.x, poses, False, prior_R, prior_t)

    # 2) pose + FOV
    s2 = least_squares(residuals, np.concatenate([s1.x, [45.0, 45.0]]),
                       args=(poses, True), method="lm")
    r2 = report("R,t + FOV fitted", s2.x, poses, True, prior_R, prior_t)

    print(f"\n  fitting the FOV cut rms from {r1[0]:.2f} -> {r2[0]:.2f} mm "
          f"({100*(1-r2[0]/r1[0]):.0f}% better)")

    if args.save:
        R, t, (fx, fy) = r2[3], r2[2], r2[4]
        out = {"sensor": args.sensor, "cad_frame": key, "n_poses": len(poses),
               "rms_mm": r2[0], "fov_x_deg": fx, "fov_y_deg": fy,
               "R": R.tolist(), "t_mm": t.tolist(),
               "rotation_vs_cad_deg": r2[1],
               "translation_vs_cad_mm": float(np.linalg.norm(t - prior_t))}
        p = POSES.parent / f"solved_{args.sensor}.json"
        p.write_text(json.dumps(out, indent=1))
        print(f"\n  wrote {p}")


if __name__ == "__main__":
    main()
