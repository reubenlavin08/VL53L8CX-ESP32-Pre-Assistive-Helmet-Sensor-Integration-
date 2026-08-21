# Transit assistance synthesis — bus ID, doors, platform edge, fusion — 2026-08-20

Companion to [[implementation-guide-2026-08-20]] (same territory, second
independent synthesis — where they agree, confidence is high). Unique
additions here: ALVU, dwell-time budget, hardest-part ranking, TransLink
specifics, read-while-stopped strategy.

## The key answer (both syntheses agree)

**No product today closes the loop "bus 99 arriving — door 3 m to your
right."** Apps do schedules; Aira does it with a paid human; nothing does
it autonomously. The chain — GTFS candidate set → YOLO bus detect → LED
OCR with temporal voting → door localization → spatial-audio + haptic
bearing — is the helmet's defensible novelty.

## 1. Route-number reading — prior systems

- **All_Aboard** (Luo lab, TVST 2024): bus-STOP-sign finder, not a sign
  reader. MobileNetV2 on ~10k Street View images per city (coords from
  GTFS — **training trick directly reusable**). 91% vs 52% Google Maps;
  final gap 1.8 m vs 7.0 m. Failure modes: shadows, angled signs, sign
  leaving FOV on final approach.
- **SRM-OCR (2025)**: super-resolution + Mamba OCR for LED route numbers;
  **85.1% single-frame** on its BusLED-700 dataset (the only public bus
  LED set). Even SOTA needs multi-frame voting.
- Wongta 2018 classical pipeline: 67.9% — how badly classic OCR does.
- **Bus door detection = one paper (Ponnada 2021), zero metrics. Open
  field.**

## 2. Feasibility math (this sensor)

- OCR sweet spot ≈ 30 px capital height (Tesseract tests); deep
  recognizers train at 32 px, ~16–24 px workable with 2× SR.
- Fisheye ≈ 16 px/deg → 175 mm LED char at 10 m ≈ 16 px (marginal), at
  20 m ≈ 8 px (unreadable). **Reliable read ~5–12 m on current sensor; a
  narrow-FOV second camera pushes to 25–30 m.**
- **Design for the STOPPED bus, not the moving one** — dwell gives a
  stationary close-range window of seconds. Announce chain must fit
  inside a 10–30 s dwell; identity at approach, door bearing after stop,
  never during the user's own motion bursts.
- LED PWM flicker capture fix: exposure ≥ one PWM period (≥1/100 s)
  and/or max-composite over 3–5 frames; camera 50/60 Hz anti-flicker does
  NOT cover sign PWM.
- Closed-set GTFS matching converts 85% open-set into **>99% practical**
  (edit-distance over ~5 candidates tolerates heavy OCR noise).

## 3. Model choice

**PARSeq** is the pick (23.8M params, 14.9 ms GPU, IIIT5k 99.0): best
accuracy-per-latency, permissive license, easy fine-tune. ABINet heavier
+ slightly behind; TrOCR 5–10× slower; EasyOCR = CRNN-era; PaddleOCR =
CPU fallback. Full comparison in [[transit-headsign-ocr-2026-08-20]].

## 4. Platform edge

- **ALVU** (Katzschmann/Rus, IEEE TNSRE 2018): ToF array + haptic belt,
  12 blind users, 162 trials, staircase detection validated — the classic
  wearable ToF result to cite.
- EyeCane caution (Sensors 2021): single-point downward sensors — "the
  step appeared to prove the hardest to detect."
- Mizuno & Tokuda 2023 design note: directional tactile pavers placed too
  close to the edge actively MISLEAD — paving detection alone is not a
  safety signal; you need the edge itself.
- Geometry: platform edge = negative obstacle; zones past the edge jump
  >1 m or no-return (drop ≈ 1.1–1.3 m). Detection at 2.5 m at 1.3 m/s =
  ~1.9 s warning — enough IF the downward ToF runs its own ≤100 ms safety
  loop independent of the vision stack. The 8×8 grid gives edge
  ORIENTATION (which zones dropped first) → "edge ahead-left."
- No published platform-edge wearable with metrics — publishable gap.

## 5. Fusion backbone

GTFS-RT + GPS = the backbone (free, city-wide, no infrastructure);
vision confirms identity + last 10 m; ToF last 3 m + safety loop;
beacons/NaviLens only where they exist (none in Vancouver). TransLink:
free API key, GTFS-RT feeds (old RTTI API deprecated). Soundscape's
audio-beacon UX worth copying even though the product died.

## Hardest-part ranking

1. **LED OCR at range on a fisheye** — highest risk, but degradable
   (worst case: "a bus is stopping" + GTFS says only one is due).
2. **Timing/UX** — fit the chain in the dwell window.
3. **Platform edge** — geometrically easy, safety-critical posture.
4. **Bus/door detection** — lowest risk; YOLO fine-tune on Vancouver's
   uniform fleet (a few hundred labeled frames).

## Second-pass additions (same agent, re-run)

- **Multi-bus disambiguation at busy stops** ("which vehicle is the 99"
  when two arrive together) — unsolved anywhere; GTFS-RT position + OCR +
  arrival-order reasoning is a differentiator. Ranked #2 hardest.
- JIS standard puts the warning tile line **80–100 cm from the platform
  edge** — camera fires the first alert at 3–4 m off the tile line; ToF
  is the hard last-line stop. **Latch both cues** (an edge doesn't vanish
  because detection flickered).
- GTFS-RT `current_status=INCOMING` at your stop_id tells you WHEN to
  start scanning, not just what for.
- Commercial destination-sign PWM frequencies (Hanover/Mobitec)
  unverifiable — measure empirically.

## Caveats

NaviLens figures vendor-claimed; Mizuno/Tokuda percentages from
API-reconstructed abstract — re-verify before public use; some §3
comparisons from established knowledge, not fresh citations.
