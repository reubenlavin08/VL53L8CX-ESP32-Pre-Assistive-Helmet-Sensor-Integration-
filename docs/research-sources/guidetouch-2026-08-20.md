# GuideTouch (arXiv:2601.13813, Skoltech, Jan 2026) — review — 2026-08-20

You flagged this PDF. Directly relevant: **2× VL53L5CX (our sensor's
predecessor) + ESP32 + 4 vibrotactile motors**, scarf-worn on
shoulders/chest, ~$100 BOM, 500 g, 12 h battery. No camera by design
(they call YOLO-class compute "bulky" — our laptop/Jetson path
sidesteps their constraint).

## What validates our decisions

1. **Their n=28 blind needs-interview ranks the same three gaps we
   prioritized**: (a) head-level hazards — "most frequent and
   dangerous," (b) drop-offs/ground risks (manholes, stairs), (c) thin
   objects (poles, bollards). Matches our head-clearance ✅, drop-off
   carve-out, and the CLOSEST-target-order fix for thin objects.
2. "More than 40% of blind individuals report head-level injuries or
   falls every few months" (their framing of the UCSC survey — same
   source lineage as our 13%/month stat).
3. Their interviews: replacing the cane is "highly undesirable" —
   third independent confirmation of your cane-alongside ruling.
4. **Haptic vocabulary must stay small — now with numbers**: pattern
   recognition 92.9% for 1–2 motor patterns but **78.4% when 3–4 motor
   combos are included**; errors concentrate in complex patterns
   (ANOVA p<1e-6). Blind users: 93.75% on primary directional cues.
   → Rule for our 3 temple motors: **never fire 3-motor patterns as
   vocabulary; ≤2 simultaneous, and prefer 1.**

## Stealable ideas (→ IDEA-BANK)

- **Drop alarm**: collar clip + buzzer — if the device falls off, it
  beeps (3–4 kHz) so a blind user can find it. Trivially cheap, real
  problem (a dropped helmet is invisible to its owner).
- **Vertical ToF splay**: their two sensors pitch 30° apart → 90°
  combined VERTICAL field (knee 30 cm to head 160 cm at just 50 cm
  standoff). Ours are yawed ±22.5° horizontally. A future third sensor
  (or re-aim experiment) could buy the same vertical coverage for the
  head-clearance + drop-off missions.
- **Rain: spinning optical cover** (3000 rpm BLDC centrifugal
  self-cleaning; beat ultrasonic + vibration in their tests, 18/20
  droplets cleared) — clever but **70 dB at head level**; our $5
  hydrophobic-coating + brim idea remains the sane version. Noted as
  the only tested-working active option.
- Detection floor math: obstacle needs ~30% of a zone; 4 cm object
  detectable at 1 m (useful cross-check for our thin-object math).

## Their weaknesses (our openings)

Static-condition lab evaluation only (no walking trials); no camera →
no labels, no guidance, no text; 4×4-era sensor; no head protection
geometry (chest-worn misses the "duck!" case); no spatial audio.

## References worth chasing later

- Xu 2023 "Intelligent Head-Mounted Obstacle Avoidance Wearable"
  (Sensors 23:9598) — head-mounted prior art, check against our
  novelty claims.
- LLM-Glasses (arXiv:2503.16475) + HapticVLM — same lab's VLM+haptics
  line.
- Gao 2025 Nature Comms cross-modal wearable (10.1038/s41467-025-58085-x).
