# PLAN — Drop alarm (helmet falls off → owner can find it)

Status: planned 2026-08-23. A blind wearer who drops the helmet (or knocks it
off a table) cannot visually search for it. Detect the drop; make something
audible happen.

## Goal

Within ~2 s of the helmet leaving the head/hand and hitting the floor, the
system announces it — reliably enough to trust, quiet enough to never cry wolf
while worn.

## Evidence (what exists today)

- **IMU stream is quats only.** `main/main.c:1371–1385` emits
  `Q:w,x,y,z,status,headacc` per ranging-loop iteration; the only enabled
  report is `SH2_ARVR_STABILIZED_GRV` @100 Hz
  (`components/bno08x/bno08x.c:114–130`, `enable_reports()`); reports decode in
  `sensor_cb` (bno08x.c:134–170) inside the ~500 Hz `imu_task`.
- **The vendored SH2 driver has the relevant on-chip detectors:**
  `SH2_SIGNIFICANT_MOTION = 0x12`, `SH2_STABILITY_CLASSIFIER = 0x13`,
  `SH2_STABILITY_DETECTOR = 0x1c` (sh2.h:108–113) — but **no freefall report
  exists in SH-2** (full sensor list sh2.h:85–127). Freefall must be computed
  from accelerometer data.
- **Helmet has NO speaker.** The piezo buzzer was cancelled by the user, BUT
  the firmware code path survives: `BUZZER_GPIO GPIO_NUM_40` is marked
  "PROVISIONAL — not wired" (main.c:61–66) and `buzzer_task` (main.c:531,
  2 kHz LEDC PWM) still builds behind `BUZZER_TEST`. Re-adding a buzzer is a
  wiring decision, not a software project.
- **Audio lives on the laptop**: `speech_worker`/`speech_next`
  (camera/cv_fusion.py:378–430) with the "query" tier always spoken; the
  "sensors lost" callout (cv_fusion.py:1111–1120) is the existing precedent
  for system-status speech.
- **Bearing context**: `imu_quat`/`imu_stamp` (cv_fusion.py:59–60, parsed at
  63–86) hold the last-known helmet orientation; the beacon code (line 1152+)
  already converts quat→yaw.
- imu-uses-2026-08-17.md item 3: PAC + **stability classifier** are already in
  sh2_SensorValue.h; item 11: head-mounted fall detection is validated
  (97–98% sensitivity, Kangas 2008) "needs an alerting path to be worth it."

## Detection options, ranked honestly

