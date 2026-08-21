# Platform-edge safety — tactile paving CV + depth drop-off — 2026-08-20

Component report (full numbers behind the syntheses' platform sections).

## Fall statistics (verified, Japan)

Mizuno & Tokuda, Heliyon 9(3):e14666, 2023 (PMC10060185):
- FY2021: **1,429 platform falls** in Japan; 28 involving visually
  impaired people. FY2020: **3 visually impaired deaths**.
- Survey: **76.0% of visually impaired respondents had fallen from a
  platform; 91.0% had near-falls.**
- 412-platform fieldwork: **64.1% of stations had no platform screen
  doors**; 17.8% wide gaps.
- PSD rollout: 943 stations 2020 (~10%) → 1,190 by 2024, ~60/yr against
  ~9,000 — **the un-doored ~90% stays addressable for decades.**
- UK/US numbers not verified this session (ORR/FTA blocked).

## Tactile paving (TWSI) segmentation — mature

- **GRFB-UNet** (ESWA 2024, code on GitHub): mIoU **94.85%** on
  TP-Dataset (public, binary masks).
- G-GhostNet variant (Sensors 26(3):770, 2026): mIoU 94% paving / 86%
  zebra at **59.2 fps on embedded NPU** — best speed/accuracy datapoint.
- YOLOv8 detection: 97% acc, mAP@0.5 0.977 (2024).
- **Tenji10K**: 10,000 first-person images, Japan — most
  helmet-camera-realistic dataset.
- **Gap: no dataset splits warning-dots from directional-bars** — for
  platform work that distinction IS the point; plan to relabel.
- Tile standard (JIS T 9251 / ISO 23599): blocks ≥300 mm; dots ⌀12 mm
  pitch 55–60 mm; bars 17 mm wide pitch 75 mm.
- Japan's 内方線付き点状ブロック (interior-line warning blocks,
  post-2011 Mejiro / 2016 Aoyama-itchōme deaths) are **asymmetric — they
  indicate which side is safe, something depth can't provide.** Camera =
  "edge ahead, safe side left"; ToF = last-metre confirm.

## Depth drop-off detection

- **No published wearable with quantified false-negative rates for
  platform edges — genuine gap.**
- Long-cane human baseline is itself well below 100% (Kim & Wall Emerson
  2010/2012/2014 — drop-off detection is technique/length-dependent).
- Asante & Imamura 2023: stereo 20 m / 95% but **5 s response** — too
  slow.
- Turchetto & Manduchi IROS 2003 (visual curb localization); Manduchi &
  Coughlan "The Last Meter" CHI 2014.

## VL53L8CX feasibility (geometry/timing)

- Helmet 1.6 m, 30° down → usable ground strip **~1.2–3.6 m** (beyond
  that slant exceeds 4 m); per-row ground resolution degrades to 0.86 m
  at 3 m.
- Drop-off signature: coherent band of zones flips valid→no-return (rail
  bed past 4 m slant). Crisp and cheap — **but identical to black mats,
  puddles, sun-blinding, specular tile. False-positive discrimination is
  the core problem.**
- Timing: 67 ms frame + 200 ms 3-frame confirm + 20 ms haptic + 0.5 s
  reaction + 0.6 s gait arrest ≈ **1.39 s** → stopping distance 1.95 m
  @1.4 m/s. Detection at 3.6 m clears **with ~1.6 m margin in ideal
  light only.**
- **Make-or-break unknown: ambient-light derating.** Open platform =
  10,000–100,000 lx; if range drops to ~2 m the warning comes as you
  step off. **Bench-test before any fusion code.**
- Mount recommendation: chest/waist buys 0.2–0.25 m slant range.
- Segmentation at 59 fps needs Pi 5+Hailo / Jetson Orin Nano class — not
  ESP32.
