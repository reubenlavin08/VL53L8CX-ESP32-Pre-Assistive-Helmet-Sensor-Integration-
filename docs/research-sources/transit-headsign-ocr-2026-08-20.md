# OCR models for LED headsigns — benchmark numbers — 2026-08-20

Component report (full citation detail behind the syntheses' OCR picks).

## Model-by-model

| Model | Size / speed | Benchmarks | Verdict |
|---|---|---|---|
| **PARSeq** (ECCV 2022, arXiv:2207.06966) | 23.8M, 3.3 GFLOPs, **14.87 ms** | IIIT5k 99.0 / SVT 97.8 / IC15 89.2 / SVTP 96.9 / CUTE80 98.6 (comb. 95.95) | **The pick** |
| ABINet (CVPR 2021, arXiv:2103.06495) | 36.7M, 22 ms | comb. lower (IIIT 96.2, CUTE 89.2) | LM iteration helps low-quality but hallucinates on contextless text |
| TrOCR (arXiv:2109.10282) | 334–558M, 120–230 ms/line | CUTE80 only 84.1 | **Disqualified** — 20× size, 10× latency, worse on curved |
| EasyOCR (CRAFT+CRNN) | — | no published numbers | weak baseline |
| DBNet++ (TPAMI 2022, arXiv:2202.10304) | 62 FPS (DBNet R18) | IC15 hmean 0.8882 (w/ oCLIP) | **detector pick** |
| PP-OCRv5 | 0.62–0.74 s/image V100 | det 0.827, rec 0.840 | full pipeline NOT 30 fps |

## Low-resolution cliff (the binding constraint)

- **TextZoom** (ECCV 2020, arXiv:2005.03341): at 64×16 px, CRNN collapses
  to **21–36%**, ASTER 31–65%; super-resolution buys +9–13%.
- **Target ≥32 px char height, floor 24 px**; dot-matrix 5×7 glyphs need
  ≥3 px/dot → ≥21 px independently.
- Geometry at 1920 px / 119.58°: 0.15 m char = **2.8 px @30 m, 8.4 px
  @10 m — the wide-angle camera physically cannot do this task.** ~48°
  lens works at 10–12 m (realistic v1); 30 m needs ~17–20° tele or 4K.
- **Union14M** (ICCV 2023): classic benchmarks are saturated; same models
  average 66.5% on real hard data; "contextless text" is a named open
  challenge — **constrain the charset per field** (digits-only head for
  route numbers).
- **No public LED dot-matrix / bus-headsign dataset exists** (0 arXiv
  hits) — collect our own. Closest: YUVA EB (seven-segment meters);
  per-digit object detection hit **100% on 438 seven-segment digits**
  (arXiv:2210.01325) — detection-as-classification beats seq2seq for
  fixed-length digits.

## Rolling shutter + PWM banding

- Banding = row-wise exposure × PWM (BurstDeflicker arXiv:2510.09996 has
  a synthetic banding pipeline for training data; also RIFLE, VDFP,
  BRACE).
- Mitigations: exposure = integer multiple of flicker half-period; LED
  signs PWM at hundreds of Hz–kHz so exposure ≥ 1 PWM period (conflicts
  with motion-blur control); **global shutter removes banding at source**
  (residual all-dark frame → brightness gate); band phase drifts
  frame-to-frame so multi-frame voting washes it out.

## Temporal voting (the cheapest multiplier)

+4.6 to +10.5 pts across video-text benchmarks (TransDETR ~+8, CoText
+10.5 @41 FPS, GloTSFormer +4.6); **YORO: recognize once per track =
~71× speedup**. Video-text SOTA is only ~44–56 MOTA — unsolved; expect
to engineer.

## Recommended pipeline

DBNet++ (5–10 Hz) → ByteTrack → PARSeq on tracked crops (YORO-style) →
per-track confidence-weighted character voting over 5–10 frames → GTFS
closed-set edit-distance match. Two heads: digits-only (route number),
alphanumeric (destination). Data: self-collected TransLink footage +
synthetic 5×7 LED-font rendering (randomized dot pitch, bloom, banding
phase) + YUVA EB pretraining.
