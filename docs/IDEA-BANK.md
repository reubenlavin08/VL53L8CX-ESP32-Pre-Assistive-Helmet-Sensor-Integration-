# IDEA BANK — every candidate idea from all research streams — 2026-08-20

For triage: mark each ✅ build / ❌ skip / 🕐 later. Effort: S (<1 session),
M (1-3 sessions), L (project). Evidence: how strong the case is.
Sources in `research-sources/`.

## ⭐ PRIORITY VIEW (first pass, ordered by impact ÷ effort — you ordered this rework 2026-08-20)

**P0 — do first (unblock everything else):**
1. VL53L8CX sunlight bench test (S) — gates platform-edge + head-clearance
2. Target order → CLOSEST (S) — thin obstacles are invisible without it
3. IMU mount calibration (S, 2 min of your hands) — gates ALL IMU features
4. Hardware buys: 2nd narrow global-shutter camera + DIY bone-conduction
   drivers + V30i (~$78) — three research streams each demand one of these

**P1 — highest impact per session:**
5. ✅ Audio beacon (Soundscape-style spatial beacon; HRTF design locked) — M
6. Head-clearance in gravity frame (your ✅ rule, IMU-compensated) — M
7. GTFS-Realtime fusion (TransLink free) — S-M, no product does it
8. Glass detection: free experiment + firmware signature — S then M
9. ✅ Apple-style signage/label OCR engine (one engine → labels, signage,
   find-by-text) — M
10. Moving-vehicle interlock + blocked-path stop-and-alert (Glide's
    honest dead-end behavior) — S

**P2 — strong, after P1:**
11. ✅ Queue detection + progress (LineChaser pattern) — M
12. ✅ Empty seat (or "describe the seating" reframe — your call) — M
13. Crosswalk alignment BEV pipeline + Glide's spoken bookends — M-L
14. Terminal guidance to doors (U1 flagship) — L
15. Drop-off detection (the terrain carve-out) — M

