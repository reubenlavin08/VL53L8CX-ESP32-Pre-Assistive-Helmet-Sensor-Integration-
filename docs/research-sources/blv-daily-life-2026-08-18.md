# BLV daily-life synthesis — 2026-08-18 (main agent, condensed verbatim)

The capstone of the utility research fleet (with `abandonment-lowtech` and
`wearables-fate` companions). Decisions extracted to `docs/UTILITY-ROADMAP.md`.

## The three findings that change the plan

1. **The helmet form factor is the biggest liability** — explicit in the
   literature ("helmet-worn devices are unsuitable… would prefer not to be
   seen in public wearing a helmet", Sensors 2022) and users ("Nobody wants
   to walk around in Big Ski Goggles"). Even the best-reviewed competitor
   (biped NOA): 8/13 named weight/bulk the main flaw. Venue bans on head-worn
   cameras are proliferating with no accessibility carve-outs. **Treat the
   helmet as the development platform; the product migrates to cap-clip /
   glasses / headband.** Head-MOUNTING is right; head-HELMET is not.
2. **Obstacle detection is the substrate, not the product.** Blind cane users
   rated "navigation is primarily about avoiding obstacles" 2.375/5 —
   disagree. Unmet needs are destination-focused: indoor nav, route, POI.
   ETAs that slow the user get abandoned (NOA cut walking speed 0.68→0.60).
3. **Head-height is the one defensible safety niche** — 13% monthly head
   injuries, dog no better than cane, and even the smart-cane-hostile Derek
   Riemer concedes above-knee detection is "the only reasonable place" for
   smart tech. NOA's most-praised capability: upper-body obstacles (8/13).

## Daily-friction map (compressed verdicts)

- UNSOLVED + our sensors CAN help: **which bus arrived** (route number on a
  moving bus, hands-free), **bus-stop pole finding** (All_Aboard: CV 91% vs
  Google Maps 52%, final gap 1.8 m vs 7 m), **entrance/doorway finding**
  ("I've lost count of the times I've ended up talking to an empty chair" /
  "so many things to trip on before I even get to the door"), **queues**
  (LineChaser, CHI 2021 — literally our sensor stack), **empty seats**
  (users named it; researchers ignore it).
- UNSOLVED but NOT our sensors: appearance verification, cooking
  heat/doneness, glass touchscreens (worsening!), self-checkout, social
  identification, gym consoles.
- SOLVED (don't compete): label reading in hand (commoditized by Meta/Seeing
  AI), screen readers, tactile labeling.
- Cross-cutting: the unmet need is **verification, not perception**; the gap
  is always **the last few meters**; **dependence is the felt cost**.

## Tool ecosystem reality

- Aira = $1.30–1.50/MINUTE — rationed emergency resource (43.6% employment
  rate context). Meta Ray-Bans adopted BECAUSE $299 + mainstream.
- Soundscape: users loved it, Microsoft killed it — **its 3D-audio beacon
  model is validated and open-source. Copy it.**
- ETA abandonment ~75%; only 29% of studies include blind participants.
- biped NOA = the benchmark: 12/13 preferred, collisions 1.62 vs 2.92 cane;
  weaknesses = bulk + "sound cues too frequent/loud" — our opening.

## Feature candidates, evidence-ranked

TIER 1: (1) entrance/doorway last-meter guidance — the vacant,
infrastructure-free niche; (2) head-height obstacles (built); (3) bus stop +
route number of arriving bus; (4) queue detection + progress; (5) empty-seat
finding.
TIER 2: (6) crosswalk ALIGNMENT (geometry only, never go/no-go, on-device
mandatory — blind pedestrians end up 5 m off over 22 m); (7) dropped-object
finding (head-aim + "top right next to the wall" precedent); (8) aisle-level
store guidance (SKU-level is unwinnable).
TIER 3 (defer): person-following (mechanism, not headline), scene memory
(no demand study + worst privacy posture).

## Delivery rules (each evidence-backed)

Pull not push, silence default (built ✓) · answer-first then "tell me more" ·
support INTERROGATION not monologue (add conversational follow-up) ·
direction in the SIGNAL (spatialized beacon — Soundscape model) not words ·
**steps, not meters** · open-ear/bone-conduction only, and still costs
awareness · haptics: ≤4 directions, location+rhythm, NEVER intensity, never
continuous (validates v11 hard-region design) · two latency budgets: safety
<500 ms on-device, description 1–2 s cloud OK · speech for symbols, haptics
for crossings (7/11) · hedge, never fake confidence ("no information beats
misleading information") · report where-in-frame so head-aim is learnable ·
suppress during conversation.

## Do-NOT-build (users' words)

Terrain detection (feet do it) · standalone pedestrian detection · currency ·
**faces/emotions/identity — ruled out entirely** (unverifiable by the user,
cost lands on third parties, OrCam's most-criticized feature; Chancey Fleet's
equity-vs-privacy tension) · go/no-go crossing decisions · persistent
recording (I-XRAY/"Glasshole 2.0"; blind users catch the backlash) · anything
that degrades the cane ("integrate rather than replace" rated 2.25/5 — they
don't even want integration; head-ToF is structurally bad at ground hazards —
SAY SO) · cloud on the safety path · the social gap generally (empty-seat is
the one geometric exception).

## Credibility

Kish: "you cannot understand blindness from a sighted perspective";
Bidleman called out a project's promo video having no audio description —
"a reliable tell that no blind person was in the room." Name one narrow task;
state what it does NOT replace; audio-describe every video; arrive at r/Blind
with one concrete design question, not "what problems do you have."

## Bottom line (verbatim)

"The vacant niche is destination-focused last-meter guidance without venue
infrastructure — the door, the pole, the desk, the seat, the end of the line
— delivered hands-free with head-directed aiming, silent by default,
sub-500 ms on-device haptics, alongside a cane that stays in charge of the
ground. Your working obstacle detection is the entry ticket, not the product."

Research gap: r/Blind + AppleVis verbatim (403-blocked) — needs a browser
session if wanted. Full citations in the agent transcript.
