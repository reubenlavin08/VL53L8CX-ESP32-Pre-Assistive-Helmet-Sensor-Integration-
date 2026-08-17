# Red-team: what NOT to do — 2026-08-16 (Opus adversarial agent, verbatim findings)

Companion to `cv-stack-research-2026-08-16.md`. Ranked by likelihood of biting
THIS project.

## Tier 1 — near-certain, physics of our exact parts

1. **target_order must be CLOSEST** (ST default is STRONGEST): a dark pole at
   0.8 m in front of a white wall at 3 m reports THE WALL. Targets <600 mm
   apart merge into one peak regardless — a sign post against a wall is
   fundamentally unresolvable. [Our firmware already sets CLOSEST — verified.]
2. **The 4 m range does not survive sunlight.** All ST numbers are dark/5 klux;
   direct sun is 32k–100k lux. 4×4@30 Hz: dark 4000 mm → 5 klux 2850 mm best /
   ~1500 mm worst (17% grey, corner). ST engineer: "at least a meter in bright
   sunlight... the detector gets swamped." User reaction time to an ETA alert
   is ~410 ms; at 1 m/s a 1 m range is at/below the published usability floor.
3. **Specs assume the target fills 100% of the zone.** A 5 cm pole at 2 m fills
   ~13% of a 4×4 zone ≈ a target 7.7× darker — below the 17% reflectance floor
   ST characterizes at all. 8×8 halves the zone but halves ambient range too.
   No config is good at both. Measure a real pole.
4. **Never average depth over a bounding box** — boxes are 40–60% background at
   the limbs; flying pixels are ~half the edge error; multipath biases LONG.
   Use central-region median or 20th percentile (safety-correct direction) +
   sigma/status rejection.
5. **Never make distance a track attribute.** Best trackers: ~1 ID switch per
   trajectory in crowds (ByteTrack 2196 IDSW on MOT17). A stale distance across
   a switch = confidently wrong haptic. Re-derive depth from the current ToF
   frame every cycle.
6. **Camera↔ToF differential latency matters.** UVC glass-to-glass 70–300 ms;
   head yaw 90°/s normal, 200°/s on turns; half-zone association budget is
   32 ms (8×8) / 64 ms (4×4). Timestamp at capture + ring-buffer ToF to match.
7. **Crosstalk cal needed the moment a pod window exists** (<60 cm Xtalk can
   exceed real signal). Two 940 nm sensors degrade each other → status 12;
   SYNC pin exists (UM3109 §4.15). Status gates: 5 = 100% valid, 6/9 ≈ 50%.

## Tier 2 — perception architecture

8. **Don't build on COCO classes.** Manduchi & Kurniawan (300+ blind people):
   13% suffer a head-level accident at least monthly, 7% fall monthly. Causes:
   tree branches (majority), poles/signs, construction; indoors: doors ajar,
   cabinets, shelves. ZERO are COCO classes. Glass is its own task (Trans10K).
   Negative obstacles are a named research blind spot.
9. **The fisheye periphery (outer 25% of our H-FoV) has no depth AND the worst
   detection** (WoodScape: −5–8 mAP at the sides). Obstacles enter from there.
   Argues for mono-depth Phase C.
10. **Motion blur is the worst corruption**: BDD100k severity-3 blur 37.1→13.5
    AP (−64%), and blur robustness does NOT improve with better detectors.
    Night −28%. No benchmark measures blur+night+fisheye jointly — we must.
11. **Lock the exposure.** Indoor→outdoor is 100–4000× (6.5–12 stops); AE
    convergence 0.6–1 s (70 s worst measured); tunnel-exit detection 55.7→24.3
    mAP. At 1.4 m/s a 1 s blackout = 1.4 m walked blind.
12. **"No return" ≠ "clear."** Glass doors read as EMPTY SPACE (specular);
    black rugs false-cliff (absorption); wet ground false-drop-off. Absence of
    signal must be its own state.

