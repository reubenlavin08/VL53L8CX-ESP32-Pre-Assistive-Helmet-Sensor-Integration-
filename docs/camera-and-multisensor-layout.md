# Camera (HBV-1716WA / OV2710) + Multi-Sensor Layout — Research & Design Reference

**Created 2026-06-08.** Canonical reference for Phase 2 (camera) + the multi-sensor
(ToF + ultrasonic + camera) layout. **Always consult this before doing camera or
sensor-placement work.** Numbers here are grounded in datasheets / manufacturer data /
cited research — estimates are marked as such.

---

## 1. Camera hardware (what Reuben bought)

- **Module:** HBV-1716WA — the **"WA" = wide-angle 140°** variant. Maker: HBVCAM /
  Huiber Vision Technology (Shenzhen). Bought 2026-06-08, C$33.99.
- **Sensor:** OmniVision **OV2710**.
- **Interface:** USB 2.0, **UVC** (USB Video Class — standard webcam protocol,
  plug-and-play, no driver). 4-pin, 1 m cable. `cv2.VideoCapture(0)` opens it.
- **Board:** ~38×38 mm, fixed focus (lens manually adjustable), 32 g.

### Datasheets on disk (downloaded 2026-06-08)
- `docs/datasheets/camera/OV2710_CSP3_full_datasheet_v1.1.pdf` — **84-page OmniVision
  sensor datasheet** (PRELIMINARY SPEC v1.1, Nov 2009). Applies 100% to this camera.
- `docs/datasheets/camera/HBVCAM_USB_module_spec_book_sibling.pdf` — vendor's module
  spec-book *format* (sibling model 1319; reference for layout, not this exact part).

---

## 2. OV2710 sensor specs (from the datasheet — firm, apply to our unit)

| Spec | Value |
|---|---|
| Optical format | 1/2.7" CMOS (OmniPixel3-HS) |
| Active array | 1920 × 1080 (2.07 MP) |
| Pixel size | 3.0 × 3.0 µm |
| Image area | 5.856 × 3.276 mm |
| **Shutter** | **Rolling (electronic)** — straight lines skew on fast head turns |
| Max frame rates | 1080p @ 30 fps / 720p @ 60 fps |
| Sensitivity | 3300 mV/lux-sec |
| S/N ratio | 39 dB |
| Dynamic range | 69 dB @ 8× gain |
| Native I/O | DVP (parallel) + MIPI — wrapped by a UVC bridge on this USB board |

Low-light is genuinely good for a 2 MP part. Rolling shutter is the main CV caveat.

---

## 3. ⚠️ Lens variant + Field of View (the trap)

