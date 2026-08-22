# IDEA BANK — priority-ranked, expandable — rebuilt 2026-08-21

Every idea is a **collapsed dropdown** — click to expand for the what/why/
how. Ranked by priority (P0 → P3), best-first within each tier. Mark your
verdict on the title line: ✅ build / ❌ skip / 🕐 later. Effort: S <1
session · M 1–3 · L project. Sources live in `research-sources/`.

Legend: ✅ = you already ruled build · ⚖ = your call pending · 🕐 =
deferred with trigger · ❌ = ruled out (kept with reasons at the bottom).

---

## P0 — status (all resolved 2026-08-21)

> [!success]- ✅ IMU mount calibration — **DONE 2026-08-21**
> Voice-guided two-pose gravity calibration, verified all three axes,
> committed. Unlocks every IMU feature below (head-clearance, floor
> rejection, leveling accuracy, beacon tracking).

> [!note]- 🕐 VL53L8CX sunlight bench test [S] — deferred; trigger = before trusting any outdoor feature
> **What**: measure real max range indoors / shade / direct sun with a
> tape measure and cardboard target (15 min).
> **Why**: datasheet says range collapses 2.4 m (dark) → ~1 m at office
> brightness; sun is 10–20× brighter. Every outdoor warning distance
> (head-clearance 2 m, drop-off 2.5 m) assumes range we may not have.
> **Source**: [[platform-edge-safety-2026-08-20]], [[QA-2026-08-21]]

> [!note]- 🕐 CLOSEST vs STRONGEST target order A/B [S] — deferred; trigger = CV distances flapping
> **What**: firmware already runs CLOSEST. A/B = 20 s captures of a thin
> pole in front of a wall under each order; compare stability + pole
> visibility.
> **Why**: STRONGEST makes a 3 cm branch silently invisible (background
> wins); CLOSEST can flap on weak near returns. Multi-target mode can
> give BOTH: closest return for safety, strongest for stable CV ranges.
> **Source**: [[QA-2026-08-21]] §1, [[implementation-guide-2026-08-20]]

---

## P1 — highest impact per session (build next)

> [!note]- 1. ✅ Soundscape audio beacon — **BUILT, needs live camera test** [key `g`]
> **What**: lock a detected object; Soundscape's actual 4-region musical
> beacon (their MIT WAVs) leads you to it; arrival melody at 1 m.
> **Left to do**: first live test with camera + verify the lost-target
> IMU sign (marked in code — flip one sign if the beacon runs the wrong
> way when the object leaves frame).
> **Source**: [[soundscape-beacon-2026-08-20]], camera/beacon.py

> [!note]- 2. Head-clearance check in the GRAVITY frame [M] — your ✅ rule, done right
> **What**: warn when overhead clearance above the top ToF rays (in
> world coordinates, IMU-compensated) drops below your 10–15 cm margin.
> **Why gravity frame**: head pitch in normal walking is ±8° = ±140 mm
> at 2 m — more than the whole margin. Fixed "top row" is wrong at the
> definition level; prior art (Muñoz 2025) dodged this — it's our
> novelty claim. Alerts: first ≥2 m, hard 1.2 m.
> **Evidence**: 13% of blind people have head-level accidents monthly;
> cane AND dog users equally. ADA's 27–80 in band = "cane misses it,
> code says it shouldn't be there."
> **Source**: [[implementation-guide-2026-08-20]] §2

> [!note]- 3. Walkable-tunnel haptics [M] — .lumen's best mechanism, unclaimed
> **What**: a virtual corridor along your path; temple motors fire ONLY
> when you drift toward its walls. Silence when centered.
> **Why**: kills haptic fatigue vs continuous steering cues; described
> in .lumen's patent but NOT claimed — free to use. Fits our v11
> firmware directly.
> **Source**: [[patents-stripmine-2026-08-20]]

> [!note]- 4. GTFS-Realtime fusion [S-M] — cheapest huge win, nobody ships it
> **What**: TransLink's free live feed tells us which buses serve this
> stop and which is arriving NOW → open-set LED reading becomes picking
> between ~5 known strings (>99% practical accuracy).
> **Note**: with camera #2 ruled out, this powers stop-context +
> arrival announcements rather than long-range sign reading — still the
> backbone of any transit feature.
> **Source**: [[transit-gtfs-navilens-2026-08-20]]

