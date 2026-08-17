#!/usr/bin/env python3
"""camera_height_offset.py - does it matter how far ABOVE the ToF pair the camera sits?

Short answer: parallax itself is fully corrected by the Stage 3 extrinsics, so the
offset is not an error term. What a vertical offset actually costs you is:

  1. FRAME EXIT   - close up, the ToF fan shifts in the image and part of it can
                    slide off the top/bottom edge, so that depth has no pixels.
  2. OCCLUSION    - the camera and the ToF see different sides of a near object;
                    no calibration can fix geometry neither sensor observed.
  3. RESIDUAL     - whatever error is left after Stage 3, driven by how accurately
                    the offset was MEASURED, not by how big it is.

Run: python docs/camera_height_offset.py
"""
import math

FY = 670.075          # px, MEASURED calibration_720p.txt (RMS 0.30 px)
H_PX, V_PX = 1280, 720
CAM_V = 63.12         # deg, MEASURED
TOF_V = 45.0          # deg, OFFICIAL DS14161
PITCH = 22.5          # both pitched the same

cam_t, cam_b = PITCH - CAM_V / 2, PITCH + CAM_V / 2
tof_t, tof_b = PITCH - TOF_V / 2, PITCH + TOF_V / 2
margin = min(tof_t - cam_t, cam_b - tof_b)

print("=" * 70)
print("CAMERA HEIGHT ABOVE THE ToF PAIR - does it hurt?")
print("=" * 70)
print(f"\ncamera vertical view : {cam_t:+.2f} .. {cam_b:+.2f} deg  (63.12 deg, MEASURED)")
print(f"ToF vertical view    : {tof_t:+.2f} .. {tof_b:+.2f} deg  (45 deg, DS14161)")
print(f"spare margin above and below the ToF fan: {margin:.2f} deg each side")

print("\n" + "-" * 70)
print("1. FRAME EXIT - how close can an object get before ToF zones fall")
print("   outside the image? (the offset tilts the ToF fan by atan(h/d))")
print("-" * 70)
print(f"{'offset':>8} | {'closest usable range':>22}")
for h_mm in (0, 10, 20, 30, 40, 50, 80):
    if h_mm == 0:
        print(f"{h_mm:6d}mm | {'no limit':>22}")
        continue
    d = (h_mm / 1000.0) / math.tan(math.radians(margin))
    print(f"{h_mm:6d}mm | {d:19.2f} m")
print(f"\n  Beyond that distance the whole ToF fan still lands inside the frame.")
print(f"  This is the ONLY hard geometric penalty, and it is small.")

print("\n" + "-" * 70)
print("2. RAW PARALLAX - pixel shift if the offset were IGNORED")
print("   (Stage 3 removes this entirely; shown so the scale is clear)")
print("-" * 70)
print(f"{'offset':>8} | " + " | ".join(f"{d:>7}" for d in
      ("0.3 m", "0.5 m", "1.0 m", "2.0 m", "4.0 m")))
print("-" * 62)
for h_mm in (10, 20, 30, 40, 50, 80):
    row = [f"{FY * (h_mm/1000.0) / d:5.0f}px" for d in (0.3, 0.5, 1.0, 2.0, 4.0)]
    print(f"{h_mm:6d}mm | " + " | ".join(f"{v:>7}" for v in row))

print("\n" + "-" * 70)
print("3. RESIDUAL AFTER CALIBRATION - what actually limits accuracy")
print("   assumes the offset is measured to +/-2 mm (realistic by hand)")
print("-" * 70)
for d in (0.3, 0.5, 1.0, 2.0, 4.0):
    px = FY * 0.002 / d
    print(f"  at {d:4.1f} m : {px:5.1f} px"
          f"{'   negligible' if px < 3 else '   visible'}")
print("\n  NOTE this does NOT depend on how big the offset is - only on how well")
print("  it was measured. A 50 mm offset measured to 2 mm is exactly as accurate")
print("  as a 10 mm offset measured to 2 mm. That is the key point.")

print("\n" + "-" * 70)
print("4. OCCLUSION - the one thing calibration cannot fix")
print("-" * 70)
print("  With a vertical offset the camera looks slightly more DOWN-ON an object")
print("  than the ToF does. Surfaces visible to one and hidden from the other")
print("  cannot be fused. The size of that band, for a flat vertical face:")
print(f"\n{'offset':>8} | " + " | ".join(f"{d:>8}" for d in ("0.3 m", "0.5 m", "1.0 m")))
print("-" * 44)
for h_mm in (10, 30, 50, 80):
    row = []
    for d in (0.3, 0.5, 1.0):
        # depth of surface hidden behind a 100 mm deep object
        band = h_mm * 0.100 / d
        row.append(f"{band:5.1f}mm")
    print(f"{h_mm:6d}mm | " + " | ".join(f"{v:>8}" for v in row))
print("\n  (band of a 100 mm deep object's top face seen by one sensor only)")

print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
print("""
  3-5 cm above the ToF pair is FINE. Specifically:

  - parallax is not an error, it is a known constant that Stage 3 measures once
    and removes exactly; its size does not degrade accuracy
  - at 50 mm the whole ToF fan still lands in frame beyond 0.31 m, which is
    already closer than the sensor's useful working range for obstacle warning
  - occlusion at 50 mm costs a ~5-17 mm band on near objects - irrelevant for
    "is something in the way", relevant only for precise surface reconstruction

  What DOES matter, in order:
    1. RIGIDITY. The camera and the ToF must not move relative to each other
       after calibration. A 1 mm shift is worth more error than a 50 mm offset.
    2. MEASURING the offset well, or better, solving it in the Stage 3 calibration
       rather than trusting a ruler.
    3. Keeping both pitched the SAME 22.5 deg, which centres the ToF band in the
       frame with symmetric margins.

  Put the camera where the mechanics are cleanest and the mount is stiffest.
""")
