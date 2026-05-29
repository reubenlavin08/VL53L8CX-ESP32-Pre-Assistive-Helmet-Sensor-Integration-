# Directional haptic mapping research — verified sources

**Date:** 2026-05-28
**Question:** how to map 4×4 sensor zones (4 columns) onto 3 head-mounted ERM motors (LEFT temple GPIO 16 / CENTER forehead GPIO 7 / RIGHT temple GPIO 15) for the v11 column→motor mapping work.
**Verification policy:** every claim below is tied to a primary source URL/DOI that was fetched and confirmed during the 2026-05-28 research pass. Where the source was paywalled / 403'd, that's noted explicitly. Do NOT cite a paper from this doc without re-checking the URL.

---

## 1. Multi-motor concurrent firing has direct precedent

**GuideTouch — arXiv 2601.13813.** 2× VL53L5CX + ESP32 + 4 ERM motors on shoulders/neck. Quote: *"the device activates the set of motors corresponding to all dangerous directions"* when an obstacle spans multiple zones. Exact match for our approach #1 (hard regional mapping + concurrent firing).

**Ghizzi et al., Nat. Commun. 16:2857 (2025)** — DOI [10.1038/s41467-025-58085-x](https://www.nature.com/articles/s41467-025-58085-x), open-access mirror [PMC11933268](https://pmc.ncbi.nlm.nih.gov/articles/PMC11933268/). 3 coin motors at forehead + L/R temples mapped to −60° → +60° horizontal FoV. The paper does NOT specify the zone-to-motor algorithm but the geometry implies one-motor-per-sector hard regional mapping. Distance encoded via frequency (200 Hz <3 m, 150 Hz ≥3 m), not amplitude — not directly applicable to our ERM PWM approach since coin motors have very limited frequency control.

**WOAD GitHub** — [github.com/MMCNJUPT/WOAD](https://github.com/MMCNJUPT/WOAD). Repo exists but does NOT contain the motor driver / zone-to-motor code. Only contains video compression / RL / FPGA / Android dirs.

---

## 2. Concurrent multi-motor firing degrades comprehension — argues for dominance weighting

**Zegarra Flores et al., arXiv 2201.04453.** 25-motor (5×5) haptic sleeve, 3D camera input, depth downsampled 1:1 to motors.
- **Single-motor identification accuracy: 98.6 %**
- **Multi-motor / multi-directional pattern accuracy: 70 %**

Strongest empirical evidence found that firing 2+ motors at full duty simultaneously degrades comprehension. This is the basis for the **dominance weighting** refinement adopted on top of approach #1: when 2+ motors would fire, the most-urgent stays at full computed duty; others scaled ×0.7. Reduces the "wall of vibration" failure mode.

PDF body was binary-unreadable via WebFetch; abstract numbers confirmed across multiple secondary indexes.

---

## 3. Squared PWM curve is well-supported for *alerting* (vs continuous tracking)

**Verrillo, Fraioli & Smith, "Sensation magnitude of vibrotactile stimuli," Perception & Psychophysics 6(6):366–372, 1969.** DOI [10.3758/BF03212793](https://link.springer.com/article/10.3758/BF03212793). Springer redirected to auth wall — confirmed only via secondary citation. Result: Stevens' power-law exponent for vibrotactile perception ≈ **0.89**. Perception grows *slower* than physical amplitude.

**Implication for design:** a squared duty curve (`duty = max × (1 − ratio)²`) *amplifies* the perceived near-vs-far gap, which is desirable for urgency-coded alerting. This is the same curve already used by the buzzer (`BEEP_CURVE_SQUARED`).

**Counter-evidence from continuous tracking:** Park et al., Sci. Rep. (2025), s41598-025-11436-6. Found Linear mapping best for vibrotactile in a circle-tracking task. Behind Nature auth — only abstract-level finding retrieved. Tracking ≠ threat alerting, so the squared choice for our use case still holds.

**Caveat:** Verrillo used sinusoidal shakers on the thenar eminence, NOT ERM coin motors on the head. The 0.89 exponent may not transfer exactly to our setup. Worth refining after walk tests.

---

## 4. Funneling illusion is NOT a problem at our motor separation

**Kaul et al., "Vibrotactile Funneling Illusion and Localization Performance on the Head," CHI 2020.** DOI [10.1145/3313831.3376335](https://dl.acm.org/doi/abs/10.1145/3313831.3376335). ACM returned 403 — confirmed via abstract excerpts in multiple secondary indexes.

Key numbers:
- Two forehead actuators **2.5 cm apart** → fused into single stimulus *almost always*
- **5 cm apart** → fused only **20 %** of trials (i.e., users hear two distinct stimuli ~80 % of the time)

**Our forehead-to-temple separation is ~7–9 cm — comfortably above the fusion threshold.** Adjacent motors (LEFT+CENTER, or CENTER+RIGHT) will be perceived as **two discrete sources**, not as a smeared phantom point. This is *good* for the directional clarity goal and validates that the dominance-weighting refinement (which keeps two motors distinguishable) is meaningful.

**Cha et al., "Centralizing Bias and the Vibrotactile Funneling Illusion on the Forehead"** — [ResearchGate 280089423](https://www.researchgate.net/publication/280089423). Confirms region-dependent funneling characteristics. Secondary source.

---

## 5. Forehead has ~2× finer spatial acuity than temples

**Oliveira et al., "Spatial discrimination of vibrotactile stimuli around the head," IEEE Haptics Symposium 2016.** DOI [10.1109/HAPTICS.2016.7463147](https://ieeexplore.ieee.org/document/7463147/). IEEE Xplore returned HTTP 418 — confirmed via abstract excerpts in secondary indexes (ResearchGate, Semantic Scholar).

ERM motors, 5 mm inter-cell spacing, head-mounted array. Mean spatial discrimination precision:
- **Forehead (midline, 1 cm above eyebrows): 3.25 mm (SD 1.79)**, threshold < 5 mm
- **Frontotemporal: 6.15 mm (SD 4.92)**
- **Temporal (1 cm above ear): 7.26 mm (SD 4.71)**

**Implication for design:** CENTER motor sits on the most discriminating skin patch — its signal will be perceptually crisper than the side motors. Side motors may need higher peak duty to feel equally salient.

**Decision (2026-05-28):** SKIP per-motor acuity gain for v1, revisit after walk tests. Avoids tuning a number we have no empirical basis for. Worth measuring perceived intensity per-motor at matched duty during the first walk session.

---

## What I could NOT verify against primary sources

These claims are based on abstracts / secondary citations only — re-verify before relying on them:

1. **WOAD's exact multi-direction handling rule** — paper methods section doesn't say; the "hard regional" assumption is an inference, not a quote.
2. **Stevens 0.89 specifically for ERM coin motors** — Verrillo 1969 used sinusoidal shakers on different body site. The number is transferred by analogy, not direct measurement.
3. **Park et al. 2025 exact equations** — Nature paywall. Only the abstract-level "linear best for vibrotactile" finding was retrieved.
4. **Israr "Tactile Brush" CHI 2011 phantom-intensity equation** — every PDF mirror tried returned 403 / cert error. Secondary sources say it uses "square root of illusion position" but we couldn't see the primary equation.
5. **Oliveira 2016 acuity numbers** — IEEE Xplore HTTP 418. Quoted numbers are consistent across multiple secondary indexes but paper body not directly verified.
6. **Kaul 2020 funneling thresholds** — ACM 403. 2.5/5 cm thresholds confirmed only via abstract excerpts in indexes.

---

## Sources NOT applicable (checked and excluded)

- **PMC10708878 (Head-mounted ultrasonic ETA)** — uses single beep alert with re-arm, no per-motor directional mapping. Not relevant for our column→motor question. Full summary in `PMC10708878_summary.md`.
- **Ghaffari et al. 2025 Cogent Engineering** — wrist-mounted 2×3 ERM array, not head-mounted. Used `8/(n−2d)` inverse curve. Pilot users could NOT localize within a wrist (different from forehead/temple geometry, which Kaul shows IS localizable). Full summary in `Ghaffari_2025_summary.md`.
- **HapticESP32, HapticPatPat, senseshift-firmware** GitHub repos — VR projects, not ETAs.
- **AssistiveLabs/SynthSense** GitHub — augmented white cane (not head-mounted), iOS-dominant; no `/whitecane` firmware folder exists (HTTP 404 on direct fetch).

---

## Design decisions adopted (2026-05-28)

Based on the verified evidence above:

1. **Approach #1 — hard regional mapping + concurrent firing** (precedented by GuideTouch)
   - col 0 → LEFT motor (GPIO 16)
   - cols 1–2 → CENTER motor (GPIO 7)
   - col 3 → RIGHT motor (GPIO 15)
   - Each motor fires independently at the worst urgency in its column(s)
2. **Squared duty curve** `duty = max × (1 − ratio)²` (Stevens-law-supported for alerting; matches buzzer)
3. **Dominance weighting** when 2+ motors fire — most-urgent at full duty, others ×0.7 (Zegarra Flores 70% finding)
4. **Buzzer keeps firing alongside motors** — global urgency stays on audio channel, direction on haptic channel (no overlap in encoded meaning)
5. **No per-motor acuity gain for v1** — defer to walk test (Oliveira finding noted; gain factor would be a guess without empirical measurement on our specific hardware/mount)

## What's genuinely open in the literature

- No open-source firmware exists for any head-mounted ETA zone-to-motor algorithm. We are filling a gap.
- No paper empirically tests "fire all" vs "winner-take-all" vs "time-multiplex" for head-mounted ETAs. Open question.
- No primary source compares linear vs squared vs inverse PWM curves specifically for ERM threat alerting (only continuous tracking, Park 2025).