> [!note]- 5. 🕐 Glass detection — DEPRIORITIZED by your ruling 2026-08-22
> **Your reasoning (sound)**: head-level glass that isn't also at cane
> level basically doesn't exist — glass walls/doors reach the floor,
> and the cane is always alongside. Collision risk ≈ handled.
> **What survives (small)**: glass still corrupts DATA — a pane can
> return the room BEHIND it (phantom far reading where a wall is) or a
> mirror can create phantom obstacles. Keep the cheap `target_status`
> filtering we already do; the full detector (CV segmentation, TOPGN
> signature, ultrasonic #36) waits for evidence it's needed.
> **Source**: [[ultrasonic-mmwave-glass-2026-08-20]], [[QA-2026-08-22]]

> [!note]- 6. ✅ Signage / label OCR engine [M] — one engine, three features
> **What**: PARSeq text recognition (15 ms/crop) beside YOLO. Powers:
> label-reading-in-hand (your ✅), close signage à la Apple (your ✅),
> and **find-by-text** ("find Heinz" — your idea) at ~0.5–3 m.
> **Limit**: camera #2 ruled out ⇒ close range only (a 15 cm sign
> character is readable to ~3–5 m on the fisheye).
> **Source**: [[transit-headsign-ocr-2026-08-20]], [[QA-2026-08-20-part2]]

> [!note]- 7. Moving-vehicle interlock + blocked-path honesty [S]
> **What**: (a) never emit "step forward" unless ToF confirms zero
> closing velocity N frames — separate auditable module; (b) when fully
> blocked: stop and SAY so, never push through (Glide's behavior).
> **Why**: small code, disproportionate consequence; the one error
> class that ends trust permanently.
> **Source**: [[implementation-guide-2026-08-20]] §3b, [[glidance-deep-dive-2026-08-20]]

> [!note]- 8. Per-user ILD skull calibration [S] — now load-bearing
> **What**: 5-min lateralization sweep through the bone-conduction pair
> measuring YOUR skull's left-right crosstalk (varies ~40 dB between
> people); sets the pan exaggeration.
> **Why**: this is the scientifically correct "personalization" for BC
> — ear-photo HRTF personalization buys nothing (BC bypasses the ear).
> **Source**: [[bone-conduction-spatial-2026-08-20]]

> [!note]- 9. On-track reassurance ping + pulse-count haptic vocabulary [S]
> **What**: faint periodic pulse = "system alive, path clear" (silence
> never means dead battery); N pulses = semantic channel (2 = hazard
> ahead, 3 = turn coming); anti-lock-style burst texture = urgency.
> **Rule**: ≤2 motors simultaneously, prefer 1 — recognition falls
> 93% → 78% with 3-motor patterns (GuideTouch, n=22, p<1e-6).
> **Source**: [[patents-stripmine-2026-08-20]], [[guidetouch-2026-08-20]]

---

## P2 — strong, after P1

> [!note]- 10. ✅ Queue detection + progress [M] — LineChaser pattern
> **What**: find the end of the line, "line moved, step forward," "you're
> next." Proven at CHI 2021 with exactly our sensors (camera + depth +
> person tracking).
> **Source**: [[QA-2026-08-20]], [[transit-bus-boarding-litreview-2026-08-20]]

> [!note]- 11. ✅ Empty-seat finding [M] — with the reframe decision open
> **What**: camera finds chairs, depth says which are empty, beacon
> guides. YOUR ✅.
> **The catch**: bags/coats on chairs are COCO's two worst detection
> classes — a false positive = sitting on someone's laptop. Research
> recommends the "describe the seating" variant (bearing + distance +
> honest confidence, you pick, beacon guides). Your call which version.
> **Source**: [[feasibility-pack-2026-08-20]] §4

> [!note]- 12. ✅ Crosswalk alignment [M-L] — BEV pipeline + Glide's spoken bookends
> **What**: bird's-eye rectify (IMU gravity) → stripe fit → geometric
> validators → LATCH heading at curb → closed-loop haptic correction
> across (veer is a random walk — open-loop pointing is useless past
> 4 m). "Approaching road" → you decide → "crossing complete."
> **The real project**: bearing precision (±3° needed); build the
> ground-truth rig first. Wet night = gyro-only fallback.
> **Never**: go/no-go calls. Alignment only.
> **Source**: [[implementation-guide-2026-08-20]] §4

