#!/usr/bin/env python3
"""tof_rigid_group_check.py - the "yaw level, then tilt the whole group" arrangement.

Reuben's construction:
    1. both sensors LEVEL, yawed +/-22.5 deg from centre
    2. group them into one rigid sub-assembly
    3. tilt the WHOLE group 22.5 deg down

versus the earlier one:
    pitch each sensor 22.5 deg down first, THEN yaw each one out

The two give different results, and the difference is not subtle. Yawing while level
puts BOTH inner boundary planes vertical and coincident - they share one plane. A
rigid rotation of the whole group cannot change that, because rigid rotations preserve
every relative angle. So the seam stays exact at every elevation.

The old order yawed each sensor about the WORLD vertical AFTER pitching it, which
tilts the two inner planes differently and opens the gap-at-top / overlap-at-bottom.

Run: python docs/tof_rigid_group_check.py
"""
import math
import numpy as np

TOF = 45.0
PITCH = 22.5
HALF_YAW = 22.5          # each sensor, from the pod centreline


def Ry(a):
    a = math.radians(a)
    return np.array([[math.cos(a), 0, math.sin(a)], [0, 1, 0],
                     [-math.sin(a), 0, math.cos(a)]])


def Rx_down(a):
    a = math.radians(a)
    return np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)],
                     [0, math.sin(a), math.cos(a)]])


t = math.tan(math.radians(TOF / 2))
GROUP = Rx_down(PITCH)                       # applied to the whole sub-assembly
SENS = {"ToF L": Ry(-HALF_YAW), "ToF R": Ry(+HALF_YAW)}

print("=" * 74)
print("RIGID-GROUP ARRANGEMENT:  yaw level, then tilt the whole thing")
print("=" * 74)

print("\n" + "-" * 74)
print("1. THE CORNER RAY YOU MEASURED")
print("-" * 74)
# NOTE on labels: for the RIGHT sensor +x is the OUTER side; for the LEFT sensor
# +x is the INNER side. Getting this backwards makes the two corners look wrong.
for name, Rs, outer_sign in (("ToF R", SENS["ToF R"], +1), ("ToF L", SENS["ToF L"], -1)):
    R = GROUP @ Rs
    for sy, lab in ((+1, "top"), (-1, "bottom")):
        for sx, side in ((outer_sign, "outer"), (-outer_sign, "inner")):
            d = R @ (np.array([sx * t, sy * t, 1.0]) / np.linalg.norm([t, t, 1.0]))
            el = math.degrees(math.asin(d[1]))
            print(f"  {name} {lab}-{side} corner ray:  elevation {el:+7.2f} deg")
    break
d = GROUP @ (SENS["ToF R"] @ np.array([0, -t, 1.0]) / np.linalg.norm([0, t, 1.0]))
print(f"\n  bottom FACE centre ray:            elevation "
      f"{math.degrees(math.asin(d[1])):+7.2f} deg")
print("""
  A corner ray descends LESS steeply than the bottom face, because part of its
  travel is sideways. That is why an edge measurement and a face measurement
  give different answers, and both are correct.""")

print("\n" + "-" * 74)
print("2. THE SEAM - are the inner boundary planes coincident?")
print("-" * 74)
# inner face of L is its +x face; inner face of R is its -x face
nL = GROUP @ (SENS["ToF L"] @ (np.array([1.0, 0, -t]) / np.linalg.norm([1, 0, t])))
nR = GROUP @ (SENS["ToF R"] @ (np.array([-1.0, 0, -t]) / np.linalg.norm([1, 0, t])))
ang = math.degrees(math.acos(abs(float(np.clip(nL @ nR, -1, 1)))))
print(f"  ToF L inner-plane normal ({nL[0]:+.5f},{nL[1]:+.5f},{nL[2]:+.5f})")
print(f"  ToF R inner-plane normal ({nR[0]:+.5f},{nR[1]:+.5f},{nR[2]:+.5f})")
print(f"\n  angle between the two planes: {ang:.4f} deg"
      f"   -> {'COINCIDENT - seam is exactly zero' if ang < 0.01 else 'not coincident'}")

print("\n" + "-" * 74)
print("3. SEAM vs ELEVATION")
print("-" * 74)


def edge_az(Rs, elev, side, n=6001):
    R = GROUP @ Rs
    best = None
    for a in np.linspace(-t, t, n):
        for u, v in ((side * t, a), (a, side * t), (a, -side * t)):
            d = R @ np.array([u, v, 1.0])
            d /= np.linalg.norm(d)
            if abs(math.degrees(math.asin(d[1])) - elev) < 0.30:
                az = math.degrees(math.atan2(d[0], d[2]))
                best = az if best is None else (max(best, az) if side > 0 else min(best, az))
    return best


print(f"{'elevation':>10} | {'L right edge':>14} | {'R left edge':>13} | {'seam':>16}")
print("-" * 62)
for elev in (0.0, -5.0, -10.0, -22.5, -30.0, -40.0):
    a = edge_az(SENS["ToF L"], elev, +1)
    b = edge_az(SENS["ToF R"], elev, -1)
    if a is None or b is None:
        continue
    seam = b - a
    tag = (f"{seam:+.2f} deg gap" if seam > 0.05 else
           f"{-seam:.2f} deg overlap" if seam < -0.05 else "edge to edge")
    print(f"{elev:+9.1f}° | {a:+13.2f}° | {b:+12.2f}° | {tag:>16}")

print("""
  Constant at every elevation. That is the whole win: the two fans share one
  boundary plane instead of crossing at a single height, so there is no height
  at which a hole opens up and none at which coverage is wasted.""")
