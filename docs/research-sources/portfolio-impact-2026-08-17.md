# Portfolio-impact research — 2026-08-17 (Opus agent, condensed verbatim)

Fourth research stream: how to make the helmet a real usable device AND a
legendary portfolio piece. Audiences that matter (science fairs are CLOSED —
he starts UBC in ~3 weeks): internship hiring managers, UBC design-team/lab
recruiters, the blind community / AT world, and the public.

⚠ TIME-CRITICAL: **UBC Engineering Design Teams recruit the first week of
September** (Imagine UBC + E-Week), explicitly take Science students, and the
helmet is a direct credential for robotics/autonomy teams.

## Ranked actions (impact ÷ hours)

1. **Reframe (2–3 h, gates everything):** "a secondary aid for head-level
   obstacles — the gap the cane leaves." >50% of blind travellers hit their
   head yearly; 13% monthly; unaffected by cane/dog (Manduchi & Kurniawan,
   n=307). Say "complements the cane, never replaces it" unprompted in the
   first 30 s. Know the "Disability Dongle" critique and technoableism by
   name. Never "helping blind people see."
2. **Cut the laptop (20–40 h):** the one move that changes the project's
   CLASS (TRL 4 → 6). Recommended: **Pi 5 + AI HAT+ (Hailo-8L)** — YOLOv8s
   25–35 fps, ~10–12 W, ~2.5–3 h on a 10 Ah pack. Don't chase battery: biped
   NOA is 3 h/battery, .lumen ~2 h — 2–4 h untethered = parity with shipping
   products (quotable).
3. **Three expert conversations (6–10 h) BEFORE more building** — free, no
   ethics gate (consultation ≠ testing):
   - Dr. Kim Zebehazy, UBC O&M program coordinator (kim.zebehazy@ubc.ca) —
     warm intro once enrolled.
   - GTT BC-Yukon monthly meeting (gtt@ccbnational.net) — ask for a
     feature-topic slot; read gttprogram.blog summaries first.
   - Pacific Training Centre for the Blind (blind-led) — go asking "should
     this exist?"
   - Also: CNIB BC Intro-to-AT Zoom (2nd Tuesday; amit.ram@cnib.ca).
   Keep a **decisions log**: expert said X → changed Y. Publish it.
4. **Quantified evaluation on a repeatable course (15–25 h):** imitate the
   2026 Sci Reports ETA protocol (walking-speed fraction, contacts,
   incidents, NASA-TLX). Self + blindfolded volunteers = fine for the
   OBJECTIVE metrics today (state the blindfold-invalidity limitation).
   Target sentence: "14 h across 4 environments, 91% on head-height
   obstacles, 2.3 FP/h indoors, 11/h in sun, 0% through glass."
5. **README as a triage surface (3 h):** 7.4 s screens; managers read the
   README, never the code. Hero GIF of the device WORKING above the fold,
   one-sentence what+why, status block ("untethered prototype, ~3 h runtime,
   not yet tested with blind users"). "Why" appears in only 26% of READMEs —
   that's the differentiator. Deep material into /docs.
6. **90-second demo video with a disclosure line** ("single take, real time,
   no cuts, no speed-ups") — full shot list below.
7. **Embedded Rerun recording on the site (4–8 h):** biped uses Rerun for
   exactly this; reviewers scrub a real walk in-browser. Closest a wearable
   gets to Show HN's "let people try it."
8. **Failure-first writeup (3–5 h):** pull the 5 best DEVLOG stories into
   600–900 words. Hiring managers verbatim: "I'm looking for the bumps in
   the road, not a pretty picture." Keep and BRING the ugly prototypes.
9. **One-button start, auto-recovery, legible state (10–15 h):** watchdog,
   graceful sensor-dropout, <60 s to first useful output. A device that
   visibly RECOVERS reads more real than one that never failed.
10. **Enclosure finish pass (8–12 h, ~$30):** 50 ms first impressions;
    aesthetics correlate with perceived usability more than actual usability
    does. Sand + primer + paint, strain relief, no hot glue. AT-specific:
    bulk/weight and "advertising disability" are documented rejection causes
    — address head-on.
11. **Accessible artifacts (3 h):** audio-described + captioned video,
    screen-reader-clean README, no image PDFs. An AT project failing this is
    self-refuting.
12. **Distribution once 1–8 exist:** Hackaday.io log (log cadence is the
    scored artifact), Sight Tech Global (attend first), Show HN (option
    value).

**Skip:** long PDF portfolios, code dumps, any admissions-facing artifact
(UBC evaluates grades + Personal Profile only).

## The 90-second shot list (keep verbatim)

0:00–0:06 locked-off shot: cane sweeps clean, head stops an inch from an open
cabinet door. Text: "A cane sweeps the ground. Over half of blind travellers
hit their head at least once a year."
0:06–0:13 the helmet on a head, hands empty. "2× ToF · camera · IMU · 3
temple motors. Runs on the helmet. No laptop."
0:13–0:38 **money shot, one continuous take, split frame**: third-person walk
| live world model (points, boxes, which motor fires), synced, latency
counter, burned-in disclosure line.
0:38–0:48 interface honesty: near-silence, one utterance at the decision
point. "It spoke 4 times in this walk."
0:48–0:58 **the deliberate failure**: glass door, show the miss, then the
mitigation or the honest "no fix yet." (Pratfall effect requires competence
FIRST; two-sided arguments need refutation or they backfire — O'Keefe,
107 studies.)
0:58–1:12 course montage + numbers card.
1:12–1:22 one real sentence from the O&M instructor / blind tester — never
faked; decisions log if it hasn't happened yet.
1:22–1:30 device NEXT TO a white cane, equal framing: "It does not replace
the cane. It watches the height the cane can't reach." URL.

## Credibility checklist (condensed)

- Framing: secondary aid, first 30 s; narrow cited problem; no rescue
  language; can name Disability Dongle + technoableism; acknowledge
  head-mount jitter/fatigue critique (Han 2024).
- People: ≥1 O&M professional + ≥1 blind adult (not family), named with
  permission; decisions log published; know Phillips & Zhao (29.3%
  abandonment, mobility aids worst, #1 predictor = ignoring user opinion);
  never recruit informally at org programs; "partner" claims need WRITTEN
  permission.
- Evidence: publish ≥1 unflattering number; baseline = cane alone; report
  cognitive load; ToF limits up front (glass, dark matte, sunlight, <60 cm
  crosstalk); blindfold testing named as an invalid usability proxy.
- Ethics: no human-participant recruitment before approval (TCPS 2 / UBC REB
  once he's enrolled); accessible consent forms (never scanned PDFs); blind
  adults sign for themselves — no guardian countersigning.
- Presentation: honest comparison table vs biped NOA / Glide / .lumen WITH a
  "what ours does worse" column; "Nothing about us without us" understood.

## Flags

- **The 300% rule** (r/embedded): a project you or others ACTUALLY USE beats
  any sophistication. Everything above serves that.
- All artifacts are assembly jobs on the same raw material — process photos +
  the live DEVLOG. Shoot as you go.
- Verify before public use: Manduchi head-injury %s, Phillips & Zhao n; do
  NOT use the untraceable "~75% ETA abandonment" figure.

Full source list in the agent transcript; headline: Ladders eye-tracking, HN
hiring threads, r/embedded threads, TechCrunch "How to fake a robotics demo",
Wistia length data, Rerun×biped, NASA TRL, Disability Dongle (CASTAC), Shew
"Against Technoableism", 2026 ETA RCT (PMC12909938), TCPS 2, UBC design teams.
