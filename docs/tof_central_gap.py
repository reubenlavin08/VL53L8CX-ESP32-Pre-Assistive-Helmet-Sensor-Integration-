#!/usr/bin/env python3
"""
tof_central_gap.py - is there a blind corridor straight ahead between the two ToF?

The 22.5 deg layout makes the two 45 deg fans meet edge-to-edge at 0 deg ANGULARLY.
But the sensors are not at the same point - they sit a baseline apart on the pod.
Each one's inner edge ray points straight ahead, parallel to the other's, so the
strip of space between them is seen by NEITHER: a constant-width blind corridor
running straight ahead forever, exactly where an obstacle matters most.

Toeing the sensors IN by a small angle crosses the fans at a finite distance and
closes it. This works out the trade.
"""
import math

SEP = 92.0        # mm between the two ToF optical axes (current: x = +/-46)
FAN = 45.0        # deg, VL53L8CX horizontal field of view
YAW = 22.5        # deg, current outward yaw of each sensor

print(f"Two ToF, {SEP:.0f} mm apart, {FAN:.0f} deg fan each, yawed {YAW:.1f} deg out.\n")

print("WITHOUT TOE-IN")
print(f"  Each inner edge ray points straight ahead (0 deg), and they are parallel.")
print(f"  -> a {SEP:.0f} mm wide BLIND CORRIDOR dead ahead that never closes.")
print(f"     Anything narrower than {SEP:.0f} mm centred ahead - a signpost, a pole,")
print(f"     a table leg - can sit in it undetected at ANY range.\n")

print("WITH TOE-IN (each sensor rotated inward by t)")
print(f"{'toe-in':>7}  {'fans cross at':>14}  {'combined FoV':>13}  {'note'}")
for t in (0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 10.0):
    cross = (SEP / 2.0) / math.tan(math.radians(t))
    cov = 2 * (FAN - t) + 2 * t - 2 * t   # = 2*FAN - 2*t : overlap eats coverage
    cov = 2 * FAN - 2 * t
    note = ""
    if cross > 3000:
        note = "useless - beyond sensor range"
    elif cross > 1500:
        note = "closes too far out"
    elif cross < 400:
        note = "closes very near, but costs coverage"
    else:
        note = "<-- practical range"
    print(f"{t:6.1f}d  {cross:11.0f} mm  {cov:10.1f} deg   {note}")

print("\nALSO WORTH DOING: move the sensors CLOSER TOGETHER.")
print("The corridor width equals the baseline, so halving the baseline halves the")
print("blind width AND halves the distance at which any given toe-in closes it.\n")
print(f"{'baseline':>9}  {'blind width':>12}  {'cross @ 3 deg':>14}  {'cross @ 5 deg':>14}")
for sep in (92.0, 70.0, 55.0, 40.0):
    c3 = (sep / 2) / math.tan(math.radians(3.0))
    c5 = (sep / 2) / math.tan(math.radians(5.0))
    print(f"{sep:8.0f}mm  {sep:9.0f} mm  {c3:11.0f} mm  {c5:11.0f} mm")

print("\nHow close can the sensors physically get?")
print("  Each SATEL board is 19.5 mm wide, mounted vertical, yawed 22.5 deg.")
print("  Projected width = 19.5 * cos(22.5) = %.1f mm, plus seat rim and wall." %
      (19.5 * math.cos(math.radians(22.5))))
print("  The camera sits between them and is 38 mm wide, so the baseline cannot")
print("  go below roughly 38 + 2*(9 + 3) = 62 mm without stacking them vertically.")
