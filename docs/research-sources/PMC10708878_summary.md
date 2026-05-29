# PMC10708878 — head-mounted ultrasonic ETA (deep summary)

**Paper:** "Intelligent Head-Mounted Obstacle Avoidance Wearable for the Blind and Visually Impaired", PMC10708878. Open access.
**Verification:** Two-pass WebFetch from NIH PMC, 2026-05-26.

## What they built
- **9× HC-SR04 ultrasonic + 1× MaxSonar-EZ1** in 3 rows on the head.
  - Top row: 4 sensors → "upper obstacles"
  - Middle row: 5 sensors including the MaxSonar → general / supplementary
  - Bottom row: implied 5 sensors → "lower regions"
- Each HC-SR04: 15° detection cone, 2 cm – 400 cm range, ~8.7 g
- MaxSonar-EZ1: 4.23 g, ~500 cm range (more expensive, more reliable)
- **Total sensor weight <90 g.** Processing on Raspberry Pi 4B (separate from head, bigger).
- Adafruit BNO085 IMU on head, outputs quaternion via I²C.

## How it decides
- 10,234 data entries collected from 3 sighted volunteers (NOT VI users) on a 15 m indoor corridor at 0.5 / 0.75 / 1.0 m/s.
- Decision tree (C4.5): **98.68% accuracy, 53 KB model, 0.42 s per 500 entries (~0.84 ms each).**
- Random Forest gets 99.74% but model is 2486 KB — too big for microcontroller deployment.
- Sampling rate >30 entries/sec → similar update rate to our current 30 Hz.
- Alert: simple beep, 0.5 s re-arm interval. 1.5 m alert threshold.

## What the IMU actually does
- Outputs 4-element quaternion (computed onboard the BNO085, so the Pi just reads it)
- Used by the decision tree as input features ("quat_j" and "quat_i" specifically called out as discriminating features)
- The model learned to use quaternion values to **suppress alerts when the user is turning their head** (so a wall passing through the side sensor briefly doesn't trigger an alert mid-rotation)
- **Algorithm not explicitly stated** — it's implicit in the trained decision tree. Not a hand-coded compensation.

## What works
- Multi-row arrangement gives top/middle/bottom coverage from a single head mount
- IMU-fused features measurably improve accuracy
- Lightweight decision tree deploys on microcontroller class hardware
- 9× cheap sensors ($1 each = $9) > 1× expensive sensor for spatial coverage on a budget

## What's missing / weak
1. **Tested only on 3 SIGHTED volunteers** — not VI users. Real-world clinical utility unproven.
2. **Indoor 15 m corridor only** — no outdoor validation, no cluttered scenes, no real-world tests
3. **No ground / drop-off detection** — system assumes flat floors
4. **No power consumption or battery life data**
5. **No total BOM cost figure**
6. **No discussion of mount form factor** (helmet vs cap vs glasses) — just "head-mount"
7. **Head-size variation** flagged as model-portability issue ("positioning of the sensor set against the subject's head is not guaranteed")
8. **Overhead obstacle detection** mentioned but not quantitatively validated
9. **IMU compensation algorithm not explicit** — embedded in trained model

## Direct lessons for our helmet
1. **3-row sensor arrangement gives single-mount coverage** that we currently lack. Even with one ToF, the GuideTouch pattern (two ToFs vertically offset) is the direct analogue.
2. **IMU quaternion as a model feature** instead of hand-coded compensation is an idea worth borrowing. When we have an IMU, we could train a small classifier on quaternion + per-row distances to learn "this looks like a real obstacle vs head-turn artifact".
3. **The 1.5 m alert threshold** at walking-pace pedestrian use lines up with our per-row thresholds (100-180 cm). Confirms the right ballpark.
4. **Decision tree (~50 KB) deploys easily on ESP32-S3.** When we want classifier-based alert suppression, this is the most practical model size.
5. **Cheap-sensor-array vs single-expensive-sensor**: their approach validates spatial-coverage-via-multiple-cheap-sensors. For us, if we go multi-sensor, ultrasonic + ToF hybrid is in the same spirit.

## What NOT to copy
- The 3-sighted-volunteer evaluation methodology — we need to do better when we eventually test
- The "indoor flat corridor only" testing scope — outdoor + cluttered is exactly where our helmet has to work
- Skipping power/cost analysis — we should report ours
- Hand-waving the IMU compensation — when we add an IMU, we should document the actual fusion math, not just train a black-box model
