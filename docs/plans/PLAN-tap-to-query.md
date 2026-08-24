# PLAN — Tap-to-query (BNO085 double-tap triggers VLM describe, zero hands)

Status: planned 2026-08-23. Source research: docs/research-sources/imu-uses-2026-08-17.md
item 5 (Tier A, effort S): "SH2_TAP_DETECTOR on-chip (no aliasing at 100 Hz host
rate). Helmet shell is a good tap substrate. 1–2 tap vocabulary max."

## Goal

Tap the helmet shell twice → the existing VLM "describe what is ahead" pipeline
runs, answer spoken over TTS. No keyboard, no voice command, no hands on the
laptop. A blind wearer's fastest possible query gesture.

## Evidence (what the code does today)

**Firmware — sensor enable.** `components/bno08x/bno08x.c` `enable_reports()`
(lines 114–130) enables exactly one report:

```c
sh2_SensorConfig_t cfg;
memset(&cfg, 0, sizeof(cfg));
cfg.reportInterval_us = 10000;       /* 100 Hz */
int r = sh2_setSensorConfig(SH2_ARVR_STABILIZED_GRV, &cfg);
```

`enable_reports()` is called from `bno08x_init()` (line 246) and re-called by
`bno08x_service()` after any hub reset (lines 270–274) — a new report must be
added in this one function to survive resets. Reports arrive in `sensor_cb()`
(lines 134–170), which switches on `v.sensorId`; it runs in the ~500 Hz `imu_task`
context (lines 287–299).

**The vendored CEVA driver already decodes taps.** `components/bno08x/sh2/sh2.h:105`
defines `SH2_TAP_DETECTOR = 0x10`; `sh2_SensorValue.h:252–261` defines
`sh2_TapDetector_t { uint8_t flags; }` with `TAPDET_DOUBLE (64)` plus per-axis
bits; `sh2_SensorValue.c:155,402` decodes it. Zero new driver code.

**Firmware — streaming.** `main/main.c` lines 1371–1385 emit the IMU line every
ranging-loop iteration (~33 Hz), before the ToF frame gate, to both stdout
(USB-CDC) and TCP: `Q:w,x,y,z,status,headacc`. Tap events get the same
dual-path treatment.

**OTA.** README.md:445 — `idf.py build && python visualizer/ota_flash.py
192.168.1.228` (POST /update with X-OTA-Token, handler `main.c:670`). No cable.

**Python — parsing.** `camera/cv_fusion.py` `_helmet_line()` (lines 63–86)
parses `DATA:`/`DATAT:`/`Q:` prefixes; both readers feed it (`helmet_reader`
TCP, line 88; `helmet_serial_reader` USB, line 117).

**Python — query pipeline.** Key `'v'` (lines 1413–1426): if `vlm_mod.busy` is
set say "still working", else `_say_q("looking")` then a daemon thread runs
`vlm_mod.describe(list(vlm_frames), "Describe what is ahead.", sensor_ctx=...,
speak=_say_q)`. Around-Me is F9 / `voice_around` flag (lines 1122–1150). Voice
commands already dispatch by *injecting the keycode* (line 1378: `vc ==
"describe"` → `k = ord("v")`) — the tap path should reuse that exact pattern.
`_say_q` (lines 856–861) posts into the latest-wins `speech_next` slot at
"query" tier (always spoken, `speech_worker` lines 382–430).

**Half-duplex voice rule.** Lines 766–770: the voice recognizer drops mic
frames while our own TTS speaks (`voice_mod.start(is_speaking=lambda:
speaking)`). Taps are *mechanical*, not acoustic — they bypass this entirely,
which is precisely why tap-to-query is worth having: it works while TTS is
talking and in loud environments where the wake word fails.

## Design

