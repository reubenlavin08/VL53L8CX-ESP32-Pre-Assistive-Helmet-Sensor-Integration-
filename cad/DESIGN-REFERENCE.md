# Design reference — every measured number, for building the pod yourself

All values extracted from ST's official STEP (`J5866.step`) or measured with calipers.
Provenance tagged. This is the sheet to design against.

---

## SATEL-VL53L8 (ToF breakout)  — all [ST-STEP], exact

| Dimension | Value |
|---|---|
| PCB | **51.500 × 19.500 × 1.578 mm** |
| VL53L8CX package | 6.400 × 3.030 × 1.750 mm, optical LGA16 |
| Package position on board | X 4.910–7.940, Y 6.550–12.950 |
| **Sensor centre from the near END** | **6.4 mm** |
| Sensor centre across the width | 9.75 mm (centred) |
| Package height above PCB | **1.750 mm** |
| Detection field of view | **45° × 45°** (65° diagonal) — [DS] DS14161 Table 2 |

**Optical axis is NOT the package centre** — [DS] DS14161 Fig. 28:
- Rx axis sits **1.480 mm** from one end, Tx **4.000 mm** further along
- Optical axis is **1.615 mm** from the long edge → **0.100 mm** off package centre
- AN5939 §4 says explicitly: design apertures to the **optical** centre

### Keep-outs — where the components actually are

| | Value |
|---|---|
| **Headers (deep)** | strip **y 0.08–2.62**, running **x 12.77–51.00**, protruding **10.06 mm** below the PCB |
| Everything else below PCB | solder pads only, max **2.13 mm** |
| Tallest thing above PCB | **8.48 mm** (a header); general top clutter to 2.64 mm |

### Clear strip at each edge before you hit a component
*(82 components on top, 36 underneath — this is what limits any rail or lip)*

| Edge | Clear on TOP | Clear on BOTTOM |
|---|---|---|
| Long edge y=0 | **0.91 mm** | **0.08 mm** ← headers sit on this edge |
| Long edge y=19.5 | **1.85 mm** | **3.10 mm** |
| End x=0 | 4.91 mm | 3.55 mm |
| End x=51.5 | 1.46 mm | 0.50 mm |

**Design consequence:** a retaining lip can only grip the **y=19.5** edge, and at most
~1.5 mm. On the header edge, use a **channel that captures the header rib** instead —
it locates the board better than a lip anyway. Board then slides in along its length.

### Cover glass — only if you put a window in front  [AN5939 Rev 3, OFFICIAL]
- Air gap **< 0.5 mm** without a gasket; **> 0.7 mm requires** one
- Air gap + glass thickness **< 1.5 mm**
- **Two circular apertures, concentric with the OPTICAL centres** — beats one oval slot
- Glass tilt ±5° max; transmittance > 87% at 940 nm
- **Simplest compliant option: no window, open apertures.** That is what the pod does.

---

## HBV-1716WA camera — all [CALIPER], measured 2026-07-31

| Dimension | Value | Note |
|---|---|---|
| PCB | **38.0 × 38.0 mm** | agrees with both sources |
| PCB thickness | **1.69 mm** | |
| Mounting holes | **Ø2.3 mm**, **28.2 mm** pitch | derived: 25.9 inner-edge + 2.3 |
| Depth, PCB back → lens front | **25.9 mm** | cap off (28.5 with cap) |
| Lens barrel outer Ø | **17.1 mm** | ⚠ 3 mm bigger than the usual M12 assumption |
| Barrel height above PCB | 24.21 mm | = depth − PCB thickness |

**No official datasheet exists for this camera** — verified negative. Every published
figure we could find was wrong: hole pitch (32 claimed), depth (17.5 claimed), barrel Ø
(~14 assumed). Trust only the measurements above.

### Calibrated optics — `camera/calibration_720p.npz`
```
MJPG 1280x720, cv2.fisheye, RMS 0.3006 px, 19 views
fx = 669.823  fy = 670.075   cx = 620.953  cy = 335.169
D  = [-0.079359, -0.006644, 0.016116, -0.007523]

MEASURED FOV:  H 119.58°   V 63.12°   D 144.02°   (box claims 140° diagonal)
```
**K is resolution-dependent — always capture at 1280×720 or recalibrate.**

---

## Locked mount geometry

| Part | Yaw | Pitch |
|---|---|---|
| Camera | 0° | **22.5° down** |
| ToF left | **22.0° out** (0.5° toe-in) | 22.5° down |
| ToF right | **22.0° out** (0.5° toe-in) | 22.5° down |

**Baseline between ToF optical axes: 34 mm.**

**Why 22.5° down:** largest downtilt keeping the top ray horizontal. Fan spans 0–45°
below horizontal; floor covered from 1.6 m out; at 2 m a person is seen floor-to-1.6 m.

**Why the camera is also 22.5°:** centres the ToF band in frame with symmetric **9.1°**
margins, keeping depth in the middle 14–86% of the image, away from the distorted edges.
20° is *worse* — bottom margin drops to 6.6°.

**Why 0.5° toe-in:** the two fans meet at 0° angularly, but the sensors are 34 mm apart,
so their inner edge rays are parallel and the 34 mm strip between them is seen by
neither — a blind corridor dead ahead. 0.5° crosses the fans at **1.95 m**, closing it,
for only 1° of overlap. Overlap is kept minimal because an unsynced second VL53L8CX
raises the noise floor. (The sensor has a **SYNC pin**, UM3109 §4.15, if it ever matters.)

**Coverage result:** ToF 90° × 45°, entirely inside the camera's view with 14.8° margin
left/right and 9.1° top/bottom. **Depth covers 53.7% of the frame area**; the rest is
camera-only — seen, but with no measured distance.

---

## Practical constraints for the enclosure

| | |
|---|---|
| Behind each ToF | **10.06 mm** of pin, then room for a DuPont housing — **[TBD], measure one** |
| Camera fixing | M2 into printed pilots; **slot them ±1.5 mm** for hole-pitch tolerance |
| FDM clearance around a PCB | 0.35 mm works |
| Wall | 2.8 mm = 3 perimeters at a 0.4 mm nozzle |
| Lid fixing | M3 **heat-set inserts**, not self-tappers — this gets opened repeatedly |
| Cable | strain relief at the exit, or a tug on the tether lands on the camera's USB connector and moves the optical datum |

---

## SOLIDWORKS notes for building it

**In-context design** — put ST's model in the assembly and build around it:
1. Open `J5866.step` → **Save As .SLDPRT**
2. **New Assembly** → insert it (fixes at origin)
3. **Insert Components → New Part**
4. Sketch on a face of the ST board → **Convert Entities** projects its real outline
   into your sketch → **Offset Entities** 0.35 mm → extrude-cut
5. The pocket now matches the real board by construction, not by transcription

**To read any dimension:** **Evaluate → Measure**, click two faces/edges/vertices.
**To see inside:** **View → Display → Section View**.

**Commands you'll need for this part:** Sketch, Extruded Boss/Base, Extruded Cut,
Shell, Fillet, Reference Geometry → Plane (for the 22.5° angled faces), and
Mate in the assembly.

**For the angled seats:** make a **Reference Plane** at 22.5° to the front face, sketch
on that, and extrude normal to it. That is far cleaner than trying to rotate solids.
