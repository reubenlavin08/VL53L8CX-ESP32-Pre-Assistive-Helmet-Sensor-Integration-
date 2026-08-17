#!/usr/bin/env python3
"""
aperture_calculator.py - how big must each sensor's window be?

A sensor sitting BEHIND a wall sees through a cone. The deeper it sits, the wider
the hole has to be, or the wall clips the outer field. This works out the minimum
opening at the outer surface for any recess depth.

    required opening = sensor's own aperture + 2 * depth * tan(half-FoV)

Angles used:
  ToF    45 x 45 deg          OFFICIAL, VL53L8CX DS14161 Table 2
  camera 119.58 x 63.12 deg   MEASURED, calibration_720p.txt (RMS 0.30 px)

Run: python docs/aperture_calculator.py
"""
import math

TOL = 1.0        # extra mm all round for print tolerance and mounting slop

print("=" * 66)
print("ToF (VL53L8CX)  -  45 x 45 deg, square")
print("=" * 66)
print("The sensor's own emitter/receiver window is ~1 mm across, and the package")
print("top is the aperture plane. 'Depth' = how far the package top sits behind")
print("the outer surface of the wall.\n")
print(f"{'depth':>7} | {'min opening':>12} | {'with 1 mm tol':>14}")
print("-" * 40)
for d in (1.6, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
    need = 1.0 + 2 * d * math.tan(math.radians(22.5))
    print(f"{d:6.1f}mm | {need:9.2f} mm | {need + 2*TOL:11.2f} mm")

print("\nST AN5939 also sets MINIMUM apertures if a WINDOW is fitted (Table 4):")
print("  air gap 0 mm    Tx circle 2.06 dia, Rx 2.01, or one slot 6.44 x 2.46")
print("  air gap 0.5 mm  Tx circle 2.87 dia, Rx 2.83, or one slot 7.25 x 3.27")
print("  -> with NO window (open hole) these do not apply; the cone rule above does.")

print("\n" + "=" * 66)
print("CAMERA (HBV-1716WA)  -  119.58 x 63.12 deg, MEASURED")
print("=" * 66)
print("The lens barrel is 17.1 mm dia and stands 24.21 mm above the PCB.")
print("If the lens TIP sits at or proud of the outer surface, the wall cannot")
print("clip anything and no aperture calculation is needed - only a 17.1 mm")
print("clearance bore for the barrel itself.\n")
print("If the lens tip is RECESSED behind the surface, the opening must be:\n")
print(f"{'recess':>7} | {'width needed':>13} | {'height needed':>14}")
print("-" * 42)
for d in (0.0, 1.0, 2.0, 3.0, 5.0):
    w = 17.1 + 2 * d * math.tan(math.radians(119.58 / 2))
    h = 17.1 + 2 * d * math.tan(math.radians(63.12 / 2))
    print(f"{d:6.1f}mm | {w:10.2f} mm | {h:11.2f} mm")
print("\nNote how fast the width grows - at 119.6 deg the half-angle is 59.8 deg,")
print("so tan is 1.72 and every 1 mm of recess costs 3.4 mm of opening width.")
print("KEEP THE LENS PROUD OF THE SURFACE. It is the only sane option.")

print("\n" + "=" * 66)
print("HOW TO CHECK YOUR OWN MODEL IN SOLIDWORKS")
print("=" * 66)
print("""
1. SECTION VIEW through the sensor's optical axis
     View > Display > Section View, pick the plane through the sensor centre.

2. MEASURE the recess depth
     Evaluate > Measure, click the sensor's front face, then the wall's outer
     face. That distance is 'depth' in the table above.

3. MEASURE the opening at the OUTER surface
     Measure across the hole on the outside face - not the inside. A straight
     bore is narrowest where it starts, so the outer edge is what clips.

4. COMPARE against the table.
     Opening smaller than 'min opening' = the wall is clipping the field.

5. If it is tight, FLARE the hole rather than just enlarging it - a countersink
   or draft that follows the cone keeps the wall thick where it can be.
""")
