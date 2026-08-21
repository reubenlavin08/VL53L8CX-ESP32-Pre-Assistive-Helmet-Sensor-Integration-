# IDEA BANK — every candidate idea from all research streams — 2026-08-20

For triage: mark each ✅ build / ❌ skip / 🕐 later. Effort: S (<1 session),
M (1-3 sessions), L (project). Evidence: how strong the case is.
Sources in `research-sources/`.

> **USER RULINGS 2026-08-20 evening** (see [[QA-2026-08-20]]):
> ✅ CV glass/mirror MATERIAL DETECTOR (lean on camera where ToF is blind)
> ✅ label-reading-in-hand · ✅ crosswalk alignment (build-intent + research
> running) · ✅ head-clearance rule: ≥10-15 cm above the TOP ToF ray ·
> 🔄 terrain + currency REOPENED (moved out of §G) · ⚖ facial recognition:
> considering, no longer privacy-blocked · **Privacy/regulatory = NOT a
> constraint this phase** · **Compute = NOT a constraint (GPU now, Jetson
> Orin future)** · cane always alongside · bone-conduction headset purchase
> pending (buying guide researching).

## A. Already built (for completeness — no decision needed)
- Silence-default engine, 60 s cooldowns, stale-drop (Soundscape constants)
- TTC terminal-buzz ticker + adaptive path cone (biosonar, 2 bug fixes)
- Two-item grammar, no numbers in walking speech; hedging ("maybe")
- Cane-blind-spot filter; person deprioritized; F8 hush; F9 query
- Brevity mode + trainer; directive commands ("step right"/"stop stop")
- Voice-guided ball-mount leveling; motor ID over WiFi; software+hardware mute
- Locked audio band (600/1250 Hz, −75 dB vs echolocation band)

## B. Audio & interaction

| Idea | From / evidence | On our stack | Effort |
|---|---|---|---|
| **HRTF spatial clicks** (sound comes FROM the obstacle) | Dad + Klatzky/Loomis (beats speech on time AND cognitive load); Paré 2021: blind users beat sighted controls, 30 min training | slab+sounddevice bank, design locked in hrtf doc | **M** |
| **Confidence = volume dimming** | Soundscape (their ONLY use of volume) | dim ticks/beacon when sensor/heading uncertain | S |
| **Distance low-pass filter** (muffled = far) | Soundscape "Behind" asset; Maimon 2024 (blind users learn it instantly) | one biquad on the tick | S |
| **3 pitch bands = elevation class** (ground/torso/head) | HRTF report; pitch-height mapping robust for blind users | part of spatial-audio build | S (with HRTF) |
| **Arrival earcon + mute** (target reached → distinct sound, then silence) | Soundscape 15 m arrival pattern | terminal-guidance completion cue | S |
| **Direction by timbre regions** (brighter = on-axis) | Soundscape 4-region beacon, readable in their source | alternative/complement to HRTF | M |
| **Interrogation interface** ("tell me more" follow-ups) | #1 requested interaction property (BLV studies) | F9 → layered depth: label → range → details | M |
| **Steps instead of meters** (user-calibrated stride) | Wayfindr + BLV preference; O&M teaches pace | stride constant + swap in phrases | S |
| **Suppress speech during conversation** (VAD gate) | BLV study P-quote; laptop mic | webrtcvad on mic input | M |
| **Scan-coaching mode** (tick as obstacle edges cross centre during head sweep) | Bat strobe groups + O&M scanning-training RCTs | IMU sweep detect + edge events | M |
| **Yield to user's own clicks** (mic detects click → device goes quiet) | White space — NO published device does this | mic transient detect; novelty claim | M |
| **Per-user ILD calibration pass** (5-min lateralization sweep) | Bone-conduction literature (skull transfer varies) | needed when bone conduction arrives | S |
| **Clock-face bearing option** (user-selectable vocab) | Preference split 7/15 clock vs 6/15 relative (Das 2025) | setting; brevity mode already has clock | S |

## C. Sensing & hardware

| Idea | From / evidence | On our stack | Effort |
|---|---|---|---|
| **B1 sync pin** — interleave the two ToF integration windows | Found in our own ULD driver (L8CX-only) | 1 wire + 1 API call; kills mutual interference | **S** |
| **Glass free-experiment**: 2 targets/zone vs a real glass door | Physics: 4% glass return may lose arbitration to the wall behind | config change + one test session | **S** |
| **Firmware glass signature** (plausible range + weak signal = suspect) | TOPGN (LiDAR intensity, +12.7% F-score) | uses signal rates we already stream | M |
| **Ultrasonic ranger** (TDK CH201 ~3.5 mm or MaxBotix $35) | 99.99% acoustic reflection off glass vs our 4%; covers glass+matte-black+sunlight; drone precedent arXiv:2510.06518 | I²C on existing bus; disagreement table = detector | M |
| **Hydrophobic cover coating + brim** | ToF's real rain failure is water ON the cover | $5 | S |
| **OV9281 global-shutter camera** (~$30) | Kills motion blur (worst detector corruption, −64% AP) | swap; recalibrate | M |
| **Foveated ROI processing** (full-frame low-res + crop where ToF says closing) | Event-camera research's one good idea | 5-10× compute saving, an afternoon | S-M |
| **IR projector/illuminator for low light** | .lumen ships 2 IR laser projectors | cheap IR LED floods; camera sees in dark | M |
| **mmWave radar** (rain-immune, coated-glass mirror) | Glidance-adjacent; V-band wearable antenna paper | DEFER — cheap modules have zero azimuth | L |
| **Barometer (BMP390)** for elevator/floor changes | 75%/97% floor-change detection | one I²C part | S-M |
| **Thermistor for ultrasonic temp compensation** | 0.18%/°C drift | with ultrasonic add | S |

