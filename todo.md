# Helmet project — TODO

Living list of work for this project. Append-only during sessions; check items off only after they're done AND verified.

## In progress

- [x] **Rotation in firmware:** `MOUNT_ROTATION_DEG = 270` confirmed working in `main.c`, applied via `rotated_zone()` helper to all three stream functions (DATA/SIGMA/STATUS). Single source of truth at the chip — all downstream consumers see body-frame data automatically.
- [x] **README first-person rewrite.** v9 now in first person; earlier sections were already mostly first-person (only remaining "you/your" are reader-addressed instructional bits, which is correct README style).
- [x] **Embed test rig photos in README.** `rig_wide_full_setup.jpg` + `rig_close_sensor_and_board.jpg` now inline at top of v9 section.
- [x] **"Limitations of this analysis" subsection added to README** with explicit caveats about ambient light, untested surfaces, motion noise, and coverage gaps.
- [ ] **Helmet-mount tilt calibration via wall stare.** Wear the helmet, stand facing a flat wall at known distance, capture N frames. From the per-row mean distance, solve for actual sensor pitch angle. Then bake that into the slant-compensation math. Better than eyeballing the mount angle.

## Queued (in order)

1. [ ] **Per-row slant compensation in firmware.**
   - Assumption: sensor at 195 cm helmet height, mounted level.
   - For each row r of the rotated 8×8 grid, precompute the zone's elevation angle below horizontal.
   - Convert reported slant distance to forward distance: `forward = slant × cos(zone_elevation)`.
   - Alert on forward distance, not slant. Fixes the "chair at 50 cm forward reads 130 cm slant and never triggers" problem.
2. [ ] **Multi-target per zone (`VL53L8CX_NB_TARGET_PER_ZONE = 2`).**
   - Enables sensor to detect both the pullup bar AND the wall behind it as separate targets per zone.
   - Combined with `TARGET_ORDER = CLOSEST`, the bar wins.
   - ~40 line firmware change (loop through all targets per zone in stream functions, take closest valid).
3. [ ] **Dynamic wearable testing once 1+2 are in.**
   - Walk hallways, doorways, around furniture.
   - Specifically test: pullup bar / overhead doorframe, chair near body, dark fabric, glass at angle, lighting changes (indoor → outdoor).
   - Decide based on real use whether a 2nd sensor is needed.

## Future ideas (no commitment, log only)

- [ ] **iPhone as IMU stand-in** (until real IMU breakout arrives). Stream IMU over WiFi UDP via SensorLog/Phyphox. Trade-offs: bulk, battery, latency. Reuben asked about hardwired UART — see "Hardware notes" below.
- [ ] **Adaptive geometric calibration once IMU is installed.** Use live pitch reading to update each zone's elevation angle in real time instead of assuming level head. Eliminates the fixed-mount-angle approximation.
- [ ] **Layered alert thresholds.** 120 cm = slow chirp, 60 cm = fast chirp, 30 cm = solid tone. Much higher information density for a blind user than binary on/off.
- [ ] **Min-zone-count for alert trigger.** Require ≥2 adjacent zones below threshold to reduce single-pixel false alerts (e.g. a thin reflective speck).
- [ ] **Second VL53L8CX sensor.** Adds peripheral coverage / floor detection. Risks: VCSEL-to-VCSEL optical interference (mitigate with non-overlapping aim OR external-sync pin), I²C address conflict (use SPI bus instead — cleaner with multiple sensors, no address conflict, ~10 MHz vs 400 kHz). Defer until single-sensor dynamic testing reveals where coverage gaps actually matter.
- [ ] **CV-adaptive thresholds (Phase 2).** Different beep pattern for person vs wall vs static obstacle once camera + CV is integrated.

## Hardware notes / open questions

- **iPhone over Lightning/USB-C → ESP32 UART (hardwired).** Not practical without an Apple MFi-licensed authentication chip on the ESP side. iPhones require MFi handshake for arbitrary serial I/O over Lightning. USB-C iPhones (15+) are slightly more open but still mostly locked down for serial. Realistic path is WiFi UDP, not UART.
- **iPhone ↔ PC photo transfer works without MFi** because it uses USB PTP/MTP (Picture Transfer Protocol / Media Transfer Protocol), which are USB standard device classes — any computer's USB stack supports them natively. MFi is only required for Apple's proprietary iAP/iAP2 protocol used by audio accessories and custom Made-for-iPhone hardware that wants arbitrary serial I/O. So the MFi chip is on the *accessory* side (e.g. a CarPlay head unit), not the computer.

## Verified from ST UM3109 (downloaded 2026-05-25)

### §4.9 Target order
- "The VL53L8CX can measure several targets per zone. Thanks to the histogram processing, the host is able to choose the order of reported targets."
- Two options: **CLOSEST** (closest first) or **STRONGEST** (strongest first).
- **Default = STRONGEST.** Our firmware explicitly overrides to CLOSEST for obstacle avoidance — without that override the sensor would report the wall instead of a closer thin object.
- Target order works at NB=1 (selects which single target gets reported) AND at NB>1 (orders the list).

### §4.10 Multiple targets per zone
- VL53L8CX can report up to 4 targets per zone.
- **Minimum distance between two targets to be DETECTED as separate = 600 mm.** Two objects closer than 60 cm apart get merged into one weighted peak regardless of NB_TARGET_PER_ZONE.
- Configured via `VL53L8CX_NB_TARGET_PER_ZONE` macro in `platform.h`, value 1–4.
- Default = 1 (one target per zone).
- Higher NB → more RAM per frame on the ESP side.

### Implication for the pullup-bar problem
- Bar in doorway with **open space behind it** (gap > 60 cm) → NB=2 + CLOSEST will resolve the bar separately. Worth trying.
- Bar with **wall close behind it** (gap < 60 cm) → multi-target won't help, sensor fundamentally can't separate them. Need a different approach (different mount angle, second sensor aimed slightly upward, etc.).

## Recurring bugs / pitfalls (don't repeat)

- ESP I²C sensor init fails ~20% of the time on warm reboot. Mitigation: host-side 3× retry in `run_one_test.ps1`.
- OTA can leave one partition in a corrupted state after many cycles. Fix: USB-flash via `idf.py -p COM10 flash` rewrites both slots cleanly.
- PowerShell em-dashes (`—`) in `.ps1` files trip Windows PS 5.1 parser. Stick to ASCII.
- Reader-thread Qt signal queue accumulation makes the visualizer lag after thousands of frames. Fixed: GUI polls latest frame at 30 Hz via QTimer, drops intermediate.

## Done

- [x] Stream `range_sigma_mm` from firmware (v8)
- [x] Build measurement script with per-zone stdev (v8)
- [x] WiFi streaming (v7)
- [x] OTA reflashing via WiFi (v7)
- [x] Buzzer obstacle alert with distance-proportional beep rate (v8)
- [x] Module 5 sensor tuning section (course side, separate)
- [x] 17-config × 3-distance black foam sweep with retry logic (v9)
- [x] Data analysis pipeline (`analyze.py` → 8 plots) (v9)
- [x] Multi-client TCP fan-out (visualizer + measure.py simultaneously) (v9)
- [x] `STATUS:` line streaming for raw per-zone status codes (v9)
- [x] Compile-time `MOUNT_ROTATION_DEG` firmware-side rotation
- [x] Visualizer frame-rate decoupling (fixes lag accumulation)
