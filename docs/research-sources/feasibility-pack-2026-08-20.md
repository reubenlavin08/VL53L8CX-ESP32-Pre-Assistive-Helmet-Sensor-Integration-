# Feasibility pack — dropped objects, terrain, currency, seats, following, headset — 2026-08-20

The six-item verdict report you ordered. Condensed-verbatim.

## Verdict scorecard

| Feature | Verdict |
|---|---|
| Dropped-object finding | **Narrow yes** — phone/wallet/bottle only; needs sensor upgrade |
| Terrain warning | **Still no** — but drop-off detection + the UPWARD sensor are the real trail story |
| Currency detection | **No** — solved by free phone apps; demo at best |
| Empty-seat finding | **Reframe** → "describe the seating" (uncertainty as a feature) |
| Person-following | **Reframe or skip** → "companion beacon" for re-finding, not locomotion steering |
| Bone-conduction headset | **Build wired (DIY) + buy Soundcore V30i for speech** — NOT the Shokz OpenMove |

## 1. Dropped-object finding

- Standing geometry kills the naive math: camera at 1.55 m → floor object
  at 1 m ground distance is 1.84 m slant, foreshortened ×0.84, at the
  worst corner of the lens. Phone at 1 m = 42×25 px (fine); keys = 17×8
  px; coin = 8×7; earring = 6 px² total.
- Detection floor for >80% recall ≈ **30–40 px shortest side** (SODA:
  14.1% AP on ≤144 px² vs 46.9% normal; SAHI tiling buys +5–14 AP —
  doubling 14% is still 28%). **Only the phone at ≤1 m clears it.**
- Prior art: Seeing AI "Find My Things" ships free; **AirTag UWB
  dominates the keys/wallet case** (through couches, in the dark). Our
  niche = untagged unexpected drops — which skews toward the small items
  we can't detect. Real differentiator: hands-free scanning, cane hand
  free.
- UX evidence (ObjectFinder, 8 blind users, 4.13/5 helpful): speech =
  Object–Distance–Direction, clock azimuth, meters far / **steps near**.
  **Separate azimuth and elevation channels beat a scalar warmer/colder
  tone** (Fitts-law study); beep repetition rate = best depth encoding.
- **Negative finding that hits our architecture: a forward head camera
  structurally misses the floor** — 2/8 blind participants couldn't find
  desk items without lowering their heads. Fix = cant camera down or add
  a downward lens.
- **Highest-leverage fix is the SENSOR: 4K at 120° = 32 px/deg = 9× area
  gain** — moves keys/cards from marginal to findable. Beats any model
  work.

## 2. Terrain warning (reopened → closed again, with one carve-out)

