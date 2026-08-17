#!/usr/bin/env python3
"""tof_rigid_group_verify.py - does the rigid-group construction really give a zero seam?

TWO WAYS to reach "22.5 deg out, 22.5 deg down", and they are NOT the same orientation:

  OLD (as built):  pitch each sensor 22.5 down about world X, THEN yaw it about world Y.
                   -> inner boundary planes end up tilted differently
                   -> seam varies with elevation: 2.02 deg GAP at level, 12 deg overlap low

  NEW (rigid group): yaw both sensors LEVEL to +/-22.5, group them, THEN tilt the whole
                   group 22.5 down about ONE axis.
                   -> with a 45 deg fan, each inner edge lands exactly on the centreline
                      BEFORE the tilt, so both inner planes are the SAME plane
                   -> tilting the group rigidly carries both together
                   -> the planes stay coincident: zero seam at EVERY elevation

Rotation matrices are not commutative; this is that fact with a physical consequence.

Run: python docs/tof_rigid_group_verify.py
"""
import math
import numpy as np

TOF = 45.0
YAW = 22.5        # rigid-group design needs EXACTLY half the FoV
PITCH = 22.5


def Ry(a):
    a = math.radians(a)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0],
                     [-math.sin(a), 0, math.cos(a)]])


def Rx(a):
    a = math.radians(a)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)],
                     [0, math.sin(a), math.cos(a)]])


t = math.tan(math.radians(TOF / 2))
# inner boundary plane normals in sensor-local coords
nA_local = np.array([1.0, 0.0, -t]) / math.hypot(1, t)     # A's RIGHT face
nB_local = np.array([-1.0, 0.0, -t]) / math.hypot(1, t)    # B's LEFT face

print("=" * 72)
print("RIGID-GROUP vs PER-SENSOR ROTATION")
print("=" * 72)

for label, RA, RB in (
    ("OLD  pitch-then-yaw, per sensor", Ry(-YAW) @ Rx(PITCH), Ry(+YAW) @ Rx(PITCH)),
    ("NEW  yaw level, then tilt group", Rx(PITCH) @ Ry(-YAW), Rx(PITCH) @ Ry(+YAW)),
):
    nA, nB = RA @ nA_local, RB @ nB_local
    ang = math.degrees(math.acos(abs(float(np.clip(nA @ nB, -1, 1)))))
    print(f"\n{label}")
    print(f"   A inner-plane normal ({nA[0]:+.5f},{nA[1]:+.5f},{nA[2]:+.5f})")
    print(f"   B inner-plane normal ({nB[0]:+.5f},{nB[1]:+.5f},{nB[2]:+.5f})")
    print(f"   angle between the two planes: {ang:.4f}°   "
          f"{'<-- COINCIDENT, zero seam everywhere' if ang < 0.01 else '<-- seam varies with elevation'}")

print("\n" + "=" * 72)
print("WHY IT WORKS")
print("=" * 72)
print(f"""  With a {TOF}° fan, the half-width is {TOF/2}°. Yaw a sensor {YAW}° off centre while
  it is still LEVEL and its inner edge lands at exactly 0° - on the centreline.
  Do that to both and their inner boundary planes are one and the same vertical plane.

  A rigid tilt of the whole group is a single rotation applied to both, so a shared
  plane stays shared. The seam cannot open or close, at any elevation.

  This REQUIRES yaw = FoV/2 = {TOF/2}° exactly. At the previously-built 22.0° the edges
  overlap by 1° before the tilt, and the construction loses its exactness.

  THE COST: the two inner edges are now PARALLEL (both at 0° azimuth), so they never
  converge. A corridor as wide as the BASELINE is seen by neither sensor at any range.
  Shrink it by moving the sensors closer together - not by changing the angle.""")
