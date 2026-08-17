# MASTER SYNTHESIS — all four research streams → one build list — 2026-08-16

Streams: CV stack (`research-sources/cv-stack-research-2026-08-16.md`), red-team
(`cv-redteam-2026-08-16.md`), BLV usefulness (`blv-usefulness-2026-08-16.md`),
aviation protocol (`CALLOUT-PROTOCOL.md`). Items marked **[BUILD NOW]** are
implemented in tonight's autonomous run; **[HW]** blocked on hardware;
**[LATER]** scoped but deferred.

## The three verdicts that reshape what we built

1. **We were 30× too chatty.** Soundscape: 60 s per-object cooldown, silence is
   the default state, hazards only. Our 2 s routine cadence must go.
2. **Numeric distances don't belong in walking speech.** No shipped product
   speaks numbers while walking; proximity = repetition rate (parking-sensor
   pattern). Numbers survive only in on-demand queries.
3. **"Person" callouts are the least-wanted feature; head-height obstacles are
   the product.** 13%/monthly head-level accident rate, unmoved by cane or dog.

## Build list with scopes

### 1. [BUILD NOW] Silence-default hazard engine (replaces routine tier)
Scope: ROUTINE tier removed from autonomous speech. Speaks only: CAUTION
hazards (<1.8 m or closing, upper-row zones only), DIRECTIVE commands, clean /
sensors-lost. 60 s per-object cooldown (approach still re-announces). Stale
items (>1.5 s) dropped at playback, Soundscape-style.

### 2. [BUILD NOW] Two-item grammar, no numbers
Scope: "obstacle, left" / "maybe pole, ahead". Distance moves to the ticker
(#3) and the query (#4). van Erp: 2-item ceiling while walking.

### 3. [BUILD NOW] Proximity ticker (repetition-rate distance)
Scope: parking-sensor tick (short 600 Hz blip) while a hazard is inside 1.8 m
in the path; period scales 1.2 s @1.8 m → 0.15 s @0.5 m. Spectrally sparse,
silence between ticks (bone-conduction masking evidence). Off when clear.

### 4. [BUILD NOW] On-demand scene query (two-tier verbosity, Apple pattern)
Scope: F9 (global) speaks up to 2 nearest objects WITH hedged distances
("person ahead, about 2 meters"), or the verbatim Soundscape empty state:
"There is nothing to call out right now." Numbers allowed here — stationary
aiming context.

### 5. [BUILD NOW] Confidence hedging + no-class honesty
Scope: det conf <0.50 → "maybe X"; ToF-only → "obstacle". Query mode: ranges
spoken as "about X" (association is zone-coarse).

### 6. [BUILD NOW] Cane-blind-spot filter
Scope: hazard triggers require a zone in the UPPER THREE rows (head/torso/
waist band of the 22.5°-down rig). Bottom-row-only returns = cane territory,
rendered but never spoken. (Proper height gating needs the IMU ground plane —
[HW] refinement.)

### 7. [BUILD NOW] Person deprioritized
Scope: selection = nearest hazard regardless of class; person gets no
priority. Tier-1 styling stays visual-only.

### 8. [BUILD NOW] Global controls
Scope: F8 hush (exists) now also silences the ticker; F9 query; `--rate` flag
(default 240; blind users comprehend 8–22 syl/s — headroom is theirs).

### 9. [BUILD NOW] ByteTrack + closing from track history
Scope: worker switches to `model.track(persist=True)` (ultralytics built-in
ByteTrack). Range history keyed by track ID instead of class name — a second
person entering can't inherit the first one's history. Closing = range rate
< −0.5 m/s over the ID's own 1 s window. Distance still re-derived from the
current ToF frame every cycle (red-team #5).

### 10. [BUILD NOW] Brevity trainer
Scope: `camera/callout_trainer.py` — flashcard drill: speaks a brevity
callout, user answers (arrow keys = direction, typed word = object), scores,
10-minute fluency loop. Mirrors how pilots learn brevity. Demo-ready.

### 11. [BUILD NOW] Docs + verification
Scope: headless end-to-end run against live hardware, snapshot, DEVLOG entry,
CV-FUSION-PLAN status update.

### 12. [HW] Temple haptics carry direction+urgency; speech carries identity
HapticHead: 2.6 s vs 6.9 s, 96% vs 54% vs spatial audio. Location > rate >
intensity, ≤2 coding params, PRESCRIPTIVE (signal the path). Blocked on motor
rewire; firmware pins already parked. Also: measure motor SPL at the ear
(masking gate) before committing to head-mounted motors.

### 13. [HW] IMU: ground-plane bbox ranging, drop-off detection, sterile-cockpit
gate (suppress speech during fast head turns), camera↔ToF de-rotation.

### 14. [LATER] Spatialized speech (Klatzky/Loomis: beats spatial language on
time AND working memory). Needs stereo/HRTF pipeline — after bone-conduction
hardware exists.

### 15. [LATER] Feature backlog by demonstrated demand: text/signs on demand
(top task, 15/20) → scene Q&A (23/24 want voice) → dropped objects → bus
numbers → door/last-10-m. Deprioritized permanently: crowd detection, face ID.

### 16. [LATER] Edge port: YOLO26n INT8 → NCNN/OpenVINO benchmark on Pi 5,
Hailo-8L HAT ($70) as insurance; fisheye-augmented fine-tune (0.283→0.698 mAP
evidence); exposure lock for outdoor.

### 17. [STANDING RULES] From red-team, non-negotiable: claims language
("supplementary cue", never cane replacement); cane stays in hand in all
testing; two spotters; silence never means safe; no crossing decisions
("crosswalk ahead, slightly left" — never "walk"); don't look tactical;
outdoor ToF range measured before claimed.
