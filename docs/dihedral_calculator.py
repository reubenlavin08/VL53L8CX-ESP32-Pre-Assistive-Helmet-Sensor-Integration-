#!/usr/bin/env python3
"""dihedral_calculator.py - what angle do two angled panels meet at?

The compound-angle problem. Two panels, each with a yaw (rotation about vertical)
and a pitch (tilt down from vertical). What is the dihedral angle where they meet?

THE METHOD - it is all in the normals.

A panel yawed psi and pitched phi down has outward normal:

    n = ( sin(psi) * cos(phi),  -sin(phi),  cos(psi) * cos(phi) )

The angle between two panels' normals is just the dot product:

    cos(theta) = n1 . n2

and the DIHEDRAL you would measure at the joint is:

    dihedral = 180 - theta

That is the whole thing. It handles any combination of yaw and pitch, which is why
you cannot get it by adding or subtracting the individual angles - a compound of
yaw and pitch is not the sum of the two.

Run: python docs/dihedral_calculator.py
"""
import math


def normal(yaw_deg, pitch_deg):
    """Outward normal of a panel yawed `yaw` about vertical, pitched `pitch` down."""
    y, p = math.radians(yaw_deg), math.radians(pitch_deg)
    return (math.sin(y) * math.cos(p), -math.sin(p), math.cos(y) * math.cos(p))


def dihedral(a, b):
    """(angle between normals, dihedral at the joint) for two (yaw, pitch) panels."""
    n1, n2 = normal(*a), normal(*b)
    d = max(-1.0, min(1.0, sum(x * y for x, y in zip(n1, n2))))
    th = math.degrees(math.acos(d))
    return th, 180.0 - th


print("=" * 76)
print("DIHEDRAL CALCULATOR  -  the angle two angled panels meet at")
print("=" * 76)
print("""
  normal of a panel:  n = ( sin(yaw)cos(pitch), -sin(pitch), cos(yaw)cos(pitch) )
  angle between:      cos(theta) = n1 . n2
  dihedral at joint:  180 - theta
""")

CASES = [
    ("camera wall", (0.0, 22.5), "ToF front face (angled)", (22.0, 22.5)),
    ("camera wall", (0.0, 22.5), "ToF side face (vertical)", (22.0, 0.0)),
    ("ToF front (angled)", (22.0, 22.5), "ToF side (vertical)", (22.0, 0.0)),
    ("camera wall", (0.0, 22.5), "flat vertical front", (0.0, 0.0)),
    ("camera wall", (0.0, 22.5), "the slanted roof", (0.0, -67.5)),
    ("left ToF front", (-22.0, 22.5), "right ToF front", (22.0, 22.5)),
]

print(f"{'panel A':<26} {'panel B':<26} {'normals':>9} {'DIHEDRAL':>10}")
print("-" * 76)
for na, a, nb, b in CASES:
    th, di = dihedral(a, b)
    la = f"{na} ({a[0]:+.0f},{a[1]:+.0f})"
    lb = f"{nb} ({b[0]:+.0f},{b[1]:+.0f})"
    print(f"{la:<26} {lb:<26} {th:8.2f}° {di:9.2f}°")

print("""
Read the labels as (yaw, pitch) in degrees. Yaw is rotation about vertical,
positive to the right. Pitch is tilt downward from vertical.
""")

print("-" * 76)
print("WHY YOU CANNOT JUST SUBTRACT THE ANGLES")
print("-" * 76)
print("""Two panels both yawed 22 apart would meet at 180 - 22 = 158 if they were
both vertical. Pitch them BOTH down by the same amount and their normals swing
closer together, so the joint OPENS UP:
""")
print(f"{'shared pitch':>13} | {'angle between':>14} | {'dihedral':>9}")
print("-" * 42)
for p in (0, 5, 10, 15, 22.5, 30, 45, 60):
    th, di = dihedral((0.0, p), (22.0, p))
    print(f"{p:10.1f}deg | {th:11.2f}deg | {di:6.2f}deg")
print("""
  -> at pitch 0 you get the flat answer, 22.00 / 158.00
  -> at pitch 22.5 it has opened to 20.31 / 159.69
  -> the steeper the shared pitch, the more the joint opens

This is the same maths as a compound mitre in woodwork, or the dihedral of a
wing meeting a fuselage. The two rotations do not add.
""")

print("-" * 76)
print("THE SHORTCUT - do not calculate it at all")
print("-" * 76)
print("""If the new panel must be flush with a face that already exists, do not work
out the angle and type it in. Inherit it:

  * Reference Geometry > Plane > select the FACE, offset 0
      - gives a plane exactly coincident with it
  * or sketch directly ON the face and use Convert Entities
  * or extrude with End Condition = Up To Surface, picking that face

The angle then comes out exactly right whatever it is, and it stays right if the
face ever moves. Typing an angle means the joint is only as accurate as your
arithmetic and your typing - and it silently goes wrong the moment anything else
changes.

Use the numbers above to CHECK the result, not to create it.
""")
