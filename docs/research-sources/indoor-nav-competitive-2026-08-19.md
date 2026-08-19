# Indoor-nav / last-meter competitive research — 2026-08-19 (Opus agent, condensed verbatim)

## The taxonomy and the hole

| Lane | Who | Last-meter? | Scales? |
|---|---|---|---|
| A. Pre-mapped venue | GoodMaps, NavCog, Waymap | corridor-to-POI, rarely true last-meter | no — venue pays per LiDAR survey |
| B. Installed markers | NaviLens, RightHear, Evelity | yes, where installed | no — physical install everywhere |
| C. Robot guide | CaBot (mapped), **Glidance (claims infra-free)** | yes (claimed) | maybe — but it's a rolling device you store |
| D. Infra-free wearable | .lumen, biped NOA | **NO — avoidance only** | yes, if it worked |

**Correction to UTILITY-ROADMAP U1**: the niche is vacant **in wearable form**;
Glidance's pre-shipping robot contests the capability itself.

## .lumen deep dive
6 cameras + 2 IR projectors + 3 IMUs + GPS, ~1 kg, ~2 h battery, €9,999,
Romania-only. Depth method undisclosed (likely stereo+IR). Forehead haptics =
continuous 100 Hz "reins" pull (guide-dog metaphor), not discrete codes.
**Ships avoidance; destination-level indoor wayfinding is explicitly FUTURE
work** ("take me to my office" = roadmap, not product). €2.17M EIC grant +
€5M SeedBlink; 1,500 claimed pre-orders; delivered units UNKNOWN; zero
independent long-form blind-user reviews found. Cautionary tale: markets
"self-driving for pedestrians," ships obstacle avoidance.

## Others, one line each
- **GoodMaps**: LiDAR-surveyed venues + ARKit camera relocalization; phone
  must be held up; pricing sales-gated; no last-meter claim.
- **NaviLens**: color codes, ~30 m range, 160° angle — POI announcement, not
  routing; only works where codes are installed.
- **Glidance Glide ($1,500-1,800)**: wheeled guide, stereo+mmWave, claims
  "Agentic Wayfinding without mapping, localization or infrastructure" incl.
  doors/elevators/counters. Sold out preorders, slipped ship dates, no
  independent reviews. **The real competitor — track its 2026 rollout.**
- **biped NOA**: 170° depth, avoidance + GPS only; founder concedes indoor
  wayfinding to glasses.
- **Apple Door Detection** (LiDAR iPhones): door + distance + signage to
  ~5 m, but requires a raised, aimed phone — competes with the cane hand.
- **Clew**: ARKit breadcrumb retrace of routes you already walked.
- **CaBot** (CMU): Velodyne + RealSense + Cartographer + iBeacon — needs map
  AND beacons. **GuideNav** (2025): vision-only teach-and-repeat, outdoor,
  needs one demonstration pass.
- **Academic consensus: zero-prior infra-free indoor DESTINATION nav is
  open/unsolved.** No canonical BLV door dataset exists (gap = publishable
  contribution).

## Why head-mounted depth wins the terminal segment (the moat, stated)
1. Hands-free continuous sensing (Apple's fatal flaw: the raised phone).
2. Head-aimed interrogation — proprioceptive, learnable pointing.
3. Head-height hazards — the verified cane gap; pocket phones can't see it.
4. **Active metric depth <4 m regardless of texture/light** — exactly the
   last-meter regime; a door detection with no depth discontinuity behind it
   is a PICTURE of a door. No monocular competitor can make that check.
5. Sub-500 ms on-device loop; cloud VLMs fail metric spatial questions.

## Architecture recommendation (adopted)
- Claim **"terminal guidance"**, never "indoor navigation": servo to a target
  already in FOV over the final 3–10 m (door, elevator panel, counter, seat,
  queue end). Inside the VL53L8CX envelope; the segment every lane drops.
- Visual servoing, not mapping. Detector = bearing; ToF = range + REALNESS
  check; IMU = heading hold when target leaves frame.
- Keep v11 haptics (≤4 regions, location+rhythm, never continuous) — note
  .lumen's continuous "reins" is the defensible opposite; A/B someday, don't
  drift silently.
- **Glass doors break ToF exactly in the doorway use case** — needs a real
  design answer (camera-verified door + absent ToF return = "glass door,
  proceed by cane").

Verification flags: search quota exhausted mid-run — vendor/tech facts solid
(direct fetches), user-reception layer thin; Augmented Cane speed figure
unverified; one agent stream fetched the WRONG domain (lumen.care) and was
discarded. Follow-ups when search resets: Glidance recipient reviews, GoodMaps
pricing, .lumen delivered units.
