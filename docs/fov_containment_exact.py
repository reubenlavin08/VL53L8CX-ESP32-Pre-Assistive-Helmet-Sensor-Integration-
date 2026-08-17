#!/usr/bin/env python3
"""fov_containment_exact.py - do the ToF fans REALLY sit inside the camera image?

The earlier coverage figure (9.06 deg margin top and bottom) treated the fields as
independent horizontal and vertical ranges. That is only valid if yaw and pitch are
separable - and they are NOT. Yawing a square cone 22 deg and pitching it 22.5 deg
swings its CORNERS further out in elevation than the nominal +/-22.5 deg band, in
exactly the same way a compound mitre is not the sum of its two angles.

This does it properly: build each ToF cone's four corner rays, rotate them into the
world, then express them in the CAMERA's own frame and test them against the real
rectangular image boundary.

A square cone is the convex hull of its four corner rays, and the camera frustum is
convex, so testing the corners is sufficient - if all four are inside, all of it is.

Rotation order is YAW after PITCH, which is how the sensors were actually built
("pointed them 22.5 down, then rotated them 22 out"). Verified: it reproduces the
measured axes (0,-0.3827,0.9239) and (0.6418,-0.3827,0.6646) exactly.

Run: python docs/fov_containment_exact.py
"""
import math
import numpy as np

CAM_H, CAM_V = 119.58, 63.12      # MEASURED, calibration_720p.txt, RMS 0.30 px
TOF_FOV = 45.0                    # OFFICIAL, DS14161 Table 2
PITCH = 22.5
CAM_YAW = 22.0                    # camera sits on the bisector
TOF_YAWS = {"ToF A": 0.0, "ToF B": 44.0}   # measured from the STEP


def rot(yaw_deg, pitch_deg):
    """Yaw applied AFTER pitch - the order the parts were built in."""
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    # pitch DOWN: (0,0,1) must map to (0,-sin p, cos p) to match the measured axes
    Rp = np.array([[1, 0, 0],
                   [0, math.cos(p), -math.sin(p)],
                   [0, math.sin(p), math.cos(p)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)],
                   [0, 1, 0],
                   [-math.sin(y), 0, math.cos(y)]])
    return Ry @ Rp


Rc = rot(CAM_YAW, PITCH)
N, U, R = Rc @ [0, 0, 1], Rc @ [0, 1, 0], Rc @ [1, 0, 0]

print("=" * 74)
print("EXACT FIELD-OF-VIEW CONTAINMENT CHECK")
print("=" * 74)
print(f"\ncamera axis  N ({N[0]:+.5f},{N[1]:+.5f},{N[2]:+.5f})")
print(f"camera up    U ({U[0]:+.5f},{U[1]:+.5f},{U[2]:+.5f})")
print(f"camera right R ({R[0]:+.5f},{R[1]:+.5f},{R[2]:+.5f})")
print(f"\ncamera image limits:  horizontal +/-{CAM_H/2:.2f} deg"
      f"   vertical +/-{CAM_V/2:.2f} deg\n")

t = math.tan(math.radians(TOF_FOV / 2))
worst_h = worst_v = 0.0
fail = False

for name, yaw in TOF_YAWS.items():
    Rt = rot(yaw, PITCH)
    print("-" * 74)
    print(f"{name}   yaw {yaw:.2f}  pitch {PITCH:.2f}   "
          f"axis ({(Rt@[0,0,1])[0]:+.4f},{(Rt@[0,0,1])[1]:+.4f},{(Rt@[0,0,1])[2]:+.4f})")
    print("-" * 74)
    print(f"{'corner':>10} | {'horiz in cam':>13} | {'vert in cam':>12} | verdict")
    for sx, sy, label in ((-1, -1, "bot-left"), (1, -1, "bot-right"),
                          (1, 1, "top-right"), (-1, 1, "top-left")):
        d = Rt @ np.array([sx * t, sy * t, 1.0])
        d /= np.linalg.norm(d)
        z, x, y = d @ N, d @ R, d @ U
        h = math.degrees(math.atan2(x, z))
        v = math.degrees(math.atan2(y, z))
        ok = abs(h) <= CAM_H / 2 and abs(v) <= CAM_V / 2
        fail |= not ok
        worst_h = max(worst_h, abs(h))
        worst_v = max(worst_v, abs(v))
        print(f"{label:>10} | {h:+10.2f} deg | {v:+9.2f} deg | "
              f"{'inside' if ok else '*** OUTSIDE ***'}")
    print()

print("=" * 74)
print("RESULT")
print("=" * 74)
print(f"  worst corner reaches  horizontal {worst_h:.2f} deg  (limit {CAM_H/2:.2f})"
      f"   margin {CAM_H/2 - worst_h:+.2f} deg")
print(f"                        vertical   {worst_v:.2f} deg  (limit {CAM_V/2:.2f})"
      f"   margin {CAM_V/2 - worst_v:+.2f} deg")
print(f"\n  {'*** SOME ToF DEPTH FALLS OUTSIDE THE IMAGE ***' if fail else 'ALL CORNERS INSIDE - every ToF zone has pixels behind it'}")

print("\n" + "-" * 74)
print("COMPARE: the separable estimate this replaces")
print("-" * 74)
sep_v = PITCH + TOF_FOV / 2
sep_h = max(TOF_YAWS.values()) - CAM_YAW + TOF_FOV / 2
print(f"""  treating the angles as independent ranges gives
      vertical   {TOF_FOV/2:.2f} deg from centre -> margin {CAM_V/2 - TOF_FOV/2:+.2f} deg
      horizontal {sep_h:.2f} deg from centre -> margin {CAM_H/2 - sep_h:+.2f} deg

  the exact corner test gives
      vertical   {worst_v:.2f} deg          -> margin {CAM_V/2 - worst_v:+.2f} deg
      horizontal {worst_h:.2f} deg          -> margin {CAM_H/2 - worst_h:+.2f} deg

  The difference is the compound-rotation effect: a yawed AND pitched square cone
  reaches further in elevation at its corners than its nominal half-angle suggests.
  Same reason a compound mitre is not the sum of its two angles.""")
