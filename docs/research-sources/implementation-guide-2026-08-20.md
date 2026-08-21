# IMPLEMENTATION DEEP-DIVE — doorway, head-height, transit, cars, crosswalk — 2026-08-20

The synthesis you ordered: "more research on doing it as well as possible"
for doorways/entrances, head-height obstacles, bus/transport (incl. getting
into cars), crosswalk alignment. Five research streams, condensed-verbatim.
Component docs with full citations sit beside this one in research-sources/.

---

## Cross-cutting findings (these change HARDWARE, not code)

**1. The fisheye is the binding constraint — three independent streams
converged on it.**
- Plate OCR: 1080p @ 119.58° → 20 px character height only to **3.2 m**.
  A 38° lens on the same sensor reaches **10.1 m**.
- Bus route number (0.15 m LED char, ≥24 px floor): **2.8 px at 30 m,
  8.4 px at 10 m**. Tangsuksant 2019 independently measured a **15 m
  ceiling** for a 15 cm numeral.
- Manduchi & Coughlan "The Last Meter" CHI 2014 (18 blind participants,
  guided to within 30 cm): "increasing the field of view does not help,
  and may even hurt, performance."

→ **Add a second boresighted ~38–50° global-shutter camera with manual
exposure.** Fisheye = scene/obstacle/acquisition; tele = text + last
metre. Global shutter also kills LED-sign banding at source.

**2. The BNO085 is load-bearing, and mag-free is right.**
- Head pitch during gait is **8° ± 2°** = ±140 mm vertical error at 2 m —
  larger than the whole head-clearance margin. Error budget: uncompensated
  ≈ 190 mm RSS; gravity-compensated ≈ 130 mm.
- Crosswalk: latch heading at the curb, dead-reckon across. 10 s crossing
  at pessimistic 2°/min drift = **~7 cm lateral** vs ~3.6 m biological
  veer. Only the delta matters — exactly why mag-free works.

**3. False-alarm economy is the dominant risk — hard evidence.** Pittet
et al., Sci. Rep. 2026 (13 BVI users, 28 m course): cane alone 2.92 body
collisions; cane + depth-camera device 1.62; cane + BuzzClip ultrasonic
**3.54 — worse than no device**, while slowing users 16%. Silence must be
the default everywhere.

---

## 1. Doorway / entrance terminal guidance

- **Calibrate to Antonazzi 2025 (J. Field Robotics)**: generic door
  detector in an UNSEEN environment = **13–48 mAP**. Fine-tuned on just
  15% of target-environment annotations: 20 → 76 mAP; at 75%, 96 mAP.
  **Domain adaptation, not architecture, is the whole game.** Their
  metrics to steal: TP% / FP% / BFD% (background false detection — the
  one that matters; announcing a door that isn't there walks the user
  into a wall confidently).
- Datasets are weak (DoorDetect 1,213 imgs; DeepDoors2 6,000). Neither
  has fisheye, storefronts, glass, hinge labels. **Plan our own capture
  loop**: Grounding DINO / OWLv2 as offline auto-labellers, hand-correct,
  nightly YOLO fine-tune. The loop beats any model choice.
- YOLO-World (35.4 AP LVIS @ 52 FPS) = prompt-driven classes without
  retraining. Fisheye caveat: polygon representations beat axis-aligned
  boxes by 40.3% mIoU on fisheye (Rashed 2020) — a peripheral box is
  mostly wall, which wrecks ToF association.
- **Door STATE from geometry, not a classifier**: closed door is coplanar
  with the wall; open = depth discontinuity past it. Our two 8×8 grids
  give two horizontal slices — fit the plane, get open/closed from the
  offset sign. "Traversable now" is the semantically correct target.
- **Hinge side**: detect door + handle, infer from spatial relationship
  (handle left → hinge right) — Watanabe & Premachandra 2026. OCR of
  PUSH/PULL overrides.
- **Glass is the hardest part.** Through glass a ToF beam returns the
  glass, the object behind, or a reflection — three wrong answers,
  non-deterministically per zone. Template = **TOPGN** (arXiv:2408.05608):
  use return INTENSITY, not range (+12.7% F-score, ~50 Hz on CPU). On the
  VL53L8CX: suspect when `target_status ∉ {5,9}` or `nb_target_detected
  ≥ 2` or `range_sigma_mm` spikes; specular when `signal_per_spad` high
  but implied reflectance implausible; then require **spatial coherence**
  (glass = rectangular patch, noise = scatter). IMU bonus: as the head
  rotates, a real plane holds in world frame, specular ghosts swing.
  **OPEN RISK: TOPGN was proven on dense LiDAR; whether 64 zones carry
  the coherence structure is unverified — prototype week one.**
