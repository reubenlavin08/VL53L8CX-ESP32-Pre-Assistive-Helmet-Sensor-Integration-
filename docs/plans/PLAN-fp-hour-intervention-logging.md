# PLAN — FP/hour + intervention logging (the measurement layer)

Status: plan only, 2026-08-23. Implements two locked findings:
- UTILITY-ROADMAP.md §Abandonment counter-measures: "False positives are
  the #1 return reason (WeWALK) → **measure FP/hour as a first-class
  metric, publish it**."
- glidance-deep-dive-2026-08-20.md §Fleet learning (openpilot-verified
  pattern) "Minimal ONE-HELMET design": always-on 60 s ring buffer
  (low-res video + ToF + IMU), clip triggers (ToF/CV disagreement, user
  override, manual "flag that"), per-session telemetry, and the
  IDEA-BANK line "every F8-hush, every user override = a labeled miss.
  Log the 10 s sensor window around each." Plus: "design the log format
  now (timestamped frames + ToF + IMU + what the system said + what the
  user did)."

## Goal

Four deliverables, one module (`camera/flightlog.py`):
(a) a per-session structured event log of every spoken alert (text, tier,
range, trigger); (b) false-positive votes — implicit (F8-hush within N s of
an alert) and explicit (voice "wrong"); (c) a 60 s rolling clip buffer
(downscaled JPEG frames + ToF grids + IMU) dumped to disk on trigger;
(d) `camera/session_report.py` computing FP/hour and alerts/hour per
session. This is the layer that turns field walks into publishable numbers
and regression clips.

## Evidence — what exists in the codebase today

- **Log-format precedents**: `camera/vlm.py:29` `LOG = _HERE /
  "vlm_log.jsonl"` ("every query appended... flywheel food") and
  `camera/voice.py:27` + lines 58-59 (`json.dumps(entry) + "\n"` append
  per event, "for threshold tuning later"). Both git-ignored
  (`.gitignore:49,52`). Same convention here.
- **The single choke point for spoken alerts**: `speech_worker()`
  (`camera/cv_fusion.py` lines 382-434). Every utterance — directive,
  caution, query — passes through it AFTER cooldown/stale/repeat
  filtering, i.e. it sees exactly what the user hears. The enqueue side
  (`speech_next` assignments in the tier engine, lines 1044-1120, F9 at
  1148, `_say_q` at 856) sees what the engine WANTED to say. Log both:
  `enqueued` (with suppress reason when dropped) is optional v2; `spoken`
  is the v1 requirement and needs only one hook.
- **Tuple already carries what we need**: `(text, key, rng, tier, born)`
  (line 405). `key` encodes the trigger ("DIRECTIVE", "obstacle",
  "id{tid}:left", "BLIND", "QUERY...", "DOOR...").
- **F8-hush**: global GetAsyncKeyState poll, edge-triggered at lines
  1005-1009 (`audio_on = not audio_on`). Voice "quiet" does the same at
  line 1393-1394. Both are the "user override" signal.
- **Voice grammar**: `camera/voice.py` builds `PHRASES`/`full_gram`
  (lines 85-86) — adding a "wrong" (explicit FP) and "flag that" (manual
  clip) phrase is the established pattern (voice-commands-2026-08-23.md).
- **Frames**: main loop holds `frame` (720p) at ~30 fps (line 867);
  `vlm_frames = deque(maxlen=10)` (line 764) is the existing frame-ring
  precedent. **ToF grids**: `tof_hist` per sensor (line 861) holds ~0.8 s;
  the raw grids land in `fo.latest[S]` via `_helmet_line` (lines 76-78).
  **IMU**: `imu_quat`/`imu_stamp` (lines 59-60) at ~100 Hz.
