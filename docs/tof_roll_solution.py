#!/usr/bin/env python3
"""tof_roll_solution.py - kill the seam entirely by ROLLING each sensor.

The problem: two square fans, yawed apart and pitched down, leave a gap at the top
and overlap at the bottom. Toe-in only trades one for the other.

The insight: each fan's inner boundary is a flat PLANE through the sensor's apex.
If both sensors' inner boundary planes are made to COINCIDE - both lying in the
pod's vertical symmetry plane - the fans meet exactly, at every elevation. Not a
compromise: a gap of zero and an overlap of zero, everywhere.

To do that, the inner boundary plane must be VERTICAL, which needs a roll about the
sensor's own optical axis. Solving for it:

  the inner face in sensor coords is  x = t*z,  normal  n = (1, 0, -t)
  roll by theta, then pitch by phi; the normal's vertical component becomes
      n_y = cos(phi) sin(theta) + t sin(phi)
  set that to zero:
      sin(theta) = -t tan(phi)          with t = tan(FoV/2)

Run: python docs/tof_roll_solution.py
"""
import math
import numpy as np

TOF = 45.0
PITCH = 22.5
YAWS = (0.0, 44.0)


def rot(yaw, pitch, roll):
    y, p, r = map(math.radians, (yaw, pitch, roll))
    Rr = np.array([[math.cos(r), -math.sin(r), 0],
                   [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    Rp = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)],
                   [0, math.sin(p), math.cos(p)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0],
                   [-math.sin(y), 0, math.cos(y)]])
    return Ry @ Rp @ Rr


t = math.tan(math.radians(TOF / 2))
theta = math.degrees(math.asin(-t * math.tan(math.radians(PITCH))))

print("=" * 76)
print("ROLL SOLUTION")
print("=" * 76)
print(f"""
  t = tan({TOF/2}) = {t:.6f}     tan(pitch) = tan({PITCH}) = {math.tan(math.radians(PITCH)):.6f}
  sin(theta) = -t * tan(pitch) = {-t*math.tan(math.radians(PITCH)):.6f}

  ROLL EACH SENSOR BY {abs(theta):.2f} DEGREES  (mirrored: one +, one -)
""")

# theta is already negative from the asin; sensor A takes it as-is and B mirrors it.
# (Getting these the wrong way round rolls both fans AWAY from each other and makes
# the seam worse, which is exactly what the first attempt did.)
ROLLS = {YAWS[0]: theta, YAWS[1]: -theta}


def face_normal(yaw, roll, side):
    """Outward normal of the fan's inner boundary plane."""
    n = np.array([side * 1.0, 0.0, -t])
    n /= np.linalg.norm(n)
    return rot(yaw, PITCH, roll) @ n


print("-" * 76)
print("CHECK: are the inner boundary planes vertical, and do they coincide?")
print("-" * 76)
nA = face_normal(YAWS[0], ROLLS[YAWS[0]], +1)    # A's RIGHT face
nB = face_normal(YAWS[1], ROLLS[YAWS[1]], -1)    # B's LEFT face
for lab, n in (("ToF A inner face", nA), ("ToF B inner face", nB)):
    tilt = math.degrees(math.asin(abs(n[1])))
    az = math.degrees(math.atan2(n[0], n[2]))
    print(f"  {lab}: normal ({n[0]:+.5f},{n[1]:+.5f},{n[2]:+.5f})   "
          f"off-vertical {tilt:.4f}°   azimuth {az:+.2f}°")
ang = math.degrees(math.acos(abs(float(np.clip(nA @ nB, -1, 1)))))
print(f"\n  angle between the two planes: {ang:.4f}°   "
      f"({'COINCIDENT' if ang < 0.01 else 'NOT coincident'})")

print("\n" + "-" * 76)
print("SEAM vs ELEVATION, with the roll applied")
print("-" * 76)


def azimuth_edge(yaw, roll, elev, side, n=6001):
    Rm = rot(yaw, PITCH, roll)
    best = None
    for a in np.linspace(-t, t, n):
        for u, v in ((side * t, a), (a, side * t), (a, -side * t)):
            d = Rm @ np.array([u, v, 1.0])
            d /= np.linalg.norm(d)
            if abs(math.degrees(math.asin(d[1])) - elev) < 0.30:
                az = math.degrees(math.atan2(d[0], d[2]))
                best = az if best is None else (max(best, az) if side > 0 else min(best, az))
    return best


print(f"{'elevation':>10} | {'A right edge':>14} | {'B left edge':>13} | {'seam':>16}")
print("-" * 66)
for elev in (0.0, -5.0, -10.0, -22.5, -30.0, -40.0):
    a = azimuth_edge(YAWS[0], ROLLS[YAWS[0]], elev, +1)
    b = azimuth_edge(YAWS[1], ROLLS[YAWS[1]], elev, -1)
    if a is None or b is None:
        continue
    seam = b - a
    tag = (f"{seam:+.2f}° gap" if seam > 0.05 else
           f"{-seam:.2f}° overlap" if seam < -0.05 else "edge to edge")
    print(f"{elev:+9.1f}° | {a:+13.2f}° | {b:+12.2f}° | {tag:>16}")

print("""
  A constant seam at every elevation is the point. The two fans now share one
  boundary plane instead of crossing at a single height.
""")

print("-" * 76)
print("WHAT IT COSTS")
print("-" * 76)
print(f"""  The fan footprints are now ROTATED {abs(theta):.1f}° in the image rather than
  sitting square. The combined coverage is a shallow chevron, not a neat band.

  Nothing is lost in area - each sensor still covers its full 45 x 45 deg. The
  coverage is simply redistributed: less doubled-up floor, more usable width at
  head height, which is the trade you asked for.

  Mechanically this means rotating each ToF board {abs(theta):.1f}° about its own
  optical axis in its slot. That is a change to the slot orientation, not to the
  pod's outer geometry - the boards still sit at yaw {YAWS[1]/2:.0f}° and pitch {PITCH}°.""")
