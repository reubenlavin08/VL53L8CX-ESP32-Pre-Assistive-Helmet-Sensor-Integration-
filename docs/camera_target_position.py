#!/usr/bin/env python3
"""camera_target_position.py - exactly where to put the camera lens tip.

The plan: lens tip level with the two ToF apertures (zero forward offset), raised
by some amount. This works out what "raised" means in world coordinates.

THE TRAP: the sensors look 22.5 deg DOWNWARD, so "up" for the camera is not world
+Y. Move the camera straight up in Y and the lens tip slides BACKWARDS relative to
the sensors' line of sight, because their sight line is tilted. To stay level with
the apertures you must move up AND forward together.

All ToF positions are recovered from the user's own STEP by check_user_assembly.py.
"""
import math

# --- from the exported assembly, recovered from geometry -------------------
OPT_A = (670.045, 294.917, 1522.646)
OPT_B = (704.789, 294.917, 1508.529)
AXIS_A = (-0.0000, -0.3827, 0.9239)
AXIS_B = (+0.6418, -0.3827, 0.6646)

CAM_PCB = 38.00        # [CALIPER] square board
CAM_BARREL_H = 24.21   # [CALIPER] lens tip in front of the PCB front face
PITCH = 22.5


def norm(v):
    m = math.sqrt(sum(c * c for c in v))
    return tuple(c / m for c in v)


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def scale(v, s):
    return tuple(c * s for c in v)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


# midpoint between the two ToF apertures
M = tuple((a + b) / 2 for a, b in zip(OPT_A, OPT_B))

# the yaw bisector: average the two axes' HORIZONTAL parts only
hA = norm((AXIS_A[0], 0.0, AXIS_A[2]))
hB = norm((AXIS_B[0], 0.0, AXIS_B[2]))
d = norm(add(hA, hB))

# camera view axis = that bisector, pitched 22.5 deg down
cp, sp = math.cos(math.radians(PITCH)), math.sin(math.radians(PITCH))
N = norm(add(scale(d, cp), (0.0, -sp, 0.0)))
# camera "up" - perpendicular to N, in the same vertical plane
U = norm(add(scale(d, sp), (0.0, cp, 0.0)))

print("=" * 74)
print("WHERE TO PUT THE CAMERA LENS TIP")
print("=" * 74)
print(f"""
ToF aperture A      ({OPT_A[0]:9.3f}, {OPT_A[1]:9.3f}, {OPT_A[2]:9.3f})
ToF aperture B      ({OPT_B[0]:9.3f}, {OPT_B[1]:9.3f}, {OPT_B[2]:9.3f})
MIDPOINT   M        ({M[0]:9.3f}, {M[1]:9.3f}, {M[2]:9.3f})

camera view axis N  ({N[0]:+.5f}, {N[1]:+.5f}, {N[2]:+.5f})   pitch {math.degrees(math.asin(-N[1])):.2f} deg down
camera "up"      U  ({U[0]:+.5f}, {U[1]:+.5f}, {U[2]:+.5f})   perpendicular to N
  check U . N = {dot(U, N):+.6f}  (must be zero)
""")

print("-" * 74)
print("THE TRAP: 'straight up in Y' is NOT 'up' for a tilted camera")
print("-" * 74)
print(f"""If you raise the camera by h in world Y only, the lens tip ends up
  {abs(N[1]):.5f} x h  BEHIND the ToF aperture plane, measured along the sight line.

Because the sensors look downward, moving vertically moves you backwards
relative to what they see.
""")
print(f"{'raise in world Y':>18} | {'ends up BEHIND by':>18}")
print("-" * 40)
for h in (10, 20, 30, 40, 50):
    print(f"{h:15d} mm | {abs(N[1]) * h:15.2f} mm")
print("""
Behind is the WRONG side: the ToF boards would then be in front of the lens tip,
inside a 119.58 deg field. That is the one thing to avoid.
""")

print("-" * 74)
print("THE FIX: move along the camera's own UP axis instead")
print("-" * 74)
print("Raising by h along U keeps the lens tip exactly level with the apertures.\n")
print(f"{'h':>6} | {'world dX':>9} {'world dY':>9} {'world dZ':>9} | "
      f"{'lens tip target (X, Y, Z)':>34}")
print("-" * 78)
for h in (20, 25, 30, 40, 50):
    dv = scale(U, h)
    P = add(M, dv)
    fwd = dot(sub(P, M), N)
    print(f"{h:4d}mm | {dv[0]:9.3f} {dv[1]:9.3f} {dv[2]:9.3f} | "
          f"({P[0]:10.3f},{P[1]:10.3f},{P[2]:10.3f})   fwd {fwd:+.3f}")

print("\n" + "-" * 74)
print("WHY ZERO FORWARD OFFSET IS THE BEST CHOICE - better than you think")
print("-" * 74)
print(f"""With the lens tip level with the ToF apertures, the whole camera BODY sits
{CAM_BARREL_H:.2f} mm BEHIND that plane (the barrel length).

A field of view only opens FORWARD. So:

  * the camera body is behind the ToF aperture plane
      -> it CANNOT enter either ToF cone, at ANY mounting height.
         Constraint A stops existing. You are free to pick the height.

  * the ToF boards are behind the lens tip plane
      -> they CANNOT enter the camera's 119.58 deg view.
         Constraint B stops existing too.

Both interference problems vanish at once. This is the right answer, and it is
right for a structural reason, not a numerical one - no tolerance to blow.
""")

print("-" * 74)
print("SO HOW HIGH? the only remaining limits")
print("-" * 74)
CAM_V, TOF_V = 63.12, 45.0
margin = (CAM_V - TOF_V) / 2
print(f"margin above/below the ToF band inside the frame: {margin:.2f} deg\n")
print(f"{'height':>8} | {'ToF fully in frame beyond':>26} | {'occlusion at 0.5 m':>19}")
print("-" * 62)
for h in (20, 30, 40, 50, 80):
    dmin = (h / 1000.0) / math.tan(math.radians(margin))
    occ = h * 0.100 / 0.5
    print(f"{h:5d} mm | {dmin:23.2f} m | {occ:16.1f} mm")
print(f"""
  Both are mild. 30-40 mm is comfortable: everything past ~25 cm is fully
  covered, and the occlusion band is under a centimetre.

  RECOMMENDATION: h = 30 mm along U.""")
P30 = add(M, scale(U, 30))
print(f"    lens tip target = ({P30[0]:.3f}, {P30[1]:.3f}, {P30[2]:.3f})")

# Are the two ToF apertures actually coplanar normal to the camera axis? If so,
# there is a single well-defined "aperture plane" to mate the lens tip against.
fa, fb = dot(sub(OPT_A, M), N), dot(sub(OPT_B, M), N)
print(f"""
  APERTURE PLANE CHECK - are both ToF apertures at the same forward distance?
    ToF A {fa:+.4f} mm     ToF B {fb:+.4f} mm     spread {abs(fa - fb):.4f} mm
  -> they ARE coplanar to within {abs(fa - fb):.2f} mm, so a single plane normal to
     the camera axis passes through both. Mate the lens tip face to that plane and
     the forward offset is exactly zero, with no coordinates typed.""")