1. **Firmware accel: freefall window + impact (RECOMMENDED).** Enable
   `SH2_ACCELEROMETER` @50 Hz; in `sensor_cb` compute |a|. Drop signature:
   |a| < ~0.4 g for ≥150 ms (a ≥40 cm fall gives ~290 ms) followed within
   500 ms by a spike > ~2.5 g. All in-firmware — nothing new streamed, no bus
   cost beyond one extra 50 Hz report on the shared bus (modest; the imu-uses
   doc's contention warning is about *raw high-rate* accel). Catches the
   actual event: falling.
2. **Firmware on-chip stability classifier ("on table" dwell).** One
   `sh2_setSensorConfig(SH2_STABILITY_CLASSIFIER, ...)`; a worn head is never
   perfectly still, so "On table / Stable" for >5 s ⇒ helmet is off the head.
   Free (event report), but it fires on *any* set-down including deliberate
   ones — it detects "not worn", not "dropped". Good as a v2 secondary signal
   ("helmet idle 10 minutes, still on?"), wrong as the drop trigger.
3. **`SH2_SIGNIFICANT_MOTION`** — detects motion *onset* (designed to wake
   phones). Wrong signal entirely; rejected.
4. **Python-side heuristic on the existing Q: stream.** Honest verdict: **not
   buildable well.** Quaternions carry orientation, not acceleration; freefall
   is invisible in orientation. What IS detectable from quats: rapid tumble
   (large inter-sample rotation) followed by frozen orientation far from the
   normal wearing pose. That mis-fires on "took helmet off and set it down"
   and misses clean vertical drops (no tumble). Usable only as a zero-firmware
   stopgap with a loud caveat; not the plan.

## The alarm itself — honest options

- Helmet-local sound: **none exists.** The 3 vibration motors at max duty
  make a faint shell rattle — not a locator for a room-scale search
  (inaudible past ~1 m; do not pretend otherwise).
- **Re-add a tiny piezo on GPIO 40** — the cancelled buzzer. Code exists
  (`buzzer_task`), OTA-only software change, ~$1 part + wiring. This is the
  only true *find-it-by-sound* solution, and it is a **hardware decision the
  user already declined once — presented as an option, not assumed.**
- **Laptop/phone TTS announcement (v1).** The laptop rides in the wearer's
  backpack (cv_fusion.py:144 comment) — when the helmet falls, the wearer and
  laptop stay together and the helmet is within a few metres. Announce
  immediately: "helmet dropped" + last-known bearing relative to the wearer's
  last heading if fresh (e.g. "helmet dropped, was facing ten o'clock"), and
  repeat every ~10 s until the Q: stream shows sustained motion again
  (= picked up). Not a homing beep, but it converts a silent failure into an
  immediate, actionable alert, with zero new hardware.

**Recommended v1: option 1 detection (firmware freefall+impact → `DROP:1`
line) + laptop TTS announcement with pickup auto-clear. Offer the GPIO-40
piezo re-add as a user decision for v2 (software already done).**

## Design

- Firmware: accel report enabled alongside GRV; drop state machine in
  `bno08x.c` (`IDLE → FREEFALL(|a|<0.4g,≥150ms) → IMPACT(|a|>2.5g within
  500ms) → LATCHED`). Latched event surfaces via `bno08x_get_drop()`; main
  ranging loop emits `DROP:1\n` (stdout + TCP, mirroring Q:, main.c:1380–1384)
  once, plus `DROP:0` when sustained motion resumes (≥2 s of |a| variance ⇒
  picked up).
- Python: `_helmet_line` parses `DROP:`; on `DROP:1` post a **directive-tier**
  announcement (bypasses cooldowns, gets the earcon pre-cue —
  speech_worker:409, 421–424) and re-post every 10 s until `DROP:0` or any
  key/voice "stop". Suppress ordinary hazard callouts while dropped (the ToF
  is staring at the floor; everything it says is garbage — reuse the
  `audio_on` gating pattern).

## Implementation steps

1. `components/bno08x/bno08x.c` `enable_reports()` (after line 129): enable
   `SH2_ACCELEROMETER`, `reportInterval_us = 20000` (50 Hz).
2. Same file, `sensor_cb`: branch for `v.sensorId == SH2_ACCELEROMETER`;
   compute `mag = sqrtf(x²+y²+z²)` (m/s²; 1 g ≈ 9.81); run the freefall→impact
   state machine on report timestamps; set `s_drop_latched` /
   `s_motion_resumed`. Thresholds as `#define`s at top for bench tuning
   (FREEFALL_G 0.4, FREEFALL_MS 150, IMPACT_G 2.5, IMPACT_WINDOW_MS 500).
3. `include/bno08x.h` + accessor `int bno08x_get_drop(void)` returning
   -1/no-change, 1/drop-latched, 0/cleared (consume-on-read).
4. `main/main.c` IMU block (after line 1385): poll `bno08x_get_drop()`, emit
   `DROP:1` / `DROP:0` via fputs + tcp_write.
5. Build + OTA (README.md:445: `idf.py build && python
   visualizer/ota_flash.py <ip>`).
6. `camera/cv_fusion.py` `_helmet_line` (line 63): parse `DROP:` into a global
   `drop_state, drop_stamp`.
7. Main loop: on rising `DROP:1` — compose text ("helmet dropped" + bearing
   from last fresh `imu_quat` if <5 s old), post at directive tier with a
   unique key each repeat (bypass `DIRECTIVE_REPEAT_S` throttle deliberately —
   or set key=f"DROP{n}") every 10 s; set `audio_on`-equivalent mute for
   hazard/caution tiers while dropped; clear on `DROP:0` with "helmet picked
   up".
8. (v2, user-gated) If the piezo returns: wire piezo → GPIO 40, set
   `BUZZER_TEST 0`, add a `drop_chirp` branch to `buzzer_task` firing a
   distinctive triple-chirp every 3 s while `s_drop_latched` — fully local,
   works with the laptop off.

## Test plan

1. **Bench truth-table** (helmet in hands, `idf.py monitor`):
   - 50 cm drop onto foam mat → `DROP:1` within 1 s. 10/10 target ≥8.
   - Normal take-off-and-set-down (hand-carried to table) → NO event, 10/10.
   - Vigorous head shakes, jog-in-place while worn, stair descent → NO event.
   - Pick up after drop → `DROP:0` within ~3 s.
2. **End-to-end:** drop while cv_fusion running → earcon + "helmet dropped"
   spoken < 2 s, repeats at 10 s, hazard callouts silent, "helmet picked up"
   on recovery.
3. **Threshold tuning log:** print |a| min/max during freefall candidates to
   the console; adjust the four #defines; record final values in DEVLOG
   (Problem→Root cause→Fix→Lesson, per portfolio rule).
4. **Motor-vibration soak:** 10 min worn with haptics firing — zero false
   DROP events (vibration is ~±0.3 g ripple, far from the 0.4 g *sustained*
   freefall window, but measure).

## Risks

- **Caught-before-floor / short drops** (<25 cm ≈ <110 ms freefall) won't meet
  the 150 ms window — accepted: a helmet caught mid-fall isn't lost.
- **Impact spike may saturate or alias at 50 Hz** — if impact detection is
  flaky, drop the impact requirement and use freefall-then-stillness instead
  (slightly slower, still honest).
- **Bus contention:** +50 Hz accel reports on the shared ToF-A bus. The
  polled-SHTP design already sustains 100 Hz GRV; monitor the `hb:` counters
  (bno08x.c:277) for pkts/calls regression after enabling.
- **TTS-only alarm doesn't help if the laptop also went down** or the wearer
  walked away before noticing — the piezo (v2) is the genuine fix; v1 is
  explicitly a notification, not a homing beacon. Say so in user docs.
- Directive-tier repeats every 10 s could annoy if `DROP:0` clearing fails —
  any keypress/voice "stop" must also clear (step 7).

## Effort

- Firmware (steps 1–5): 2 h including threshold bench-tuning.
- Python (steps 6–7): 1 h.
- Testing (truth-table + soak): 1.5 h.
- **Total ~4.5 h.** v2 piezo: +0.5 h software; hardware/wiring separate and
  user-gated.

## Dependencies

- None on tap-to-query, but both edit `enable_reports()`/`sensor_cb` — land
  them as one firmware change to OTA once.
- Buzzer v2 depends on the user reversing the piezo cancellation (GPIO 40
  reserved, code present).
- No dependency on `imu_mount_cal.json` (|a| is orientation-free; the bearing
  phrase uses raw yaw delta only).
