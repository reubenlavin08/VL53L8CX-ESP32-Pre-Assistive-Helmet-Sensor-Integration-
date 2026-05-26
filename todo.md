# Helmet project — TODO

Living list of work for this project. Append-only during sessions; check items off only after they're done AND verified.

## In progress

- [x] **Rotation in firmware:** `MOUNT_ROTATION_DEG = 270` confirmed working in `main.c`, applied via `rotated_zone()` helper to all three stream functions (DATA/SIGMA/STATUS). Single source of truth at the chip — all downstream consumers see body-frame data automatically.
- [x] **README first-person rewrite.** v9 now in first person; earlier sections were already mostly first-person (only remaining "you/your" are reader-addressed instructional bits, which is correct README style).
- [x] **Embed test rig photos in README.** `rig_wide_full_setup.jpg` + `rig_close_sensor_and_board.jpg` now inline at top of v9 section.
- [x] **"Limitations of this analysis" subsection added to README** with explicit caveats about ambient light, untested surfaces, motion noise, and coverage gaps.
- [x] **Helmet-mount tilt calibration via wall stare** (done 2026-05-25). Sensor at 73", wall at 32", 200-frame capture. Fit gave **~13° pitch down** (dominant) plus a small ~few-degree roll that I'm ignoring as second-order for now. Calibration script lives at `visualizer/calibrate_tilt.py`; raw capture in `visualizer/raw_frames/wall-tilt-calib-h185cm-d81cm_*.csv`.

## Queued (in order)

1. [~] **Per-row slant compensation in firmware** — IMPLEMENTED, awaiting flash.
   - `MOUNT_PITCH_DEG = 13.0f` in `main.c`, anchored by the wall-stare calibration.
   - `compute_row_cos_table()` builds the per-row cosine table at sensor init.
   - Nearest-distance loop now iterates body-frame zones and multiplies slant by `g_row_cos[row]` before comparing to threshold.
   - Practical effect at 13° pitch (8x8): top rows barely change (cos ~0.99), bottom row reads 84% of slant (cos = 0.84). Floor-near obstacles in lower rows now trigger sooner.
   - Raw `DATA:` stream is unaffected (still slant) — analysis tools see what the sensor sees.
2. [ ] **Multi-target per zone (`VL53L8CX_NB_TARGET_PER_ZONE = 2`).**
   - Enables sensor to detect both the pullup bar AND the wall behind it as separate targets per zone.
   - Combined with `TARGET_ORDER = CLOSEST`, the bar wins.
   - ~40 line firmware change (loop through all targets per zone in stream functions, take closest valid).
3. [ ] **Dynamic wearable testing once 1+2 are in.**
   - Walk hallways, doorways, around furniture.
   - Specifically test: pullup bar / overhead doorframe, chair near body, dark fabric, glass at angle, lighting changes (indoor → outdoor).
   - Decide based on real use whether a 2nd sensor is needed.

## Research synthesis (2026-05-26)

Did a full Phase-1 data re-analysis (latency-focused wearable lens) + spawned 3 background research agents (ST docs, academic literature, market survey). All findings written up in [`docs/research-optimal-config.md`](docs/research-optimal-config.md).

Key conclusions baked into firmware:
- 4×4 @ 20 Hz currently (Phase 1 says 30 Hz is better; 60 Hz worth testing)
- CONTINUOUS mode, sharpener 5, TARGET_ORDER CLOSEST (defensible at our <100 ms budget per ST)
- Per-row thresholds 60/60/80/95 cm (4×4) — our innovation, not in literature
- Ratio-based beep urgency (forward / row_threshold) — our innovation

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
