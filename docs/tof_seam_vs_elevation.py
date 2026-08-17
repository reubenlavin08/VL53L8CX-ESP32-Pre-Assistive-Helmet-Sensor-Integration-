#!/usr/bin/env python3
"""tof_seam_vs_elevation.py - the seam between the two ToF fans is NOT constant.

The design figure "44 deg apart, 45 deg each, so 1 deg of overlap" is only true in
one horizontal slice - the one through the sensors' own axes, 22.5 deg below level.
Everywhere else the seam is different, and at the TOP of the fans it becomes a GAP.

Why: each fan is a square pyramid whose half-width is 22.5 deg measured in the
sensor's OWN horizontal plane. Pitch the sensor 22.5 deg down and that plane is no
longer level, so the fan's width in WORLD azimuth changes with elevation - widening
toward the bottom and narrowing toward the top.

This works out the real azimuth limits of each fan at every elevation, and reports
where they overlap and where they leave a hole.

Run: python docs/tof_seam_vs_elevation.py
"""
import math
import numpy as np

TOF = 45.0
PITCH = 22.5
YAWS = (0.0, 44.0)          # measured from the STEP


def rot(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    Rp = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    Ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    return Ry @ Rp


t = math.tan(math.radians(TOF / 2))
R = {y: rot(y, PITCH) for y in YAWS}


def azimuth_span(yaw, elev_deg, n=4001):
    """World-azimuth range this fan covers at a given world elevation."""
    Rm = R[yaw]
    lo, hi = None, None
    for a in np.linspace(-t, t, n):          # sweep the local horizontal parameter
        for b in (-t, t):                    # both local vertical edges
            for u, v in ((a, b), (b, a)):
                d = Rm @ np.array([u, v, 1.0])
                d /= np.linalg.norm(d)
                e = math.degrees(math.asin(d[1]))
                if abs(e - elev_deg) < 0.35:
                    az = math.degrees(math.atan2(d[0], d[2]))
                    lo = az if lo is None else min(lo, az)
                    hi = az if hi is None else max(hi, az)
    return lo, hi


print("=" * 76)
print("ToF SEAM vs ELEVATION  -  where the two fans overlap, and where they don't")
print("=" * 76)
print("""elevation 0 = dead level (horizon).  The sensors' AXES sit at -22.5 deg.
azimuth 0 = straight ahead along ToF A; the bisector is at +22.0 deg.\n""")
print(f"{'elevation':>10} | {'fan A right edge':>17} | {'fan B left edge':>16} | {'seam':>18}")
print("-" * 76)

worst_gap, worst_at = 0.0, None
for elev in (0.0, -2.0, -5.0, -10.0, -15.0, -22.5, -30.0, -35.0, -40.0, -44.0):
    a_lo, a_hi = azimuth_span(YAWS[0], elev)
    b_lo, b_hi = azimuth_span(YAWS[1], elev)
    if a_hi is None or b_lo is None:
        continue
    seam = b_lo - a_hi          # positive = GAP, negative = overlap
    if seam > worst_gap:
        worst_gap, worst_at = seam, elev
    tag = f"{seam:+.2f} deg GAP" if seam > 0.01 else (
          f"{-seam:.2f} deg overlap" if seam < -0.01 else "edge to edge")
    print(f"{elev:+9.1f}° | {a_hi:+16.2f}° | {b_lo:+15.2f}° | {tag:>18}")

print("-" * 76)
print(f"""
WHAT THIS MEANS

  At the sensors' own axis elevation (-22.5 deg) you get the 1 deg of overlap the
  design intended. That number was never wrong - it was just never the whole story.

  Toward the BOTTOM the fans widen in azimuth and overlap heavily. That overlap is
  wasted coverage, and two unsynced VL53L8CX units illuminating the same volume
  raise each other's noise floor (they have a SYNC pin, UM3109 4.15, if it matters).

  Toward the TOP they pull apart and leave a GAP dead ahead. Worst: {worst_gap:.2f} deg
  at {worst_at:+.1f} deg elevation.

  The gap matters more than the overlap, because the top of the fan is the LEVEL
  ray - the part of the field looking straight out at head height, where an
  obstacle is most likely to be something worth avoiding.
""")

print("-" * 76)
print("FIXES, IF THE TOP GAP MATTERS")
print("-" * 76)
print("""  1. MORE TOE-IN. Reduce the yaw separation by about 2 deg (44 -> 42) so the fans
     meet at the LEVEL ray instead of at their axes. Closes the gap where it
     matters; deepens the overlap lower down, where overlap costs little. One
     number, and the cheapest real fix.

  2. LESS DOWNTILT. The effect scales with pitch - at zero pitch the seam is the
     same at every elevation. But downtilt is what puts the floor in view, so this
     trades a known problem for a worse one.

  3. ACCEPT IT. The camera still sees the gap; it just carries no measured distance
     there. For "is something in the way" that may be fine, especially as an
     obstacle at head height is usually wide enough to enter one fan anyway.

  NOT A FIX: rolling the sensors about their own axes. Their fan edges are ALREADY
  level (verified: all four top corners sit at y = 0.000). The azimuth width of a
  square pyramid varies with elevation whenever its axis is pitched, whatever the
  roll. That is spherical geometry, not a mounting error, and no roll removes it.""")
