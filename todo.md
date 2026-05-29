# Helmet project — TODO

Living list of work for this project. Append-only during sessions; check items off only after they're done AND verified.

## In progress (no active items — see Queued)

## Recently shipped (2026-05-25 → 2026-05-28)

- [x] **Rotation in firmware:** `MOUNT_ROTATION_DEG = 270` confirmed working in `main.c`, applied via `rotated_zone()` helper to all three stream functions (DATA/SIGMA/STATUS). Single source of truth at the chip — all downstream consumers see body-frame data automatically.
- [x] **README first-person rewrite + v9 photos + Limitations subsection.**
- [x] **Helmet-mount tilt calibration via wall stare** (2026-05-25). Pitch 13° → 20° after physical mount adjustment. `visualizer/calibrate_tilt.py` + raw captures in `visualizer/raw_frames/wall-tilt-calib-h185cm-d81cm_*.csv`.
- [x] **Per-row slant compensation in firmware** (shipped). `MOUNT_PITCH_DEG = 20.0f`, `compute_row_cos_table()` runs at boot, nearest-distance loop multiplies slant by `g_row_cos[row]` before comparing to per-row thresholds. Raw `DATA:` stream is unaffected (still slant) so analysis tools see what the sensor sees.
- [x] **Per-row alert thresholds** in firmware (60/60/80/95 cm at 4×4 — innovation, not from literature).
- [x] **Urgency-ratio buzzer** — beep rate scales with `forward / row_threshold` (ratio²) instead of absolute distance. Lower-row obstacles beep faster at the same forward distance because their FoV exits sooner.
- [x] **30 Hz ranging at 4×4** (bumped from 20 Hz after wearable-latency research; latency dominates per-zone noise by 10–40× for a moving user — see `docs/research-optimal-config.md`).
- [x] **OTA bug RCA closed** (2026-05-26): verbose UART logging throttling OTA to 15 KB/s. Fixed by reverting to INFO log level. Now 164 KB/s.
- [x] **Phase 2A/B/C/D research synthesis** (`docs/research-optimal-config.md`): ST docs deep-dive, academic literature review, market survey, with source-verification appendix retracting fabricated AN5912/AN6066/ETH-median-filter citations.
- [x] **Below-chest coverage research** — three options documented (move sensor lower / two-sensor stack / multi-row ultrasonic). Hybrid path = preferred.
- [x] **Haptic motors bench-tested** (2026-05-26 single motor, 2026-05-28 all 3). Driver: 2N3904 NPN low-side switch + 1 kΩ base resistor per motor. GPIO 7/15/16, LEDC ch 1/2/3 timer 1 @ 1 kHz.
- [x] **Haptic motor physical-position mapping VERIFIED** (2026-05-28) via single-pin OTA pulse test (`HAPTIC_ID_MODE`):
  - **GPIO 7  = CENTER (forehead)**
  - **GPIO 15 = RIGHT temple**
  - **GPIO 16 = LEFT temple**
  - Aliases `HAPTIC_GPIO_CENTER` / `_RIGHT` / `_LEFT` in `main.c`.
