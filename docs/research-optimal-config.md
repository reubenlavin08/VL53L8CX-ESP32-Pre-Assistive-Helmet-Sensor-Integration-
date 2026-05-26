# Research: optimal VL53L8CX configuration for a helmet-mounted ETA

**Date:** 2026-05-26
**Goal:** decide the right `(resolution, freq, sharpener, target_order, NB_TARGETS)` for a single VL53L8CX mounted at 186 cm helmet height, pitched ~20° down, on a visually-impaired user walking 1.0–1.5 m/s. False negatives are dangerous; false positives are merely annoying.

This document collects everything I learned across (1) a data-re-analysis of my own v9 sweep, (2) ST's official documentation, (3) published academic literature, and (4) the commercial assistive-device market. Sources are cited inline; the raw agent reports are preserved in `research-raw/`.

---

## Headline finding

**There is no published peer-reviewed work on a head-mounted VL53L8CX wearable ETA for visually-impaired users.** The closest analogues are belt-mounted (Ghaffari 2025), single-zone VL53L1X helmet prototypes (Preprints.org 2025), or drone/robot multi-zone deployments. ST publishes no application note for this use case. My helmet sits in a real gap.

That means I cannot copy a config off the shelf. The choice has to be reasoned through from physics + analogous-platform data + my own empirical sweep.

---

## My decision (and what's now in firmware)

