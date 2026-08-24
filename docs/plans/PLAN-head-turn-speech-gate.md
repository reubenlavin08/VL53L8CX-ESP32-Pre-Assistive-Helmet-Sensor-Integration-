# PLAN — Head-turn speech gate (sterile cockpit on yaw rate)

Status: plan only, 2026-08-23. Implements imu-uses-2026-08-17.md Tier A
item 2: "Sterile-cockpit speech gate on yaw rate: suppress CAUTION above
~80-120°/s (measured head-turn peak 104°/s), never DIRECTIVE. **White
space — no published ETA gates alerts on head pose** (Reyes Leiva 2021
survey confirms the gap)." Part of the documented novelty claim (items
2+8+9: "IMUs in VI-assistive tech never model the user's own behaviour").

## Goal

When the wearer is actively scanning (fast head turn), a CAUTION callout is
worse than useless: the azimuth word ("left") is stale by the time the
sentence lands (a 240°/s scan moves the world 60°+ during one utterance),
and the utterance collides with the user's own deliberate information-
gathering. Gate CAUTION-tier speech while |yaw rate| > ~100°/s; release
with hysteresis; log every gated event for the writeup (this is the citable
measurement: how often the gate fires, what it suppressed).

## Evidence — current state in camera/cv_fusion.py

- **IMU stream**: `Q:w,x,y,z,st,acc` lines parsed in `_helmet_line()`
  (lines 79-85) at ~100 Hz from serial (`helmet_serial_reader`, line 117)
  or TCP (`helmet_reader`, line 88). Only the LATEST quat is kept
  (`imu_quat`, `imu_stamp`, lines 59-60) — no history, so no rate exists yet.
- **Yaw extraction precedent**: `_yaw_now()` (lines 788-796) already
  converts quat → `quat_to_R` (line 192) → forward vector →
  `atan2(-f[0], f[1])` yaw in degrees, applying `mount_cal`. Angle wrap
  helper `_wrap()` at line 798.
- **Tier engine hook point**: "TIER ENGINE v2" block, lines 1011-1120.
  Structure: directive branch (lines 1044-1058, `near_path < DIRECTIVE_MM`),
  then the caution `else:` branch (lines 1059-1109) which builds `cand` and
  enqueues `speech_next = (text, key, rng, "caution", now)` at line 1108.
  "path clear" release is also caution-tier (lines 1060-1064). Sensor-loss
  is separate (lines 1111-1120) and is **directive** tier.
- **There is no ROUTINE tier in v2** (silence is the default state,
  speech_worker docstring lines 388-395), so in practice the gate applies
  to CAUTION only. If a routine tier ever returns, it inherits the gate.
- **Tier semantics** (`speech_worker`, lines 382-434): directive repeats at
  1.2 s, caution has 60 s per-object cooldown, query always speaks. The
  gate must sit BEFORE enqueue, not in speech_worker — a gated caution must
  not consume its cooldown slot or occupy the latest-wins queue.

## Design

### Yaw-rate estimator (in the reader path, ~100 Hz)

Extend `_helmet_line()` (line 79): on each `Q:` line, compute raw yaw from
the quat (chip frame is fine for a RATE — mount_cal is a constant rotation
and cancels in the delta, so the estimator needs no calibration), keep a
short deque of `(t, yaw)`, and publish a smoothed rate:

```
# module globals next to imu_quat (line 59)
yaw_hist = collections.deque(maxlen=12)   # ~120 ms at 100 Hz
yaw_rate = 0.0                            # deg/s, smoothed, signed

# in _helmet_line, Q: branch, after imu_stamp update:
w,x,y,z = q
yaw = degrees(atan2(2*(w*z + x*y), 1 - 2*(y*y + z*z)))  # direct, no matrix
yaw_hist.append((imu_stamp, yaw))
if len(yaw_hist) >= 2:
    (t0,y0),(t1,y1) = yaw_hist[0], yaw_hist[-1]
    if t1 - t0 > 0.02:
        r = _wrap_deg(y1 - y0) / (t1 - t0)      # endpoint fit over ~110 ms
        yaw_rate = 0.7*yaw_rate + 0.3*r          # EMA, tau ≈ 30 ms extra
```

Delta-yaw math notes: `_wrap_deg(a) = ((a+180) % 360) - 180` handles the
±180° seam; the endpoint difference over a 120 ms window IS the smoothing
(equivalent to a boxcar derivative — single-sample deltas at 100 Hz would
be quantization-noisy at BNO085 resolution). GRV yaw drifts 0.5°/min
(datasheet, imu-uses doc) — irrelevant at rate timescales. Staleness: if
`time.monotonic() - imu_stamp > 0.3`, treat rate as 0 (never gate on stale
data — no IMU must mean no gate, not a stuck gate).

### The gate + hysteresis

```
GATE_ON_DPS  = 100.0    # enter gated state above this (measured peak 104)
GATE_OFF_DPS = 60.0     # leave only below this...
GATE_OFF_DWELL_S = 0.25 # ...sustained this long (settle time)
```