- Firmware enables `SH2_TAP_DETECTOR` alongside the GRV. It is an on-chip
  event report (fires only on taps) — near-zero bus traffic, safe on the
  shared/polled bottom bus (imu-uses doc, Engineering notes: "Event reports
  are free").
- `sensor_cb` latches a volatile tap event (`s_tap_flags`, `s_tap_count`);
  the main ranging loop drains it next iteration (≤ ~30 ms added latency,
  irrelevant vs the 2–6 s VLM answer) and emits `TAP:1` or `TAP:2` (single /
  double, from `TAPDET_DOUBLE`) to stdout + TCP, exactly like the Q: line.
- Python: `_helmet_line` grows a `TAP:` branch that stamps a shared
  `tap_event = (count, time.monotonic())`. The main loop consumes it and
  injects a keycode.
- **Vocabulary (v1): double-tap → describe (`k = ord("v")`). Single-tap →
  ignored.** This deliberately deviates from the brief's "single-tap →
  Around-Me": a single tap is indistinguishable from a door-frame bump, a
  helmet adjustment, or setting the helmet down — the false-positive cost is
  an unwanted TTS paragraph. Double-tap is the BNO085's own discriminated
  gesture (TAPDET_DOUBLE) and is near-impossible to do by accident. If
  field use proves single-tap clean, map it to Around-Me (`voice_around =
  True`) with a one-line change — the plumbing below carries the count
  either way.
- Debounce (python side): drop any TAP event within 1.0 s of the last
  accepted one, and drop TAP-triggered describe when `vlm_mod.busy` is set
  (the `'v'` handler already answers "still working", which is the right
  behavior — keep it). Drop stale events (>0.5 s old) so a queued tap
  can't fire long after the gesture.
- Interaction with speech: none needed beyond the above — the describe path
  already acks with "looking" and serializes through `speech_next`.

## Implementation steps

1. `components/bno08x/bno08x.c` — in `enable_reports()` (after line 129) add:
   ```c
   memset(&cfg, 0, sizeof(cfg));
   cfg.reportInterval_us = 0;   /* event-driven: on-change only */
   cfg.changeSensitivityEnabled = true;
   r = sh2_setSensorConfig(SH2_TAP_DETECTOR, &cfg);
   ```
   (If the hub rejects interval 0, fall back to a slow keep-alive interval,
   e.g. 100000 us; taps still arrive as events.)
2. Same file — add `static volatile uint8_t s_tap_flags; static volatile
   uint32_t s_tap_seq;` and a `sensor_cb` branch:
   `else if (v.sensorId == SH2_TAP_DETECTOR) { s_tap_flags =
   v.un.tapDetector.flags; s_tap_seq++; }`
3. Same file + `include/bno08x.h` — new accessor
   `bool bno08x_get_tap(uint8_t *flags)` returning true once per new
   `s_tap_seq` (consume-on-read, like the Q status pattern).
4. `main/main.c` — in the per-iteration IMU block (after the Q: emit,
   line 1385): if `bno08x_get_tap(&tf)` emit
   `TAP:%d\n` with `2` if `(tf & TAPDET_DOUBLE)` else `1`, via `fputs` +
   `tcp_write` (mirror lines 1380–1384).
5. Build + OTA: `idf.py build && python visualizer/ota_flash.py <helmet-ip>`
   (README.md:445). Watch boot log for the new
   `enable TAP detector -> 0` line; confirm OTA rollback-confirm fires
   (`main.c:592` task).
6. `camera/cv_fusion.py` — `_helmet_line` (line 63): add
   `elif s.startswith("TAP:")` → set global `tap_event = (int(s[4:]),
   time.monotonic())` (guarded try/except like the Q branch).
7. `camera/cv_fusion.py` — main loop, next to the voice dispatch (line 1372):
   consume `tap_event`; if count==2, not stale (<0.5 s), and ≥1.0 s since
   last accepted tap: `k = ord("v")`. (Single-tap: log only, v1.)
8. On-screen debug: append `TAP` to the status line (line ~1355 area) for
   1 s after any event, so bench tuning is visible.

## Test plan

1. **Bench, serial console:** helmet on desk, `idf.py monitor` — tap shell
   twice; verify `TAP:2` lines; single tap → `TAP:1`. Confirm Q: stream
   cadence unchanged (no bus contention regression, heartbeat `hb:` counters
   in bno08x.c:277 steady).
2. **Through-foam test (the real question):** helmet WORN, tap the shell at
   normal finger force at 3 spots (side, top, brow). Target ≥8/10 double-taps
   detected. Foam decouples shell from head, not from the IMU — the IMU is
   mounted to the shell, so shell taps should couple well; measure, don't
   assume.
3. **False-positive soak:** 15-min walk with haptics firing (motors share the
   shell — the vibration is the most likely false trigger). Count spurious
   TAP lines; target 0 double-taps. If motors trip it, gate tap acceptance in
   python on "no motor active" (needs a motor-state line — or simply require
   the stricter double-tap only, which vibration is unlikely to mimic).
4. **End-to-end:** double-tap → "looking" ack < 0.5 s → VLM answer spoken.
   Double-tap during a spoken answer → "still working".
5. **Reset survival:** power-cycle IMU (hub reset log line) → tap again;
   works because enable_reports() re-runs.

## Risks

- **Tap detector tuning is fixed on-chip** (sensitivity lives in FRS records);
  if through-foam/finger-force detection is marginal there is no simple knob.
  Mitigation → fallback below.
- **Haptic motors false-triggering taps** (same rigid shell). Double-tap-only
  vocabulary is the primary mitigation; test 3 quantifies it.
- **Fallback if SH2 tap proves unreliable:** host-side accel-spike detection.
  Note honestly: **we stream quats only today** — this fallback needs firmware
  to enable `SH2_LINEAR_ACCELERATION` (~50–100 Hz) and stream a new `A:x,y,z`
  line first (~half the size of this whole plan again), and the imu-uses doc
  warns high-rate accel adds traffic to the shared, polled ToF-A bus. Prefer
  doing spike detection *in firmware* (in `sensor_cb`, no streaming) if we go
  there: |a| > ~2.5 g impulse, two impulses 100–500 ms apart = double-tap.
- Latency: tap→TAP-line is bounded by the ranging loop (~30 ms) — fine; if the
  loop is ToF-stalled the IMU block still runs every iteration (main.c:1371
  comment), so taps survive ToF stalls.

## Effort

- Firmware (steps 1–4): 1.5 h including OTA + console check.
- Python (steps 6–8): 1 h.
- Testing (bench + worn + soak): 1.5 h.
- **Total ~4 h** (excluding the fallback path; add ~3 h if needed).

## Dependencies

- None on other planned work. Does NOT need `imu_mount_cal.json` (taps are
  orientation-independent).
- WiFi up for OTA (or USB flash fallback).
- `camera/voice.py` untouched; tap and voice dispatch coexist by design.
