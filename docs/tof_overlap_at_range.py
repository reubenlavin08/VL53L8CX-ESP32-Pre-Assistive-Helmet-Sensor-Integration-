#!/usr/bin/env python3
"""tof_overlap_at_range.py - how much do the two ToF fans actually overlap, in mm?

The angular seam is only half the story. The two sensors are physically a few cm
APART, so even fans that are angularly edge-to-edge do not meet in space - their
inner rays run parallel and leave a strip of blind corridor forever.

Geometry, looking down from above:

    left sensor at x = -b/2, inner ray leaning +alpha across the centreline
    right sensor at x = +b/2, inner ray leaning -alpha

    left inner ray  at range d:   x = -b/2 + d*tan(alpha)
    right inner ray at range d:   x = +b/2 - d*tan(alpha)

    they cross when   d = b / (2*tan(alpha))

  alpha = (fan half-width) - (yaw per sensor)
        = 22.5 - separation/2        for a 45 deg fan

  alpha > 0  -> toe-in, the fans eventually merge
  alpha = 0  -> inner rays PARALLEL, a b-wide blind strip at every range, forever
  alpha < 0  -> they diverge, the hole grows with distance

Run: python docs/tof_overlap_at_range.py
"""
import math

FAN = 45.0
BASELINE = 37.50      # mm between the two optical centres - MEASURED from the STEP.
                      # Re-measure if the layout changed; the answer scales with it.
RANGES = (0.5, 1.0, 2.0, 3.0, 4.0)

print("=" * 78)
print("ToF FAN OVERLAP vs RANGE")
print("=" * 78)
print(f"  fan width {FAN} deg     baseline {BASELINE:.2f} mm between optical centres")
print("  positive = OVERLAP (fans meet), negative = BLIND STRIP dead ahead\n")

print(f"{'separation':>11} {'toe-in':>8} {'fans merge at':>15} | " +
      " | ".join(f"{r:>4.1f} m" for r in RANGES))
print("-" * 78)

for sep in (43.0, 43.5, 44.0, 44.5, 44.75, 45.0, 45.5, 46.0):
    alpha = FAN / 2 - sep / 2          # degrees of toe-in per sensor
    ta = math.tan(math.radians(alpha))
    if alpha > 1e-9:
        merge = BASELINE / (2 * ta) / 1000.0
        mtxt = f"{merge:8.2f} m"
    elif abs(alpha) < 1e-9:
        mtxt = "   never"
    else:
        mtxt = "   never"
    cells = []
    for d in RANGES:
        w = 2 * (d * 1000.0) * ta - BASELINE      # + = overlap mm, - = gap mm
        cells.append(f"{w:+7.1f}")
    star = "  <-- yours" if abs(sep - 44.75) < 0.01 else ""
    print(f"{sep:9.2f}° {alpha:+7.3f}° {mtxt:>15} | " + " | ".join(cells) + star)

print("\n" + "-" * 78)
print("YOUR CASE: 44.75 deg separation")
print("-" * 78)
alpha = FAN / 2 - 44.75 / 2
ta = math.tan(math.radians(alpha))
merge = BASELINE / (2 * ta)
print(f"""  toe-in per sensor      {alpha:+.3f} deg
  angular overlap        {FAN - 44.75:.2f} deg
  fans actually merge at {merge/1000:.2f} m

  AT 4 m:  {abs(2*4000*ta - BASELINE):.1f} mm of BLIND STRIP dead ahead - not overlap.

  The angular overlap is real but tiny, and it takes {merge/1000:.1f} m for the two
  inner rays to close the {BASELINE:.1f} mm head start the baseline gives them.
  Everything nearer than that has a gap, narrowing with distance.""")

print("\n" + "-" * 78)
print("THE POINT")
print("-" * 78)
print(f"""  At EXACTLY {FAN:.0f} deg separation the inner rays are parallel: a {BASELINE:.1f} mm blind
  strip at 1 m, at 4 m, at any range. Angularly perfect, spatially never closing.

  So a little toe-in is worth having - not for angular coverage, but to close the
  physical corridor the baseline creates. The question is only where you want it
  closed, and 'nearer than the sensor's useful range' is a reasonable answer.

  Is a {BASELINE:.0f} mm strip at 4 m worth worrying about? It subtends
  {math.degrees(math.atan(BASELINE/4000)):.2f} deg - about {math.degrees(math.atan(BASELINE/4000))*670/57.3:.1f} camera pixels. An obstacle
  worth avoiding at 4 m is wider than that, so it lands in one fan or the other
  regardless. This matters much more at 0.5 m, where the same strip is a far
  larger share of what is in front of you.""")
