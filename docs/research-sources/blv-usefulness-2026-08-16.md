# BLV usefulness research — 2026-08-16 (Opus agent, verbatim findings)

Third research stream (after cv-stack and cv-redteam). The user-side evidence:
what blind pedestrians actually want, what shipped products do, what gets
devices abandoned. Feeds `docs/MASTER-SYNTHESIS-2026-08-16.md`.

## Headline: three things the current prototype gets wrong

1. **It announces the class users rank LOWEST.** "Person" detection was singled
   out (ASSETS'23, 20+ BLV users) as researcher-overweighted: "as a dog user…
   the dog detects those people." The zone that justifies a head-mounted device
   is head-height obstacles: Manduchi & Coughlan 2012 (~300 blind people) —
   **13% suffer head-level accidents at least monthly, unaffected by cane or
   dog use.** Nothing on the market moves that number. That is the product.
2. **Every ~2 s is ~30× too chatty.** Microsoft Soundscape (open source —
   constants readable in AutoCalloutGenerator.swift): same object never
   re-announced within **60 s**; evaluator gated on >5 m travelled AND ≥5 s;
   trigger ranges 10/20/50 m with release at 2× trigger; stale queued callouts
   dropped at playback. "Soundscape is designed not to be too chatty."
   Chatter/false positives are the #1 named abandonment cause ("it's beeping
   all the time… what is the point?").
3. **"person left, 2" is three items; the walking ceiling is two.** van Erp
   2020 (ACM TACCESS, 14 blind adolescents under walking+noise load): recall
   collapses to ~1.6–3.2 items; explicit recommendation: **cap at 2**.

## Ship this week (value/effort order)

1. **Filter to the cane's blind spot** — suppress below-knee and anything the
   cane arc contacts first; announce head/torso obstructions, overhangs,
   poles, wide/approaching objects beyond cane preview.
2. **Adopt Soundscape suppression constants wholesale** (60 s cooldown, 5 s/5 m
   evaluator, 10 m hazard trigger, 2× release, drop stale callouts; scale
   trigger with walking speed).
3. **Cut to two items** — "pole, left" not "pole left, 2".
4. **Proximity = repetition rate, not a number.** No obstacle-avoidance product
   speaks numeric distance. Apple: "feedback becomes more frequent as you get
   closer" + pitch step. Oko: entire signal state as beat, no speech. biped:
   pan=azimuth, pitch=elevation, timbre=class.
5. **Three-level interruption policy** (Soundscape QueueAction:
   interruptAndClear / clear / enqueue). Only predicted collision interrupts.
6. **Instant hush gesture; silence is the default state** (Apple two-finger
   double-tap; Oko designed-silence when unsure).
7. **Per-category earcons + per-category toggles** (Soundscape sense_safety /
   sense_mobility / sense_poi / low_confidence).
8. **Confidence as hedging words**: good fix → plain, medium → "about", poor →
   "around"; near-field → "close by", no number. ("A really nice detailed
   description that could be total rubbish!")
9. **Explicit empty state** — "There is nothing to call out right now"
   (verbatim Soundscape) so silence-from-nothing ≠ silence-from-crash.
   Counter-example: Lookout's unstoppable "No text in view" → "useless".
10. **Push TTS rate up.** Blind listeners: ~8 syl/s parity, trained ~22 syl/s
    (sighted cap ~8). Budget ~1.5 s human reaction after a cue (Adebiyi 2017).

## Next month

11. **Temple motors carry direction+urgency; speech carries identity.**
    HapticHead (CHI'17): head haptics vs spatial audio **2.6 s vs 6.9 s,
    96.4% vs 54.2%**, 2.3° precision. TOCHI around-head with blind users:
    5.7 cm path deviation. .lumen ships forehead haptics (CE, 400+ testers).
    Vibrotactile RT ~44% faster than audio in noise. Constraints:
    **location > pulse rate > intensity** (~5 JNDs on ERM intensity); **≤2
    coding parameters**; **prescriptive beats descriptive** (signal the path,
    not the obstacle — .lumen's centre-pulse = go straight).
12. **Spatialize the speech** (Klatzky 2006: spatialized sound beat spatial
    language on travel time AND working-memory load; Loomis 2005: spatialized
    SPEECH best). Do NOT use abstract earcons for direction (Nees & Liebman
    2023 meta-analysis: worst on all measures).
13. **Direction vocabulary user-selectable; default 8 sectors** ("ahead /
    ahead-left / left / …", Soundscape has zero clock wording). Preference
    split 7/15 clock vs 6/15 relative (Das 2025). Blind travellers over-rotate
    ~17° and quantize turns to ~90° (Ahmetovic '18) — fine angles are wasted.
    Binary L/R insufficient: "how far to the right? … difference between
    walking past and walking into."
14. **Distance units: meters/feet/STEPS setting; near-field = tempo not
    numbers** (Wayfindr: many "may not easily relate to feet or metres").
15. **Feature backlog by demonstrated demand**: (1) text/signs on demand
    (15/20 top task); (2) safe-path/head-height clearance (RNIB: only 9% feel
    safe walking independently); (3) conversational scene Q&A (23/24 want
    voice; head-mounted = #1 form factor); (4) dropped-object finding; (5) bus
    numbers; (6) door/entrance last-10-m; (7) empty seats. DEPRIORITIZE:
    person/crowd detection, queues, face ID (privacy backlash).
16. **Apple's two-tier verbosity**: continuous non-speech proximity baseline;
    gesture escalates to detail ("Open door 5 ft away" → attributes → text).

## Design around, not solve

- **Bone conduction still masks** (May & Walker 2017), worst broadband. Keep
  cues spectrally sparse, leave silence. 7/11 blind participants wanted
  tactile specifically for street crossings → crossing mode = audio drops.
- **Never output a crossing decision.** Say "crosswalk ahead, slightly left";
  never "walk". (ACB/NFB positions.)

## Non-negotiables from users' own words

- Assume the cane stays in the other hand; be strictly additive.
- Don't look tactical ("Robocop", "toilet seat" are the named failures).
- Price ceiling ~$1,000–1,500 one-off; hostility to subscriptions.

## Agent's sourcing caveats
Search budget ran out mid-run; some quotes came via proxies — spot-check
verbatim wording before publishing. Unclosed gaps: no HRTF-vs-spoken-direction
head-to-head; no terse-vs-full-sentence controlled study (Kuriakose 2023 is
mild counter-evidence — users preferred detail); no temple two-point
discrimination values; motor-buzz audibility near ears untested — measure ours.

Sources: Soundscape source (github.com/microsoft/soundscape) · Apple Detection
Mode · Wayfindr principles · Manduchi & Coughlan 2012 (PMC3398697) · Klatzky
2006 · Loomis 2005 · van Erp 2020 · Adebiyi 2017 · HapticHead CHI'17 · Nees &
Liebman 2023 · Das 2025 (arXiv 2504.20976) · Ahmetovic ASSETS'18 · May &
Walker 2017 · Dietrich 2013 · ASSETS'23 (arXiv 2505.19325) · Sauerburger O&M ·
ACB on APS · r/Blind · AppleVis · Oko · .lumen · Glidance
