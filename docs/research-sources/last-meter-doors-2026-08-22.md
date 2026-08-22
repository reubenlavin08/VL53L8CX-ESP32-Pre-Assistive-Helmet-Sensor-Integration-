# Last-10-m door guidance — Maps handoff, OSM prior, scan-and-select — 2026-08-22

Answers your three questions: how blind people use Google Maps, "the
door you probably want," and implementing scan-and-select.
Condensed-verbatim; live data queried today.

## 1. How blind people use Google Maps — and what "arrived" means

- Screen reader (TalkBack/VoiceOver) + **Detailed Voice Guidance** for
  walking (launched 2019 for exactly this population: progress updates,
  distance-to-turn, crossing warnings — verify the toggle still exists
  on your phone, 2-min test). **Lens in Maps** speaks storefront names
  when you raise the camera (2023, screen-reader integrated).
- **The punchline**: "You have arrived" fires on GPS proximity to the
  address centroid — typically **5–20 m out, often the wrong side of
  the building**. The phone reliably delivers the right block face,
  never the door.
- This gap has a name in the literature: **"the last-few-meters
  wayfinding problem"** (Saha et al., ASSETS 2019 — read in full; N=22
  formative study of coping techniques + vision-based probe). **Our
  handoff design is exactly the identified gap.**

## 2. The "door you probably want" — OSM reality check (live queries)

- Global OSM: 5.39M entrance-tagged nodes. Sounds good until you zoom:
- **Downtown Vancouver core (live Overpass query today): 652 buildings,
  118 entrance nodes, only 30 entrance=main** (<18% coverage).
- **Dunbar residential (your neighborhood): 3,547 buildings, ZERO
  entrance nodes.**
- Academic confirmation: researchers *infer* entrances because tagged
  ones are missing (Mobasheri 2017).
- Google Places API does NOT expose entrance coordinates publicly
  (Google keeps its internal "entrance arrows"); Apple/Bing nothing.
- **Verdict: OSM is a bonus prior when present (downtown, transit),
  never the mechanism. The camera finds doors; OSM at best promotes a
  candidate to slot 1.** Query is trivial + cacheable (one Overpass GET
  around the pin, pre-fetched before the trip).

## 3. Scan-and-select — implementation evidence

- **Glide confirmed** (FAQ): users scan for "stairs, doors, elevators,
  counters," pick, get guided — and notably Glide shipped this BEFORE
  full navigation (validates our priority). **No public detail on
  multi-candidate announcement — our bearing+distance candidate list
  may be a genuine differentiator.**
- **Auditory menu science**: compressed SPEECH cues beat abstract
  earcons for dynamic item sets (spearcons, Human Factors 2013) —
  don't invent a tone vocabulary for candidates; use terse spatialized
  speech.
- **N ≤ 3 + "more"** as the last item (design assumption backed by
  working-memory limits, not a specific citation).
- **Ordering**: GPS-destination-bearing alignment FIRST, then distance
  (nearest-first picks the loading dock you already passed);
  door-likeness filters, doesn't order; OSM entrance=main promotes.
- **Vocabulary**: "Door one, twelve o'clock, eight meters — glass
  double door." One attribute max. **Speak each candidate FROM its
  actual bearing** (we have spatial audio — spearcon + spatialization
  agree).

## The recommended flow (build spec)

1. **Trigger**: phone says "arrived" or user double-taps → destination
   lat/lon+name to helmet; OSM entrances pre-fetched/cached.
2. **Scan**: user pans head ~2–3 s; camera+ToF find door candidates;
   IMU anchors each in world frame.
3. **Announce ≤3 + "more"**, each spatialized from its true direction,
   ordered by destination-bearing then distance; "— likely main
   entrance" when OSM agrees.
4. **Select**: number (voice later; button-cycle + long-press now).
   Confirmation tone FROM the chosen door's bearing.
5. **Beacon lock** → existing Soundscape beacon; haptics take over
   inside ~2 m (traffic noise masks audio near facades); terminal:
   "Door, one meter, handle on the right."
6. **Fallbacks**: "no doors found — try panning"; "rescan" anytime.

## To verify cheaply later

Detailed Voice Guidance toggle on a 2026 phone; Lens-in-Maps TalkBack
flow; Places API non-exposure (95% confident); Glide's actual
multi-candidate UX (watch a full demo); AppleVis threads (site blocked
the agent).
