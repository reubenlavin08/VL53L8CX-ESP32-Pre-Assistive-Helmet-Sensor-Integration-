# UTILITY ROADMAP — from working hardware to something blind people would keep
## 2026-08-18 — synthesis of all seven research streams

Sources: `research-sources/blv-daily-life-2026-08-18.md` (capstone) +
`abandonment-lowtech-2026-08-18.md` + `wearables-fate-2026-08-18.md` + the
2026-08-16/17 streams. This file is the decision layer.

## The strategic reframe (three sentences)

Obstacle detection is the **entry ticket, not the product** — blind users
rank destination guidance above avoidance, and every avoidance-only device
died or stalled (best case: 75 units/year). The vacant, infrastructure-free
niche our exact sensors serve: **last-meter guidance** — the door, the bus
pole, the route number, the end of the line, the empty seat — plus the one
hard-numbered safety gap, head-height obstacles. The helmet itself is the
**development platform**, not the product form; the migration path is
cap-clip/headband, and we say that openly.

## Build order

### Phase U1 — the flagship: TERMINAL GUIDANCE to entrances/doorways
(2026-08-19 competitive update: claim "terminal guidance," never "indoor
navigation" — servo to a target already in the camera's view over the final
3–10 m. The niche is vacant IN WEARABLE FORM; Glidance's pre-shipping robot
claims the capability on wheels — track it. Every shipping wearable, .lumen
included, does avoidance only; .lumen's indoor wayfinding is explicitly
future work. Full lane analysis:
`research-sources/indoor-nav-competitive-2026-08-19.md`.)
Detect doors/entrances (YOLO fine-tune — no BLV door dataset exists, so ours
is a publishable contribution), **depth-verify the opening** (a door
detection with no depth discontinuity behind it is a picture of a door — the
check no monocular competitor can make), guide by spatialized cue + steps
("door, ahead, about ten steps"). Precedent: All_Aboard (91% vs 52% Google
Maps). Known hard case to design for, not around: glass doors kill the ToF
return exactly here — camera-sees-door + no-ToF-return = "glass door,
proceed by cane."

### Phase U2 — transit pair
(a) bus-STOP pole finding (same detector family); (b) **route number of the
arriving bus** — OCR burst on bus-shaped detections, spoken once: "the 14".
Hands-free head-aim is the variant phones can't do. #1-ranked need (text)
in its only underserved form.

### Phase U3 — queue + seat
LineChaser pattern (person detection + depth): "end of the line, left,
about six steps," then progress ticks as it moves. Empty-seat finding via
depth-plane + chair detection: the one social-adjacent feature that is
geometric, not interpersonal.

### Phase U4 — crosswalk ALIGNMENT (geometry only)
Zebra-stripe orientation vs body heading → "drift left" during crossing.
NEVER go/no-go. On-device only.

### Continuous alongside: head-height safety channel (built) + the
verification interface — F9 evolves into ask-and-refine ("what's ahead?" →
"tell me more") because interrogation, not monologue, is the #1 requested
interaction property.

## Delivery invariants (locked by evidence, most already built)

- Silence default ✓ · pull-first ✓ · hedging ✓ · on-device safety path ✓
- CHANGE: distances in **steps** (user-calibrated stride), not meters
- ADD: spatialized audio beacon (Soundscape's validated open-source model)
  when bone-conduction hardware arrives
- Haptics: ≤4 directions, location+rhythm only, never intensity, never
  continuous (v11 hard-region design validated)
- Suppress narration during conversation (VAD gate — future)
- Every published video gets audio description (credibility tell)

## Hard do-not-build list

Faces/emotions/identity · go/no-go crossing calls · persistent recording ·
terrain narration · standalone pedestrian callouts · currency · cloud on
the safety path · anything replacing the cane (head ToF is structurally bad
at ground hazards — state it in every writeup).

## Abandonment counter-measures (the graveyard's lessons)

- False positives are the #1 return reason (WeWALK) → measure FP/hour as a
  first-class metric, publish it.
- Year one is the abandonment cliff; success claim = sustained use, not demo.
- Don't couple to hardware someone else can kill (Aira/Samsung,
  Envision/Glass) — our stack is commodity USB parts by design.
- Weight/bulk killed the best-reviewed device — drives the platform-migration
  plan.
- Free multimodal phone AI ate OrCam — never compete with it on description;
  own the depth+continuous+hands-free slice it can't reach.