> [!note]- 13a. ✅ Door UX ruling 2026-08-22: scan-and-select, never guess
> **Your concern**: "how does it know which door I want — don't guide
> me to random doors." **Answer**: Glide's shipped pattern — announce
> candidates ("two doors: twelve o'clock 8 m, two o'clock 15"), YOU
> pick, beacon locks. Signage OCR breaks ties. Full navigation stays on
> the phone (even Soundscape's creator delegates to Google Maps);
> helmet owns the last ~10 m only. **Research DONE 2026-08-22**: full
> build spec in [[last-meter-doors-2026-08-22]] — OSM entrances = bonus
> only (live query: downtown Vancouver <18% coverage, Dunbar ZERO);
> order candidates by destination bearing not distance; ≤3 + "more";
> spatialized terse speech; our multi-candidate list may out-do Glide's.
> **Source**: [[glidance-deep-dive-2026-08-20]], [[last-meter-doors-2026-08-22]]

> [!note]- 13. Terminal guidance to doors [L] — the U1 flagship
> **What**: detect door → ToF confirms real opening (depth behind) +
> range → beacon/haptics steer you to it. Door STATE from geometry
> (coplanar with wall = closed); hinge side from handle position; read
> the sign next to it (Apple's pattern).
> **Reality check**: unseen-environment door detectors are 13–48 mAP;
> our own capture loop (auto-label → correct → nightly fine-tune) is
> what makes it work: 15% local data took 20→76 mAP.
> **Source**: [[implementation-guide-2026-08-20]] §1

> [!note]- 14. Drop-off detection [M] — the one terrain carve-out
> **What**: down-ToF ground-plane-absent detection (stairs down, curbs,
> platform edges). Canes miss 1-in-5 to 1-in-3 drop-offs even with good
> technique.
> **Honest spec**: "extends cane drop-off coverage, degraded in full
> sun" (pending the sunlight test). False-positive discrimination
> (black mats, puddles) is the hard part, not detection.
> **Source**: [[feasibility-pack-2026-08-20]] §2, [[platform-edge-safety-2026-08-20]]

> [!note]- 15. Trajectory-prediction alerts [M] — biped's one good idea
> **What**: warn only on collision COURSE, not proximity — ByteTrack
> velocity + your own motion → per-object TTC; .lumen's 0.3 m
> predicted-trajectory gate as the threshold.
> **Source**: [[patents-stripmine-2026-08-20]], indoor-nav research

> [!note]- 16. Intervention logging → data flywheel [S-M] — Glidance's fleet learning at N=1
> **What**: 60 s ring buffer (video + ToF + IMU + what the system
> said); auto-save clips on: ToF/CV disagreement, user override,
> near-miss, low confidence, manual "flag that." Weekly: label failures
> → eval set first → retrain → replay old clips as regression tests.
> **Why**: every stumble becomes a training label; the telemetry schema
> is what turns one helmet into a fleet later.
> **Source**: [[glidance-deep-dive-2026-08-20]] (openpilot-verified pattern)

> [!note]- 17. Pose-aware floor rejection + speech gate on fast head turns [S each]
> **What**: (a) expected-floor-per-zone from live pitch replaces the
> crude row filter — kills look-down false alerts; (b) suppress routine
> speech while the head turns >~100°/s (sterile cockpit).
> **Unlocked by**: the IMU cal you just did.
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 18. Tap-to-query + auto-silence in vehicles [S each]
> **What**: the BNO085's on-chip tap detector = F9 without a keyboard
> (helmet shell is a good tap substrate); on-chip activity classifier
> silences callouts in cars/buses automatically.
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 19. Interrogation interface [M] — "tell me more"
> **What**: layered on-demand depth: F9/tap gives labels → repeat gives
> ranges → repeat gives details. The #1 requested interaction property
> in BLV studies. Around-Me variant: 4 quadrants, max ONE item each
> (Soundscape's pattern).
> **Source**: [[blv-daily-life-2026-08-18]], [[soundscape-beacon-2026-08-20]]

> [!note]- 20. Drop alarm [S] — helmet beeps when it falls off
> **What**: clip/tether or IMU-freefall trigger → helmet chirps so a
> blind owner can find it. A dropped helmet is invisible to its owner.
> **Source**: [[guidetouch-2026-08-20]]

> [!note]- 21. Distance low-pass + confidence dimming on audio [S each]
> **What**: muffled = far (blind users learn it instantly); dim the
> tick/beacon when sensor confidence drops — volume carries CONFIDENCE,
> never distance (bats actively remove the loudness cue).
> **Source**: [[hrtf-spatial-audio-2026-08-20]], [[biosonar-2026-08-20]]

> [!note]- 22. Steps instead of meters + clock-face option [S each]
> **What**: user-calibrated stride → "about six steps" near (ObjectFinder
> users preferred steps close-up); clock-face vs left/right as a
> setting (preference split 7/15 vs 6/15 in studies).
> **Source**: [[feasibility-pack-2026-08-20]] §1, [[CALLOUT-PROTOCOL]]

---

## P3 — future / gated / on-trigger

> [!note]- 23. 🕐 Teach-and-repeat route retrace [L] — your ruling: interesting, not #1
> **What**: walk a route once (with a sighted guide), IMU + camera
> odometry records landmarks; later the beacon/tunnel replays it. NOT
> full SLAM. Glide ships this pattern ("walk once or twice").
> **Source**: [[patents-stripmine-2026-08-20]], GuideNav

> [!note]- 24. 🕐 Companion beacon [M] — your ruling: low priority, demand thin
> **What**: voice-locked "where's my person" re-finding (companion
> stepped away), ≤4 m, fails loudly to the cane. NOT continuous
> locomotion-following (nobody asks for that; the elbow beats it; a
> UWB tag beats vision anyway). CHI 2026 demand is group/semi-static.
> **Source**: [[feasibility-pack-2026-08-20]] §5

> [!note]- 25. Dropped-object mode, narrowed [M]
> **What**: head-aim floor search for phone/wallet/bottle-sized items
> ONLY (keys/coins are below the detection floor at 720p). Speech =
> object-distance-direction, steps near, separate azimuth/elevation
> channels — never scalar warmer/colder.
> **Honest**: AirTags dominate the tagged case; our niche = untagged
> unexpected drops, hands-free.
> **Source**: [[feasibility-pack-2026-08-20]] §1

> [!note]- 26. Bus/transit features beyond GTFS [L] — partially blocked by no-camera-2
> **What survives**: stop-finding (All_Aboard pattern), arrival
> announcements from GTFS-RT, bus-door localization once stopped
> (~2–8 m, zero prior art = novelty claim), LineChaser boarding cue.
> **What's blocked**: route-number OCR at range (needs pixels we don't
> have).
> **Source**: [[transit-assistance-synthesis-2026-08-20]]

> [!note]- 27. Platform-edge safety loop [M] — after the sunlight test
> **What**: independent ≤100 ms ToF loop; drop-off band signature +
> edge orientation ("edge ahead-left"); camera segments the warning
> tile line for early speech; latched alerts. 76% of blind respondents
> have fallen off a platform; no published wearable baseline.
> **Source**: [[platform-edge-safety-2026-08-20]]

> [!note]- 28. Storefront-vs-display-window ruleset [M]
> **What**: entrance = walkable floor continuity across the threshold;
> window = sill at 0.4–1 m; + metric width class + handle height + OCR.
> No published work — ours to invent. Scored ruleset, not learned.
> **Source**: [[implementation-guide-2026-08-20]] §1

> [!note]- 29. WA/CWA/NA ground classes [M] — .lumen's Live Map layer 3
> **What**: walkable / conditionally-walkable / non-walkable ground
> segmentation from down-ToF + camera, richer than binary obstacle.
> **Source**: [[patents-stripmine-2026-08-20]]

> [!note]- 30. Complexity-scaled cue intensity [M]
> **What**: haptic/audio intensity driven by corridor width + upcoming
> turn angle (from the ToF walkable estimate), not just obstacle
> distance. .lumen's path-complexity score.
> **Source**: [[patents-stripmine-2026-08-20]]

> [!note]- 31. Panic/fallback button [S]
> **What**: one dedicated input → all guidance stops, calm orientation
> mode. (Glide ships one.)
> **Source**: [[patents-stripmine-2026-08-20]]

> [!note]- 32. Scan-coaching + yield-to-user-clicks [M each]
> **What**: (a) tick as obstacle edges cross center during a deliberate
> head sweep (O&M scanning training); (b) mic detects the user's own
> echolocation click → device goes quiet (published nowhere — novelty).
> Note: click-yielding matters less now the 2–5 kHz ban is lifted.
> **Source**: [[biosonar-2026-08-20]]

> [!note]- 33. VAD conversation gate [M]
> **What**: laptop mic + voice-activity detection → suppress routine
> callouts while you're talking with someone.
> **Source**: [[blv-daily-life-2026-08-18]]

> [!note]- 34. B1 sync pin — interleave the two ToF windows [S]
> **What**: 1 wire + 1 API call (`set_external_sync_pin_enable`,
> L8CX-only) kills mutual interference between sensors A and B.
> **Source**: [[ultrasonic-mmwave-glass-2026-08-20]] (found in our own driver)

> [!note]- 35. Hydrophobic cover coating + brim [S] — $5 rain fix
> **What**: the ToF's real rain failure is water ON the cover glass.
> (GuideTouch's spinning-cover alternative works but is 70 dB.)
> **Source**: [[ultrasonic-mmwave-glass-2026-08-20]], [[guidetouch-2026-08-20]]

> [!note]- 36. Ultrasonic ranger add-on [M] — the glass backstop
> **What**: TDK CH201 or MaxBotix (~$35) on the existing I2C bus;
> 99.99% acoustic reflection off glass vs our 4%; covers matte-black +
> sunlight too. Disagreement with ToF = material detector.
> **Source**: [[ultrasonic-mmwave-glass-2026-08-20]]

> [!note]- 37. IR LED illuminator [M] — camera night vision
> **What**: cheap IR floods let the camera see in darkness (.lumen
> ships IR projectors; our ToF already works in the dark — only the
> camera goes blind).
> **Source**: [[QA-2026-08-20-part2]] §2

> [!note]- 38. Foveated ROI processing [S-M]
> **What**: full-frame low-res + full-res crop where ToF says something
> is closing. 5–10× compute saving in an afternoon.
> **Source**: cv-stack research 2026-08-16

> [!note]- 39. Barometer for floor changes [S-M]
> **What**: BMP390 (~$3, I2C) detects elevator/stair floor transitions
> at 75–97% accuracy.
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 40. Ground-plane bbox ranging + head-as-gimbal memory + step-counter odometry [M each]
> **What**: (a) range camera-only detections from geometry (d =
> h/tan(pitch+θ)) beyond ToF reach; (b) 2–5 s obstacle memory ("pole
> still on your right") — unpublished framing; (c) "about 30 m since
> the doorway" from step counting (~1% error head-worn).
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 41. Fall detection + stumble ground-truth logging [M / S]
> **What**: head-worn fall detection is validated at 97% — needs a
> phone alert path to matter; every stumble auto-labels a missed-alert
> (feeds idea 16).
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 42. Camera↔ToF de-rotation + firmware timestamps [M]
> **What**: during fast head scans the 67 ms ToF latency misregisters
> zones by up to 1.4 m at 3 m; IMU de-rotation + timestamps fix it.
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 43. Miniguide-style range presets [S]
> **What**: user-settable caution range (0.5/1/2/4 m) — shipped and
> liked in the Miniguide; context-dependent needs.
> **Source**: [[blv-daily-life-2026-08-18]]

> [!note]- 44. NaviLens code reading [M] — opportunistic only
> **What**: read ddtag markers where transit systems installed them
> (30 m vendor-claimed). None in Vancouver — never a dependency.
> **Source**: [[transit-gtfs-navilens-2026-08-20]]

> [!note]- 45. Vertical ToF splay experiment [M]
> **What**: GuideTouch pitches its two sensors 30° apart for 90°
> VERTICAL coverage (knee→head at 50 cm standoff). A re-aim experiment
> or third sensor could serve head-clearance + drop-off together.
> **Source**: [[guidetouch-2026-08-20]]

> [!note]- 46. Rideshare "is this my car" scorer [M-L]
> **What**: 1:1 verification vs the app's plate/make/colour; plate ≥5/7
> chars = decisive; fail-closed ("likely your ride, unconfirmed — ask
> the driver"). BC plates are rear-only ⇒ post-stop confirmation only.
> Go/no-go blocker: getting trip data out of the Uber app.
> **Source**: [[implementation-guide-2026-08-20]] §3b

> [!note]- 47. Gyro-drift test with motors running [S] — publishable micro-result
> **What**: no published BNO085 drift data under vibration-motor load;
> 20 minutes of logging = a citable plot for the writeup.
> **Source**: [[imu-uses-2026-08-17]]

> [!note]- 48. 4K camera swap (same mount, not a second camera) [S-M hardware]
> **What**: 9× pixel area (32 px/deg) makes keys/cards findable and
> extends OCR range ~3×. Distinct from the REJECTED second boresighted
> camera — this replaces the existing one. Global-shutter option
> (OV9281-class) also kills motion blur.
> **Source**: [[feasibility-pack-2026-08-20]], [[implementation-guide-2026-08-20]]

> [!note]- 49. Platform/process: Rerun embed · Pi 5+Hailo untethered build · 90-s demo video · fisheye detector fine-tune · FP/hour metric · expert conversations (UBC O&M, GTT)
> **What**: portfolio-impact items — scrubbing a real walk in-browser
> (biped used Rerun); TRL upgrade to untethered; the demo shot-list is
> already locked; publish false-positives-per-hour as a first-class
> metric (WeWALK died by false positives).
> **Source**: [[portfolio-impact-2026-08-17]]

> [!note]- 50. Zenodo DOI — waiting on YOUR 3-minute GitHub toggle
> **What**: disclosure is already live (GitHub release v1.0-disclosure).
> zenodo.org → Log in with GitHub → Account → GitHub → flip
> `vl53l8cx-pointcloud-esp32` → tell me → I cut a release and the DOI
> mints automatically.
> **Source**: [[DEFENSIVE-PUBLICATION]]

> [!note]- 51. Text-noticed earcon [S-M] — solves "when do we read signs"
> **What**: cheap text DETECTION runs continuously; when salient text
> appears (big, centered, stable ~1 s) a tiny chirp says "readable text
> here" — you pull the actual READ with a command. 60 s cooldown per
> region. Reading itself is always on-demand ("read what's in my hand").
> **Source**: [[QA-2026-08-22]] §2

> [!note]- 53. ✅ "What's in my hand" — VLM description on demand [M] — **research done, build-ready**
> **What**: keypress → one concise spoken sentence about the live frame
> ("what's in my hand" / "what's ahead"). Query tier only; safety audio
> always preempts.
> **The design (researched 2026-08-22)**: Qwen3-VL-8B local via Ollama
> (6 GB, ~2 s) + Claude API fallback; sharpest-of-10-frames selection;
> bottom-center crop for hand mode; sensor-fusion prompting (YOLO+ToF
> state injected as text) to kill hallucination; **forced abstention**
> — BLV users can't detect wrong answers, so "I can't see that" beats a
> guess. WorldScribe (UIST 2024) validated the exact cascade we'd have.
> **Source**: [[vlm-integration-2026-08-22]]

> [!note]- 52. Event-driven detector scheduling [S-M] — your FPS insight
> **What**: YOLO at 2–3 fps idle; boost to full rate when ToF sees
> something new/closing, the beacon is guiding, or a query fires.
> Speech is event-driven anyway — constant full-rate CV is waste. Pairs
> with foveated ROI (#38); key for the untethered build.
> **Source**: [[QA-2026-08-22]] §4

---

## ⚖ Open questions (your call, no default)

> [!question]- Facial recognition
> You lean "not necessarily useful"; no longer privacy-blocked by your
> ruling. Research: users' own verdict was negative; third-party harm
> documented in the docs for whenever this goes public. Sitting until
> you decide.

> [!question]- Empty seat: auto-pick vs "describe the seating"
> See idea 11 — both buildable; the reframe converts the socially
> costly false positive into honest information.

---

## ✅ Already built & shipped (no decision needed)

> [!success]- The shipped stack (expand for the full list)
> Silence-default callout engine (60 s cooldowns, stale-drop, approach
> re-announce) · TTC terminal-buzz ticker + range-adaptive path cone ·
> two-item grammar, hedging, no numbers walking · cane-blind-spot
> filter · person deprioritized · F8 hush / F9 query · brevity mode +
> trainer · directive commands · voice-guided leveling · motor ID over
> WiFi · software+hardware mute · **Soundscape beacon (key g)** ·
> **IMU mount calibration** · sensors-lost callout · Glide-style
> stop-don't-push behavior partially via directive tier.

---

## ❌ Rejected — with reasons (don't re-litigate without new evidence)

> [!failure]- Second boresighted narrow camera — YOUR ruling 2026-08-21
> Consequence accepted: no text at range (bus headsigns out), last-metre
> uses fisheye centre + ToF. The 4K SWAP (idea 48) remains available.

> [!failure]- Wired/DIY bone conduction install — YOUR ruling 2026-08-21
> Bluetooth BC accepted instead (speech + mono ticker + coarse beacon
> all tolerate BT latency). Wired AMCaoYiLi pair purchased $33.90 for
> September precision work; DIY transducer bonding dropped.

> [!failure]- Terrain narration — reopened by you, then closed by evidence
> ToF range collapses to ~1 m in sunlight = sees no farther than the
> cane sweeps; black ice is a material problem our sensor can't touch;
> hikers' revealed preference is poles/dog/buddy; IMU classification is
> reactive (feet do it free). Survivor: drop-off detection (idea 14) +
> the upward sensor as the real trail story.

> [!failure]- Currency detection — reopened by you, then closed by evidence
> Free apps (Cash Reader, Seeing AI) + 117k free BEP readers own it;
> CAD/EUR/GBP identifiable by touch; head camera makes framing WORSE
> than a phone. Demo-only at best.

> [!failure]- "Find me an empty seat" (naive auto-pick)
> Backpack/handbag are COCO's two worst classes; a false positive =
> public humiliation = abandonment. Reframed as idea 11.

> [!failure]- Open-space person-following
> Wrong identity ~20% of trajectory time (IDF1 75–80) on EASY
> benchmarks; from behind in coats ≈ coin flip; the elbow beats it
> walking; a UWB tag beats vision. Narrowed to idea 24.

> [!failure]- Go/no-go crossing calls
> The one error that kills; ACB/NFB positions agree. Alignment only.

> [!failure]- Faces/emotions/standalone pedestrian callouts
> Users explicitly reject person-callouts ("people move"); people stay
> as INPUTS to queue/follow/collision features. Face ID: see open
> questions.

> [!failure]- Full indoor SLAM / venue mapping
> GoodMaps' lane; needs infrastructure or beacons; our moat is
> perception, not mapping.

> [!failure]- PDR breadcrumb return-path
> 9 m error from one head turn — heads lead turns; killed by physics.
> (Teach-and-repeat, idea 23, is the viable cousin.)

> [!failure]- Continuous rich sonification (vOICe-style)
> 73 h training, zero adoption in 30 years.

> [!failure]- Loudness = distance
> Bats actively remove the cue; blind users are poor at absolute
> loudness. Volume = confidence only.

> [!failure]- Event cameras / cheap radar now / stochastic-resonance haptics
> Quote-only pricing + no pretrained detectors; zero azimuth + sees
> through walls; wrong physiological regime (our motors are
> supra-threshold).

> [!failure]- .lumen's continuous 100 Hz haptic "reins"
> Defensible alternative but conflicts with our silence-default
> evidence base; A/B someday, don't drift into it silently.

> [!failure]- Persistent recording / scene memory as a user feature
> Privacy blast radius with no demand study. (Engineering telemetry,
> idea 16, is different: local, for training.)

---

## Standing rules (your rulings, quick reference)

Privacy/regulatory ≠ a constraint this phase · compute ≠ a constraint
(GPU now, Jetson-class later) · the cane is always alongside · haptic
patterns ≤2 motors · echolocation-band ban VOIDED (sparse sounds still
required — the band carries speech/traffic) · head-clearance = 10–15 cm
above the top ToF ray, gravity-framed · prototype freely, mine every
patent, review only before selling.