- **Apple Detection Mode** (verified, iPhone User Guide): announces
  distance → open/closed → attributes (how to open) → door decorations
  (reads signs near the door). Four toggleable channels; double-tap for
  more detail. Lessons: continuous cheap channel + ON-DEMAND rich channel;
  read the signage.
- **Terminal-phase UX**: Ahmetovic "Turn Right" ASSETS 2018 — blind users
  **overshoot rotations by 17° average, worst on slight turns**. Never
  issue discrete small-angle commands close-in; use continuous closed-loop
  null-seeking on the three temple motors. Vibrotactile beats voice by
  >25% task time for localization.
- Elevator panels: public dataset of 3,718 panel images / 35,100 buttons
  + MIT code (zhudelong/elevator_button_recognition).
- **Storefront vs display window: no published work — ours to invent.**
  Strongest cue is ground-plane continuity across the threshold (walkable
  floor = entrance; sill at 0.4–1.0 m = window). Add metric width
  (pedestrian 0.8–1.1 m, double 1.6–2.0, garage 2.4–5), handle height,
  OCR. Ruleset, not learned — we have no labels.

## 2. Head-height obstacles

- **The justifying stat** (Manduchi & Coughlan CACM 2012, survey n=300):
  **"13% experience head-level accidents at least once a month"** — and
  frequency did NOT differ between cane and dog users. Neither aid covers
  it.
- **Code-backed framing**: ADA §307 — cane-detectable below 27 in,
  clearance required above 80 in (2032 mm). **The 27–80 in band is "cane
  misses it, code says it shouldn't be there."**
- **Critique of our top-ray rule — one fatal flaw**: there is no fixed
  "top row." Head clearance only exists in a GRAVITY-ALIGNED frame; a
  fixed sensor-frame ray points at wildly different heights with posture.
  Closest prior art (Muñoz 2025, forehead ZED + Jetson) DISCARDED frames
  when the user looked up/down; we can compensate with the IMU instead —
  and that gap is our novelty claim.
- **Hard ceiling**: under an ADA-minimum 2032 mm doorway a 1.90 m user
  has only **130 mm** of legal clearance — uncompensated error (190 mm)
  exceeds it. **The 10–15 cm rule is viable ONLY with IMU gravity
  compensation.** Widen to 30 cm uncompensated and tall users get alerted
  in every legal doorway → net-harmful per Pittet.
- Alert distances (τ ≈ 0.8–1.0 s dead time): first alert ≥ 2.0 m, hard
  alert 1.2 m, below 0.8 m already failed. Blind cane speed 0.68 m/s →
  comfortable.
- **Sensor settings that decide success**:
  - **Target order → CLOSEST, not default STRONGEST.** A 3 cm branch at
    2 m fills ~2% of a zone — under STRONGEST the background wins and
    **the branch is silently invisible. Single highest-leverage change in
    the system.**
  - Enable multi-target (600 mm merge limit = branch merges with wall
    behind — document).
  - Raise sharpener above 5% default (mixed-pixel edges).
- **Awning vs branch — no published solution**: (a) planarity/extent,
  (b) closing rate must match own IMU forward speed, (c) 3-of-5
  persistence (200–330 ms) — cheapest and most effective.
- **Architectural inversion**: camera = primary EXISTENCE detector, ToF =
  metric range confirmer. ToF fails SILENTLY on the highest-value targets
  (wet bark, matte black, glass, oblique + sunlight). A detector whose
  worst failure is silence must not decide to stay quiet. Camera-says /
  ToF-silent → trust the camera, range from ground plane.

## 3. Public transport

- **Highest-leverage, lowest-cost item in the whole report: fuse
  GTFS-Realtime day one.** GPS + stops.txt → the complete legal set of
  route strings at this pole (a handful). TripUpdates + STOPPED_AT often
  leave ONE candidate. **Open-set LED OCR becomes closed-set
  classification over K strings** — edit-distance scoring kills "R4"→"84".
  `trip_headsign` gives the destination WITHOUT reading it. TransLink
  endpoints free & documented (see transit-gtfs-navilens doc). 90 s
  staleness ⇒ RT proposes, vision confirms, never the reverse.