- [x] **Safety GPIO boot config** — all 3 motor GPIOs forced OUTPUT-LOW with pulldown at the very start of `app_main` regardless of `HAPTIC_TEST` state. Prevents stuck-on motor after warm reboot.
- [x] **Directional-haptics research with primary sources** (2026-05-28) — full citations in `docs/research-sources/directional-haptics-mapping.md`. Verifies that concurrent multi-motor firing is precedented (GuideTouch), squared PWM curve is supported for alerting (Stevens' law), funneling isn't an issue at our motor separation (Kaul 2020), and dominance weighting is warranted (Zegarra Flores 70% finding).
- [x] **Directional column→motor haptic drive IMPLEMENTED** (2026-05-28). `ranging_task` maps obstacle columns to LEFT/CENTER/RIGHT motors each frame: hard regional mapping + per-motor most-urgent tracking + squared duty curve + dominance weighting. `haptic_motors_init()` runs at boot in sensor mode; LEDC infra pulled out of `#if HAPTIC_TEST`. Bench-confirmed. **ERM dead-zone fix:** added `HAPTIC_DUTY_MIN` (130) floor so an alerting motor is felt the instant the buzzer fires instead of staying silent until ~20 cm. New knobs: `HAPTIC_DIRECTIONAL`, `HAPTIC_DUTY_MIN`, `HAPTIC_DOMINANCE_NUM/DEN`.

## Queued (in order)

1. **Walk-test the directional haptics + tune.** The drive is implemented and bench-confirmed; now wear it and walk.
   - Tune `HAPTIC_DUTY_MIN` (currently 130) — raise if the motor still feels weak right at the alert threshold, lower if it's too strong across the whole band.
   - Confirm direction holds while moving (left obstacle → left temple, etc.) and that two-sided/doorway scenes fire both side motors with dominance contrast.
   - **Open watch item:** HTTP server wedged once when motors ran sustained at high duty point-blank (~11 cm desk obstacle). Did not recur in normal use. If it reproduces during walking: add motor-terminal 100 nF + rail 100 µF caps (mailed), a duty cap, or an HTTP watchdog.
2. **Solder perfboard for the helmet rim** when 1N5819 Schottky kit arrives — three 2N3904s, three 1 kΩ resistors, three flyback diodes (cathode → 3V3), one 100 µF bulk cap across 3V3, JST connectors out to motors.
3. **Multi-target per zone** (`VL53L8CX_NB_TARGET_PER_ZONE = 2`) — helps thin obstacles in open doorways. ~40 line firmware change.
4. **Dynamic wearable testing.** Walk hallways, doorways, around furniture. Specifically test: pullup bar / overhead doorframe, chair near body, dark fabric, glass at angle, lighting changes (indoor → outdoor). Decide whether 2nd sensor is needed.
5. **Second VL53L8CX aimed downward** (SPI bus) for the belly-button-and-below blind spot.

## Research synthesis (2026-05-26)

Did a full Phase-1 data re-analysis (latency-focused wearable lens) + spawned 3 background research agents (ST docs, academic literature, market survey). All findings written up in [`docs/research-optimal-config.md`](docs/research-optimal-config.md).

Key conclusions baked into firmware:
- **4×4 @ 30 Hz currently** (Phase 1 latency analysis showed frame latency dominates per-zone noise by 10–40× for a moving user; 60 Hz worth testing)
- CONTINUOUS mode, sharpener 5, TARGET_ORDER CLOSEST (defensible at our <100 ms budget per ST)
- Per-row thresholds 60/60/80/95 cm (4×4) — our innovation, not in literature
- Ratio-based beep urgency (forward / row_threshold) with squared curve — our innovation
- 3-motor directional haptic ring (LEFT/CENTER/RIGHT temple/forehead) — wired + verified + research-backed, column-mapping logic pending (see Queued #1)

What's empirically open (publishable contributions):
- No published paper has tested VL53L8CX on a head-mounted ETA for visually impaired
- No paper has measured detection latency vs frame rate for moving pedestrian
- No paper has characterised ground-plane false-positives for downward-pitched head mount
- No published outdoor / direct-sun VL53L8CX wearable data

## Live test snapshots

- **2026-05-25:** Bumped `MOUNT_PITCH_DEG` 13° → 20° based on user re-measurement after physical mount adjustment. Should be re-verified with another wall-stare capture when convenient. Compensation table at 20° pitch on 8x8: row 0 cos = 0.98 (top, basically unchanged), row 7 cos = 0.74 (bottom, ~26% reduction).
- **2026-05-25:** ESP-direct web viewer live at `http://192.168.1.228/`. Phone-friendly. Shows nearest forward distance + 8×8 grid with red=close, green=far. Polls `/api/status` every 200 ms.

## Dynamic-testing findings (live observations during wearable testing)

- **2026-05-25: chest-and-below obstacles invisible at close range.** Confirmed by walking-around test. Sensor at 186 cm helmet height + 13° pitch + 22.5° half-FoV means bottom edge of view is 35.5° below horizontal. Belly button (~120 cm body) at 60 cm forward needs 47.7° down → outside cone. Chest (~140 cm) needs 37.5° down → also outside. Slant compensation can't fix this — it's the FoV geometry. **Vertical angular range needed to cover "slightly-above-head + belly-button at 60 cm" = ~61°, but sensor only has 45° vertical FoV. One head-mounted sensor cannot cover both ends.** Options:
  - Bump `MOUNT_PITCH_DEG` to **20°** (recommended single-sensor compromise): top of FoV at 2.5° above horizontal (keeps a bit of head-height coverage), bottom at 42.5° (catches down to lower chest at 60 cm). Belly button still uncovered.
  - Bump to 25–30° to catch belly button, lose all above-horizontal coverage.
  - Mount sensor lower on body (chest). Belly button becomes near-horizontal. Loses overhead.
  - Add second VL53L8CX aimed downward (already on future-ideas list — this is the real fix).

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

## OTA root-cause finding — RESOLVED 2026-05-26

Spent the evening of 2026-05-25 debugging "OTA fails mid-stream" with serial captures over COM10. Real cause:

- **Verbose logging was throttling OTA to UART speed.** With `CONFIG_LOG_DEFAULT_LEVEL_VERBOSE`, every OTA chunk produced ~400 B of UART log output. At 115200 baud (~11 KB/s ceiling), log writes blocked the OTA task, slowing the whole transfer to ~15 KB/s. A 930 KB OTA then took 60+ seconds and curl's `--max-time 90` clipped the tail.
- **Heap was healthy throughout** (237 KB free, min-free 229 KB stable). Disproves the heap-fragmentation hypothesis.
- **`esp_ota_write` succeeded on every chunk.** No actual partition corruption this session. Earlier 65 KB mid-stream drops were real partition damage from accumulated bad-OTA boots before rollback was enabled — those are prevented now.

**Fix applied:** `sdkconfig.defaults` reverted to `CONFIG_LOG_DEFAULT_LEVEL_INFO`. OTA-handler heap-progress logs kept (INFO level, no throttle penalty).

**Verified 2026-05-26 morning:** OTA push timed at **6.3 seconds at 164 KB/s** (was 60+ s at 15 KB/s). Clean reboot, sensor streaming after, heap healthy. Case closed.

**What still could break OTA (recoverable, not blocking):**
- Sensor I²C init flake (~20% of warm reboots) is independent of OTA but could prevent the HTTP server coming up that boot.
- Other future causes (long-uptime heap fragmentation, WiFi rate-limit) → all diagnostic plumbing in place: `serial_capture.py`, `/api/health`, per-chunk heap logs, runtime `esp_log_level_set("OTA", ESP_LOG_VERBOSE)` to enable verbose without throttling.

## Recurring bugs / pitfalls (don't repeat)

- ESP I²C sensor init fails ~20% of the time on warm reboot. Mitigation: host-side 3× retry in `run_one_test.ps1`.
- ~~OTA can leave one partition in a corrupted state after many cycles.~~ **FIXED** with `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y` + `esp_ota_mark_app_valid_cancel_rollback()` call in `ota_rollback_confirm_task` (waits for WiFi + first sensor frame, then confirms). Bad OTAs now auto-revert to the previous slot instead of bricking.
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
