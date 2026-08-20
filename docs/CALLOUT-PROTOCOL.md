# Callout protocol design — aviation-derived, two modes — 2026-08-16

Scope: how the narrator talks. Two selectable modes sharing one decision engine:
**PLAIN** (regular English, demos, first-time users) and **BREVITY** (learned
compact protocol for real sustained use, modeled on fighter/ATC communication).

Pending input: the BLV-features research agent (running) may adjust bearing
conventions (clock-face vs left/right) with user-preference evidence.

---

## 1. What aviation actually solved, mapped to us

| Aviation practice | Why it works | Our version |
|---|---|---|
| **BRAA fixed slots** (Bearing, Range, Altitude, Aspect) | Listener parses by position, zero grammar processing | Fixed order: `[WHAT] [BEARING] [RANGE] [ASPECT]`, never varied |
| **Directive over descriptive** (TCAS: "CLIMB CLIMB", not "aircraft below") | Under time pressure, tell the ACTION not the situation | Imminent tier speaks commands: "stop", "step left" |
| **Escalation tiers** (traffic advisory → resolution advisory) | Attention budget spent by threat level | 3 tiers: routine / caution / directive |
| **Word repetition = urgency** ("TERRAIN TERRAIN") | Urgency encoded in form, not volume | Directive words doubled: "stop stop" |
| **Brevity codes** (single words with exact meanings, learned once) | Seconds saved per exchange compound | BREVITY mode vocabulary (§4) |
| **Clock bearings** ("bogey, two o'clock") | Body-relative, 12 discriminable sectors | Optional bearing style; O&M already teaches clock language at the dinner table ("chicken at 6") |
| **Aspect** ("hot" = closing) | Closing target ≠ static target | "closing" suffix when range rate < −0.5 m/s |
| **Sterile cockpit rule** | No chatter during critical phases | Fast walking / turning = suppress routine tier entirely |
| **Alert tones precede voice** (TCAS chime) | Pre-cues attention, buys parse time | Short earcon before directive-tier speech only |

## 2. The three tiers (both modes)

| Tier | Trigger | Interrupt? | Cadence |
|---|---|---|---|
| **DIRECTIVE** | anything < 0.8 m in the path cone (±15°), or TTC < 1.2 s | immediately, cuts current speech | every utterance until cleared |
| **CAUTION** | obstacle/detection < 1.8 m, or closing fast | skips cadence floor (already built) | on change only |
| **ROUTINE** | identified object, stable, 1.8–4 m | no | ≥ 2 s cadence, once per object (hysteresis, built) |

Directive chooses the command by free-space: compare left vs right half-field
ToF means → "step left" / "step right"; neither free → "stop stop".

## 3. PLAIN mode (demo + onboarding)

```
routine:    "person ahead, 2 meters"
caution:    "obstacle left, 1 meter"     (earcon: none)
closing:    "person ahead, 2 meters, closing"
directive:  [tick tone] "stop stop"  /  "step right"
```
Current terse grammar is already 80% of this; add the aspect word + directive
tier + earcon.

## 4. BREVITY mode (learned, for real use)

Design rules: ≤3 syllables/slot, no fillers, numbers bare (meters implied),
bearing as clock hour ("ten" = 10 o'clock) or L/R sector, learned via the
built-in trainer (§6).

```
slots:      [WHAT] [CLOCK] [RANGE] [ASPECT?]
routine:    "man ten, three"            person at 10 o'clock, 3 m
caution:    "block twelve, one"         unlabeled obstacle dead ahead, 1 m
closing:    "man twelve, two, hot"      person ahead 2 m and closing
directive:  [tick] "break right" / "stop stop"
clear:      "clean"                     path clear again after a directive
link loss:  "blind"                     sensors stale >1 s (never silent-fail)
```

Vocabulary v1 (keep under ~15 words; 3-motor haptics research says small
vocabularies only):

| code | meaning | | code | meaning |
|---|---|---|---|---|
| man | person | | block | unlabeled obstacle (ToF-only) |
| car | any vehicle | | post | pole/thin vertical |
| dog | animal | | step | curb/level change (future) |
| hot | closing | | clean | path clear |
| blind | sensor loss | | break L/R | directive turn |
| stop stop | halt | | check L/R | caution-level look/lean |

## 5. Engine changes required (cv_fusion.py)

1. `MODE = "plain" | "brevity"` — key `b` toggles, `--mode` flag.
2. Tier classifier in the announce-picker (range, path-cone test, range-rate
   from the existing 1 s median history → TTC).
3. Directive tier: bypass queue AND current utterance — pyttsx3 can't cut
   audio mid-word cleanly, so keep directive utterances ≤2 syllables and let
   the ≤1 s tail ride; the earcon (winsound.Beep, built-in) fires instantly.
4. Aspect: range-rate = slope of rng_hist samples; "hot"/"closing" when
   < −0.5 m/s.
5. "clean" after a directive clears (one-shot, not repeated).
6. "blind" when both sensor ages > 1 s (red-team #18: silence must never mean
   safe).
7. Sterile-cockpit gate: IMU yaw rate (once IMU is rewired) or frame-diff
   proxy now — suppress ROUTINE while turning fast.

## 6. The trainer (portfolio gold, cheap to build)

`camera/callout_trainer.py`: flashcard drill — speaks a brevity callout, user
points/answers, score tracked; 10 minutes to fluency. This mirrors exactly how
pilots learn the codes, makes the two-mode design demonstrable to a judge in
60 seconds, and doubles as the demo script: run PLAIN for the audience, then
BREVITY to show expert throughput (utterance time drops ~60%: measured
"obstacle left, 1 meter" ≈ 1.5 s vs "block ten, one" ≈ 0.6 s at rate 240).

## 7. Build order

1. Tier engine + directive commands + earcon (PLAIN mode complete) — ~1 session
2. Range-rate/TTC + "hot"/"closing" + "clean"/"blind" — same session
3. BREVITY vocabulary + `b` toggle — trivial once 1–2 exist (string tables)
4. Trainer — ~half session
5. Sterile-cockpit gate — after IMU rewire

## 8. Open questions (waiting on BLV research agent)

- Clock-face vs left/right: which do blind users prefer? (O&M uses both.)
- Earcon design: is a tick tone acceptable or does it mask environmental sound?
- Should ROUTINE tier exist at all outdoors, or only on-demand ("what's ahead")?

---

## §9 — LOCKED audio-band constraint (2026-08-20, answers §8's earcon question)

Tick = 600 Hz, earcon = 1250 Hz, terminal trill = 600 Hz AM@22 Hz. Measured
in-band leakage into the 2–5 kHz human-echolocation band: **−75 dB (tick),
−70 dB (earcon)**. A "crisper" 3 kHz tone would sit at 0 dB — dead centre of
the band users' own clicks and echoes occupy (echoes arrive −27 dB below the
click; users defend +12 dB SNR at 4–5 kHz). **Never brighten these tones.**
Also: no sustained/noise-like textures (they deny binaural masking release);
sparse transients only. Cites: Thaler 2017, Castillo-Serrano 2021 — see
research-sources/biosonar-2026-08-20.md.
