# PLAN — Interrogation layers (Around-Me quadrants + depth-on-repeat)

Status: plan only, no code. Written 2026-08-23 against `camera/cv_fusion.py` @ current tree.

## Goal

Upgrade the on-demand "what's around me" query from a flat two-item list into:

1. **Around-Me sector answer** — max ONE item per sector. Not
   front/left/right/behind: the camera sees only forward ~120°
   (119.58° H per calibration; ToF narrower still), so the honest sectors
   are **front-left / front-center / front-right**, plus a fixed truthful
   coda when relevant: "behind you I can't see".
2. **Depth on repeat** — pressing/asking again within 10 s peels a layer:
   - Layer 1: labels + sectors ("person front-left; door front-right")
   - Layer 2: same items with ranges ("person, 2 meters; door, 4 meters")
   - Layer 3: VLM one-liner (existing `vlm.describe` path, "looking" ack)
3. **One responder** — F9, voice "what's around", and the future helmet
   tap-gesture all call a single `around_me(layer)` function. Today they
   are already half-unified (voice sets `voice_around = True`, consumed by
   the F9 block) but the answer logic lives inline in the frame loop.

## Evidence

- **The block to refactor** — `cv_fusion.py` lines ~1122–1150: the F9
  handler. Current behavior: take the two nearest ranged detections
  (`sorted(...)[:2]`), speak `"{nm} {direction_word(az)}, about {m} meters"`,
  fall back to nearest ToF `alert_zones` obstacle, else "There is nothing to
  call out right now". Queued via `speech_next = (text, f"QUERY{now}", 0,
  "query", now)`. Problems: no sector coverage (both items can be the same
  direction), ranges always spoken (verbose for a first glance), logic
  trapped inline.
- **Entry points already converge** — `voice_around` flag (line 756) set by
  voice dispatch `vc == "around"` (line ~1398), consumed at line 1126
  `if (f9_now and not f9_was_down) or voice_around:`. Unification is a
  refactor, not new plumbing.
- **Two-tier verbosity precedent** — the F9 comment itself cites "the Apple
  two-tier verbosity pattern"; MASTER-SYNTHESIS tier engine: silence
  default, query tier on demand, numbers allowed in query context only.
- **VLM layer exists** — key `v` path (line ~1413): `vlm_mod.describe` on
  `vlm_frames` with sensor context and `_say_q` speak callback, single-flight
  via `vlm_mod.busy`. Layer 3 is a call into this, not new code.
- **Sector honesty** — camera FOV 119.58° × 63.12° (calibrated); nothing in
  the system senses behind the wearer. Research on BLV query UX
  (vlm-integration-2026-08-22.md): users want "minimum viable information";
  hallucinated/overreaching answers erode trust — claiming knowledge of
  "behind" would be exactly that.

## Design

### `around_me(layer)` — one responder, module-level in cv_fusion main scope

Inputs it closes over (already in the frame loop): `dets`, `zones`/
`alert_zones` (with cached `zn["az"]`), `pixel_azimuth`, `_say_q`,
`vlm_frames`, `vlm_mod`.

- **Sectorization**: azimuth thirds of the camera FOV —
  front-left = az < −20°, front-center = |az| ≤ 20°, front-right = az > +20°
  (±20° matches the beacon's A-region feel; tune live). Candidate pool =
  ranged detections (rows < 3 association as today) plus, for sectors with
  no labeled det, the nearest `alert_zones` ToF obstacle in that sector
  ("obstacle"). **One item per sector: nearest wins.** Order spoken
  left → center → right (consistent scan order beats nearest-first for a
  mental map).
- **Layer 1 (labels)**: "person front-left; door front-center". Hedge low
  confidence with "maybe" (existing `CONF_HEDGE`). Empty: "nothing close in
  front". Append "behind you I can't see" on layer 1 when at least one
  sector is reported; omit it on the empty answer ("nothing close in
  front" already scopes the claim). Terse, no ranges.
- **Layer 2 (ranges)**: same snapshot re-spoken with ranges: "person
  front-left, about 2 meters; door front-center, about 4 meters". Reuse the
  1 m / whole-meter phrasing from the current block (lines 1137–1139).
  **Snapshot rule**: layer 2 re-answers over the items captured at layer 1
  (stored in `around_state`), re-ranged from live data when the same
  tid/name is still visible — repeat must feel like "more about THAT", not
  a re-roll.
- **Layer 3 (VLM)**: exactly the key-`v` path: `_say_q("looking")` then
  `vlm_mod.describe(list(vlm_frames), "Describe what is ahead.",
  sensor_ctx=..., speak=_say_q)` on a daemon thread; respect
  `vlm_mod.busy` ("still working"). A 4th press within the window wraps to
  layer 1 with a fresh snapshot.
- **Repeat window**: `around_state = {"t": 0.0, "layer": 0, "items": []}`;
  a trigger within `AROUND_REPEAT_S = 10.0` of the last increments layer,
  else resets to layer 1. Timestamp on trigger, not on speech end (simpler;
  10 s is generous).

### Trigger unification

- F9 edge-detect stays where it is but its body becomes
  `around_me_trigger()` (bumps/reset layer, calls `around_me`).
- Voice: `vc == "around"` sets `voice_around = True` exactly as now; the
  consumer calls `around_me_trigger()`.
- Future tap: whatever detects the tap (IMU transient) just calls
  `around_me_trigger()` — zero further wiring. Document this contract in a
  comment above the function.

## Implementation steps

1. `cv_fusion.py` — constants near the tier-engine block (~line 349):
   `AROUND_REPEAT_S = 10.0`, `SECTOR_EDGE_DEG = 20.0`.
2. `cv_fusion.py` — new `_around_snapshot(dets, alert_zones)` →
   `[{"name", "sector", "az", "rng", "tid"}]` (pure function of the frame's
   data; unit-testable) and `around_me(layer, items)` → text. Place next to
   `_say_q` (~line 856).
3. `cv_fusion.py` — `around_state` dict + `around_me_trigger()` beside the
   other mode state (~line 755); replace the body of the F9 block
   (lines ~1126–1149) with a call; keep the `voice_around` flag consumption.
4. `cv_fusion.py` — layer 3: extract the key-`v` VLM launch (lines
   ~1413–1426) into `_vlm_ask(question, hand=False)` so layer 3 and the
   `v`/`h` keys share one implementation (they drift otherwise).
5. HUD: brief `AROUND L2` putText for 1 s after each answer (dev aid).
6. `docs/DEVLOG.md` entry per project convention.

## Test plan

- **Unit**: `_around_snapshot` with synthetic dets/zones — one item per
  sector, nearest wins, ToF-only obstacle fills an empty sector, hedging at
  conf < CONF_HEDGE. Layer text for 0/1/3-sector cases.
- **Bench**: stand facing a person-left / chair-center scene: press F9 →
  labels only; press again ≤ 10 s → same items with meters; third press →
  VLM sentence ("looking" first). Wait 11 s → press → back to layer 1.
- **Equivalence**: voice "helmet … what's around" and F9 produce identical
  text for the same scene (assert same code path via log).
- **Honesty**: empty room → "nothing close in front" (and no fabricated
  "behind" claim); sensors lost → existing "sensors lost" tier still fires
  independently.
- **Non-blocking**: layer 3 never stalls the frame loop (thread), and a
  hazard directive preempts any layer's speech (query tier already yields —
  verify with a walk-toward-wall during an answer).

## Risks

- **Snapshot staleness** — layer 2 speaks 10-s-old items if the user turned
  away; mitigate: re-range live by tid/name, drop items no longer visible
  with "…gone" omitted silently (terse > complete).
- **Sector edges flapping** for an object near ±20°: harmless here (single
  utterance, not a stream), so no hysteresis needed — note it and move on.
- **VLM single-flight collision**: layer 3 while a `v`-key query runs →
  "still working" (existing busy guard covers it once step 4 unifies the
  path).
- **Repeat window vs speech duration**: a long layer-2 answer plus TTS at
  240 wpm could eat ~5 s of the 10 s window; if repeat feels tight in
  testing, restart the window when speech ends (speech_worker knows; add a
  `last_query_done` stamp) — deferred until felt.

## Effort

- Snapshot + responder + layer state: **2–2.5 h**
- F9/voice refactor + VLM extraction: **1–1.5 h**
- Bench testing + phrasing tuning: **1–1.5 h**
- **Total: ~4–5 h** (one session).

## Dependencies

- None new. VLM layer needs the NIM key + connectivity (already required by
  `v`/`h`); layers 1–2 are fully offline.
- Future tap-gesture is a consumer of this API, not a dependency.
- Independent of PLAN-find-by-text.md; if both land, key `f` and mode
  exclusivity interactions should be smoke-tested together.
