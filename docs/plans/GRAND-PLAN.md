# GRAND PLAN — every addition, in execution order — 2026-08-23

> **EXECUTION STATUS (same evening)**: ALL build items (1–9) implemented,
> compiled, unit/live-tested where testable without the wearer, committed
> and pushed (see DEVLOG 2026-08-23 for the full record). Firmware with
> tap + drop + /api/pattern + /api/tunnel builds clean — **OTA flash
> pending helmet power-on**. Remaining items need the wearer: **item 0
> (live walk test of everything)** and **item 10 (demo video + physical
> finish)**. Laptop verified field-ready for the entire stack.

Ten scoped plans (each has its own PLAN-*.md in this folder with full
design, file-referenced steps, tests, risks, hours). This document is
the ORDER and the reasoning. Execute consecutively; test + commit after
each; the deadline guard at the bottom decides what gets cut.

## Ordering principles

1. **Live-test before building** — nothing new lands on untested code.
2. **Measurement before features** — the FP/hour logger goes in early
   so every later feature gets measured from its first hour.
3. **Batch the firmware** — everything that touches main.c ships in ONE
   build + OTA flash (tap, drop, /api/pattern) to minimize flash risk.
4. Small/low-risk before flagships; conditionals last; video is the
   fixed finale.

## The order

| # | Item | Plan doc | Hrs | Needs Reuben? |
|---|---|---|---|---|
| 0 | **Live-test + fix day** — l, g (verify IMU sign!), d, v/h, voice | — | ~2-3 + fixes | YES (gate) |
| 1 | **FP/hour + intervention logging** (flightlog.py, ring clips, session_report) | PLAN-fp-hour-intervention-logging | 6-8 | test only |
| 2 | **Steps-not-meters** (+stride cal) | PLAN-steps-not-meters | 3-4 | 1-min stride walk |
| 3 | **Head-turn speech gate** (100°/s on / 60 off, gate_log for the novelty writeup) | PLAN-head-turn-speech-gate | 4-5 | shake test |
| 4 | **Firmware batch + OTA**: tap-to-query (TAP: line → describe) + drop alarm (accel freefall → DROP: → laptop announces) + /api/pattern (duck haptic for #7) | PLAN-tap-to-query, PLAN-drop-alarm | 8-10 | tap/drop tests |
| 5 | **Interrogation layers** (one around_me(layer) responder for F9/voice/tap; labels→steps→VLM) | PLAN-interrogation-layers | 4-5 | listen test |
| 6 | **FLAGSHIP: find-by-text** (ocr.py via nemotron; scan-pan; beacon lock on the word; "read that") | PLAN-find-by-text | 8-10 | pantry demo |
| 7 | **FLAGSHIP: head-clearance** — ⚠ do its 10-min GEOMETRY CHECK first (top-row zones on a doorframe: does the ~+1° top edge actually see overhead in gait?) — if marginal, ship v1 as "overhead alert during head sweep" and log the splay re-aim as v2 | PLAN-head-clearance | 9-10 | broom test |
| 8 | conditional: **spatialized clicks** (directional ticker) | PLAN-spatialized-clicks | 4-6 | listen |
| 9 | conditional: **walkable tunnel** (needs /api/tunnel firmware, second flash) | PLAN-walkable-tunnel | 9-10 | hallway |
| 10 | **Demo video + physical finish + README landing** (locked shot list; glass-door honesty beat; tap-describe signature moment) | portfolio-impact doc | 8-12 | YES |

Core total (0–7): ~45 h. With 8–10: ~70 h.

## Dependency notes

- 4 before 5 (tap trigger feeds the unified responder) — but 5 works
  keyboard/voice-only if 4 slips.
- 4's /api/pattern before 7's duck haptic (speech-only fallback exists).
- 1 before 6/7 so the flagships are born measured.
- 9 requires a second firmware flash — that's why it's conditional/last.
- Stale-memory correction (from scoping): motor map is CENTER=18,
  RIGHT=8, LEFT=17 (main.c, ID-verified) — not the 7/15/16 in old notes.

## Deadline guard (UBC design-team window ≈ Sept 2)

Hard rule: **items 10 (video) and 0 (live test) are untouchable.** If
the calendar reaches **Aug 29** and item 6 isn't done, stop feature
work wherever it stands and jump to 10. Cut order when behind:
9 → 8 → 7 → 5. Never cut: 0, 1, 10.

## Standing rules during execution

Silence-default is inviolable (new sounds opt-in) · directive tier and
sensors-lost are never gated by anything · every item ends with a test
listed in its plan doc + a DEVLOG entry + a commit · FP/hour gets
reported from item 1 onward.
