# Patent strip-mine — .lumen + Glidance implementation details — 2026-08-20

You approved mining both filings for engineering specifics. Full texts
read via FreePatentsOnline. Bottom line: **.lumen's spec is rich —
5 buildable mechanisms; Glidance's is thin** (no numbers anywhere) but
still yields 5 UX patterns. Neither claims anything head-mounted-shaped
except .lumen — and .lumen's claims require a sound-localization mic
array we don't have, so even their device claim doesn't read on us.

## .lumen US 2022/0282985 A1 (filed 2022, DOTLUMEN)

**Their stack**: forehead camera + depth (tech-agnostic — NO IR
projector specs in this filing) + IMU + **sound-localization mic
array** (a modality we lack) + optional GPS/temperature.

**Haptics**: minimum 3 forehead actuators — left/right/center =
turn-left/turn-right/forward. Same topology as our temple motors. Cues
vary in duration/periodicity/intensity/frequency, scaled by a
**path-complexity score** (walkable width 10 cm–3 m, distance to
target, number+angle of turns, slopes, ambient noise). No numeric
waveforms disclosed.

**Guidance modes** (the gold):
1. **Walkable Tunnel** — a virtual 3D tunnel along the path; haptics
   fire ONLY when the user nears the tunnel walls. Error-correction,
   not continuous steering — silence when centered.
2. **Milestone mode** — waypoint-per-cue.
3. **Audio beacon on the path** — spatialized sound placed N m ahead
   along the route; walk toward the sound. (Convergent with our
   Soundscape beacon — two independent teams landed on it.)

**Perception**: 3-layer "Live Map" — L1 objects with predicted future
positions; L2 inferred relations (handle→door, light→crossing); L3
ground classes **walkable / conditionally-walkable / non-walkable**.
Safety: path rejected if a predicted trajectory comes within **0.3 m**;
conditional crossings need condition confirmation first.

**Claims**: narrow — the device claim needs the mic array + all 7
processing sub-units. Tunnel/complexity-scaling are described, NOT
claimed here (check EP/WO family before selling, as always).

## Glidance WO 2025/137615 A1

**Honest finding: embodiments are thin — zero numeric waveforms,
thresholds, or geometry.** Broad functional filing tied entirely to a
*rolling handle platform* — nothing reads on a head-mounted device.

Disclosed patterns worth taking:
- **Pulse-COUNT vocabulary**: N pulses = hazard, different N = turn;
  layered on left/right location. Weak "pings" = on-track, strong =
  hazard.
- **On-track reassurance ping** — periodic faint confirmation so
  silence never means "dead device."
- **Brake-pulse messaging** ("like anti-lock brakes") — burst-pause-
  burst trains as an urgency TEXTURE distinct from steady vibration.
- **Panic button** — one hardware input to a safe fallback mode.
- **Walk-once route memorization**, shared + refined across devices
  (the fleet-learning claim language lives here).
- Only specific sensor config at claim level: "at least two RGB depth
  cameras."

## Xu 2023 (Sensors 23:9598) — novelty-claim correction

Head-mounted **9× ultrasonic + BNO085 (our exact IMU!)** + Pi 4B,
audio warnings, decision-tree classifier 98.7%. **This is published
prior art for head-mounted ACTIVE ranging + IMU + real-time obstacle
warning.** Our novelty language must narrow from "nobody ships
head-mounted active depth" to: head-mounted **optical multizone
depth with metric mapping, calibrated camera fusion, and terminal
guidance** — Xu is acoustic, coarse, warning-only, no mapping.

## Build-this-month shortlist (merged, deduped)

1. **Walkable-tunnel haptics** — silence when centered; motors only
   near the corridor walls. Direct fit to v11 firmware.
2. **Pulse-count + burst-texture vocabulary** (≤2 motors per the
   GuideTouch rule; counts and textures carry semantics).
3. **On-track ping** (faint periodic reassurance).
4. **Complexity-scaled intensity** (corridor width + turn angle from
   ToF, not just obstacle distance).
5. **0.3 m predicted-trajectory gate** (suppress "clear" if a moving
   track will cross the corridor).
6. **Walk-once route record/replay** (BNO085 + camera odometry →
   beacon/tunnel replay).
7. **Panic/fallback button**.
8. WA/CWA/NA three-class ground segmentation.
