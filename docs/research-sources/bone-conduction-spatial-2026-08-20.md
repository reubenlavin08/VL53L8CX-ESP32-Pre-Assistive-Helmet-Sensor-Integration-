# Spatial audio through bone conduction — physics + verdict — 2026-08-20

Answers the personalized-HRTF question from the writeup you sent.
Condensed-verbatim from the research agent; core dB claims verified from
abstracts, memory-only items flagged.

## Verdict in one line

**Ear-scanning personalization buys ~nothing on our hardware.** It
personalizes pinna cues that bone conduction physically bypasses, for
elevation we encode with pitch bands and front-back we resolve with the
IMU. The scientifically correct "personalization" for BC is a **skull
calibration** — our 5-min per-user ILD sweep (already in IDEA-BANK) —
because transcranial attenuation varies by tens of dB between people.

## 1. Spatial audio through BC works (for azimuth)

- **MacDonald, Henry & Letowski 2006** (US Army Research Lab, Int J
  Audiol 45:595): HRTF-processed noise at 8 azimuths via bone vibrators
  vs headphones — "localization performance was found to be nearly
  identical for both audio systems." Verified. The strongest single
  answer: BC spatial audio works with conventional HRTF processing.
- Zeitooni 2016: binaural benefit via bilateral BC is real but ~half
  the dB benefit of air conduction. Verified.
- Stenfelt 2024 (Sci Rep): **ITD-based lateralization significantly
  impaired via BC.** Verified.
- Percepts are lateralized (in-head), weakly externalized — sufficient
  for an obstacle-direction display.
- Georgia Tech SWAN "bonephones" used BC spatial audio for blind
  navigation (memory, unverified).

## 2. Transcranial crosstalk — the real physics limit (verified numbers)

**Stenfelt 2012** (28 unilaterally deaf subjects, mastoid): median
transcranial attenuation = **3–5 dB below 0.5 kHz, ~0 dB at 0.5–1.8
kHz, ~10 dB at 3–5 kHz, ~4 dB at 8 kHz**; intersubject spread ~40 dB.

- Near-ZERO left/right isolation at 0.5–1.8 kHz — where our 400 Hz/1 kHz
  elevation bands sit. A commanded 10 dB ILD arrives much smaller at the
  cochleae.
- **Ren 2025** (Adv Sci): bilateral BC crosstalk causes wave
  interference AT the cochleae — lateralization violates the normal
  intensity rule; naive ITD is corrupted by phase superposition.
- BC crosstalk cancellation exists (Barnsley & Culling 2025, ~10 dB
  improvement, needs recalibration) — stretch option as fixed per-user
  filters.

## 3. Front-back confusion

Head movement virtually eliminates front-back confusion even with
generic HRTFs (Wightman & Kistler 1999; Begault 2001 found
individualized HRTFs gave NO significant improvement for speech —
memory-flagged figures). Our 100 Hz IMU puts us permanently in the
best case.

## 4. Rendering recommendation (updates the locked HRTF design)

1. **ITD = secondary cue only** (impaired + interference-corrupted on
   BC).
2. **Primary cue: exaggerated per-side ILD**, transducers as far
   forward/apart on the shell as possible.
3. **The 5-min per-user ILD calibration sweep is now load-bearing** —
   it directly measures the wearer's transcranial attenuation.
4. Full KEMAR/slab convolution is harmless and cheap — keep it, but the
   exaggerated ILD + calibration do the actual work.
5. Realistic azimuth resolution: 8 directions/45° cleanly demonstrated;
   maybe 20–30° with good rendering (estimate).

## ⚠️ OPEN DESIGN TENSION (flagging for you)

Best L/R isolation is at **3–5 kHz (~10 dB TA)** — but that is exactly
the **2–5 kHz human-echolocation band we locked as forbidden** (BC still
delivers to the cochlea, so it masks echo perception just like air
sound). Options to resolve empirically during the calibration sweep:
(a) keep carriers ~600 Hz and lean entirely on exaggerated ILD +
calibration (isolation ~3–5 dB); (b) move ILD carriers to **6–8 kHz** —
above the echolocation core, TA ~4 dB, still better than the 1 kHz
null; (c) per-user crosstalk-cancellation filters. Decide with data,
not taste.

Unverified-this-session: Wenzel 1993 percentages, Wightman/Begault exact
figures, Apple/Sony mechanisms, SWAN cites.
