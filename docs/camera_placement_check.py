#!/usr/bin/env python3
"""camera_placement_check.py - where can the camera physically go?

Two sensors sharing a pod can blind each other. This checks BOTH directions for any
camera position you propose:

  A. does the CAMERA BODY stick into a ToF's 45 deg cone?
  B. do the ToF BOARDS stick into the camera's 119.58 x 63.12 deg view?

Frame: pod-local, with BOTH sensors already pitched 22.5 deg down, so this axis
system is tilted with them. That removes the pitch from the maths entirely -
everything below is measured relative to the sensors' own line of sight.

  X = right     Y = up (perpendicular to the sight line)     Z = forward

Origin = the mid-point between the two ToF apertures.

Run: python docs/camera_placement_check.py
"""
import math

# --- measured hardware, cad/DESIGN-REFERENCE.md ----------------------------
CAM_PCB = 38.00          # [CALIPER] square
CAM_BARREL_D = 17.10     # [CALIPER]
CAM_BARREL_H = 24.21     # [CALIPER] lens tip above the PCB front face
CAM_H_FOV = 119.58       # [MEASURED] calibration_720p.txt, RMS 0.30 px
CAM_V_FOV = 63.12        # [MEASURED]

TOF_FOV = 45.0           # [DS] DS14161 Table 2
TOF_BASELINE = 37.50     # [MEASURED from your STEP]
TOF_YAW = 22.00          # each, out from the bisector
TOF_PCB_L, TOF_PCB_W = 51.500, 19.500     # [ST-STEP]

TT = math.tan(math.radians(TOF_FOV / 2))          # 0.41421
CT_H = math.tan(math.radians(CAM_H_FOV / 2))      # 1.71586
CT_V = math.tan(math.radians(CAM_V_FOV / 2))      # 0.61374

print("=" * 74)
print("CAMERA PLACEMENT CHECK")
print("=" * 74)
print(f"""
Frame is tilted WITH the sensors (both already 22.5 deg down), so:
  Y = how far the camera sits ABOVE the ToF sight line
  Z = how far the camera sits FORWARD of the ToF aperture plane
""")

print("-" * 74)
print("A. DOES THE CAMERA BLOCK THE ToF?")
print("-" * 74)
print(f"""Each ToF opens 22.5 deg upward from its own axis. At Z mm forward, the top
of that cone is at Y = {TT:.5f} x Z. Anything below that line is IN THE WAY.

The camera's worst point is its BOTTOM edge - the PCB is {CAM_PCB:.0f} mm square, so the
bottom sits {CAM_PCB/2:.0f} mm below the lens axis - at whatever Z the lens tip reaches.

  RULE:  lens axis height  >  {CAM_PCB/2:.0f} + {TT:.4f} x (forward protrusion)
""")
print(f"{'camera forward of ToF':>22} | {'min lens-axis height':>21}")
print("-" * 48)
for f in (0, 10, 20, 30, 40, 50):
    need = CAM_PCB / 2 + TT * f
    print(f"{f:19d} mm | {need:18.1f} mm")

print(f"""
  Read it the other way: for a given height, the camera may protrude forward by
  at most  (height - {CAM_PCB/2:.0f}) / {TT:.4f}  =  {1/TT:.3f} x (height - {CAM_PCB/2:.0f}).
""")

print("-" * 74)
print("B. DO THE ToF BOARDS BLOCK THE CAMERA?")
print("-" * 74)
print(f"""This is the harder constraint, and it is the one people get wrong.

The camera is {CAM_H_FOV:.2f} deg wide. Half-angle {CAM_H_FOV/2:.2f} deg, tan = {CT_H:.4f}.
So anything sitting Z mm FORWARD of the lens tip must be more than
{CT_H:.4f} x Z sideways, or it is in shot. That is brutally demanding.

  Vertically it is gentler: half-angle {CAM_V_FOV/2:.2f} deg, tan = {CT_V:.4f}.
""")
print(f"{'mm forward of lens tip':>22} | {'must be sideways by':>20} | {'or below by':>12}")
print("-" * 60)
for f in (5, 10, 20, 30, 50):
    print(f"{f:19d} mm | {CT_H*f:17.1f} mm | {CT_V*f:9.1f} mm")

print(f"""
  THE CLEAN ANSWER: put the lens tip FORWARD of everything else. Nothing behind
  the lens tip plane can ever enter the view, because the field only opens
  forward. One rule, no arithmetic, impossible to get wrong.
""")

print("-" * 74)
print("SO: IS IT FINE FOR THE LENS TO SIT IN FRONT OF THE ToF?")
print("-" * 74)
print(f"""  YES - and it is actively the RIGHT choice, for constraint B.

  If the lens sat BEHIND the ToF boards, those boards would be forward of the
  lens tip and inside a {CAM_H_FOV:.1f} deg field. A board {TOF_PCB_L:.1f} mm long,
  10 mm forward of the lens, would need to be {CT_H*10:.1f} mm off to the side to stay
  out of shot. It will not be. You would get the board in the corners of every frame.

  The cost of moving forward is constraint A: the camera's bottom edge starts
  reaching into the ToF cones. That is what the table above bounds.

  Both are satisfied at the same time by stacking the camera ABOVE the ToF pair
  with the lens tip proud. Worked example:
""")
for h, f in ((25, 0), (30, 20), (35, 35), (40, 50)):
    okA = h >= CAM_PCB / 2 + TT * f
    print(f"    lens axis {h:3d} mm up, {f:3d} mm forward -> "
          f"ToF cones {'CLEAR' if okA else '*** BLOCKED ***'}"
          f"   (needs >= {CAM_PCB/2 + TT*f:.1f} mm up)")

print("\n" + "-" * 74)
print("HOW MUCH DOES THE FORWARD OFFSET MATTER FOR THE FUSION?")
print("-" * 74)
print("""  Almost not at all. The forward offset is just the Z component of the same
  translation vector t that Stage 3 already solves for. Like the height, it is a
  fixed constant, measured once, removed exactly.

  It is NOT a source of error. It is a source of OCCLUSION - the camera peeks
  slightly further around a near object than the ToF does. At these distances
  that band is a few mm. Irrelevant for "is something in the way".

  What matters is the same thing as always: RIGIDITY. Whatever offset you build,
  it must not change after you calibrate.""")

print("\n" + "-" * 74)
print("HOW TO MEASURE WHERE THE LENS ACTUALLY FALLS, IN SOLIDWORKS")
print("-" * 74)
print(f"""  The lens tip is {CAM_BARREL_H:.2f} mm in front of the camera PCB's front face
  ({CAM_BARREL_H:.2f} = {CAM_BARREL_H + 1.69:.2f} mm total depth minus the {1.69} mm board). Barrel is
  {CAM_BARREL_D} mm diameter.

  1. Evaluate > Measure
  2. Click the LENS TIP FACE (the flat front annulus of the barrel)
  3. Ctrl-click a ToF chip's TOP FACE
  4. Open the Delta X/Y/Z readout in the Measure dialog

  Delta along the sight line = forward protrusion (Z above)
  Delta perpendicular       = height offset (Y above)

  Feed those two numbers back into the tables here.""")