- **Disagreement trigger, free**: `alert_zones` (line 983) = near ToF
  zones claimed by NO detection — the fusion's built-in shadow-mode signal
  named by the glidance doc ("ToF/CV disagreement — our fusion already
  computes both").

## Design

### Session layout

```
camera/sessions/2026-08-23_1912/        (git-ignored dir)
  events.jsonl        one line per event, append-only
  meta.json           start time, args (units mode, --mode, --rate), git rev
  clips/
    1912_43_override/ frames_000.jpg..._119.jpg, tof.npz, imu.jsonl, why.json
session_report.py     reads any/all session dirs
```

### (a) Event log

One writer function `flightlog.event(kind, **fields)` (thread-safe append,
same open-append-close style as voice.py:58). Events:

- `{"e":"spoken","t":...,"text":...,"key":...,"tier":...,"range_mm":...}`
  — hooked in `speech_worker` right after the filters pass (immediately
  before `speaking = True`, line 420). The `key` IS the trigger record.
- `{"e":"audio_toggle","t":...,"on":false,"src":"F8"|"voice"}` — hooks at
  lines 1005-1009 and 1393-1396.
- `{"e":"fp_vote","t":...,"mode":"implicit"|"explicit","alert_key":...,
  "alert_t":..., "latency_s":...}`
- `{"e":"gated",...}` from PLAN-head-turn-speech-gate, if built.
- `{"e":"clip","t":...,"trigger":...,"dir":...}`
- `{"e":"heartbeat","t":...}` every 60 s — gives session DURATION robustly
  even after a crash (report uses last heartbeat, not last event).

### (b) FP marking

Keep `last_alert = (t, key, tier)` updated on every non-query `spoken`
event. Implicit vote: on F8-hush (audio ON→OFF edge only) or voice
"quiet", if `now - last_alert.t < FP_WINDOW_S` (N = 10 s) and tier was
caution → log `fp_vote mode=implicit` against that alert AND fire the clip
buffer. Directive alerts are excluded from implicit votes (hushing during
"stop stop" is panic, not disagreement) but included for explicit ones.
Explicit vote: new voice phrase "wrong" (voice.py grammar + command map;
ungated like "stop"/"quiet") and a keyboard fallback `x` in the key
dispatch (lines 1400-1503) → `fp_vote mode=explicit` against `last_alert`
regardless of window, plus clip. Votes are VOTES, not labels — the weekly
curation pass (glidance doc step 4) confirms against the clip.

### (c) 60 s rolling clip buffer (openpilot pattern, fleet-size 1)

Three rings, filled from the main loop (all cheap):
- **Frames**: every 0.5 s, `cv2.resize` the current 1280x720 frame to
  640x360 and JPEG-encode q=70 → `deque(maxlen=120)` of `(t, bytes)`.
- **ToF**: every frame-loop pass (~15-30 Hz effective), snapshot
  `(t, gridA, gridB)` post-hold from the `zones` build → `deque` trimmed
  to 60 s.
- **IMU**: subsample to ~20 Hz in `_helmet_line` → `deque(maxlen=1200)` of
  `(t, w, x, y, z)`.

**Storage math** (the reason 2 fps/360p is right): 640x360 q70 JPEG of a
natural scene ≈ 25-40 KB. 120 frames ≈ **3-5 MB per 60 s clip** (RAM cost
of the ring: same ~4 MB — trivial). ToF: 2 sensors x 16 zones x 4 B x
20 Hz x 60 s ≈ 154 KB (npz, less). IMU: 1200 lines x ~60 B ≈ 72 KB. Total
≈ **4-6 MB per clip** — a 2 h walk with 20 triggers ≈ 100 MB. (openpilot
budget for comparison: ≤5 MB low-res video per DRIVE — we are in the same
class per event.)

**Triggers** (each writes the buffer via a background thread — never block
the frame loop): (1) implicit/explicit FP vote (override); (2) manual
"flag that" voice phrase or `x` key long-form; (3) disagreement burst:
`alert_zones` nearer than 1000 mm persisting > 1 s with zero ranged
detections (rate-limited: ≥ 120 s between disagreement clips, else a bad
scene fills the disk); (4) directive fired ("stop stop" is always worth a
clip). Per-trigger debounce: one clip per 30 s max globally. `why.json`
stores trigger type + the associated event.

### (d) Report script

`camera/session_report.py [session_dir|--all]`: duration from
heartbeats; counts by tier; **alerts/hour** (spoken, non-query);
**FP votes/hour** and **FP rate = votes / caution alerts**; clips by
trigger; median alert range. Plain-text table to stdout, one CSV line per
session appended to `camera/sessions/summary.csv` for the trend chart in
the writeup. ~80 lines, stdlib only.

## Implementation steps

1. New `camera/flightlog.py`: `start_session(meta)`, `event(...)`,
   `RingBuffer` (frames/tof/imu), `save_clip(trigger)` (background
   thread), `note_spoken/last_alert` helpers. ~150 lines.
2. `camera/cv_fusion.py` `main()` (near line 690): `flightlog.
   start_session({...args...})`; heartbeat piggybacked on the frame loop.
3. `speech_worker` (line 420 area): `flightlog.spoken(text, key, tier,
   rng)` after the filter gauntlet, before `speaking = True`.
4. Main loop: frame-ring feed next to `vlm_frames.append` (line 873,
   0.5 s throttle); ToF snapshot after the `zones` build (~line 930); IMU
   subsample in `_helmet_line` `Q:` branch (line 84).
5. F8 handler (lines 1005-1009) + voice `quiet` (line 1393): on ON→OFF
   edge call `flightlog.override("F8"|"voice")` → implicit-FP logic +
   clip.
6. `camera/voice.py`: add "wrong" and "flag that" to `PHRASES`/command
   queue; `cv_fusion` dispatch (lines 1372-1399): map to explicit FP and
   manual clip; add `x` key fallback.
7. Disagreement + directive triggers: in the tier engine — directive
   branch (line 1057) and an `alert_zones` persistence check (~line 990).
8. New `camera/session_report.py` per (d).
9. `.gitignore`: `camera/sessions/`. DEVLOG entry + a first real-walk
   report pasted into the devlog (the metric exists once it's measured).

## Test plan

- Desk session, 5 min: walk at a chair (caution fires), F8 within 10 s →
  `events.jsonl` shows spoken + audio_toggle + fp_vote(implicit) + clip;
  clip dir has ~120 jpgs spanning 60 s, tof.npz loads, imu.jsonl parses.
- Say "helmet, wrong" after an alert → fp_vote(explicit). Say "helmet,
  flag that" with no alert → clip with trigger=manual, no fp_vote.
- F8 with NO recent alert → audio_toggle only, no fp_vote (window check).
- Disagreement: hold a thin pole (no COCO class) at 0.8 m for 2 s → one
  clip, then none for 120 s despite persisting.
- `session_report.py` on the session → duration within ±1 min, counts
  match a manual tally of events.jsonl, FP/hour arithmetic checked by hand.
- Perf: frame-loop time with logging on vs off (< 1 ms/frame budget; JPEG
  encode is 2/s and ~3 ms — fine).
- Crash-robustness: kill the process mid-session → report still computes
  duration from heartbeats.

## Risks

- **Frame-loop jank** from clip saves → mitigated: rings hold encoded
  bytes already; `save_clip` only writes files, in a daemon thread.
- **Disk creep** on long sessions with a noisy scene → trigger debounce +
  rate limits; report prints total MB so creep is visible.
- **Privacy**: clips contain bystanders. UTILITY-ROADMAP hard-do-not-build
  list bans *persistent recording* — a 60 s ring that persists only on
  explicit trigger events is the openpilot compromise; state it in the
  writeup, keep sessions local-only and git-ignored.
- **Vote pollution**: F8 pressed to silence the device for a phone call
  reads as an implicit FP. Acceptable — votes are curated against clips
  weekly, and the 10 s window bounds it.
- Two writers (speech thread + main loop) appending events.jsonl →
  single lock in flightlog; jsonl lines are atomic-enough at this rate.

## Effort

~6-8 h: 2.5 h flightlog module, 1.5 h cv_fusion + voice wiring, 1 h report
script, 1-2 h live test walk + tuning debounces, 0.5 h DEVLOG/writeup notes.

## Dependencies

None hard. PLAN-head-turn-speech-gate logs into this schema if both land
(build this first or use its standalone gate_log.jsonl). PLAN-steps-not-
meters: record units mode in meta.json. Future consumers: weekly curation
/ regression-replay (glidance doc step 4) and the stumble-logging idea
(imu-uses item 12) plug into the same clip trigger list.
