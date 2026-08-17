# CV stack research — 2026-08-16 (Opus research agent, verbatim findings)

Commissioned for the CV-fusion build. Companion red-team report:
`cv-redteam-2026-08-16.md`. Decisions taken from these live in
`docs/CV-FUSION-PLAN.md`.

## 1. Detector choice in 2026

Pi 5 CPU-only, 640px, FP32:

| Model | Format | ms/frame | FPS | Source |
|---|---|---|---|---|
| YOLO26n | NCNN | 67.0 | ~15 | Ultralytics docs |
| YOLO26n | OpenVINO | 104.6 | ~9.6 | Ultralytics docs |
| YOLO26n | ONNX | 126.0 | ~7.9 | Ultralytics docs |
| YOLO11n | OpenVINO | 80.9 | 12.4 | LearnOpenCV |
| YOLO11n | MNN | 115.8 | 8.6 | LearnOpenCV |
| YOLO11n | ONNX | 156.8 | 6.4 | LearnOpenCV |
| YOLO11n | NCNN | 292.1 | 3.4 | LearnOpenCV |

Published sources CONTRADICT on NCNN (fastest vs slowest) — thread/build config.
Benchmark yourself; don't trust either.

- **YOLO26n** (2026-01-14): 2.4M params, NMS-free end-to-end, DFL removed for
  edge export/quantization, ~43% faster CPU than YOLO11n, mAP 40.9 vs 39.5.
  AGPL-3.0 (fine for open-source portfolio). **The pick.** [Measured locally
  2026-08-16: 46 ms = 22 fps at imgsz 416 on the laptop CPU.]
- **RT-DETR: skip** — transformer cost, CPU-hostile. RF-DETR Nano (Apache 2.0)
  the only credible DETR edge option, higher risk.
- INT8: 13→22 fps observed on YOLO11n; YOLO26 quantizes better by design.
  Input resolution is the biggest lever; 320–416px sufficient for 1–5 m targets.
- **Hailo-8L AI HAT+ (~$70)**: YOLOv8n ~60 fps on Pi 5. The "it definitely
  works" Pi-port insurance.

## 2. Monocular depth + sparse ToF fusion

Proven pattern (= phone LiDAR):
- **DELTAR** (ECCV 2022) — founding paper, VL53L5CX-class ToF + RGB.
- **CFPNet** (github.com/denyingmxd/CFPNet) — **closest to our exact hardware**:
  VL53L5CX 8×8, explicitly handles ToF-FoV≪camera-FoV. REL 0.127→0.103.
  Survives 2×2 zones (46.5% REL reduction). 20M params, GPU-class.
- **Prompt Depth Anything** (CVPR 2025), **Prior Depth Anything** (ICLR 2026) —
  arbitrary sparse metric priors, zero-shot.
- **The cheap version to build first: global scale-shift alignment.** Depth
  Anything V2 gives relative depth; solve `d_metric ≈ a·d_rel + b` against the
  32 ToF zones with RANSAC. Closed-form, microseconds. Known limit: one global
  (a,b) is wrong in mixed near/far scenes → per-region fits next.
- Dense mono depth on Pi: **unproven** — no published Pi/Hailo benchmarks.
  Laptop-side only; run at 2–5 Hz as a scene channel, ToF+detector at 15–30 Hz.

## 3. Commercial/academic assistive systems — what users actually said

- **biped.ai NOA**: 3 depth cams, 170° FoV target, spatial audio via bone
  conduction, aggressive filtering. Detects branches AND holes/drop-offs.
- **ETA efficacy RCT (Sci Reports Jan 2026, n=13 BLV)** — the key source:
  NOA significantly fewer body collisions than cane or BuzzClip; 12/13
  preferred NOA; 100% said complements cane. **BuzzClip failed on
  frustration + vibration "too weak"/confusable — NOT on detection.**
  Rich reliable signals did NOT raise cognitive load; unreliable ones do.
- **Cane's documented gap = elevated obstacles + identity.** Head/upper-body
  collisions are the hazard class. Say this explicitly in the write-up.
- **Sight Guide (Cybathlon 2024)**: Jetson backpack, 16-motor belt, 95.7% lab
  success; feedback rate **~1 Hz**. Perception can run 15 Hz; alerts far slower.
