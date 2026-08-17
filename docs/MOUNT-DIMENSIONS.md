# Mount dimensions — measured hardware

Working sheet for the 3D-printed helmet mount. **Caliper measurements beat every datasheet here**
— we have the parts in hand and the camera has no official spec sheet at all.

Started 2026-07-31.

---

## Camera — HBV-1716WA (OV2710, 140° fisheye)

| Dimension | Value | Source |
|---|---|---|
| Board outline | **38 × 38 mm** | ✅ MEASURED 2026-07-31 (matches both datasheet + reseller drawing) |
| Mounting-hole spacing | ❓ **28 mm or 32 mm** | CONFLICT — sibling datasheet says 28, reseller drawing says 32. **NEEDS CALIPER** |
| Mounting-hole diameter | ❓ ~Ø2 mm claimed | NEEDS CALIPER |
| Depth, board back → lens front | ❓ **17.5 or 25 mm** | CONFLICT — sibling says ~17.5–18, reseller drawing says 25. **NEEDS CALIPER** |
| Lens barrel outer diameter | ❓ | NEEDS CALIPER (drives the mount's bore) |
| PCB thickness | ❓ | NEEDS CALIPER |

**Optical note:** the mount must aim the **lens axis**, not the board centre. Need the lens-centre
offset from the board edges if it is not centred.

## ToF — SATEL-VL53L8CX

| Dimension | Value | Source |
|---|---|---|
| Board outline | **51 × 19 mm** | ✅ MEASURED 2026-07-31 |
| Snap-off satellite section? | ❓ | ST drawing pending / NEEDS INSPECTION |
| PCB thickness | ❓ | NEEDS CALIPER |
| Mounting holes (position + Ø) | ❓ | NEEDS CALIPER |
| **Sensor optical centre, offset from board edges** | ❓ | **NEEDS CALIPER — most important number.** The mount aims the sensor's optical axis, not the board. |
| Sensor package height above PCB | ❓ | NEEDS CALIPER |
| Connector type + height | ❓ | NEEDS CALIPER |

---

## ✅ GEOMETRY LOCKED 2026-07-31

- **ToF left:** 22.5° out to the left + 22.5° down
- **ToF right:** 22.5° out to the right + 22.5° down
- **Camera:** straight ahead (0° horizontal) + **22.5° down**
- **One angle for everything: 22.5°.** Simpler bracket, fewer ways to get it wrong.

Why the camera also sits at 22.5° down (`docs/camera_tof_overlap.png`): it centres the ToF
fan in the camera frame with **symmetric 9.1° margins** top and bottom, so the depth band
occupies the middle 14–86% of the image, away from the frame edges where fisheye distortion
is worst and our calibration is least constrained. At 20° downtilt the bottom margin drops to
6.6° and the ToF band reaches 90% of frame height — closer to the edge, not further from it.
Camera then sees −9.1° (above horizon) to +54.1°.

## Geometry the mount has to hit

From `reference-helmet-camera-sensor-layout` and the calibration:

- **Two ToF sensors, 22.5° off-centre each** (45° apart) = **90° combined, edge-to-edge.**
  NOT 45° off-centre — that leaves a 45° blind hole straight ahead.
- **Both tilted down 22.5°** so the fan reaches below shoulder height up close.
- Compound angle per sensor: **22.5° out + 22.5° down.**
- **Camera measured FOV: H 119.6°, V 63.1°, D 144.0°** (calibrated 2026-07-30, RMS 0.30 px).
  The ToF net (90° H × 45° V) sits comfortably inside the camera's 119.6° × 63.1°.
- **Camera and ToF must be rigidly fixed to each other.** Stage 3 measures the transform between
  them; if they can shift, that calibration silently goes stale. One bracket, not two.

## Open design decision

Maximise **fusion overlap** (ToF fan centred in the camera view, depth on as much of the image as
possible) versus maximise **total coverage** (camera aimed further down to bracket the ToF fan,
extending vision below where ToF reaches). Decide before fixing the angles.
