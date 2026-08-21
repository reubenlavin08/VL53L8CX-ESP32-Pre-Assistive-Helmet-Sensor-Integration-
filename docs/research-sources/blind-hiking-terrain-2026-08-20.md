# Blind hiking — first-person accounts, hazards, negative evidence — 2026-08-20

Feeds the REOPENED terrain question ([[IDEA-BANK]] §C/§G). Companion doc:
the full terrain-feasibility report (agent still running) will land beside
this one. Condensed-verbatim from the research agent; links inline.

## Bottom line first

**Mostly aspirational, with one narrow real seam.** The blind-hiking
community's unanimous answer is poles + guide dog + buddy — not devices.
The most experienced blind hikers disparage the tech that exists. The one
evidence-backed gap: **obstacles above the ground plane** — overhanging
branches and suspended logs at 2–3 ft, named independently by two sources
as exactly what cane/pole sweep cannot detect. A torso/head-height
*complement* to poles fits the evidence; a "trail navigator" does not.
Even for that gap nobody asked for a device — they just report getting
hit — so demand is unproven until validated directly (r/Blind or
Awarewolf customers).

## (a) First-person accounts

- **Derek Riemer, "Hiking Blind"** (richest source) —
  https://derekriemer.com/posts/2022/05/23/hiking-blind/ — "I tend to like
  to carry two trekking poles... I keep one pole in front of my feet, and I
  shuffle that pole from one foot to the other." Rejects elbow-guiding and
  tethers ("I never connect to someone else with a tether like most blind
  runners do"); endorses the buddy system: "should be two buddies when one
  of the party members is blind."
- **Trevor Thomas (BBC Ouch)** —
  https://www.bbc.com/news/blogs-ouch-34186187 — "Hiking alone seemed to
  give me some control"; "It is the one environment which does not
  discriminate. It treats me the same as everyone else." Guide dog
  Tennille: "Anything serious will cause her to stop dead in her tracks and
  pull me away." Trekking poles "to continually scan for obstructions in
  front."
- **Blind Travels solo RMNP hike** —
  https://blindtravels.com/hiking-solo-when-blind-or-visually-impaired/ —
  "used my cane to probe each stair"; "Small swings of the cane also help
  to move some of the larger rocks"; navigated by time-distance estimation,
  compass, and other hikers' "voices as a constant marker."
- **Perkins "8 Tips for Hiking While Blind"** —
  https://www.perkins.org/resource/8-tips-for-hiking-while-blind/ — sighted
  guide, short rope to stay connected, walking poles, boots. **No
  technology mentioned anywhere.**

## (b) Hazards named

- Riemer: talus ("Loose boulders, rocks, and other debris A.K.A. talus
  will twist your ankles"), roots/holes/steps, **"fallen trees won't
  necessarily be found by poles, sometimes they can be balanced... a good
  2-3 feet in the air"**, "A log with branches sticking out taken to the
  legs hurts a surprising amount," steep drop-offs/exposure, scree,
  inability to read weather.
- AccessRecreation —
  https://www.accessrecreation.org/Trail_Guidelines/Blind_and_visually_impaired.html
  — cane locates trail edge and obstacles; **overhanging branches are the
  key danger because they sit "outside the sweep zone of the cane."**
- Blind Travels: loose rolled rocks mid-path, mud pools, inconsistent
  carved stone stairs, stream crossing on a "sketchy wooden bridge with no
  handrails."

## (c) Negative evidence (the stronger side)

- Riemer on tech: **"talking compasses are mostly trash"; "there's no such
  thing as an accessible topo-map"; "Accessible maps don't even come close
  to providing what visual maps do."**
- Thomas: GPS "was not accurate enough for a blind person to be able to
  pinpoint exactly where they were" — solved with a trained dog, not a
  device.
- Perkins' official guide: zero devices. AccessRecreation asks for trail
  maintenance + written descriptions (addressed to land managers, not
  hardware).
- Five r/Blind threads asking exactly this question (search snippets;
  Reddit unfetchable): "a sturdy wooden cane for hills" + sighted guide
  (reddit.com/r/Blind/comments/w1zv44), "two hiking poles" (…/tylsn7),
  cane+poles paired plus O&M training (…/w796e6), poles for speed
  (…/yoozc8), a Dakota Disk cane tip (…/bxe49w). **Not one community
  answer is a device.**
- The social model is partly the point: Thomas's "does not discriminate"
  framing suggests device mediation subtracts what they hike for.

## (d) Products

- **Awarewolf Gear All Terrain Cane** — the only real trail-specific
  product; purely mechanical titanium cane. Founder Dave Epstein
  (retinitis pigmentosa): "there wasn't anything on the market for blind
  hikers, other than flashlights and first aid kits." £99 ex-VAT; **RNIB
  is exclusive UK distributor** — the category's one commercial
  validation, and it has no electronics. https://awarewolfgear.com/ ;
  https://attoday.co.uk/innovative-cane-designed-for-hiking-launches-for-blind-and-partially-sighted-people/
- No electronic wearable marketed for blind trail use found. biped.ai
  domain is dead; WeWALK/Glidance/.lumen are urban-marketed (not
  exhaustively verified).
- Decay signals: blindhiker.com and teamfarsight.org are DNS-dead;
  2020visionquest.org redirects to an unrelated site (domain sold).

## Implication for our build

Our helmet already IS the above-ground-plane complement (head/torso
coverage the pole sweep misses) — the trail case strengthens the existing
head-clearance feature rather than justifying a new "terrain narration"
one. Hold the terrain verdict until the feasibility agent (ToF+IMU
roughness sensing) reports.

## Coverage caveats

NFB Braille Monitor and AFB AccessWorld unfetchable (403/404); Reddit
quotes are search snippets, not full threads; "no electronic trail product
exists" is probable, not exhaustive.
