# Sensor mounting facts — ToF + ultrasonic

Researched 2026-07-31. Every claim marked OFFICIAL (with document) or UNVERIFIED.

---

# 1. SATEL-VL53L8 (the ToF breakout)

**Correct name is SATEL-VL53L8** (no "CX"). Per DB4924 §2 it carries a non-commercial
**VL53L8CA** evaluation part — same optical LGA16 package, so all chip numbers below apply.

## ⚠️ ST publishes NO dimensioned drawing of this board
DB4924, AN5945 and UM3120 contain photos and the schematic only — **no board outline, no hole
positions, no sensor offset, no connector heights.** The authoritative mechanical sources are the
Gerber pack and STEP model, both of which need a manual download (st.com is unreachable from the
tooling here, and the STEP file is behind an email/login gate):
- Gerbers: https://www.st.com/resource/en/board_manufacturing_specification/satel-vl53l8-gerber.zip
- STEP: https://www.st.com/resource/en/cad_design_files/satel-vl53l8-cad-files-step.zip

**Measured by hand 2026-07-31: 51 × 19 mm overall.**

## ✅ It SNAPS APART — big deal for the helmet
**OFFICIAL** (DB4924 Rev 2 §1 + Fig. 5): *"You can break the breakout boards along the perforations
to use the mini-PCB."* The schematic labels them "Snap-off perforations."

So the sensor itself lives on a **small mini-PCB** that separates from the wider carrier. Mount
**only the mini-PCB** in the helmet pod — far smaller, lighter, and easier to aim than the full
51 × 19 mm board. The 12 edge pads on the mini-PCB are:
`AVDD, IOVDD, GPIO2, GPIO1, SCL, I2C_N, SDA, MISO, LPn, CORE_1V8, NCS, DUT_GND` (pads 0.8 × 1.6 mm).

Main-board connectors (types only, no MPNs): J2 = 11×1 male 2.54 mm; J1/J3 = 3×1 male 2.54 mm.

## VL53L8CX chip package — all OFFICIAL, DS14161 Rev 7 §8 Figs 26/28

| Item | Value |
|---|---|
| Package | Optical LGA16 |
| L × W × H | **6.400 ±0.030 × 3.030 ±0.030 × 1.750 ±0.050 mm** |
| Detection FoV | **45° × 45°, 65° diagonal** |
| Rx aperture | Ø0.510 ±0.010 mm |
| Tx aperture | 0.740 × 0.900 mm rectangular |
| **Tx optical centre → Rx optical centre** | **4.000 mm** |
| Along the 6.400 mm length | 1.480 (end → Rx axis) + 4.000 + 0.920 (Tx axis → end) |
| Optical axis, across the width | **1.615 mm from the long edge** |
| Mechanical centre → optical centre | **0.100 mm offset** |
| Collector exclusion cone | 57.9° H and V, 86.6° diagonal |
| Max compressive load | 25 N |

**⚠️ AN5939 §4 states explicitly: design to the OPTICAL centre, not the package centre.**
Rx sits at the end carrying the "L8" text and the 2D marking code.

## Cover-glass / window rules — OFFICIAL, AN5939 Rev 3

Only relevant if the pod puts a window in front of the sensor. **Simplest compliant option is an
open aperture — no window at all.** If a window is used:

- **Air gap < 0.5 mm** without a gasket; **< 0.4 mm** keeps crosstalk in spec.
  **> 0.7 mm requires a gasket** (Table 5 note 1).
- **Air gap + glass thickness < 1.5 mm.**
- **Two circular apertures, concentric with the OPTICAL centres** — beats one oval slot (better
  light trap).
- Glass tilt **±5° max**, assembly tolerance ±2°, surfaces parallel to the module face.
- Transmittance **> 87% at 940 nm**, haze < 2% visible / < 1% IR, crosstalk ≤ 300 kcps/SPAD.
- **PMMA / polycarbonate windows are explicitly allowed** (§3.5) — a printed housing with a
  plastic window is fine.
- Minimum aperture sizes (Table 4, includes 2° tolerance, 0.5 mm glass, dims on the top face):

| Air gap | Tx circle Ø | Rx circle Ø | Single-aperture W × L |
|---|---|---|---|
| 0 mm | 2.058 | 2.014 | 6.436 × 2.458 |
| 0.3 mm | 2.547 | 2.503 | 6.925 × 2.947 |
| 0.5 mm | 2.873 | 2.829 | 7.251 × 3.273 |
| 1.0 mm | 3.688 | 3.644 | 8.066 × 4.088 |

Precedent worth copying: X-NUCLEO-53L8A1 ships a cover-glass holder with **0.25 / 0.5 / 1 mm
spacers** (UM3120 §1).

