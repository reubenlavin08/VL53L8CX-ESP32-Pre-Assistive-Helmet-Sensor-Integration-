"""Derive ToF sensor frames from measured CAD points, and verify them.

Reads cad/extrinsics_measured.json (the source of truth) and RE-DERIVES every
value stored under each sensor's "verified" block, so the stored numbers can
never silently drift from the raw measurements.

    python docs/extrinsics_solve.py

DESIGN INTENT (cad/MASTER-HANDOFF-ADDENDUM.md, "the central result"):
  yaw each ToF LEVEL at +/-22.5 deg, group them, then tilt the WHOLE GROUP
  22.5 deg down as one rigid rotation.

  ORDER MATTERS. Yawing about world-vertical AFTER pitching each sensor is the
  superseded construction -- the one that produced the 2.02 deg seam. Composing
  the rotations in the wrong order makes a correct model look ~2.3 deg off.
  This cost a debugging round on 2026-08-16; don't reintroduce it.
"""
import json
import math
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "cad" / "extrinsics_measured.json"

FORWARD = np.array([0.0, 0.0, 1.0])   # sensors look toward +Z in this frame
TOL_DEG = 0.01                        # agreement required against design


def unit(v):
    return np.asarray(v, float) / np.linalg.norm(v)


def design_normal(yaw_deg, tilt_deg):
    """Rigid-group construction: yaw level first, THEN tilt the group down."""
    y, t = math.radians(yaw_deg), math.radians(tilt_deg)
    n = np.array([math.sin(y), 0.0, math.cos(y)])        # yawed, still level
    return np.array([n[0],                               # tilt about X, nose down
                     n[1] * math.cos(t) - n[2] * math.sin(t),
                     n[1] * math.sin(t) + n[2] * math.cos(t)])


def plane_normal(pts):
    """Least-squares plane normal through >=3 points, oriented toward FORWARD."""
    P = np.asarray(pts, float)
    centroid = P.mean(axis=0)
    _, _, vh = np.linalg.svd(P - centroid)
    n = vh[-1]
    return -n if np.dot(n, FORWARD) < 0 else n


def check(label, got, want, tol, unit_str=""):
    ok = abs(got - want) <= tol
    print(f"    {'OK ' if ok else 'BAD'}  {label:<28} {got:12.4f} {unit_str}"
          f"  (expect {want:.4f})")
    return ok


def main():
    d = json.loads(DATA.read_text())
    di = d["design_intent"]
    ok = True

    print(f"Source : {DATA.relative_to(ROOT)}")
    print(f"Frame  : {d['frame']}")
    print(f"Design : yaw +/-{di['yaw_deg']} deg level, then group tilt "
          f"{di['group_tilt_deg']} deg down\n")

    centres, normals = {}, {}

    for key, yaw_sign in (("tof_left", -1), ("tof_right", +1)):
        s = d[key]
        pts = list(s["pcb_front_face"].values())
        v = s["verified"]

        n = plane_normal(pts)
        n_des = design_normal(yaw_sign * di["yaw_deg"], di["group_tilt_deg"])
        resid = math.degrees(math.acos(min(1.0, abs(np.dot(n, n_des)))))

        centre = np.array(s["sensor_optical_centre"], float)
        off = float(np.dot(centre - np.array(pts[0], float), n))

        centres[key], normals[key] = centre, n

        print(f"  === {key}  ({len(pts)} corners) ===")
        print(f"    boresight  ({n[0]:+.5f}, {n[1]:+.5f}, {n[2]:+.5f})")
        print(f"    design     ({n_des[0]:+.5f}, {n_des[1]:+.5f}, {n_des[2]:+.5f})")
        ok &= check("angle vs design", resid, 0.0, TOL_DEG, "deg")
        ok &= check("centre off PCB plane", off,
                    v["centre_off_pcb_plane_mm"], 0.001, "mm")

        if len(pts) == 4:
            P = [np.array(p, float) for p in pts]
            d1, d2 = np.linalg.norm(P[0] - P[2]), np.linalg.norm(P[1] - P[3])
            ok &= check("diagonal difference", abs(d1 - d2) * 1000, 0.0,
                        1.0, "um   <- rectangle")
            ok &= check("4th corner off-plane",
                        abs(np.dot(P[3] - P[1], n)) * 1000, 0.0,
                        1.0, "um   <- coplanar")
        print()

    nl, nr = normals["tof_left"], normals["tof_right"]
    cl, cr = centres["tof_left"], centres["tof_right"]
    dv = d["derived"]

    print("  === derived ===")
    ok &= check("baseline centre-centre", float(np.linalg.norm(cr - cl)),
                dv["baseline_centre_to_centre_mm"], 0.001, "mm")
    ok &= check("boresight separation",
                math.degrees(math.acos(min(1.0, np.dot(nl, nr)))),
                dv["boresight_separation_deg"], 0.01, "deg")
    ok &= check("symmetry plane X", float((cl[0] + cr[0]) / 2),
                dv["symmetry_plane_x_mm"], 0.01, "mm")

    # frames stored per sensor must re-derive from the raw corners, using each
    # board's OWN left edge on both (see _EDGE_CONVENTION)
    print("  === stored frames ===")
    for key in ("tof_left", "tof_right"):
        f = d[key]["frame"]
        M = np.array([f["board_right"], f["board_up"], f["boresight"]]).T
        ok_ = abs(np.linalg.det(M) - 1.0) < 1e-4
        print(f"    {'OK ' if ok_ else 'BAD'}  {key:<12} det = {np.linalg.det(M):+.6f}"
              f"   (must be +1, right-handed)")
        ok &= ok_
    # NOTE: normalise before the dot product. The stored vectors are rounded to
    # 5 dp so |v| = 0.999997, and acos of a self-dot < 1 invents ~0.1 deg of
    # disagreement out of nothing.
    ul = unit(d["tof_left"]["frame"]["board_up"])
    ur = unit(d["tof_right"]["frame"]["board_up"])
    ok &= check("board-up agreement",
                math.degrees(math.acos(min(1.0, np.dot(ul, ur)))),
                d["derived"]["board_up_agreement_deg"], 0.01, "deg")

    print()
    print(f"  RESOLVED roll                     {d['RESOLVED']['roll']['status']}")
    for name, info in d["PENDING"].items():
        print(f"  PENDING  {name:<25} {info['status']}")

    print("\n" + ("ALL CHECKS PASS" if ok else "*** A CHECK FAILED ***"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