## D. Guidance features (the utility roadmap, expanded with competitor steals)

| Idea | From / evidence | On our stack | Effort |
|---|---|---|---|
| **Terminal guidance to doors** + depth-verified openings | U1 flagship; All_Aboard 91% vs 52%; open patent space | detector fine-tune + servo loop + spatial audio | **L** |
| **Apple-style door attributes** (open/closed state, read the sign/handle text) | Apple Detection Mode (best door UX shipped) | staged detail on demand after door lock | M (after U1) |
| **Bus stop + route number OCR** | U2; users' #1 unmet transit pain | detector + OCR burst on bus-shaped boxes | L |
| **Queue end + progress** (LineChaser pattern) | CHI 2021, literally our sensors | person detection + depth + track | M |
| **Empty seat finding** | Users volunteered it; geometric not social | chair detection + depth-empty check | M |
| **Crosswalk ALIGNMENT (never go/no-go)** | 5 m drift over 22 m documented; Oko does state only | stripe orientation vs IMU heading | M |
| **Dropped-object mode** (head-aim floor search) | Tied-highest usefulness score; Meta-glasses precedent | look-down + small-object detect + guidance | M |
| **Teach-and-repeat route retrace** (Clew/GuideNav pattern) | GuideNav: vision-only, validated with guide-dog handlers | record landmarks on a walk, retrace later — NOT full SLAM | L |
| **Trajectory-prediction alerts** (warn only on collision COURSE, not proximity) | biped's core claim ("like a self-driving car") | ByteTrack velocity + own-motion → TTC per object | M |
| **Precision-Finding-style homing** (escalating haptic/audio as bearing aligns) | Apple UWB pattern, universally praised UX | terminal-guidance final meters | S (within U1) |
| **NaviLens code reading** | 30 m range, 160° angle, installed in transit systems | their SDK/spec on our camera = free venue infra where it exists | M |
| **Miniguide-style range presets** (0.5/1/2/4 m user-set) | Shipped, liked; context-dependent needs | CAUTION_MM as a setting/gesture | S |

## E. IMU (from the dedicated report — gated on mount cal)

| Idea | Evidence | Effort |
|---|---|---|
| **Pose-aware floor rejection** (expected-floor per zone from live pitch) | replaces crude row filter; kills look-down false alerts | S |
| **Speech gate during fast head turns** (>~100°/s) | unpublished in ETAs — novelty | S |
| **Tap-to-query** (chip's on-board tap detector) | replaces F9 in the field; helmet = good tap substrate | S |
| **Auto-silence in vehicles** (on-chip activity classifier) | 2 config calls | S |
| **Ground-plane bbox ranging** (d = h/tan(pitch+θ)) | ranges camera-only detections past ToF field | M |
| **Drop-off/stairs detection** (expected-floor differencing) | honest to ~2.5 m; distinguish no-floor from no-signal | M |
| **Head-as-gimbal obstacle memory** (2-5 s, "pole still on your right") | unpublished framing; rotation nearly free | M-L |
| **Camera↔ToF de-rotation + firmware timestamps** | 1.4 m misregistration at 3 m during scans | M |
| **Step-counter landmark odometry** ("about 30 m since the doorway") | ~1% head-worn count error | S |
| **Fall detection** (head placement validated 97%) | needs an alert path (phone) to matter | M |
| **Stumble logging as ground truth** (every stumble = a missed-alert label) | developer gold | S |
| **Gyro-drift test WITH motors running** | no published BNO085 data — publishable micro-result | S |

## F. Platform / process

| Idea | From | Effort |
|---|---|---|
| **Zenodo DOI defensive publication** (DEVLOG + calibration writeup) | Patent verdict: blocks others, costs an hour | **S** |
| **Rerun embed on the site** (scrub a real walk in-browser) | biped uses Rerun; near-zero competition | M |
| **Pi 5 + Hailo HAT untethered build** | TRL 4→6; parity with $1,500 products | L |
| **90-s demo video** (shot list locked in portfolio doc) | disclosure line, deliberate glass failure | M |
| **Fisheye-augmented detector fine-tune** | 0.283→0.698 mAP documented | M-L |
| **FP/hour as a first-class published metric** | WeWALK died by false positives | S |
| **Expert conversations** (UBC O&M prof, GTT, PTCB) + decisions log | credibility artifact; free | M |

## G. Rejected — with the reason (don't re-litigate without new evidence)

- **Faces/emotions/identity** — users' own verdict + third-party harm
- **Go/no-go crossing calls** — the one error that kills; ACB/NFB positions
- **Persistent recording / scene memory** — privacy blast radius, no demand study
- **Full indoor SLAM / venue mapping** — GoodMaps' lane, needs infrastructure
- **PDR breadcrumb return-path** — 9 m error from one head turn; heads lead turns
- **Continuous rich sonification (vOICe-style)** — 73 h training, zero adoption
- **Loudness = distance** — bats actively remove the cue; blind users bad at absolute distance
- **Stochastic resonance haptics** — wrong regime (our motors are supra-threshold)
- **Event cameras** — quote-only pricing, no pretrained detectors, ToF already gives TTC
- **Cheap radar now** — zero azimuth, sees through walls (false positives)
- **Standalone pedestrian callouts** — users explicitly reject (people as
  INPUTS to queue/follow/collision features stay)
- ~~Terrain narration / currency~~ — **REOPENED by user 2026-08-20**
  (terrain: rocky/trail niche; currency: research running)
- **.lumen's continuous 100 Hz haptic "reins"** — defensible alternative, conflicts with our
  evidence base; A/B someday, don't drift silently