## Tier 3 — haptic UX (what gets devices abandoned)

13. **Don't over-alert.** ICU: 72–99% of alarms false/non-actionable → disuse.
    Compliance probability-matches reliability (70%-reliable alert obeyed ~70%).
    BLV users caught only 49% of a recognizer's errors and were "certain" in
    84% of false positives — they cannot check the device.
14. **No continuous vibration; motors must be inaudible.** Habituation time
    constant 1.5–2 min (louder = faster). Use 50–200 ms pulses; rate carries
    urgency. **Masking:** auditory-loss-alone added +33% obstacle contacts in
    trials — more than the ETA's whole benefit. A helmet shell radiates motor
    noise next to the ears the user navigates with. MEASURE motor SPL at the
    ear — falsifiable design gate. Bandwidth: 3 motors ≈ 2 bits, 5–6 reliable
    patterns; two simultaneous motors → 42–66% identification.

## Tier 4 — demo-to-field

15. **Cables end field trials.** Sight Guide: 95.7% lab success; qualification
    run lost to a belt cable disconnect, final run to a dead depth camera.
    87% of cable failures at the housing junction; USB flex spec = 100 cycles.
    Head-worn cables flex on every head turn.
16. **Power budget on coincident peaks, not averages.** WiFi TX 345–500 mA +
    3× ERM inrush ~120 mA each ≈ 880 mA coincident — and the haptic pulse and
    the WiFi frame reporting it PEAK TOGETHER. Brownout fails late-session on a
    sagging cell, never on the bench. 470–1000 µF bulk, stagger motor starts
    5–10 ms, back off TX during pulses.
17. **Benchmark FPS sustained, not first-60 s**: Pi 5 −19% by 300 s, throttle
    at ~120 s/80 °C; camera sensor +10 °C over 1–2 h → dark current doubles
    every 6–10 °C → detector quietly degrades. Slow drift, no event to debug.
18. **The link must fail loudly.** ESP32 TCP: set TCP_NODELAY (74–84 ms → 6 ms,
    free 10×). p95 152 ms degraded; 1 s stalls happen. The user cannot
    distinguish "link dead" from "path clear" — both are silence. Heartbeat +
    distinct link-lost haptic + stale-data rejection.

## Tier 5 — claims and testing (cheapest to fix, most damaging wrong)

19. **Never claim cane replacement.** FDA framing: "adjunctive device to other
    assistive methods such as a white cane or a guide dog." NRC 1986: ETA =
    "ancillary aid to supplement a primary aid." Blind reviewer of Stanford's
    Augmented Cane: automated avoidance destroys the information the cane
    exists to deliver.
20. **Blindfolded-sighted testing ≠ user testing — and it FLATTERS the device**
    (Qiu 2024: blindfolded participants performed significantly BETTER than
    blind participants on the same prototype). Of 70 ETA papers: 51.4%
    simulation-only, 22.9% actual blind users, 1.4% reached production.
21. **Standard test protocol** (EyeCane study): expert cane user KEEPS the cane
    in every condition; two spotters; indoor closed course; the ETA is the
    variable, the cane the constant.

**Forbidden README sentences:** "replaces the white cane" / "lets blind people
see" / "tested with blindfolded volunteers so it works for blind users" /
"detects all obstacles" / "medical device". Use instead: "A research prototype
exploring camera + time-of-flight obstacle sensing as a supplementary cue. It
is not a mobility aid, not a medical device, and not a substitute for a long
white cane, a guide dog, or O&M training. It has not been evaluated with blind
users."

**Through-line:** real field trials died to cables, connectors, power, and
light — not algorithms. And the region with no depth (outer 25%) is where the
detector is worst and where obstacles enter. Device-class failure mode is
social (abandonment by week two), not technical.

**Unverified numbers flagged by the agent** (re-check before quoting): the
"23% of head-level injuries required medical attention" figure; 32/64/150 Hz
head-vibration acceptability thresholds; pouch-cell internal resistance.
