# Ghaffari et al. 2025 — verified summary

**Source:** "An assistive haptic-based obstacle avoidance system for individuals with profound visual impairment", *Cogent Engineering* 12:1 2560974, DOI 10.1080/23311916.2025.2560974. Published 22 Sep 2025. Open access (Taylor & Francis/Informa UK).

**Verification:** PDF provided by user 2026-05-26. Prior research-agent claims about this paper were retro-confirmed against the actual text below.

## Hardware
- 2× VL53L5CX laser breakout boards (NOT VL53L8CX). 8×8 zones.
- 90° relative angle between the two sensors → combined 90° azimuth FoV (each is 45° horizontal × 65° diagonal).
- ESP32 microcontroller (Xtensa). ESP-IDF firmware in C (matches our stack).
- 750 mAh Lithium battery in sensor module (battery lasts several days).

## Mount + geometry
- **Sensor module worn on belt at ~1 m height** (NOT head/helmet).
- Justification: at 1 m sensor height + 65° vertical FoV, ground distance 1.5 m forward → minimum detectable obstacle height = 3.7 cm from floor. They explicitly do the math to show belt mount + wide FoV solves the floor-coverage problem mechanically.

## Sensor settings (what they actually use)
- Resolution: 8×8 (compile-time choice for higher spatial detail)
- Frequency: not explicitly stated as a number but implied "real-time"
- **NB_TARGET_PER_ZONE: not enabled / not discussed.** The "representation matrix" sent over the air is 8×8 single-target. So the universally-claimed "every wearable VL53L5/8CX paper uses ≥2 targets" claim from the prior research pass is **wrong** — Ghaffari uses 1.

## Alert / feedback design (the most useful part)
- **NOT a binary on/off alert.** PWM duty cycle on a vibrator is a smooth function of distance: `α = 8 / (n − 2d)` for d > (n−2)/2, else 0.
- `n` parameter is tunable per environment:
  - `n = 255` → max coded distance = **127 cm** (indoor)
  - `n = 601` → max coded distance = **300 cm** (outdoor)
- "Just noticeable" power level (~30 mW, 10% of max) starts at:
  - d = 90 cm (n=255 indoor)
  - d = 205 cm (n=601 outdoor)
- "Warning" power level (~150 mW, 50% of max) at:
  - d = 39 cm (indoor)
  - d = 88 cm (outdoor)
- ERM vibrator intrinsic freq 115 Hz, PWM carrier freq 89 Hz, max mech power ~300 mW.

## Haptic module
- 2 modules, one per wrist.
- 6 ERM vibrators per module in 2×3 array (2 cm horiz spacing, 4 cm vert).
- 8×8 zones from each sensor get downsampled into the 2×3 vibrator layout.
- **Wrist mount chosen because pilot found head haptics uncomfortable** — Reuben's plan for helmet-rim ERMs may hit the same problem; worth testing comfort early.
- Wireless 2.4 GHz radio between sensor and haptic modules.
- Vibrator battery: 3 h full-load (high power draw). Sensor battery: several days.

## Evaluation
- n = 7 visually impaired subjects, aged 50–78. Lecture hall path with chairs/tables.
- Median path time: 64 s with system vs 95 s without. p < 0.05 (significant).
- Collisions: median 1 vs 1 (not significant; trend in favour).
- Q4 (could distinguish left vs right wrist vibration): 7/7 scored 10/10. Perfect lateral discrimination.
- Q5 (could distinguish WHICH vibrator on same wrist): 3 scored 1, 1 scored 6, 1 scored 10. **Users mostly could not localise within a wrist.** Implication for our helmet ring: a 6-motor ring may be overkill — 3-4 directional motors likely sufficient.

## Lessons for the helmet project
1. **Mount location is the primary lever for vertical coverage**, not sensor settings. Belt mount + wide FoV solves the floor problem mechanically.
2. **Proportional feedback beats binary alert.** PWM duty cycle (or beep gap modulation) scaled by distance gives a smoother experience indoors than on/off thresholds. Our current `g_urgency_forward / g_urgency_threshold` ratio is the right direction but currently maps to beep gap with a simple linear function — Ghaffari's exponential-feel curve is worth comparing.
3. **Indoor vs outdoor needs different ranges.** They expose `n` as a user-tunable param to switch. We could expose `MAX_ALERT_CM` as a runtime knob.
4. **Multi-target per zone is NOT used by Ghaffari.** Reduces our urgency to enable it — the doorway problem may not have a published solution at all.
5. **Head haptics were rejected in pilot for comfort.** Test rim-mount comfort early before building out the 4-6 motor design.