- Community revealed preference is non-electronic (poles, canes, Dakota
  Disk tips; Perkins guide mentions zero tech; Riemer: "talking compasses
  are mostly trash"). One commercial success in the niche: a titanium
  cane, zero electronics.
- **Snow/ice: real pain point, wrong sensor.** "Snow is piled over the
  surfaces we need our canes to detect" (Lepofsky, CBC). But black ice
  is FLAT — a material problem: literature uses lidar return intensity
  (87%), mmWave (95%), NIR — never depth. VL53L8CX doesn't expose usable
  per-zone reflectance. Not feasible.
- **Datasheet ceiling: max range on 17% grey drops 2.4 m (dark) →
  0.9–1.0 m at 5 klux.** Daylight is 50–100+ klux. **On a sunlit trail
  the downward ToF sees about as far as the cane already sweeps.** 4×4
  zones from 1.6 m = ~45×63 cm ground footprints — a root or 5 cm step
  averages away.
- IMU terrain classification is accurate (95–99%) but classifies what
  you're ALREADY standing on — reactive; feet do that free.
- **The carve-out: drop-off detection.** Canes miss 1-in-5 to 1-in-3
  drop-offs (constant-contact 79%, two-point 63% — Kim et al.).
  Ground-plane-absent is a big resolvable signal even at 16 zones.
  Honest spec: "extends cane drop-off coverage, degraded in full sun."
- Two independent sources name obstacles ABOVE the ground as the unserved
  trail hazard — **the upward sensor is the off-road story.** arXiv
  "visually impaired + trail/hiking" = zero results.

## 3. Currency detection (reopened → closed)

- ACB v. Bessent still open; BEP March 2026 filing: tactile $10 in
  production 2026, then $50 2028, $20 2030, $5 2032–35, $100 2034–38 —
  **and the $1 can never legally be redesigned.** Non-tactile USD for a
  decade+, forever for $1s.
- But: BEP has given out **117,439 free iBill readers**; Cash Reader app
  (119 currencies, offline, AppleVis Hall of Fame) is loved; Seeing AI
  free. **CAD/EUR/GBP are identifiable by touch alone** (BoC: tactile
  dots) — only USD needs machine reading.
- Head-camera physics: you hold the bill up anyway → lose phone
  autofocus, gain an aiming problem (Envision had to engineer framing
  guidance). **Skip, or demo-only with no gap claim.**

## 4. Empty-seat finding → reframe

- **Chair AP ≈ 26 and does NOT improve with better detectors**
  (occluded, self-similar by nature). Person AP ≈ 53 — the occupancy
  signal is 2× more reliable than the seat signal.
- **The bag-on-the-chair kills "find me an empty seat":** backpack
  (14.2) and handbag (13.7) are the two WORST common-class APs in COCO;
  a draped jacket isn't a class. A false positive walks a blind user
  across a room to sit on someone's laptop — social humiliation is a
  primary abandonment driver. Miss costs nothing; FP costs dignity.
- IROS 2022 robotic cane: seat choice is SOCIALLY dynamic (convenience,
  privacy, intimacy) — users don't want the nearest seat.
- StereoPilot: spatial-audio rendering **tripled information transfer,
  cut positioning error 40%, halved grasp time vs speech** — build the
  beacon, let the user pick.
- **Ship "describe the seating"**: seats with bearing/distance/honest
  confidence ("one at 10 o'clock, 3 metres, something on the seat — not
  sure"), then beacon to the user's choice. Caveat: seat-finding appears
  in no needs-ranking survey reached — sanity-check on r/Blind.

## 5. Person-following → narrow reframe or skip

- LineChaser IS the prior art (follows the last person in a queue) —
  open-space following is exactly the part IBM/CMU avoided.
- **Fresh demand evidence (CHI 2026 group-tours paper, 8 blind users)**:
  users want "to know the situation of the people I was with" — i.e.
  **"tell me where my people are" in group/semi-static settings. Nobody
  asks for continuous locomotion-following.**
- Tracker reality: IDF1 75–80 ⇒ **~a fifth of trajectory time carries
  the wrong identity** — catastrophic for one safety-relevant target;
  benchmarks are static elevated cameras, not a walking 720p head; from
  behind in winter coats, re-acquisition after occlusion ≈ coin flip.
- **The elbow beats it while walking** (zero latency, transmits terrain
  through the guide's body, socially default). We only win when the arm
  isn't available: carrying things, queues, or **companion stepped away
  and needs re-finding**.
- If built: "companion beacon" — locked by explicit voice command, range
  capped in the 4 m ToF envelope, fails LOUDLY back to the cane. Honest
  note: **a BLE/UWB tag on the companion's phone beats vision here for a
  fraction of the effort.** If the reason is portfolio, say so in the
  writeup.
- Reddit was network-blocked all session — forum sentiment under-sampled.

## 6. Bone-conduction headset — REVERSES the interim OpenMove rec

- **Latency is disqualifying for spatial ticks over Bluetooth SBC.**
  Threshold: <30 ms undetectable; open-ear means the real world is a
  zero-latency reference → assume ~30–35 ms budget. Measured SBC =
  **257–260 ms** → at 90°/s head turn the tick lands **~23° off**, and
  it JITTERS (can't calibrate out).
- **Every Shokz model is SBC-only.** Only sub-80 ms consumer option
  found: Bose Ultra Open $379.99. Wired bone conduction on Amazon.ca:
  effectively extinct (Sportz Titanium discontinued).
- **DIY wins twice**: (1) wired = zero latency, deterministic; (2) a
  consumer band is a second rigid body that shifts vs the helmet IMU —
  fatal for precise spatial audio. Bonded transducers sit at a known
  pose vs the BNO085. One device to don unsighted, not two.
- **Buy list (Amazon.ca verified)**:
  - 🥇 **Dayton Audio BCE-1 exciter $76.00** (B00HFG6AZG) or 2× generic
    BC drivers **$16.62 ea** (B0CZ7HJBVW) + PAM8403 class-D amp — the
    spatial-tick path.
  - 🥈 **Soundcore V30i $44.99** (B0CNCHLR56) — open-ear ear-hook (no
    rear band), 30–36 h — **speech/menus only, not head-tracked ticks**.
  - 🥉 Soundcore AeroFit Pro $79.99 (LDAC ≠ low latency; still not a
    head-tracking fix).
  - **NOT the Shokz OpenMove $99.95**: SBC-only, 6 h battery, rear band
    fights the strap and decouples from the IMU. Brand premium for the
    worst fit.
  - Suggested: **V30i + 2 drivers = ~$78 total, both paths covered.**
- Mic: don't buy a headset for its mic — separate USB mic on the helmet
  decouples the problems.

## Cross-cutting takeaways (three items agree)

1. **Sensor resolution, not algorithms, is the binding constraint** —
   720p@120° is why keys aren't findable; 4K = 9× area gain, worth more
   than any model work. (Matches the implementation guide's tele-camera
   verdict — two independent syntheses now say: buy better optics.)
2. **A forward head camera structurally misses the floor** — measured
   with real blind users. Cant down or add a downward lens.
3. **Reframes beat kills**: seat→describe, following→companion beacon.
   Both convert socially-costly false-positive systems into honest
   information systems.
