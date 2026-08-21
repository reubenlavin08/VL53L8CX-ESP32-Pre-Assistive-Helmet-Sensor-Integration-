# Bus boarding literature review — who did what, with numbers — 2026-08-20

Component report (citation backbone behind the syntheses). Method: direct
fetches of DBLP/Crossref/arXiv/Europe PMC; paywalled items flagged.

## Corrections to common attributions

1. **All_Aboard = Schepens/Harvard (Gang Luo's lab)** — not IIIT, not
   MSR India, not Manduchi.
2. AI Suitcase consortium (CAAMP) = Alps Alpine + IBM Japan + OMRON +
   Shimizu (no Mitsubishi).
3. **IBM/Asakawa have NO bus-stop or bus-boarding paper** — full DBLP
   sweep (27 hits): all indoor/campus/museum/airport. Kyoto/Tokyo bus
   trials unverifiable in literature — press-only if real.

## IBM/CMU line (indoor, but methods transfer)

- NavCog (W4A 2016) / NavCog3 (ASSETS 2017, TACCESS 2019 "in the Wild")
  — BLE-beacon turn-by-turn.
- CaBot (ASSETS 2019); PathFinder (CHI 2023); WanderGuide
  (arXiv:2502.08906).
- Airport study (CHI 2019, 10.1145/3290605.3300246): blind users
  completed real airport itineraries independently with BLE — closest to
  vehicle boarding.
- **LineChaser (CHI 2021, 10.1145/3411764.3445451)** — queue advancement;
  the only validated "advance now" cue design; structurally identical to
  "step to the door when it's your turn."

## All_Aboard (the field-study gold standard)

Pundlik, Shivshanker, Traut-Savino, Luo, TVST 13(1):11, 2024
(10.1167/tvst.13.1.11, PMC10793390, arXiv:2309.10940): MobileNetV2 on
~10,000 Street View stop-sign images; on-device; detection 10–15 m;
4-level distance-coded homing tone, top level <2 m; 24 legally blind
participants, 20 Boston stops. **91% vs 52% (p<0.001); final gap 1.8 m
vs 7.0 m (p<0.001).** Route OCR + boarding = explicit future work.

## Manduchi (UCSC) / CCNY

- Flores & Manduchi, IEEE Pervasive Computing 2018 (paywalled).
- RouteNav transit-hub wayfinding, ASSETS 2023.
- **S-BLE dataset** (arXiv:2512.22422, Dec 2025): 28 users, 20 shuttle
  buses, 2 BLE beacons/vehicle — Be-In-Be-Out boarding detection.
- Pan/Yi/Tian ICMEW 2013 bus detection (paywalled, pre-DL).
- Route OCR: Tsai & Yeh 2013; Cheng & Tsai 2014; Shafique 2025
  (Algorithms 18(10):616).

## Bus door localization — the confirmed gap

- arXiv full-text `"bus door"` = **0 results**. Only adjacent work:
  - Perumal 2024 (Sensors 24:6411): full pipeline bay detection 96.9% +
    Tesseract OCR 97.2% — **but 160–248 s per stage, dataset-only, no
    blind users.**
  - Tangsuksant 2019: where-to-stand classifier 86%; **15×15 cm route
    number legible to max 15 m** (the empirical ceiling).
  - Aircraft cabin door detection (ICARCV 2018); indoor door detection
    (>95%, arXiv:1301.0432).

## UX evidence

- "Catching the Right Bus" (ICCHP 2016) + BlindMobi (2019) + Lim (2008):
  the BLE-hailing cluster exists because **identifying/hailing the right
  bus is an 18-year-old unsolved complaint.**
- StopInfo (ASSETS 2014): riders need PHYSICAL stop descriptions, not
  just route data.
- Babu & Fuller 2015 (7 blind users, CTA Bus Tracker): help-seeking
  clusters on ETA determination and finding bus location.
- Floating bus stops WORSEN boarding (Edwards 2026 rapid review).
- **No study specifies announcement timing for the boarding sequence** —
  usable constraints: 15 m camera bus-ID ceiling, All_Aboard's 10–15 m
  onset + <2 m peak, LineChaser's advance cue.
- Rahi 2016 priority ranking (20 legally blind): #1 missing tactile
  indicators, #2 unsafe sidewalks, #3 obstacles, **#4 can't read bus
  numbers**, #6 fear of falling, #9 platform gaps.
