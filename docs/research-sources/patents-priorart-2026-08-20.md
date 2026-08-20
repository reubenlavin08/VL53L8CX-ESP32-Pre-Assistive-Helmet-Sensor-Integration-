# Prior-art & patentability synthesis — 2026-08-20 (Opus agent fleet, condensed verbatim)

**Bottom line: nothing in the seven candidate claims survives as clearly
novel. PUBLISH, DON'T PATENT.** (Indicative search, not a legal clearance
opinion — Google Patents was blocked; academic axis solid.)

## Per-claim verdicts

| # | Our claim | Verdict | Killer reference |
|---|---|---|---|
| 1 | ±22.5° ToF pair + fisheye, planar-target extrinsics | NOT NOVEL | DiscoBand (UIST 2022, 16 yawed multizone ToF on a wearable); DELTAR (ECCV 2022, VL53L5CX+RGB planar calibration); GuideTouch (two angled ToF + haptics, blind nav) |
| 2 | Signal-weighted effective zone centroids + joint rigid solve | NOT NOVEL as method | Glennie & Lichti 2010 — per-beam angular corrections fit vs planar targets, 16 years earlier |
| 3a | Terminal guidance (bearing+range+IMU hold) | NOT NOVEL | NaviSense (arXiv 2509.18672); Toyota US9915545 claim 1 (verified) |
| 3b | Door depth-verification (no return = glass) | INCREMENTAL | Apple ships door+distance+state (iOS 16); Passage-Aware RGB-D SLAM "geometric opening validation" |
| 4 | Head-as-gimbal pose-tagged ToF memory | INCREMENTAL | **eLife 2018;7:e37841 (CARA)** — head-worn depth swept by head motion, pose-tagged egocentric map, blind users; Zebedee US9146315 |
| 5 | Head-pose-gated alert suppression | NOT NOVEL | Same eLife paper's Spotlight mode; Microsoft US9977573 |
| 6 | Plain/brevity two-mode callouts + trainer | NOT NOVEL | Apple US8381107 (verbosity tiers with auto-promotion, 2010); Honeywell US12347422 (phraseology coach) |
| 7 | IMU voice-guided mount leveling | NOT NOVEL | Phase One US8189058 (priority 2000): sound frequency/amplitude rises approaching alignment |

**Genuinely thin air (narrow engineering slices, not inventions):** analytic
per-zone ray correction derived from the VCSEL illumination profile (DELTAR
et al. treat zones as uniform); minimal-overlap seam-abutted tiling;
time-decayed occupancy tied to an orientation input (zero claim-scoped hits);
"sparse-ToF + decay on a microcontroller" as a whole — **unpublished, and
worth publishing.**

## Competitor portfolios (beyond Toyota/Apple — see companion docs)

- **.lumen = the real one.** US11371859, US12044541, US12546619 (granted
  2026-02), WO 2022/161855 w/ CA member. **US 2022/0282985 nearly describes
  our build**: head-worn camera + depth + IMU + left/centre/right haptics.
  Our non-infringement anchors: no sound-localisation mic array, no
  object-relationship modelling, no conditional-walkable-area, no POI
  routing. FTO risk nil while non-commercial open-source; READ THESE FIRST
  if ever commercializing.
- **Microsoft**: densest (~12-15 families). US9977573 (head-orientation →
  attended-subspace sounds) highest read-on; Soundscape core US9612722 live
  to ~2035; the head-mounted-depth+binaural claims require ray-casting into
  a reconstructed model + per-point HRTF distance delays — our anchor.
- **biped**: ONE pending family (filed as Fusion Lab Technologies SARL), no
  grants, no US member; claims score-based object selection; ToF/IMU not
  claimed.
- **Glidance**: zero corporate patents; one PCT under founders' names —
  every claim requires wheels + grip; a head-worn device cannot infringe.
- **WeWALK**: one family, pure cane hardware claims. Not a threat.
- **OrCam**: 221 records, camera+recognition+audio; no depth/ToF claims.
- **Open hole**: Apple's two pending continuations may drop the
  display/viewfinder limitation — the biggest unread item.

## ⚠ THE UBC CORRECTION (behavioral rule)

**UBC is institution-owns (since ≥1993), not inventor-owns** (that's
Waterloo). Policy LR11 s5.5: "University Research Products are owned by the
University"; trigger s5.1 = ANY use of UBC facilities/equipment/
UBC-administered funding OR scope-of-duties; students explicitly included
(s6.8). Coursework carve-out (s2.1) is four-conditions-narrow and a PI can
void it. Revenue split if UBC owns: 50% to inventors NET of all patent/legal
costs.
**Rule: keep the helmet on personal equipment, personal time, outside
coursework/UBC funding. Get ownership answered IN WRITING before folding it
into any ENPH project or lab.**

## Economics (AIPLA 2023 + USPTO 2025 fees)

Provisional drafting median $5k (self-drafted $65 — but enables nothing =
worth nothing); complex electrical utility $11k drafting; realistic all-in
to grant **$20-30k over 2-3 years**; enforcement median **$600k through
trial**; IPR defense $350k. PCT = 30-month deferral, not a world patent.
**Europe/China rights are ALREADY GONE** (absolute novelty; the public repo
did it). US/Canada 12-month grace clocks started at first public commit.
"Patent pending" buys ~nothing legally pre-grant; admissions don't score it.

## Action list (adopted)

1. **Defensive publication (~1 hr, free): push DEVLOG + calibration writeup
   to a Zenodo DOI** (and/or arXiv) — permanently blocks anyone patenting
   our specific approach, and it's citable.
2. Cite prior art proactively in our own writeup (eLife 2018 CARA, Zebedee,
   DiscoBand, DELTAR, Glennie & Lichti). Frame: "efficient implementation of
   known techniques on a $6 sensor and an ESP32" — honest and stronger.
3. Keep UBC boundary (above).
4. If ever commercial: read .lumen US12044541 c1, US2022/0282985 c1,
   Microsoft US9977573 in full first.

Gaps a real search would close: Apple continuations' claims, CPC-class
sweeps (A61H3/061, G01S17/86, G01S7/497, G06T7/80), ST's own zone-FoV
portfolio, CN-language art.