- **Bus stop finding is SOLVED — cite All_Aboard (Luo lab, TVST 2024),
  don't rebuild**: 91% vs Google Maps 52%; final gap 1.8 m vs 7.0 m; its
  4-level homing tone is one of two validated audio encodings in the
  boarding literature.
- **Route-number OCR best number**: SRM-OCR on BusLED-700 (2025) —
  **85.1%** on real degraded LED signs. Pipeline: DBNet++ 5–10 Hz →
  ByteTrack → PARSeq (14.9 ms) on tracked crops → per-character
  confidence-weighted voting over 5–10 frames (+4.6 to +10.5 pts; also
  washes out banding). TrOCR disqualified (huge, slow, worse on curved).
  **Constrain the charset per field** — language models hallucinate on
  contextless 3-digit route numbers; consider per-digit object detection
  (100% on 438 seven-segment digits). Read on approach only — transverse
  pass at 5 m smears 9 px per 10 ms.
- **"Which door is the bus door": ZERO arXiv hits for the phrase — a
  genuine novelty claim.** IBM/Asakawa have no bus work (full DBLP
  sweep). Transferable: LineChaser CHI 2021 "advance now" cue.
- **Platform edge**: Japan FY2021 = 1,429 platform falls; survey: **76%
  of blind respondents had fallen off a platform, 91% near-falls**; 64%
  of stations have no screen doors, rollout ~62 stations/yr — the market
  stays for decades. Tactile-paving segmentation is mature (mIoU ~94.9%,
  59 fps embedded) but NO public dataset splits warning-dots from
  directional-bars — relabel. Geometry: helmet ToF usable ground strip
  1.2–3.6 m; stopping needs 1.95 m at 1.4 m/s → clears in ideal light
  only. Drop-off signature (coherent band of zones flipping to
  no-return) is identical to black mat/puddle/sun — **false-positive
  discrimination IS the problem** (EyeCane's downward sensor has a
  documented step-failure record). Japan's interior-line warning blocks
  are ASYMMETRIC — they tell which side is safe, which depth can't.
  Consider chest/waist ToF mount (buys 0.2–0.25 m slant).

## 3b. Rideshare / getting into cars

- **The gap is real**: Uber/Lyft ship only visual (Beacon/Amp) or
  verbal-at-contact affordances — nothing helps a blind rider LOCATE the
  car. US v. Uber (settled 2022, ~$2.2M over wait-time fees) documents
  the boarding interval as where blind riders lose.
- **Plate OCR the decisive numbers** (UFPR-SR-Plates 2025): single
  low-res frame **1.7%** → +super-resolution 31.1% → **+majority vote
  per character position over 5 frames = 44.7%**. Best multi-frame
  method 96.7%; competition winners ~82% — **1 in 5 wrong even at SOTA.
  Fail-closed is mandatory.**
- Night: plates are retroreflective — force MANUAL exposure on the tele
  camera, expose for the plate. Auto-exposure beside headlights kills the
  8 pm demo. **BC has rear-only plates** — an approaching car has no
  plate; the plate pipeline is post-stop CONFIRMATION, never approach
  announcement.
- **1:1 verification, not classification** — the app hands us
  plate/make/model/colour. LLR scorer: plate ≥5/7 chars, zero
  contradicted ≈ +15 (decisive alone); make/model +2; colour +1.5 day /
  **+0.3 night** (silver/white/grey collapse under street lighting); any
  contradicted plate char = hard reject. "Confirmed" ≥ 12 — unreachable
  without a plate.
- **Don't try to see the door handle** (no dataset; geometry against us;
  flush EV handles). O&M answer: localize the door seam / B-pillar /
  window line at 2–4 m, then hand off to touch: "hand on the car, slide
  down and right 20 cm."
- **Safety non-negotiables**: no plate read → never "this is your ride"
  (two black Camrys). Moving-vehicle interlock — never "step forward"
  unless ToF confirms zero closing velocity N frames — as a SEPARATE
  auditable module with its own tests.
- **Unglamorous go/no-go: getting plate/make/model out of the Uber app**
  (no public rider API — accessibility-tree scraping, screen OCR, or the
  user speaks it). Solve first.

## 4. Crosswalk alignment

- **The architecture-deciding finding** (Kallie 2007): veer is a RANDOM
  WALK in heading, not a fixed bias — initial-pointing cues did NOT
  reduce it. **Open-loop alignment is worthless past ~4 m; "learn the
  user's bias" is dead. Continuous closed-loop correction the whole way
  across.** No published system does mid-crossing correction in traffic
  (Crosswatch tells users to pocket the phone before crossing) — genuine
  contribution.
