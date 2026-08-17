#!/usr/bin/env python3
"""
camera_tof_baseline.py - how much does the camera-to-ToF offset actually matter?

The camera and the ToF sensors sit a few cm apart, so they see the world from
slightly different viewpoints. Project a ToF measurement into the camera image
assuming they were co-located and it lands in the WRONG PIXEL - the error grows
as the baseline grows and as the target gets closer. This is parallax.

Stage 3 measures the offset and corrects for it exactly, so a large baseline is
not "wrong" - but a smaller one is more forgiving of any error in that measurement,
which is the real argument for keeping the camera close to the ToF pair.

Uses the MEASURED camera intrinsics from calibration_720p.npz.
"""
import math

FX = 669.823          # px, MEASURED (calibration_720p.txt, RMS 0.30 px)
FY = 670.075
W, H = 1280, 720

print(f"camera: {W}x{H}, fx={FX:.1f} px  (measured, RMS 0.30 px)\n")

print("PARALLAX - how far off a ToF point lands if the offset is IGNORED")
print("(this is what Stage 3's [R|t] exists to correct)\n")
print(f"{'offset':>7} | " + " | ".join(f"{d:>8}" for d in
      ("0.3 m", "0.5 m", "1.0 m", "2.0 m", "4.0 m")))
print("-" * 62)
for off_mm in (10, 20, 30, 40, 60, 80):
    row = []
    for d_m in (0.3, 0.5, 1.0, 2.0, 4.0):
        px = FY * (off_mm / 1000.0) / d_m
        row.append(f"{px:6.0f}px")
    print(f"{off_mm:5d}mm | " + " | ".join(f"{v:>8}" for v in row))

print("\nRESIDUAL ERROR - what is left AFTER Stage 3, if the offset measurement")
print("is itself off by 2 mm (a realistic hand-measurement error):")
for d_m in (0.3, 0.5, 1.0, 2.0, 4.0):
    px = FY * 0.002 / d_m
    print(f"  at {d_m:4.1f} m : {px:5.1f} px"
          f"{'   <- negligible' if px < 3 else '   <- visible'}")

print("\nMOUNT HEIGHT - what the CAMERA sees, tilted 22.5 deg down")
print("(vertical FoV 63.12 deg measured, so it spans -9.06 to +54.06 deg)\n")
CAM_V = 63.12
TILT = 22.5
top, bot = TILT - CAM_V / 2, TILT + CAM_V / 2
print(f"{'height':>7} | {'floor seen from':>16} | {'sees a 1.75 m person fully at':>30}")
print("-" * 62)
for h in (1.40, 1.50, 1.60, 1.70, 1.80):
    d_floor = h / math.tan(math.radians(bot))
    # distance at which the top ray clears 1.75 m
    if top < 0:                       # top ray points above horizontal
        rise = math.tan(math.radians(-top))
        d_head = (1.75 - h) / rise if h < 1.75 else 0.0
    else:
        d_head = float("inf")
    print(f"{h:6.2f}m | {d_floor:13.2f} m | "
          f"{('already' if d_head <= 0 else f'{d_head:.2f} m'):>30}")

print("\nNOTE: every distance scales LINEARLY with mount height, so the shape of")
print("the answer does not change - only where it starts.")