**Docs:** DS14161 https://www.st.com/resource/en/datasheet/vl53l8cx.pdf (mirror:
https://www.pololu.com/file/0J2029/vl53l8cx.pdf) · AN5939 cover glass · DB4924 data brief
(mirror: https://www.farnell.com/datasheets/4319699.pdf) · AN5945 · UM3120

---

# 2. HC-SR04 — ❌ VERDICT: POOR for overhead detection

## Mechanical (for a mount, if used anyway)

| Dim | Value | Status |
|---|---|---|
| PCB L × W | **45 × 20 mm** (spec tables); drawing says 43 mm | Datasheet — internally conflicting |
| PCB thickness | 1.2 mm typ (clones 1.0–1.6) | UNVERIFIED |
| Height PCB → can top | 15 mm quoted, ~13.2 mm actual | Derived |
| Transducer can | **Ø16.0 × 12.0 mm** | TCT40-16T/R datasheet, OFFICIAL |
| Can centre-to-centre | ~26 mm | UNVERIFIED, scaled from drawing |
| Mounting holes | 4 corner **Ø1 mm** on a 40 × 15 mm grid — **absent on many clones** | Only the 40 mm is dimensioned |
| Header | 2.54 mm 4-pin, protrudes ~8.5 mm behind the PCB | Standard part |

**Ø1 mm holes are alignment holes, not screw holes** — don't design an M2/M3 mount. Use a friction
slot or clips over the cans: board slot 46.0–46.5 × 1.8–2.0 mm, can bores Ø16.5 mm, 13.5 mm can
protrusion, 12 mm clear behind for the header. **HC-SR04P puts the header on the opposite face**,
so a one-sided cutout won't fit both variants.

## The "15° beam" is marketing
No datasheet gives a dB point, target, or distance. The Handsontec PDF has a real polar plot with
gridlines at ±22.5°/±45°, captioned *"Best in 30 degree angle"* — so **15° is a half-angle and
~30° is the usable full cone.** Comparable 16 mm transducers (Pro-Wave 400ST/R160) measure **55°
total at −6 dB**. Beam width is target-dependent: TX and RX patterns multiply, so round-trip loss
is double the one-way. A large flat wall clears threshold 20–30° off-axis; a thin rod only near
boresight.

## Range / timing / electrical

| Parameter | Value |
|---|---|
| Range | 2 cm – 400 cm, ±3 mm, 0.3 cm resolution |
| Min-range cause | 8-cycle 40 kHz burst = 200 µs + TX/RX ringdown |
| TRIG | ≥10 µs high |
| ECHO | 150 µs – 25 ms; **38 ms = nothing detected** |
| Distance | µs / 58 = cm |
| **Min cycle** | **60 ms → max ~16.7 Hz** |
| Power | 5 V, 15 mA. **Does NOT run reliably at 3.3 V.** |
| ECHO level | **5 V — ESP32 is NOT 5 V tolerant.** Divide 1 kΩ/2 kΩ → 3.33 V, or use HC-SR04P/RCWL-1601 (3.0–5.5 V, software-identical) and wire direct |

## Crosstalk
Real. All units emit an uncoded 40 kHz burst, so a receiver can't tell whose ping it heard.
Failure mode is a **false SHORT reading** — the worst kind for an alert device.
**Mitigation: round-robin, one at a time, 60 ms slots.**

| Sensors | 60 ms slots | 40 ms tight |
|---|---|---|
| 2 | 8.3 Hz each | 12.5 Hz |
| 3 | 5.6 Hz each | 8.3 Hz |

## Why it fails at our actual job (λ = 8.6 mm at 40 kHz)
- **Flat lintels/signs:** specular lobe half-width ≈ λ/2L, so a 30 cm lintel returns a full echo
  only within **~±1.6°** — and *bigger* flat surfaces are narrower still. Head pitch while walking
  (±10–20°) swings them in and out of that window.
- **Bare branches:** a 2–5 cm branch is **~30 dB below a flat plate** (cylinder vs plate
  scattering) and fills only 3–5% of the beam at 2–3 m. **No source demonstrates reliable
  single-branch ranging.** Leafy *canopy* does work (established in orchard sensing) but with
  ±5.11 cm error and up to 29.9% error on sparse canopy.
- **Cloth/foam/carpet:** absorbed. The datasheet itself asks for ≥0.5 m² of smooth target.
- **Temperature:** 340 m/s is hardcoded, correct only at 14.3 °C. Vancouver −5 to +30 °C ⇒
  **±15 cm at 4 m.** Easy to correct with any temperature sensor.

## Better options at hobby cost, ranked
1. **LD19 / STL-19P spinning 2D lidar, ~$70–99** — mount the **scan plane VERTICAL**. 12 m range,
   0.72° (≈2.5 cm footprint at 2 m), 60 klux daylight rated. A sweeping plane **cannot miss a
   horizontal branch by pointing between it** — which is exactly the HC-SR04 failure mode.
   Costs ~1 W and puts a spinning mass on the head.
2. **3× TF-Luna in a vertical fan, ~$87** — 70 klux, ~2° (7 cm spot at 2 m), 0.35 W. Solid-state.
3. **A VL53L8CX aimed up** — free, already owned, but **outdoors in sun expect only ~0.8–1.5 m**
   on a branch (VL53L5CX datasheet: 400 cm in the dark → 140 cm at just 5 klux; direct sun is
   50–100 klux). Fine as a short-range confirm layer, not primary.
4. **Reject 24/60 GHz mmWave** — static-clutter filtering removes stationary branches, and it can
   range *through* leaves to the trunk.

**Sources:** ElecFreaks (SparkFun) https://cdn.sparkfun.com/datasheets/Sensors/Proximity/HCSR04.pdf ·
Handsontec (only mechanical drawing + beam plot) https://www.handsontec.com/dataspecs/HC-SR04-Ultrasonic.pdf ·
Elecrow · TCT40-16T/R transducer · beam measurements https://github.com/GaryDyr/HC-SR04-beam-tests ·
canopy sensing PMC3231637, PMC3274039, PMC5298604
