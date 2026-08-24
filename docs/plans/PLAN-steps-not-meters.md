# PLAN — Steps, not meters (user-calibrated stride distances)

Status: plan only, 2026-08-23. Implements the UTILITY-ROADMAP delivery
invariant: "CHANGE: distances in **steps** (user-calibrated stride), not
meters" (docs/UTILITY-ROADMAP.md §Delivery invariants), and the Phase U3
phrasing target "end of the line, left, about six steps".

## Goal

Speak walking-relevant distances as calibrated steps ("about six steps")
instead of meters. Steps are body-scaled: a blind pedestrian executes "six
steps" directly; "three meters" requires a mental conversion mid-walk. Keep
meters available in the stationary query context (F9) via a setting, because
F9 is an aiming/survey tool, not a locomotion cue.

## Evidence — where every spoken distance in cv_fusion.py originates

Audit of `camera/cv_fusion.py` (all spoken text goes through `speech_next` /
`_say_q`):

1. **`spoken_range(mm)` (line 565)** — the old "bare number = meters,
   half-meter steps, 'close' under 0.75 m" formatter. **DEAD CODE since
   tier-engine v2**: grep shows zero call sites (the v2 engine removed
   numbers from caution callouts — "No numbers -- the ticker carries
   proximity", line 1096-1097). It is the natural home for the new
   step formatter.
2. **F9 on-demand scene query (lines 1122-1149)** — the only autonomous-loop
   place that speaks numbers today: `"{nm} {direction_word(az)}, about
   {'1 meter' if m < 1.3 else f'{m:.0f} meters'}"` (lines 1138-1139) and the
   obstacle fallback `"obstacle {direction_word(az)}, about
   {max(1, round(zn['z']/1000))} meters"` (lines 1144-1145).
3. **Door scan announcement, `_door_scan()` (line 853)** —
   `f"door {i+1}, {hr} o'clock, about {m:.0f} meters"`. This is a WALKING
   context: the user is about to travel to the door.
4. **Not spoken, don't touch**: the VLM sensor context string
   `f"{d['name']} {d['range_mm']/1000:.1f}m"` (line 1419) is prompt text for
   the cloud model; on-screen overlays (lines 989, 1000) are sighted-observer
   UI. Directive/caution tiers speak no numbers at all (by design), so the
   ticker and tier engine are untouched by this plan.

## Design

**Stride constant.** `STRIDE_M`, persisted in `camera/stride_cal.json`
(git-ignored, like `vlm_log.jsonl` — add to `.gitignore`):
`{"stride_m": 0.68, "steps_counted": 15, "dist_m": 10.0, "t": "..."}`.
Default when the file is absent: 0.7 m (typical adult walking stride;
mark output hedged with "about" always). Loaded once at `main()` startup
next to the mount-cal load (line 690).

**30-second calibration** (no new hardware; two interchangeable protocols):

- *Known distance*: user stands at one end of a pre-measured path (e.g. a
  10 m hallway, tape-measured once). Press `k` (new key) → "calibration:
  walk your marked distance, press k when you arrive, counting steps" →
  walk → press `k` → the device asks nothing; user then presses digit keys
  or speaks the count? Too fiddly. Simpler: **count-steps-over-measured-path
  via CLI**: `python camera/cv_fusion.py --calibrate-stride` prompts in the
  console: "distance walked (m)?" and "steps taken?", writes
  `stride_cal.json`, exits. Done once per user, sub-30-seconds, zero
  in-loop UI.
- *Optional later upgrade*: the BNO085 step counter (imu-uses-2026-08-17.md
  Tier C item 13, ~1% count error head-worn) can count the steps
  automatically over the measured path — one `sh2_setSensorConfig` call —
  removing the manual count. Not in scope for v1.

**Conversion + phrasing rule** (replaces the body of `spoken_range`):

```
def spoken_steps(mm):            # rename/repurpose spoken_range (line 565)
    steps = (mm / 1000.0) / STRIDE_M
    if steps < 2:   return "right there"
    if steps <= 20: return f"about {int(round(steps))} steps"
    return f"about {mm/1000.0:.0f} meters"     # steps stop being countable
```

Whole steps only, always "about" (association coarseness + stride variance
make single-step precision dishonest). Above ~20 steps the count loses
meaning — fall back to meters (matches Tier C item 13's honesty note:
"'about 30 metres' honest, '31.4 m' not").

**Setting / toggle.** New CLI flag `--units {steps,meters,auto}`, default
`auto`:
- `auto`: door-scan announcements (walking context) → steps; F9 (stationary
  survey) → meters.
- `steps` / `meters`: force everywhere.
Runtime toggle: new key `u` cycles the mode and speaks it ("units: steps"),
wired into the key dispatch block (lines 1400-1503).

## Implementation steps

1. `camera/cv_fusion.py` line 565: repurpose dead `spoken_range()` into
   `spoken_steps(mm)` per the design above; module-global `STRIDE_M` with
   0.7 default.
2. `main()` near line 690 (mount-cal load): load
   `camera/stride_cal.json` if present, set `STRIDE_M`, print confirmation.
3. Add `--calibrate-stride` early-exit branch in `main()` (before camera
   open): console prompts, compute `dist/steps`, sanity-check 0.4-1.0 m
   (reject and re-ask outside that), write JSON, print result, exit.
4. Add `--units` argparse flag (near line 636) + `units` state variable +
   `u` key handler in the dispatch block (lines 1400-1503).
5. F9 block (lines 1138-1145): route both number phrases through a helper
   `spoken_dist(mm, context="query")` that picks steps/meters from the
   units mode + context.
6. `_door_scan()` line 853: same helper with `context="walking"` →
   "door 1, ten o'clock, about six steps".
7. `.gitignore`: add `camera/stride_cal.json`.
8. `docs/DEVLOG.md`: entry per the portfolio-documentation rule.

## Test plan

- Unit-style REPL check: `spoken_steps()` at 500/1400/4900/20000 mm with
  stride 0.7 → "right there" / "about 2 steps" / "about 7 steps" /
  "about 20 meters".
- Calibration flow: run `--calibrate-stride`, enter 10 m / 14 steps, confirm
  file contents and reload on next launch.
- Live: stand a measured 4 m from a door, run door scan → spoken step count
  should match a real walk to the door within ±1 step.
- F9 in `auto` still says meters; after pressing `u` twice (force steps),
  F9 says steps. F8/audio and tier engine unaffected (no numbers there).

## Risks

- Stride length varies with speed and clutter (short cautious steps indoors);
  a single constant is ±20% in practice. Mitigation: "about" hedging, whole
  steps, meters fallback past 20 steps. Note for the writeup, don't
  over-engineer.
- Users trained on the old meter phrases (just Reuben for now) — trivial.
- `spoken_range` deletion: confirmed no call sites, but re-grep before
  removing.

## Effort

~3-4 h total: 1 h formatter+setting, 1 h calibration CLI, 1 h wiring both
call sites + toggle, 0.5-1 h live test + DEVLOG.

## Dependencies

None on other plans. Synergy: the session logger (PLAN-fp-hour-intervention-
logging) should record the units mode per session so alert phrasing is
reproducible. Optional future: IMU step counter (firmware one-liner) for
automatic calibration and "about 30 steps since the doorway" odometry.