| Setting | Value | Rationale |
|---|---|---|
| `SENSOR_RESOLUTION` | **4×4** | Latency-dominated tradeoff (see Phase 1 below). My use case = binary alert + buzzer, NOT obstacle classification. Literature picks 8×8 because researchers want spatial detail for classification I don't need. |
| `RANGING_FREQ_HZ` | **30** (testing higher) | At 1.5 m/s walking, frame latency dominates measurement noise by 10–40×. The minimum reaction blind zone at our data's configs comes from the highest frame rate. |
| `RANGING_MODE` | **CONTINUOUS** | ST: *"max ranging distance and ambient immunity are better."* Advised for fast / high-performance use. |
| `SHARPENER_PERCENT` | **5** (ULD default) | My v9 sweep showed 0% effect on uniform surfaces. Default is the safe choice. |
| `TARGET_ORDER` | **CLOSEST** | At 30 Hz our timing budget is 33 ms (< ST's 100 ms STRONGEST-recommended threshold). For obstacle avoidance, CLOSEST is the safer error direction. ST's STRONGEST default exists for false-positive suppression at long budgets — doesn't apply to us. |
| `NB_TARGET_PER_ZONE` | **2** (was 1) | Every wearable VL53L5/8CX paper uses ≥2. Catches thin obstacles partially filling a zone (e.g. doorframe edge with open space behind). Subject to ST's 600 mm minimum target separation rule (UM3109 §4.10). |
| Per-row alert thresholds | **60 / 60 / 80 / 95 cm** (4×4) | My innovation, not in literature. Bottom rows look at body-level obstacles at oblique angles — their FoV exits before the obstacle reaches body proximity, so the alert needs to fire while the obstacle is still in view. Each row's threshold is set so the alert fires before the obstacle becomes invisible. |
| Beep urgency rule | **ratio = forward / row_threshold** | A row-3 obstacle at 70 cm forward (74 % of its 95 cm threshold) beeps faster than a row-0 obstacle at 50 cm forward (83 % of its 60 cm threshold). Absolute distance is misleading when thresholds differ per row. |

---

## Phase 1 — re-analysis of my v9 data through the wearable lens

I had 51 captures (17 configs × 3 distances) from the static foam-board sweep. Re-aggregated through a model that combines:

- **Reaction blind zone (cm)** = (frame period in s) × (walking speed in cm/s) + (human reaction time × walking speed)
- **4σ noise band (cm)** = 4 × per-zone σ (in cm) — the 95 % confidence width on distance reading

Both quantities are in cm of "things I get wrong", so they can be summed. The minimum total is the best config.

For 1.5 m/s walking + 0.5 s reaction time, at d = 48 cm:

| Config | σ (mm) | Frame ms | Reaction blind (cm) | 4σ noise (cm) | **Total (cm)** |
|---|---|---|---|---|---|
| B2 (4×4 / 10 Hz) | 0.90 | 100 | 90 | 0.36 | 90.4 |
| B5 (4×4 / 15 Hz) | 1.09 | 67 | 85 | 0.44 | 85.4 |
| **B8 (4×4 / 30 Hz)** | 1.52 | 33 | 80 | 0.61 | **80.6** |
| A2 (8×8 / 10 Hz) | 3.45 | 100 | 90 | 1.38 | 91.4 |
| A5 (8×8 / 15 Hz) | 4.19 | 67 | 85 | 1.68 | 86.7 |

**Insight:** the latency penalty (5–15 cm) is 10–40× larger than the noise penalty (0.4–1.7 cm). **Frame rate dominates noise for a wearable.** My earlier suspicion that 10 Hz might be too slow is confirmed.

Extrapolation: at 60 Hz @ 4×4, predicted σ ≈ 2.1 mm (√(freq) scaling), giving reaction blind ≈ 70 cm + 0.85 cm = ~71 cm — 10 cm better than 30 Hz. **60 Hz is worth empirical testing.**

Plots: `visualizer/plots/wearable_noise_vs_latency.png`, `visualizer/plots/wearable_score.png`. CSV: `visualizer/plots/wearable_score.csv`. Script: `visualizer/analyze_wearable.py`.

---

## Phase 2A — ST documentation deep-dive

**Bottom line: ST gives almost no use-case-specific guidance for wearables / fast-moving targets.** I read UM3109, the DS13754 datasheet, UM2884 (L5CX equivalent), and multiple ST community threads.

What ST does say:

- **Hard limits:** 60 Hz @ 4×4, 15 Hz @ 8×8.
- **Frame rate:** the only quantitative recommendation is *"avoid going below 5 Hz when measurements are taken at distances less than 5 cm"* — useless for me.
- **Ranging mode:** CONTINUOUS gives *"max ranging distance and ambient immunity"*; advised for fast / high-performance. AUTONOMOUS is for low-power.
- **Target order:** default STRONGEST. *"It is highly recommended to use the strongest target to avoid false positives when the timing budget is greater than 100 ms."* My 30 Hz = 33 ms → ST's STRONGEST argument doesn't apply; CLOSEST is fine for obstacle avoidance.
- **Sharpener:** default 5 % per UM3109 (one community post claimed 14 % in newer ULD; my local header doesn't define this constant — chip firmware sets it).
- **Multi-target:** compile-time `VL53L8CX_NB_TARGET_PER_ZONE` macro 1–4. **600 mm minimum separation between targets to be resolved as distinct** (UM3109 §4.10). Default 1.
- **Sunlight tolerance:** 4 m range in dark, 2.8 m at 5000 lux indirect daylight, much worse at >10 klx direct sun. Downward pitch helps because the sky is out of FoV.
- **Motion blur:** **not documented anywhere**. No formula, no Hz-vs-velocity guidance. Embedded `motion_indicator` plugin tracks per-zone motion intensity but doesn't give a "minimum Hz for X m/s target" answer.

What ST does NOT say (must be determined empirically):
- 4×4-vs-8×8 for moving targets
- NB_TARGET_PER_ZONE for cluttered indoor scenes
- CLOSEST vs STRONGEST at sub-100 ms budgets
- Helmet/wearable-specific geometry

---

## Phase 2B — academic literature review

Searched Google Scholar, IEEE Xplore, ArXiv, ResearchGate, PMC. **No paper found uses the VL53L8CX specifically on a head-mounted ETA.** The VL53L8CX is recent enough that most published wearable work uses the predecessor **VL53L5CX** (same architecture and API).

Relevant papers found:

1. **Ghaffari et al. (2025), Cogent Engineering** — belt-mounted, 2 × VL53L5CX at 90° offset, 8×8, multi-target enabled. n = 7 trial subjects. Wrist haptics chosen because pilot found head haptics uncomfortable.
2. **Preprints.org 2025 (202504.0678)** — head-mounted but uses three single-zone VL53L1X (not multi-zone). 81° composite horizontal FoV, 15–150 cm range, ±1 cm bench accuracy. Indoor static-target evaluation only.
3. **Niculescu et al., ETH `Matrix_ToF_Drones`** (2024) — most rigorous published characterization of VL53L5CX on a moving platform. 8×8 @ 15 Hz (datasheet max for full resolution). **Processing recipe: take the median of the center 4 pixels per column to reject motion noise.** Open source on GitHub. Explicit tradeoff statement: *"60 Hz at 4×4 vs 15 Hz at 8×8"* — they chose spatial detail.
4. **Müller et al., BatDeck (arXiv 2412.10048)** — explicit failure mode: ToF is *"heavily impaired by reflective surfaces and glass walls"*. Drove them to fuse ultrasonic.
5. **Basnet et al., MDPI Sensors 2026** — 12 × VL53L8CX aerial perception system. Most aggressive multi-VL53L8CX deployment in literature; not wearable but confirms L8CX as a viable obstacle-avoidance primary sensor.
6. **Borelli, Giovinazzo et al., ProxySKIN** — VL53L8CX in robotic skin. Explicitly discusses **"blind spots" between adjacent sensors** — direct warning for a single-sensor helmet build.
7. **Šindler 2025** — preliminary L8CX evaluation on a line-following robot. Static only.

**Patterns across papers:**

- **Resolution:** every wearable/moving paper picks 8×8 — but for spatial classification, not binary alerting.
- **Frame rate:** 15 Hz @ 8×8 is the default. For 1.0–1.5 m/s walking that's 7–10 cm per frame — adequate for static-target evaluation, but no paper actually tests pedestrian-pace dynamic obstacles.
- **Multi-target:** universally used in wearable papers; default 1 is considered insufficient.
- **Recurring failure modes:** glass / reflective surfaces, direct sunlight > 10 klx, inter-sensor blind spots.
- **No paper reports quantitative false-negative rate for moving pedestrians.** Almost all detection-rate data is for static obstacles at fixed distances.

**Gaps in the literature:**

- No head-mounted multi-zone VL53L5/8CX wearable for the visually impaired.
- No published study of frame rate vs detection latency at walking pace.
- No characterization of ground-plane false-positive rate for a downward-pitched (~20°) head-mounted sensor at ~186 cm.
- Outdoor / direct-sun wearable VL53L8CX results don't exist in the literature.

These are all questions my project naturally generates data for.

---

## Phase 2C — market / commercial survey

17 commercial / academic assistive devices reviewed. Sensor tech distribution:

- **Ultrasonic** dominates the under-$500 tier (Sunu Band $299, WeWALK ~$700, iGlasses ~$100, BuzzClip ~$249, IIT-Delhi SmartCane ~$50). All single- or dual-transducer.
- **Stereo IR depth cameras** dominate the premium tier (Biped NOA €3500, .lumen Glasses ~$3000+, Glide robot $1500 + subscription). All built on Intel RealSense-class depth modules.
- **RGB camera + AI** (OrCam $4500, Envision ~$3000, ARx ~$500) — these do not actually do obstacle avoidance; they're readers/recognizers.
- **Multi-zone ToF (VL53L8CX class) is essentially absent from shipping products.** Only academic prototypes use single-zone VL53L1X.

**Form factor distribution:**

- Cane / cane-attachment: 3
- Wrist: 1 (Sunu Band)
- Glasses: 5
- Chest / shoulder / vest / harness: 4
- **Head-mounted (helmet): zero commercial.** Only the 2025 Preprints.org academic prototype.
- Robot guide: 1 (Glide)

**Update rates:** Sunu Band publishes 30 fps; nobody else discloses a number. *"Real-time"* with no quantification is standard.

**Alert modalities:** haptic dominates (12 of 17 devices use vibration motors against skin). **No shipping device uses a buzzer the way this helmet does.** Worth considering a haptic-strap upgrade for v2 — buzzers can be ambient-noise-masked.

**Ranges:** ultrasonic devices cluster at 2–3 m effective (5–9 m marketing claims don't hold up to soft / angled targets per AccessWorld reviews). Camera-based systems claim 10–15 m.

**Reported failure modes:** ultrasonic devices systematically miss soft fabric, angled glass, and low-reflectivity dark surfaces (well-documented in independent reviews). ToF has different failure modes (sun saturation, very dark or specular surfaces).

### Gaps the helmet project fills

1. **Head-mounted form factor is empty commercially** — gives a high vantage and pitch control no wrist/chest device gets.
2. **Multi-zone ToF (16 or 64 zones) is unused commercially.** ~64× the spatial resolution of a Sunu Band at similar power.
3. **Different failure modes from ultrasonic** — a ToF helmet fail-complements existing ultrasonic canes rather than competing with them. Compelling as a *secondary* device.
4. **Drop / curb detection via per-row distance discontinuity** is a real capability ultrasonic devices can't do, and only Biped (€3500 stereo) currently offers.

---

## Recurring known failure modes I have to design around

Compiled across all three research phases:

1. **Glass / specular surfaces** — sensor sees through or off them. ETH's BatDeck team had to fuse ultrasonic to handle this.
2. **Direct sunlight > 10 klx** — SPAD saturation. Downward pitch helps (sky out of FoV).
3. **Inter-sensor blind spots** (when 2+ sensors are used) — coverage doesn't fill smoothly between sensors.
4. **Soft / dark / low-reflectivity surfaces** — weak return, status codes degrade to 9 or 10.
5. **Single-sensor FoV physics** — at 186 cm + 20° pitch, the bottom edge of the cone is 42.5° below horizontal. Anything at chest-and-below within 60 cm forward is **optically invisible** to the sensor regardless of any firmware tuning. Real fix is a second sensor; per-row thresholds buy partial coverage by alerting before the obstacle leaves FoV.

---

## What's empirically open (my project's contribution opportunity)

Things no published source has tested for this device class — opportunities to generate genuinely new data:

- Detection latency vs frame rate for a moving pedestrian at 1.0–1.5 m/s
- False-positive rate for the ground plane in a downward-pitched head-mounted sensor at typical walking height
- Outdoor / direct-sun behavior of VL53L8CX in a wearable context
- Comparative test of `NB_TARGET_PER_ZONE = 1 vs 2` for thin obstacles in cluttered indoor scenes (doorways, furniture)
- Per-row threshold approach (my innovation) — quantify how it reduces false negatives at body level

---

## Recipes worth borrowing

- **ETH cluster-based obstacle detection** (`Matrix_ToF_Drones/Firmware/src/tof_driver/ToF_process.c`, verified 2026-05-26): status-filter {5,9} + binarize at distance threshold + 8-connected DFS island detection + reject clusters smaller than `MIN_PIXEL_NUMBER`. The min-cluster-size step is what makes them resilient to single-pixel spikes. Their distance bands: REACT 1.4m → SLOW 0.7m → STOP 0.4m → FEAR 0.15m (drone, but layered structure is the pattern).
- **Nature Comms 2025 vibrotactile pattern**: 3 coin motors (2.7×10 mm) on forehead + temples, 200 Hz vs 150 Hz buzz frequency to encode <3m vs >3m. Achieves 100% collision avoidance at 320 ms total end-to-end latency. Frequency-coded distance > on/off pattern.
- **PMC10708878 head-mounted ETA pattern**: 9 ultrasonic sensors arranged in 3 rows on head, IMU quaternion to compensate head turns, single audio beep with 0.5 s re-arm. 1.5 m alert threshold for pedestrian use.
- **Biped's stereo drop-off detection** — 30 cm drop detection via per-row distance discontinuity. Doable on lower ToF rows.
- **AV multi-return LIDAR analogy**: first-return = CLOSEST, multi-return = NB_TARGET_PER_ZONE>1. Multi-return is the standard mechanism for "seeing past" partial obstructions (vegetation in forestry, doorframe in our use case). Combined with a min-cluster-size rule it's the well-trodden path.

---

## Source verification update — 2026-05-26

After the first research pass, I verified the most load-bearing claims against primary sources. Outcomes:

### Verified TRUE (read primary source)
- **UM3109 ST claims** — all quotes in Phase 2A above. Cross-checked against the local PDF I downloaded.
- **ETH `Matrix_ToF_Drones` repo exists and uses VL53L5CX.** Fetched `Firmware/src/tof_driver/ToF_process.c` directly. Saved at `docs/research-sources/ETH_ToF_process.c`.
- **Nature Communications 2025 paper** (`s41467-025-58085-x`) — real, March 2025, open access. Uses Synexens CS30 (not VL53L8CX), 6 FPS, 320 ms latency, 3 vibrotactile motors at 150/200 Hz, 100% collision avoidance.
- **PMC10708878** — real, head-mounted ultrasonic ETA, 9× HC-SR04 + 1× MaxSonar-EZ1 + IMU, 1.5 m alert threshold.

### Verified FALSE — corrections to retract
- ~~"ETH `Matrix_ToF_Drones` uses **median of center 4 pixels per column** to reject motion noise."~~ **FALSE.** I read the source code. There is no median filter anywhere in `ToF_process.c`. The actual ETH algorithm is DFS island detection + `MIN_PIXEL_NUMBER` cluster threshold (see "Recipes worth borrowing" above). The original research agent fabricated the median claim — possibly hallucinated from the median being a common motion-noise technique elsewhere.

### Could not verify (treat as unconfirmed)
- ~~Ghaffari et al. 2025 Cogent Engineering~~ — **NOW VERIFIED 2026-05-26 via PDF supplied by user.** See `docs/research-sources/Ghaffari_2025_summary.md` for full notes. Important corrections to prior claims:
  - 2× **VL53L5CX** (not L8CX), at 90° azimuth offset, belt-mounted at ~1m height. Confirmed.
  - **NB_TARGET_PER_ZONE is NOT enabled.** The earlier claim that "every wearable VL53L5/8CX paper uses ≥2 targets" is wrong — Ghaffari uses single-target. Doorway/multi-target remains unstudied in the wearable literature.
  - Wrist haptics chosen because **pilot found head haptics uncomfortable** — relevant warning for our helmet-rim haptic plan.
  - Indoor/outdoor split via `n` parameter (127 cm range indoor, 300 cm outdoor). Proportional PWM feedback, not binary alerts.
- **"AN5912" (VL53L5CX app note) and "AN6066" (VL53L8CX calibration app note)** — searched ST's site directly. **Neither document number appears in ST's catalog.** Likely fabricated by the prior research agent. Real VL53L8CX-specific app notes are AN5897 (PCB thermal), AN5945 (SATEL connection), AN6271 (water/liquid). UM3109 remains the authoritative user manual.

### Headline finding still holds
"No published peer-reviewed work on a head-mounted VL53L8CX wearable ETA for visually-impaired users." The Nature Comms 2025 paper is the closest analog (head-glasses-mounted, but uses Synexens CS30 not VL53L8CX). The helmet project is still in a real gap.

### Pattern lesson
Earlier research agent hallucinated three specific things (AN5912, AN6066, ETH median filter) with plausible-sounding numbers/labels. Going forward: **a claim about a specific document number or specific algorithm only counts after primary-source verification.** Web search of titles + abstracts is not enough.

---

## Below-chest coverage — what other people do (2026-05-26)

The single-sensor head-mounted helmet cannot see floor-to-chest within ~3 m due to FoV physics (see Recurring failure modes). The literature shows three approaches:

### 1. Move the sensor lower (Ghaffari solution)
**Mount on belt or chest at ~1 m, wide FoV.** At 1 m height + 65° vertical FoV, an obstacle 3.7 cm tall is detectable at 1.5 m forward (Ghaffari 2025). Trade-off: loses the head-height vantage that catches overhanging branches, signs, low ceilings, doorways from above.

### 2. Stack two ToF sensors with combined vertical FoV (GuideTouch solution)
**arXiv 2601.13813** — "GuideTouch": 2× VL53L5CX **vertically aligned at 30° relative angle** = combined 90° vertical FoV. Single shoulder/torso enclosure. Detects obstacles at knee level (30 cm) AND head level (160 cm) from 50 cm distance. Direct relevance to our project: this is the head + chest two-sensor configuration. We could use one helmet-mounted (current) + one chest-mounted with downward pitch, combined FoV covers floor to head.

### 3. Multi-row ultrasonic array (PMC10708878 solution)
**9× HC-SR04 in 3 rows on head + 1× MaxSonar-EZ1, IMU for head-turn compensation, audio beep with 0.5 s re-arm, 1.5 m alert threshold, <90 g total, ~$50 BOM.** Each ultrasonic has 15° cone — much narrower than ToF zones — but mounting 3 rows gives top/middle/bottom coverage from one head location. Decision tree classifier (98.68%) for obstacle-vs-noise. Limitation: ultrasonic misses soft/angled targets reliably.

### 4. Separation of concerns across multiple devices (literature pattern)
Several reviews mention three-device approaches: **cane = drop-offs/holes, handheld = far large obstacles, glasses = overhead.** WeWALK SmartCane 2 uses TDK SmartSonic ultrasonic at cane handle for multi-height. Trade-off: more cognitive load on user, more devices to charge/maintain.

### What none of them solve
**Indoor close-quarters without alert flooding.** Every paper either:
- (a) accepts more false positives indoors (safety-first, like Nature Comms 2025 explicitly states), or
- (b) reduces alert range indoors (Ghaffari: 127 cm indoor vs 300 cm outdoor via `n` param), or
- (c) requires the user to manually toggle modes (most ultrasonic devices).

There is **no published indoor-clutter-aware alert suppression algorithm** for these devices. This is a real open opportunity: a software classifier that recognises "currently in a tight indoor space" and de-prioritises non-collision-course obstacles. Could fuse with IMU walking-speed + heading rate to flag "user is moving slowly and turning" = "in tight space" = "raise threshold for alert suppression."

### Recommended path for our helmet (synthesizing the above)
Phase 1.5 (before camera): **add a second VL53L8CX at chest/sternum, pitched ~30° down.** Wire to same ESP32 via I²C address bridge (need a `LPn` toggle since both default to 0x29). Combined coverage replicates GuideTouch but at higher resolution (each 8×8 instead of analog). Total BOM <$25 incremental.

Alternative if cost/wiring matters: **one HC-SR04 at chest pointed straight down at ~45° forward angle** — covers floor + ankle level at <1 m forward. Single output, easy ADC read or echo timing on a GPIO. Misses everything ultrasonic misses (carpet, soft furnishings, low-reflectivity dark surfaces) but catches the geometric gap.

---

## Sources

### Phase 1 — my own data + plots
- `visualizer/measurements.summary.csv`
- `visualizer/raw_frames/*.csv` (51 captures)
- `visualizer/plots/wearable_noise_vs_latency.png`
- `visualizer/plots/wearable_score.png`
- `visualizer/plots/wearable_score.csv`
- `visualizer/analyze_wearable.py`

### Phase 2A — ST documentation
- [UM3109 (VL53L8CX ULD user guide)](https://www.st.com/resource/en/user_manual/um3109-a-guide-to-using-the-vl53l8cx-timeofflight-multizone-ranging-sensor-with-enhanced-ranging-performance-stmicroelectronics.pdf)
- [DS13754 datasheet](https://www.st.com/resource/en/datasheet/vl53l8cx.pdf)
- [UM2884 (VL53L5CX equivalent)](https://www.st.com/resource/en/user_manual/um2884-a-guide-to-using-the-vl53l5cx-multizone-timeofflight-ranging-sensor-with-a-wide-field-of-view-ultra-lite-driver-uld-stmicroelectronics.pdf)
- ST community: [outdoor motion tracking](https://community.st.com/t5/imaging-sensors/feasibility-of-vl53l5cx-vl53l8cx-for-outdoor-motion-tracking/td-p/845002), [VL53L8CX at 60 Hz](https://community.st.com/t5/imaging-sensors/vl53l8cx-at-60-hz/td-p/769220), [direct sunlight](https://community.st.com/t5/imaging-sensors/improve-efficiency-of-vl53l8cx-sensor-under-direct-sunlight/td-p/887110), [VL53L5CX outdoor](https://community.st.com/t5/imaging-sensors/vl53l5cx-outdoor-performance-or-a-suggested-alternative/td-p/832409), [sharpener](https://community.st.com/t5/imaging-sensors/vl53l5cx-should-i-change-sharpener-for-my-use-case-how-can-i/td-p/136426)

### Phase 2B — academic literature
- [Ghaffari et al., Cogent Engineering 2025](https://www.tandfonline.com/doi/full/10.1080/23311916.2025.2560974)
- [Head-mounted ToF preprint (Preprints.org 202504.0678)](https://www.preprints.org/manuscript/202504.0678)
- [ETH `Matrix_ToF_Drones`](https://github.com/ETH-PBL/Matrix_ToF_Drones)
- [Stargate (arXiv 2309.03678)](https://arxiv.org/html/2309.03678v2)
- [BatDeck (arXiv 2412.10048)](https://arxiv.org/html/2412.10048)
- [Basnet et al. MDPI Sensors 2026](https://www.mdpi.com/1424-8220/26/4/1140)
- [PMC10708878 — head-mounted ultrasonic ETA](https://pmc.ncbi.nlm.nih.gov/articles/PMC10708878/)
- [PMC10007677 — wearable obstacle detection review](https://pmc.ncbi.nlm.nih.gov/articles/PMC10007677/)

### Phase 2D — new sources (2026-05-26 verification pass)
- [Nature Communications 2025 — wearable obstacle avoidance for visually impaired](https://www.nature.com/articles/s41467-025-58085-x) — PMC mirror: [PMC11933268](https://pmc.ncbi.nlm.nih.gov/articles/PMC11933268/)
- [LIDAR Magazine — Multiple Return Multiple Data](https://lidarmag.com/2017/04/29/multiple-return-multiple-data/)
- [LIDARvisor — What is Multi-Return LiDAR](https://lidarvisor.com/what-is-multi-return-lidar/)
- ETH `Matrix_ToF_Drones/Firmware/src/tof_driver/ToF_process.c` — saved at `docs/research-sources/ETH_ToF_process.c`

### Phase 2C — market survey
- [Sunu Band](https://sunu.io/pages/faq), [WeWALK Smart Cane V2](https://www.tdk.com/en/featured_stories/entry_084-WeWALK-Smart-Cane-2.html), [iGlasses](https://www.rehabmart.com/pdfs/ambutech_iglasses.pdf), [BuzzClip](https://imerciv.com/), [IIT-Delhi SmartCane](https://assistech.iitd.ac.in/smartcane.php), [Biped NOA](https://biped.ai/en/user-manual), [.lumen Glasses](https://newatlas.com/wearables/dotlumen-ai-glasses-blind-independence/), [STRAP](https://www.strap.tech/), [Glide](https://glidance.io/product/), [OrCam](https://www.orcam.com/en/myeye2/specification/), [Envision](https://www.letsenvision.com/glasses/home), [ARx AI](https://arx.vision/products/arx-ai-gen1-5), [BrainPort](https://www.wicab.com/brainport-vision-pro), [Eyeronman](https://www.asme.org/topics-resources/content/wearables-help-the-blind-walk)
