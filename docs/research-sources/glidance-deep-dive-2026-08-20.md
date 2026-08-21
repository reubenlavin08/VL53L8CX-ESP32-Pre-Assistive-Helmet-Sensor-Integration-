# Glidance / Glide — technical deep-dive from primary sources — 2026-08-20

Sources: official "Glide FAQ & Overview — July 2026" docx (you downloaded;
extracted verbatim below) + glidance.io/technology page (you pasted).
External research agent running for independent reviews + the
fleet-learning design pattern.

## What Glide actually is

Two-wheeled, ~9 lb (4 kg) self-steering "primary mobility aid" — you hold
a telescoping handle, push it ahead of you, it steers and brakes
autonomously. Founded by **Amos Miller — blind, ex-Microsoft Research,
led Microsoft Soundscape** (the same lineage as our callout engine).
Community of 8,000+ blind/low-vision co-designers. $1,499 USD +
**mandatory $30/mo subscription** (LTE + cloud AI + OTA features).
Launching US/Canada/UK; preorders sold out twice; first units shipping
2026.

## Sensor + compute stack (from the FAQ, verbatim facts)

- **Two stereo-depth cameras in the handle** + speaker + mic + haptics +
  center/left/right buttons.
- Camera-based → **fails in complete darkness** (they're "testing
  lighting solutions"); low-light OK.
- On-device inference + cloud services: core functions (obstacle
  avoidance, straight-line keeping, line-of-sight target detection) run
  **offline**; "cloud AI necessary for line-of-sight target on location"
  uses WiFi/LTE (built-in SIM, auto-carrier).
- Battery 6+ h active walking (~30,000 steps), 95 Wh, USB-C.
- IP54; −20.5 to 40.5 °C; **snow/ice explicitly NOT supported at
  launch**.
- Phone required (BT-paired, stays in pocket); audio routes through
  companion app → user's own BT headset, mixing with other apps.

## Feature behaviors worth STEALING (maps to our stack)

1. **Crosswalk protocol**: announces "approaching road," stops before the
   down-curb, **user decides when to cross** (never interprets signals);
   during crossing it "keeps you walking straight without veering,
   aiming toward the opposite curb cut"; announces **"crossing
   complete."** → Almost exactly our BEV+IMU crosswalk plan; adopt the
   two spoken bookends + explicit responsibility split.
2. **Target scan-and-select UX**: user scans for "stairs, doors,
   elevators, counters," picks one, Glide guides to it. → This is our
   terminal-guidance UX pattern, validated by their 8,000-user community.
   Fixed target vocabulary, additions via OTA — no user-trained objects
   at launch.
3. **Blocked-path behavior**: fully blocked → **stop and alert, never
   push through**; then collaborate with the user on an "off-curb
   maneuver" or new path. → Our directive tier should have the same
   honest dead-end state.
4. **Stairs protocol**: detects up vs down, announces which, **guides to
   the railing**, tells you on arrival. Railing-seeking is a brilliant
   touch. Curbs/potholes/uneven pavement = steer around or stop+alert.
5. **Overhead obstacles**: branches/signs/awnings detected and steered
   around — confirms head-height as table-stakes for a premium device.
6. **Narrow-path alert**: tight spaces get an explicit "path has
   narrowed" callout; keeps pace with the person ahead in crowds.
7. **Two-mode structure**: Freestyle (user decides where; device handles
   obstacles/veer) ships first; Directed Navigation (turn-by-turn, saved
   routes) comes later OTA. → Validates our obstacle-first, guidance-
   second roadmap.
8. **Social signaling**: red bumper + LED ring so the public reads it as
   an assistive device — the abandonment literature's "device shame"
   factor, addressed in hardware.
9. **Deafblind support** via haptics + BT hearing aids.

## The "fleet learning" claim (their website, decoded)

Their words: "Every step Glide takes captures real-world data —
perception, intent, motion, human behavior, and safety-critical
interactions — continuously improving the model's intelligence… More
consumer devices deployed → more steps → better models → more adoption…
a compounding data flywheel." Plus "Agentic Wayfinding™: navigation as a
perceptual problem, no HD maps, no fixed infrastructure, no prior
knowledge."

**What it means concretely** (standard pattern, Tesla-style): deployed
devices log camera/sensor snippets — especially interventions, stops,
near-misses, and disengagements — upload to the cloud, humans/auto-
labelers mine the hard cases, models retrain centrally, improved weights
ship back OTA to every unit. The subscription pays for exactly this
loop. Their moat claim: this data "cannot be fully simulated."

**Our single-user version (already in IDEA-BANK, now unified):**
- The **own-data capture loop** (auto-label → hand-correct → nightly
  fine-tune) IS the flywheel at fleet-size 1.
- **Stumble/intervention logging as ground truth**: every F8-hush, every
  user override, every stumble = a labeled miss. Log the 10 s sensor
  window around each.
- A "flag that" voice/tap command to bookmark hard moments in the field.
- Session recordings from field walks = our "steps."
- If the helmet ever multiplies, the telemetry schema is what makes it a
  fleet — design the log format now (timestamped frames + ToF + IMU +
  what the system said + what the user did).

## Business-model facts (for the competitive picture)

$1,499 + $30/mo; 2-yr warranty; 60-day return (min 30 days' use); not
insurance-reimbursable; carry-on compliant (95 Wh); 4-yr minimum OTA
support commitment. Prototype lineage: Hugo, Ada, Marie, DeLorien,
Galileo, Rover. Awards: Edison, SXSW Pitch, RBR50, CES CTA Foundation.

## What Glide does NOT do (our openings)

- Nothing above the user's own decision at crossings (no signal state).
- No reading of text/signage/route numbers mentioned anywhere.
- No transit assistance.
- Dead in darkness (camera-only); we have active ToF.
- Occupies one hand permanently; helmet is hands-free.
- Wheeled = ground-constrained (stairs = carry it).