The sensor is identical across the family; **only the lens changes.** HBVCAM does **not**
publish a datasheet for the 140° "WA" lens (it's a reseller lens-swap). The cleanest
public data is HBVCAM's own **lens ladder** for the OV2710:

| Lens (Diagonal) | HFOV | VFOV | Source |
|---|---|---|---|
| 100° (1716 S1.0) | 85° | 58° | hbvcamera.com spec page |
| 130° | 103° | 65° | hbvcamera.com spec page |
| **140° (our WA)** | **≈ 108–110°** | **≈ 66–68°** | **extrapolated from the two above** |

- Trend from vendor data: **HFOV grows ~0.6° per 1° of diagonal; VFOV only ~0.23°.**
  On a 16:9 sensor, going wider mostly buys **horizontal**; vertical stays modest.
- **DO NOT use the 85°/58°/100° numbers as ours** — that's the narrow-lens sibling.
- The "140°" on the listing is the **diagonal**, measured through barrel distortion.
- **The only way to get the true HFOV/VFOV/distortion is a checkerboard calibration.**
  Use `cv2.calibrateCamera` → intrinsics + distortion coeffs. Do this when the cam arrives.

**Working assumption until calibrated: HFOV ≈ 109°, VFOV ≈ 67°.**

---

## 4. UVC mode limits (design-critical for the CV pipeline)

- **1080p @ 30 fps is MJPEG-only** (compressed).
- **YUY2 (uncompressed) tops out at 640×480 @ 30** — no 1080p in raw over USB2 bandwidth.
- ⇒ For full resolution in OpenCV you **must** request MJPG:
  ```python
  cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
  cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
  ```
- Cheap clones sometimes mis-report modes — enumerate the *actual* FOURCCs on first plug-in.

---

## 5. ToF↔ToF mutual interference (researched 2026-06-08, with sources)

**Verdict: real phenomenon for dToF in general, but for the VL53L8CX it's gentle and
self-reporting — not the showstopper to fear.**

- **Multiple dToF sensors DO interfere** — measured in the literature (people build
  time-coding suppression schemes that cut interference noise ≥95%). Not a non-issue
  in the general case.
- **But the L8CX failure mode is benign:** it's a **SPAD histogram dToF**. A second,
  *unsynchronized* sensor's 940 nm pulses arrive at random phase → smear across the
  histogram as an **elevated noise floor**, raising SIGMA / cutting max range / causing
  occasional dropouts in the overlap zone — **NOT a stable phantom obstacle** (unlike
  continuous-wave iToF, which gets genuine wrong-distance errors).
- **It self-reports — but NO dedicated interference flag** (corrected 2026-06-08 from UM3109).
  Interference degrades into **low-confidence `target_status` codes**; closest symptom is
  **status 12 = "target blurred by another."** Only **status 5 = 100% valid** (6/9 = 50%, rest
  <50%) → mask non-5 zones in firmware.
- **First-party fix = the SYNC pin** (corrected 2026-06-08 — I'd doubted it existed; it does).
  Dedicated **SYNC input (ball B1)**, `vl53l8cx_set_external_sync_pin_enable()`, UM3109 §4.15,
  *specifically* for "multiple VL53L8CX devices... emitting 940 nm." Host-trigger the two SYNC
  edges **offset in time** → no simultaneous emission → interference gone regardless of geometry
  (Rev 4+; either ranging mode; autonomous+SYNC = lower power; NOT GPIO1/INT, the data-ready output).
- **Or geometric:** angle the 45° fields **edge-to-edge** (zero hardware; at 4×4 the top/bottom
  overlap is already sub-zone). See full options in `camera-compute-and-fusion-options.md`.
- **At short range (<2 m), return signal is strong → big SNR margin → effect is small.**

---

## 6. ToF sensor geometry & layout design

**Single VL53L8CX = 45° × 45° square FoV (≈ 65° diagonal).** Max range ~400 cm.

### Vertical: the down-tilt fix
- **At 0° (level), it misses everything below shoulder height up close** — at sensor
  height h=1.6 m, it sees nothing below ~1.3 m until ~1 m out, below waist until ~2 m.
- **Tilt the axis down 22.5°** → vertical FoV becomes **0° (top beam level with head)
  to −45° (bottom beam)**. Catches head-level and everything below.

**Trig** (sensor at height h, FoV 0° to −45°, distance d ahead):
```
highest point seen = h
lowest point seen  = h − d·tan(45°) = h − d
floor first seen at  d = h        (floor closer than h is a near-field blind spot)
```
Worked at **h = 1.6 m** (scales linearly — re-do with real temple-mount height):

| Distance ahead | Vertical band seen | Note |
|---|---|---|
| 0.5 m | 1.1–1.6 m | waist-up only |
| 1.0 m | 0.6–1.6 m | down to knee |
| **1.6 m** | **0.0–1.6 m** | **full height, head to floor** |
| 2–4 m | head-to-floor then floor strip out to ~3.9 m | |

A 0.3 m curb is first detected ~1.3 m ahead (good warning while walking forward).

### Horizontal: the two-sensor net (and the correction)
- Each sensor = 45° horizontal (±22.5° about its axis).
- **To sit edge-to-edge (no overlap, no gap), the two axes must be 45° apart →
  each sensor 22.5° OFF-CENTER.** Combined = **90° horizontal**, meeting at dead center.
- ❌ **Do NOT point each 45° off-center (90° apart)** — that opens a **45° blind hole
  straight ahead** (you'd walk face-first into a centered obstacle).
- Edge-to-edge = FoVs only *touch* at center ⇒ negligible overlap ⇒ interference negligible.
- **Each sensor's mount is a compound angle: 22.5° outward + 22.5° down.**

### Combined two-ToF coverage (left/right design)
- **Horizontal: 90°** (−45°…+45°), seamless, no front gap.
- **Vertical: 0° to −45°** (both tilted the same). Head-level down to floor-fan.
- **Nothing above head** → that's the gap the ultrasonics cover.

### Residual gaps (two of them, and we have two ultrasonics)
1. **Overhead** — nothing above head level (doorframes, branches, pullup bars, low ceilings).
2. **Near-field-low** — floor within ~h (1.6 m) + short objects that appear *suddenly* close.

---

## 7. Ultrasonics (HC-SR04) — overhead / near-low alert

Cheap binary "something there" alert (no zones). Good complement. **Caveats:**
- **40 kHz mutual crosstalk** — fire both at once and they interfere with *each other*.
  **Must alternate** (ping L, await echo, then R). Halves overhead refresh.
- **5 V part:** ECHO outputs 5 V; ESP32 is 3.3 V-only → **voltage divider / level-shifter
  on ECHO**. TRIG accepts 3.3 V.
- **Slow:** ~60 ms/ping min → two alternating ≈ 8 Hz. Fine for "duck", useless for fast motion.
- **Narrow (~15° cone) + surface-picky:** reflects away from soft/angled surfaces → can
  miss a tilted obstacle.
- **Placement decision (open):** 2 up / 2 down / **1 up + 1 down** (recommended — both
  failure modes are dangerous, coverage of both beats redundancy on one).

---

## 8. Camera ↔ ToF overlay relationship (Phase 3 fusion)

> **Calibration + fusion mechanics live in `camera-calibration-and-depth-fusion.md`**
> (fisheye/ChArUco recipe, projection math, depth↔pixel fusion SOTA). This section is
> just the FOV-geometry relationship.

Using camera ≈ **109° H × 67° V** (assumed, pre-calibration) and the left/right ToF net
**90° H × 45° V**:

- **ToF fits inside the camera frame** both ways (90<109 H, 45<67 V) — clean overlay,
  every depth zone has a matching pixel region *if aimed right*.
- **Aiming:** the ToF net is tilted down (0° to −45°). To line up, **tilt the camera down
  too** (e.g. centered near −22.5°) so its vertical window brackets the ToF fan. A
  forward-level camera (covering +33.5°…−33.5°) would leave the ToF's −33.5°…−45° band
  below the frame and waste the camera's upper half on a region ToF can't see.
- **Horizontally the camera sees wider than the ToF** (~109° vs 90°) → the camera's
  left/right edges are **CV-only, no depth**. Plan for that (mono CV out there).
- **Design tension:** optimize for **max fusion overlap** (pack ToF inside the camera
  frame) vs **max total coverage** (let ToF/ultrasonics spill beyond the frame). Decide
  per goal before fixing mount angles.

---

## Sources
- OV2710 datasheet (OmniVision, on disk) + [OmniVision OV2710 page](https://www.ovt.com/products/ov2710/)
- HBVCAM lens ladder: [1716 S1.0 100° page](https://www.hbvcamera.com/full-hd-1080p-usb-cameras/hbvcam-1716-2710-s1.0.html), [130° lens page](https://www.hbvcamera.com/2-mega-pixel-usb-cameras/1080p-cmos-micro-camera-module-with-130degree-lens.html)
- [HBV-1716WA listing (140°)](https://www.amazon.com/HBV-1716WA-Industrial-Electrical-Electronic-Components/dp/B0BV8XRPWC)
- Interference: [Multi-laser dToF interference suppression (Optica 2024)](https://opg.optica.org/ao/abstract.cfm?uri=ao-63-12-3349), [SPAD array review (Springer Nano)](https://link.springer.com/article/10.1186/s11671-026-04493-x), [ST Community — VL53L5CX interference](https://community.st.com/t5/imaging-sensors/interference-between-tof-sensors-vl53l5cx/td-p/76049), [Pololu VL53L8CX (45×45, 940 nm, error flag)](https://www.pololu.com/product/3419)