- OrCam explicitly NOT a mobility aid; WeWalk degrades to ultrasonics offline;
  Glidance steers rather than alerts (lower cognitive load claim).
- Users prefer head-mounted form factors and conversational interfaces
  (arXiv 2505.19325, 646 papers + 24 BLV interviews).
- **Methodology sins to avoid**: blindfolded-sighted-only, indoor-only,
  no cognitive-load metric (NASA-TLX).

## 4. Semantics, tracking, TTC

- 90-object BLV taxonomy exists (arXiv 2407.16777); COCO misses the top
  hazards: curbs, stairs, poles, bollards, branches, manholes, scaffolding.
- Tier 1 moving (track + TTC): person, cyclist, car, bus/truck, motorcycle, dog.
- Tier 2 static collision: pole/bollard, wall/door, parked vehicle, bench,
  branch (head-level — the differentiator).
- Tier 3 ground geometry: curb/stairs/drop-off — **geometry problems for
  ToF+IMU, not detection problems.**
- ByteTrack: cheap Kalman/IoU, right call. HEADS-UP dataset (arXiv 2409.20324)
  for head-mounted trajectory prediction.
- **Highest-value technique: IMU ground plane → metric range from bbox bottom**
  `d ≈ h_cam / tan(pitch + θ_pixel)` — ~50 lines, zero inference, works on any
  hardware, ToF zones give 32 free calibration points/frame.
- Negative obstacles (drop-offs): ToF-vs-expected-ground-plane differencing.
  No ML. biped parity feature.

## 5. Edge deployment

Pi 5: ONNX Runtime (easy, 6–8 fps) → OpenVINO (12 fps) → NCNN (verify) →
Hailo-8L HEF (~60 fps). RKNN is Rockchip-only, N/A on Pi.
Android: LiteRT (ex-TFLite) + QNN/NeuroPilot NPU delegates; Ultralytics
Flutter plugin exists. Phone NPU beats Pi 5 CPU.

## 6. Fisheye

- Real problem: peripheral deformation vs CNN translation invariance.
  Undistorting costs FoV + resampling artifacts.
- **Best evidence-backed fix: fisheye-AUGMENTED training.** Bike-ped safety
  system (arXiv 2604.17046): stock COCO model mAP@50:95 0.283 → 0.698 with
  matched-distortion augmentation. **2.5× from augmentation alone.**
- At ~120° we're at the mild end (literature targets 190°+). Cylindrical
  projection is the fallback middle path.
- Keep full FoV, do NOT undistort at inference.

## Ranked value-for-effort

1. IMU ground plane → metric range from bbox bottom (~1 day, very high)
2. Fisheye-augmented fine-tuning (~2 days, very high)
3. RANSAC scale-shift mono-depth anchoring (~1 day, high)
4. YOLO26n + benchmark NCNN/OpenVINO/MNN at 416 (~1 day, high)
5. ByteTrack + TTC on Tier-1 only (~2 days, high)
6. **Alert-UX layer: hysteresis, arbitration, strong unambiguous haptics,
   1–2 Hz — highest and most under-rated** (RCT: feedback design is the
   bottleneck, not the model)
7. Hailo-8L HAT for Pi port ($70, high)
8. Drop-off detection from ToF vs ground plane (~1 day, high)
9. Walkable-surface segmentation (~2 MB TinyML) — later
10. Depth Anything V2 on-device — laptop luxury for now
11. Learned ToF-fusion nets — cite, don't deploy
12. RT-DETR / fisheye-native archs — wrong compute class

Full source list in the agent transcript; headline sources:
- ETA RCT: pmc.ncbi.nlm.nih.gov/articles/PMC12909938/
- Sight Guide: arXiv 2506.02676 · BLV taxonomy: arXiv 2407.16777
- CFPNet: arXiv 2411.04480 · DELTAR: arXiv 2209.13362
- Fisheye augmentation: arXiv 2604.17046 · HEADS-UP: arXiv 2409.20324
- Ultralytics Pi guide + YOLO26 · LearnOpenCV Pi benchmarks (they disagree)