**P3 — future / on-demand:**
16. 🕐 Route retrace (teach-and-repeat) — your ruling: interesting, not #1
17. 🕐 Companion beacon (person-following, narrowed) — your ruling: thin
18. Bus route OCR + bus-door guidance — L (after camera #2)
19. Fleet-style data flywheel telemetry schema — S to design, pays later

> **USER RULINGS 2026-08-20 evening** (see [[QA-2026-08-20]]):
> ✅ CV glass/mirror MATERIAL DETECTOR (lean on camera where ToF is blind)
> ✅ label-reading-in-hand · ✅ crosswalk alignment (build-intent + research
> running) · ✅ head-clearance rule: ≥10-15 cm above the TOP ToF ray ·
> 🔄 terrain + currency REOPENED (moved out of §G) · ⚖ facial recognition:
> considering, no longer privacy-blocked · **Privacy/regulatory = NOT a
> constraint this phase** · **Compute = NOT a constraint (GPU now, Jetson
> Orin future)** · cane always alongside · bone-conduction headset purchase
> pending (buying guide researching).
>
> **Round 2 (evening, indoor-nav feedback — see [[QA-2026-08-20-part2]]):**
> ✅ audio beacon (Soundscape deep-dive running) · ✅ queue detection ·
> ✅ empty seat · ✅ find-by-text ("Heinz") · ✅ Apple-style signage OCR ·
> 🕐 person-following (low pri) · 🕐 route retrace (future, not #1) ·
> **priority×impact rework ordered → PRIORITY VIEW above** · adopt
> Glidance's best features ([[glidance-deep-dive-2026-08-20]]) ·
> **echolocation-band ban VOIDED** (rare skill, helmet serves the same
> function) — ILD carriers may use 3–5 kHz; sparse sounds still required
> (band carries speech/traffic cues).

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

## H. From the implementation deep-dive (2026-08-20 late — see [[implementation-guide-2026-08-20]])

| Idea | Evidence | Effort |
|---|---|---|
| **Second boresighted ~38–50° GLOBAL-SHUTTER camera, manual exposure** | 3 independent analyses: fisheye can't do text (2.8 px @30 m) or last-metre precision; global shutter kills LED banding at source | **S-M (hardware buy)** |
| **VL53L8CX sunlight bench test** | Load-bearing unknown for platform-edge AND head-clearance margins; do BEFORE fusion code | **S — do first** |
| **Target order → CLOSEST** | Under STRONGEST a 3 cm branch at 2 m is silently invisible (background wins). Single highest-leverage setting change | **S** |
| **GTFS-Realtime fusion** (TransLink free API) | Turns open-set LED OCR into closed-set over ~5 candidates → >99% practical; `trip_headsign` = destination without reading it; NO product does this | **S-M** |
| **Head-clearance in GRAVITY frame** (IMU-compensated, not fixed top row) | Head pitch ±8° in gait = ±140 mm at 2 m; uncompensated error 190 mm > tall-user margin 130 mm under ADA doors. Muñoz 2025 dodged this — our novelty claim | M (refines the ✅ ruling) |
| **BEV-first crosswalk pipeline** (IMU gravity → bird's-eye → stripe fit → validators → latch + closed-loop haptic) | Veer is a random walk (open-loop useless); nobody does mid-crossing correction in traffic; CDSet-3434 + CDNet SSVM ready | M-L |
| **Moving-vehicle interlock** (never "step forward" unless ToF confirms zero closing velocity, N frames) | Separate auditable module; small code, disproportionate consequence | **S** |
| **Rideshare 1:1 verification scorer** (plate ≥5/7 chars decisive; fail-closed; night = manual exposure) | Plate voting 1.7%→44.7% over 5 frames; BC plates rear-only ⇒ post-stop confirm only; Uber has NO blind-rider location aid | M-L |
| **Platform-edge independent safety loop** (≤100 ms, ToF-only, edge orientation from which zones drop) | 76% of blind users have fallen off a platform; no published wearable baseline = publishable | M |
| **Bus door localization** (YOLO fine-tune, Vancouver's uniform fleet) | ZERO literature ("bus door" = 0 arXiv hits) — genuine novelty; low technical risk | M |
| **Door state from geometry** (wall-coplanarity via our two 8×8 slices, not RGB classifier) | Antonazzi: unseen-env door detectors are 13–48 mAP; domain adaptation is the game; "traversable now" is the right target | M (within U1) |
| **Storefront-vs-display-window ruleset** (ground-plane continuity across threshold + width + handle + OCR) | No published work — ours to invent | M |
| **Own-data capture loop** (Grounding DINO auto-label → hand-correct → nightly fine-tune) | 15% target-env annotations: 20→76 mAP. The loop beats any model choice | M |
| **DIY wired bone-conduction** (Dayton BCE-1 $76 or 2× $16.62 drivers + PAM8403, bonded to shell) + Soundcore V30i $44.99 for speech | SBC Bluetooth = 260 ms jitter → tick ~23° off during head turns; wired = 0 ms, known pose vs IMU. **NOT the Shokz OpenMove** | **S ($78 total)** |
| **4K camera upgrade** (32 px/deg) | 9× pixel area; makes keys/cards findable; both syntheses: sensor > algorithms | S-M (hardware) |
| **"Describe the seating"** (bearing + distance + honest occupancy confidence, beacon to user's pick) | Replaces "find empty seat"; StereoPilot: spatial audio 3× info rate, ½ grasp time; uncertainty as a feature | M |
| **Companion beacon** (re-find a companion who stepped away; voice-locked, ≤4 m, fails loudly) | CHI 2026 demand is "where are my people," not locomotion-following; honest note: a UWB tag beats vision here | M |
| **Drop-off detection** (ground-plane-absent, down ToF) | Canes miss 1-in-5 to 1-in-3 drop-offs; the one terrain carve-out; "degraded in full sun" | M |
| **Dropped-object mode, narrowed** (phone/wallet/bottle only; steps-near speech; separate az/el channels, not warmer/colder) | ObjectFinder 4.13/5; only phone clears the 30–40 px detection floor at 720p | M |
| **✅ Find-by-text** ("find Heinz" → spot the word in video, beacon to it) | YOUR idea 2026-08-20 — sidesteps the SKU database war; same OCR engine as labels/signage | M |
| **Glide crosswalk bookends** ("approaching road" → user decides → "crossing complete"; never interpret signals) | Glidance FAQ, validated by 8,000-user community | S (within crosswalk build) |
| **Glide target scan-and-select UX** (scan for doors/stairs/elevators/counters → pick → guide) | Their terminal-guidance UX, shipping | S (UX pattern for U1) |
| **Blocked-path stop-and-alert** (never push through; offer alternatives) | Glide behavior; honest dead-end state for our directive tier | S |
| **Stairs → guide to the RAILING** | Glide protocol detail; railing is the graspable target, not the stair | S (within guidance) |
| **Narrow-path callout** ("path narrows") | Glide behavior | S |
| **Intervention logging → data flywheel** (log 10 s around every F8/stumble/override; "flag that" bookmark; telemetry schema) | Glidance's fleet learning at fleet-size 1; see [[glidance-deep-dive-2026-08-20]] | S-M |
| **Drop alarm** (helmet falls off → it beeps so a blind owner can find it) | GuideTouch's clip+buzzer; a dropped helmet is invisible to its owner | S |
| **Haptic patterns ≤2 motors, prefer 1** (hard rule for the 3 temple motors) | GuideTouch n=22: 92.9% recognition at 1–2 motors → 78.4% with 3–4 motor combos (p<1e-6) | S (rule) |
| **Vertical ToF splay experiment** (re-aim/add a sensor for 90° vertical coverage, knee→head at 50 cm) | GuideTouch's 30°-splayed pair; serves head-clearance + drop-off missions | M |
| **Walkable-tunnel haptics** (silence when centered; motors only near the corridor walls) | .lumen patent's best mechanism — described, NOT claimed; kills haptic fatigue | **M — build-this-month** |
| **Pulse-count + burst-texture haptic vocabulary** (N pulses = semantics; ALB-style bursts = urgency; ≤2 motors) | Glidance patent patterns + GuideTouch's accuracy rule | S |
| **On-track reassurance ping** (faint periodic pulse: silence never means dead device) | Glidance patent; pairs with our "blind" callout | S |
| **Complexity-scaled cue intensity** (corridor width + turn angle drive intensity, not just distance) | .lumen path-complexity score | M |
| **0.3 m predicted-trajectory gate** (suppress "clear" if a moving track will cross the corridor) | .lumen safety check; ByteTrack velocity already available | M |
| **Walk-once route record/replay** (IMU+camera odometry → beacon/tunnel replay) | Glidance learned-routes + .lumen milestones; = teach-and-repeat 🕐 ruling | L |
| **Panic/fallback button** (one input → guidance stops, safe orientation mode) | Glidance patent; we have GPIO + keys | S |
| **WA/CWA/NA ground classes** (walkable / conditional / non-walkable, not binary obstacle) | .lumen Live Map L3; fits our up/down sensor split | M |

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
- ~~Terrain narration / currency~~ — REOPENED by user 2026-08-20, then
  **research verdicts came back NO** ([[feasibility-pack-2026-08-20]]):
  terrain = wrong sensor (ToF range collapses to ~1 m in sunlight; black
  ice needs reflectance we don't have; hikers use poles not devices) —
  EXCEPT the drop-off carve-out below; currency = solved by free apps +
  117k free iBill readers, CAD/EUR/GBP tactile. Your call stands to make.
- **"Find me an empty seat"** — bag-on-chair kills it (backpack/handbag
  are COCO's two worst classes; FP = public humiliation = abandonment).
  REFRAME kept in §H.
- **Open-space person-following** — IDF1 75–80 ⇒ wrong identity ~20% of
  the time; the elbow beats it walking; a BLE/UWB tag beats vision
  anyway. REFRAME kept in §H.
- **.lumen's continuous 100 Hz haptic "reins"** — defensible alternative, conflicts with our
  evidence base; A/B someday, don't drift silently