State machine in the main loop (per-frame, before the tier engine):
`gated` becomes True the instant `abs(yaw_rate) > GATE_ON_DPS`; becomes
False only after `abs(yaw_rate) < GATE_OFF_DPS` continuously for
`GATE_OFF_DWELL_S`. The wide ON/OFF band plus the dwell kills chattering
when the user hovers near threshold mid-scan (head turns decelerate through
the band on every reversal).

### Hook into the tier engine

- Wrap ONLY the caution enqueues: the `cand` enqueue at lines 1107-1109 and
  the "path clear" enqueue at lines 1062-1064. When `gated`, skip the
  `speech_next` assignment (and skip nothing else — `rng_hist` bookkeeping
  at lines 1087-1094 keeps running so the range median is warm the moment
  the gate lifts). The engine re-evaluates every frame, so a still-present
  hazard speaks automatically on release; no deferred-queue machinery
  needed, and `STALE_S` (line 347) semantics are untouched.
- **NEVER gated**: the directive branch (lines 1044-1058) — "stop stop" /
  "step right" must land mid-scan; the sensor-loss callout (lines
  1111-1118, directive tier, "silence must never mean safe"); the query
  tier (F9 lines 1122-1149, door/VLM/level `_say_q` — the user asked);
  the proximity ticker (`ticker_worker`, line 523 — 40 ms blips are
  azimuth-free and carry the safety channel while speech is gated).
- HUD: append `GATED` to the status line (line 1356 area) while active, so
  sighted-observer video review can see the gate work.

### Gated-event logging (the writeup data)

Append one JSON line per suppression to `camera/gate_log.jsonl`
(precedent: `vlm_log.jsonl` camera/vlm.py:29, `voice_log.jsonl`
camera/voice.py:27; git-ignored like both):
`{"t": ..., "yaw_rate": ..., "text": ..., "key": ..., "range_mm": ...,
"tier": "caution", "gate_entered_t": ...}` — plus one line per gate
enter/exit with peak rate and duration. Log at most one suppression line
per (key, gate-episode) to keep the file readable. If
PLAN-fp-hour-intervention-logging lands first, write these into its
session `events.jsonl` with `"event": "gated"` instead of a separate file.

## Implementation steps

1. `camera/cv_fusion.py` lines 59-60 area: add `yaw_hist`, `yaw_rate`
   globals + `_wrap_deg`; extend the `Q:` branch of `_helmet_line()`
   (line 79) with the estimator above. (`import collections, math` at top.)
2. Constants block (near line 345): add `GATE_ON_DPS`, `GATE_OFF_DPS`,
   `GATE_OFF_DWELL_S`.
3. Main loop, just above the tier engine (line 1011): gate state machine
   (`gated`, `gate_below_since`, staleness check), plus gate enter/exit
   logging.
4. Guard the two caution enqueues (lines 1062-1064, 1107-1109) with
   `if not gated:`; log a suppression event in the `else`.
5. Status-line `GATED` flag (line 1356) + optional yaw-rate readout on the
   IMU HUD line (line 1339).
6. `.gitignore`: `camera/gate_log.jsonl`. DEVLOG entry.

## Test plan

- Bench, rig on head, audio on, a chair at 1.2 m off-axis: hold still →
  caution callout arrives. Shake head at scan speed while re-approaching →
  no caution speech; ticker still ticks; stop turning → callout arrives
  within ~1 frame + dwell. Verify with `gate_log.jsonl` timestamps.
- Directive check: walk at a wall while turning the head fast → "stop stop"
  must still fire (never gated). Same for F9 mid-turn.
- Chatter check: slow deliberate pans right at ~80-100°/s for 30 s → gate
  transitions in the log should be few (< 1/5 s); tune GATE_OFF/dwell if not.
- Rate sanity: print `yaw_rate` while turning ~90° in 1 s → ≈ 90°/s; check
  the ±180° seam by turning through the boot-heading antipode.
- Regression: no IMU connected (`imu_quat is None`) → gate permanently off,
  behaviour identical to today.

## Risks

- **Sign/seam bugs** in yaw wrap → false rates near ±180°; covered by the
  seam test. Estimator uses direct atan2-from-quat, so no mount_cal
  dependency (a constant rotation cannot change a yaw RATE magnitude
  measurably at these window lengths).
- Gating too eagerly hides a real hazard during a scan — mitigated by:
  directive tier ungated, ticker ungated, and the hazard re-announcing the
  frame the gate lifts. This is exactly the sterile-cockpit tradeoff; the
  log quantifies it for the writeup.
- Reader-thread vs main-thread shared floats: CPython assignment is atomic;
  same pattern as `imu_quat` today. Keep the estimator in the reader (100 Hz)
  not the frame loop (~30 Hz) or fast turns alias.
- Vibration from haptic motors adding gyro noise — imu-uses doc flags
  drift-under-vibration as unmeasured; rates this large (100°/s) are far
  above that noise floor, but check the log during motor activity once.

## Effort

~4-5 h: 1.5 h estimator + state machine, 1 h tier-engine wiring + HUD,
0.5 h logging, 1-2 h live tests + tuning + DEVLOG.

## Dependencies

Requires the IMU streaming (`Q:` lines) — already live in the flashed
helmet firmware. No mount_cal needed. Pairs with
PLAN-fp-hour-intervention-logging (shared event log); independent of
PLAN-steps-not-meters.
