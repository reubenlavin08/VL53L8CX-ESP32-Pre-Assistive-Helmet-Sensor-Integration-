# Reading guide — everything from 2026-08-18 → 08-20

You sent ideas without reading replies; this is the catch-up index, in
reading order. Everything lives in `docs/` — open this note in Obsidian and
click through.

## 0. The two bottom-line answers first

**Is it novel?** As a *system*, no — every architecture-level claim has prior
art (a 2018 paper even did head-swept depth mapping for blind users). As
*engineering slices*, yes: the signal-weighted zone-centroid calibration,
seam-abutted sensor tiling, head-pose-gated alerts, and the whole
"sparse ToF + smart decay on a $6 sensor" implementation are unpublished.
Nobody ships head-mounted ACTIVE depth — that's the moat.

**Is it patentable / already patented?** Not worth patenting: ~$25k to grant,
~$600k to enforce, and our public repo already destroyed Europe/China rights
(absolute-novelty countries). Nothing we do infringes anyone as open-source
non-commercial — but **.lumen's granted patents nearly describe our build**
(read before ever selling), and **UBC owns anything built with their
facilities — keep this project on your own gear and time.** The right move:
**defensive publication** (1 hour, free, Zenodo DOI) — permanently blocks
anyone patenting our approach. Full verdicts:
[[patents-priorart-2026-08-20]].

## 1. The decision docs (read these two properly)

1. [[IDEA-BANK]] — **~50 stealable/buildable ideas from everything below,
   one triage table. This is the doc you mark up.**
2. [[UTILITY-ROADMAP]] — the strategy: obstacle detection is the entry
   ticket; the product is "terminal guidance" (door/pole/seat/queue over the
   final metres) + head-height safety.

## 2. Your requests, in order, and where each answer lives

| You asked | The answer doc | One-line takeaway |
|---|---|---|
| "research how to make it really useful / what blind people need" | [[blv-daily-life-2026-08-18]] | Get off "avoidance" — destination help + head-height is the product; helmet form factor is the top rejection risk |
| (supporting) abandonment + low-tech reality | [[abandonment-lowtech-2026-08-18]] | Mobility aids = worst-abandoned category; "shut-up mode should be the default" — a blind engineer |
| (supporting) what happened to every commercial wearable | [[wearables-fate-2026-08-18]] | All 8 dead/abandoned/niche; phone AI ate OrCam; false positives kill returns |
| "how do we do indoor navigation / last step" + ".lumen and competitors" | [[indoor-nav-competitive-2026-08-19]] | Nobody ships wearable last-meter guidance; .lumen ships avoidance only at €9,999; Glidance (wheeled) is the one live threat |
| "is anything I'm doing innovative or patentable" | [[patents-priorart-2026-08-20]] + [[patents-toyota-blaid-2026-08-20]] + [[patents-apple-2026-08-20]] | See §0. Toyota: 40-60 filings, none head-mounted or depth. Apple's door patent granted Jan 2026 but camera+viewfinder only |
| "radar in bats" (Dad) | [[biosonar-2026-08-20]] | Found 2 real bugs in our code (both FIXED); our audio is accidentally echolocation-safe (now locked); glass free-experiment queued |
| "HRTF, pitch, pulse, volume" (Dad) | [[hrtf-spatial-audio-2026-08-20]] | Complete buildable design: spatial clicks, rate=distance, pitch=height, volume=confidence only. Blind users beat sighted controls with this pattern after 30 min training |
| (spun off) ultrasonic/radar for glass | [[ultrasonic-mmwave-glass-2026-08-20]] | Ultrasound reflects 99.99% off glass vs our 4%; free B1-sync interference fix found in our own driver; radar deferred |

## 3. Older context (if you want the full arc)

- [[MASTER-SYNTHESIS-2026-08-16]] — the callout-engine evidence (Soundscape
  constants, 2-item limit, silence default)
- [[portfolio-impact-2026-08-17]] — demo craft, UBC design-team deadline
  (first week of Sept!), credibility checklist
- [[imu-uses-2026-08-17]] — 14 ranked IMU features (floor rejection,
  tap-to-query, head-as-gimbal memory)
- [[CALLOUT-PROTOCOL]] — the aviation two-mode voice design (+ §9 locked
  audio band)
- [[FIELD-TEST-RUNBOOK]] — the backpack rig procedure

## 4. What already changed in the code from all this (no action needed)

TTC terminal-buzz ticker · range-adaptive path cone (bug fix) · audio band
locked · silence-default engine · brevity mode · IDEA-BANK compiled.
Everything committed + pushed through `docs/IDEA-BANK.md`.

## 5. Waiting on you

1. Mark up [[IDEA-BANK]] (✅/❌/🕐)
2. Go/no-go: HRTF spatial-audio engine build
3. Glass free-experiment (needs you + a glass door)
4. IMU mount calibration (2 min, still not run — gates all IMU features)
5. Zenodo defensive publication — say the word and I'll prep it