- Veer magnitude (Guth 2018, 22 m simulated crossing): unaided ≈ 3.6 m
  lateral ≈ 9.2° effective; beaconing cut it ~5×. (Units caveat: PMC
  prints "ft," geometrically must be inches — verify before quoting.)
  APS benchmark: "ended within crosswalk" 23.2% → 76.7% with a far-side
  cue. **Verbal descriptions do NOT help staying in the crosswalk** —
  never solve veer with speech.
- **Curb-ramp trap** (FHWA primary): diagonal ramps point ~45° off BOTH
  crossings — users align to ramp slope and walk into the intersection
  centre. (Scott JVIB 2011 is the paywalled key cite — interlibrary.)
- **Recommended algorithm — BEV-first (our real edge)**: fisheye →
  undistort → inverse-perspective-map to bird's-eye using IMU gravity +
  helmet height → light seg on the BEV tile → RANSAC stripe fit →
  geometric validators (alternating polarity, width monotonicity,
  cross-ratio ≈ 1/4 — Crosswatch 2008's principled FP rejection: 72% TPR
  at 0.5% FPR) → 1 s circular median → LATCH heading at commit →
  cross-track control (heading delta + lateral offset — heading-only
  never fixes "parallel but 1 m left") → deadband ±5° / ±0.5 m → 1.0–1.2
  Hz L/R temple haptic. Everyone else runs detection on the perspective
  image; live per-frame IPM off the IMU is the update Murali/Coughlan
  2013 was waiting for.
- Dataset: **CDSet-3434** (HuggingFace, Apache-2.0 — day/rain/night/
  damaged/glare) + CDNet's SSVM temporal module (F1 +13 @288, 33 fps on
  Jetson Nano). Mapillary Vistas for pedestrian-perspective pixels;
  Cityscapes has NO crosswalk class.
- **UX**: bone conduction only; mostly silent (Coughlan & Shen 2013:
  tones inaudible at busy corners, users preferred vibration). One
  utterance at curb → haptic align → double-pulse aligned → **silence =
  on-track** → drift pulses at 1.0–1.2 Hz (validated cadence) only
  outside deadband → ToF-triggered "curb, 2 metres." Direction by motor
  LOCATION never rhythm; avoid pitch-as-distance (only 59% map it
  intuitively). Fewer instructions = better clarity AND safety
  (Parsimonious Instructions, IMWUT 2025). Keep detector→haptic <150 ms.
- **The real project: bearing PRECISION.** Published systems report
  detection %, almost never bearing degrees; we need ±3° to beat 9° veer,
  and the literature is silent on whether pedestrian-height worn-paint
  gets there. **Build the ground-truth rig before the detector.** Wet
  night asphalt (the Vancouver case) has no published numbers — expect
  gyro-only fallback from the curb latch, which is why the dead-reckon
  stage must work standalone.
- **Asymmetry over everything: a confidently-wrong correction steers a
  blind person into traffic.** Gate hard on confidence; prefer "crosswalk
  not detected."

---

## DO THESE THREE FIRST

1. **Sunlight bench test, VL53L8CX** — ambient derating is the
   load-bearing unknown for platform-edge AND head-clearance margins.
2. **Glass coherence test on the 8×8 grid** — TOPGN unverified at 64
   zones; know early if we need different hardware.
3. **Order the second camera** (~38–50°, global shutter, manual
   exposure) — three independent analyses say the fisheye can't do text
   or the last metre. Optics; no model fixes it.

## Genuine novelty claims (portfolio)

1. Continuous mid-crossing veer correction in traffic (nobody does it)
2. Ground-plane-referenced overhead clearance with IMU compensation
   (Muñoz explicitly doesn't)
3. Bus door localization from the sidewalk (zero literature)
4. GTFS-RT × camera fusion (no shipping product)
5. Car-door-handle dataset from pedestrian height (doesn't exist, cheap
   to collect)

## Sourcing caveats

WebSearch quotas exhausted; all via direct fetches (arXiv, Crossref,
OpenAlex, Europe PMC, vendor pages). Re-verify: ST UM3109 target-order
semantics + daylight range (st.com timed out), BNO085 GRV drift spec,
Mapillary class list, Guth 2018 ft/inches. Paywalled keys worth chasing:
Scott JVIB 2011 (alignment cues), Manduchi & Kurniawan AER 2011
(head-level accident breakdown).
