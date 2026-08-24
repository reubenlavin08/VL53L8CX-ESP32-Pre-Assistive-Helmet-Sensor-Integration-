# PLAN — Spatialized proximity clicks (CONDITIONAL)

Status: plan only, 2026-08-23. Upgrade the mono TTC ticker to
direction-carrying stereo clicks. Scope deliberately tight: **azimuth pan
only** (ILD-primary), no elevation pitch bands in v1.

## Goal

The ticker currently says *how soon* (rate = K/TTC) but not *where*. Add
constant-power stereo panning so the click itself carries the hazard's
azimuth, exactly the way `beacon.py` already pans its beacon. Rate law,
terminal trill, standoff heartbeat, speech-muting: all unchanged.

## Evidence

- Current ticker: `cv_fusion.py` `ticker_worker()` (~line 523) plays mono
  WAVs via `winsound.PlaySound(..., SND_ASYNC)` — no pan possible. State
  arrives via `tick_state[0] = (ttc, near_path)` set in the tier engine
  (~line 1041); `ttc` from ~1.2 s of `path_hist`, rate clamped
  `TICK_RATE_MIN..MAX` with `TICK_K/ttc`, trill below `TTC_TERM_S`,
  heartbeat inside `STANDOFF_MM`. Tones built by `_make_tone` /
  `_make_trill` (600 Hz blip, amp 0.10; trill 22 Hz AM).
- Azimuth already exists per zone: the tier engine caches `zn["az"]`
  (calibrated `pixel_azimuth`, + = wearer's right) and computes
  `near_path = min(zn["z"] for zn in path)` — we just never kept WHICH zone.
- Pan pattern to copy: `beacon.py` `Beacon._cb` — persistent
  `sounddevice.OutputStream` (stereo float32, blocksize 1024) and
  constant-power pan `gl, gr = cos(th)*amp, sin(th)*amp` with
  `th = (az+90)/180 * π/2`, rear azimuths mirrored to the sides.
- Why ILD-primary: `docs/research-sources/bone-conduction-spatial-2026-08-20.md`
  — ITD is impaired and phase-corrupted through bone conduction
  (Stenfelt 2024, Ren 2025); the correct rendering is exaggerated per-side
  level difference. MacDonald 2006: BC azimuth localization ≈ headphones.
  (`hrtf-spatial-audio-2026-08-20.md`'s full HRTF adds little on BC —
  explicitly out of scope.)

## Design

- New shared state: `tick_state[0] = (ttc, near_path, az)` where `az` is the
  azimuth of the argmin path zone (the zone that produced `near_path`).
  One-line change at the tier-engine site: track the zone, not just the min.
- New `ClickStream` class (put it in `beacon.py` beside `Beacon`, or
  `camera/clicks.py`): persistent stereo `sounddevice.OutputStream`.
  - Pre-render the 40 ms 600 Hz blip and the 280 ms trill once as float32
    arrays (same synthesis as `_make_tone`/`_make_trill`, minus the WAV
    round-trip — keep amp 0.10 / 0.16).
  - Callback schedules the next blip `1/rate` seconds after the previous
    blip START; per-blip gains from beacon's constant-power formula with
    the latest `az`. Snapshot `az` once per blip (a click must not pan
    mid-click).
  - Exaggerate the ILD (BC doc's recommendation): map az through
    `az_eff = clip(az * 1.6, -90, 90)` before the pan formula — tune live.
  - API: `update(ttc, rng, az)`, `mute(bool)` (speech ducking), `close()`.
- `ticker_worker()` becomes a thin 20 ms loop that feeds `ClickStream` from
  `tick_state` and `speaking` — the winsound sleep-loop timing (which
  jitters by the sleep quantum anyway) moves into the audio callback where
  it is sample-accurate.
- Fallback: if `sounddevice` import or stream open fails, keep the current
  winsound mono path untouched (field laptop audio stack is not guaranteed).
  One code path behind `--mono-ticker` too, for A/B.
- Coexistence with `Beacon`: two independent OutputStreams is fine for
  sounddevice/WASAPI; beacon already ducks under speech, clicks mute under
  speech (`speaking`), and beacon guidance + ticker already coexist today.

## Implementation steps

1. `camera/cv_fusion.py` tier engine: replace
   `near_path = min(...)` with argmin over `path`, publish
   `(ttc, near_path, near_az)` in `tick_state[0]` (update the two writer
   sites: main loop and leveling-mode silence, plus the `audio_on` gate).
2. `camera/beacon.py`: add `ClickStream` (pre-rendered blip/trill, TTC rate
   law constants imported/duplicated from cv_fusion, constant-power pan with
   ILD exaggeration factor).
3. `cv_fusion.py` `ticker_worker()`: instantiate `ClickStream`, feed it;
   keep winsound branch as fallback + `--mono-ticker` flag.
4. Delete nothing else — `TICK_WAV`/`TERM_WAV` generation stays for the
   fallback path.
5. DEVLOG entry.

## Test plan

1. Bench, headphones: hold a hand at ~1 m, 45° left / centre / 45° right of
   the pod; walk it inward. Clicks must pan hard-left / centre / hard-right
   and accelerate identically to the current build (rate law untouched).
2. Pan-snap check: swing the hand across the field mid-approach — each
   individual click is single-sided (no mid-click smear), successive clicks
   step across.
3. Speech masking: trigger a caution callout during ticking — clicks mute
   while `speaking`, resume after.
4. Trill: close inside TTC_TERM_S — trill fires panned to the hazard side.
5. Fallback: uninstall/hide sounddevice → mono winsound path, no crash.
6. Field (bone-conduction headset): repeat 1 and confirm left/right is
   legible — this is the ILD-exaggeration tuning session (factor 1.3–2.0).

## Risks

- BC transcranial crosstalk at 600 Hz is near 0 dB (Stenfelt 2012) — the
  commanded ILD arrives compressed; mitigations: exaggeration factor, or
  raise blip frequency toward ~2.5–3 kHz where isolation is ~10 dB (test 6
  decides; frequency is one constant).
- Two audio streams + pyttsx3 SAPI on one WASAPI device: watch for device
  contention on the field laptop; fallback path covers it.
- `ttc` is computed from the PATH minimum while `az` is that zone's bearing —
  when two hazards straddle the path the argmin can flap left/right between
  frames. Cheap damping: only adopt a new `az` when it moves >8° or the
  argmin zone changes for 3 consecutive frames.

## Effort

~4–6 h total: 2 h ClickStream + wiring, 1 h bench tests, 1–2 h BC headset
tuning, 0.5 h DEVLOG.

## Dependencies

- `sounddevice` (already used by beacon) and the beacon assets untouched.
- No firmware, no hardware. Independent of the head-clearance plan; if both
  land, the duck directive still pre-empts via the existing speech tiers.
