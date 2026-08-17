# Camera Calibration, Dewarping & Depth↔Pixel Fusion — Research Reference

**Created 2026-06-08.** Companion to `camera-and-multisensor-layout.md`. Covers (A) how to
calibrate + dewarp the 140° HBV-1716WA, and (B) the state of the art in fusing sparse
distance data (ToF) onto camera pixels. **Consult before writing the calibration or fusion code.**

---

## PART A — Calibrating & dewarping the 140° wide camera

### A1. Which distortion model? → **FISHEYE (Kannala-Brandt), not pinhole**

Our lens is **140° diagonal** — exactly the boundary where the standard model fails:

- **Standard pinhole** (`cv2.calibrateCamera`, radial+tangential k1,k2,k3,p1,p2): designed
  for narrow/normal lenses. On a 140° barrel-distorted image it gives **poor results or
  fails** — it can't model the extreme edge distortion, and undistorting throws away a lot of FOV.
- **Fisheye / Kannala-Brandt** (`cv2.fisheye`, 4 coeffs **k1,k2,k3,k4**): purpose-built for
  wide/fisheye lenses. Sources agree it's the right pick for **≤140° diagonal FOV**.
- **Verdict: use `cv2.fisheye`.** We're at the top of its sweet spot.

(If a calibration ever comes out poor, the fallback ladder is: fisheye → omnidirectional
`cv2.omnidir` (for >180°) — but we won't need that at 140°.)

### A2. Calibration target → **ChArUco board** (not plain checkerboard)

ChArUco = checkerboard + ArUco markers in the white squares. Why it beats a plain checkerboard
**for a wide lens specifically**: it still works when **part of the board is occluded or off-frame
or edge-distorted**, because each marker is uniquely identified — so you can fill the *corners*
of a 140° frame (where distortion is worst and a plain board is hardest to fully capture).

### A3. Workflow (do this when the camera arrives)

1. **Generate + print** a ChArUco board (`cv2.aruco.CharucoBoard`); mount it flat & rigid.
2. **Capture 20–40 images** covering the WHOLE frame — especially the **edges and corners**
   (worst distortion), at varied tilts and distances. Lock the lens focus first (it's adjustable).
3. **Detect** markers/corners (`cv2.aruco.detectMarkers` → `interpolateCornersCharuco`).
4. **Calibrate:** `cv2.fisheye.calibrate(objpoints, imgpoints, size, K, D, flags=...)`
   - Useful flags: `CALIB_RECOMPUTE_EXTRINSIC | CALIB_FIX_SKEW`.
   - `CALIB_CHECK_COND` can throw on a bad image — drop the offending frame and re-run.
   - Output: **K** (3×3 intrinsics: fx, fy, cx, cy) and **D** (k1..k4).
5. **Validate:** undistort a test image, check straight edges are straight; aim
   **reprojection error < ~0.5 px**. From K you also get the **true HFOV/VFOV**
   (HFOV = 2·atan(cx/fx) etc.) — this finally replaces the ~109°/67° estimate with measured numbers.

### A4. Dewarping — three options, pick by purpose

- **(i) Full rectilinear undistort** — `cv2.fisheye.estimateNewCameraMatrixForUndistortRectify`
  (+ `initUndistortRectifyMap` + `remap`). The `balance` param (0..1) trades **FOV vs
  straightness**: balance=0 crops to a tight rectilinear core, balance=1 keeps more FOV but
  bends edges. A 140° lens rectilinearized to balance=1 stretches the corners enormously.
- **(ii) Mild undistort** — keep balance low, accept FOV loss; good if downstream CV wants
  straight lines (e.g. line/plane detection).
- **(iii) DON'T dewarp the image at all (recommended for fusion).** Keep the raw fisheye frame
  and instead map your *depth points* INTO it using the fisheye projection model
  (`cv2.fisheye.projectPoints`). Rectifying a 140° image to overlay depth wastes the wide FOV
  you paid for and resamples every pixel. For sparse ToF overlay, projecting 64 points is far
  cheaper and lossless. **See Part B.**

---

## PART B — Depth↔pixel fusion (ToF zones onto camera pixels)

> **⚠️ CURRENT FIRMWARE CONFIG (main.c, 2026-06-08): `VL53L8CX_RESOLUTION_4X4` = 16 zones,
> NOT 64.** Each zone ≈ **11.25°** angular (45°/4). The "64 zones" in the examples below
> assume 8×8 — at the current 4×4 it's **16 zones**, a coarser overlay. Resolution is a
> live design tension (see review note): 4×4 = 60 Hz-capable + ~4× lower per-zone noise but
> coarse; 8×8 = 64 zones but capped 15 Hz + noisier. For camera fusion the camera supplies
> the spatial detail and the ToF supplies coarse true-depth — so 4×4 may be the right call.

### B1. The core projection math (this is the whole trick)

A 3D point `(X,Y,Z)` in the camera frame maps to pixel `(u,v)` by:
```
Z · [u, v, 1]ᵀ  =  K · [R | t] · [X, Y, Z, 1]ᵀ
```
- **K** = camera intrinsics (from A3). **[R|t]** = the extrinsic rigid transform from the
  ToF frame to the camera frame.
- Inverse (pixel + depth → 3D ray): `Xc = (u−cx)·d/fx`, `Yc = (v−cy)·d/fy`, `Zc = d`.
- **For our fisheye camera, replace the linear `K·` projection with `cv2.fisheye.projectPoints`**
  so the lens distortion is applied — otherwise points land in the wrong pixels at the edges.

### B2. Our case is SPARSE + ANGULAR (easier than LiDAR depth completion)

The VL53L8CX gives an **8×8 = 64 zones**, each with a **known ray direction** (its slot in the
45°×45° FoV) and a measured distance. So each zone is already a 3D point in the ToF frame:
`P = distance × unit_ray(zone_row, zone_col)`. Pipeline:

1. **Calibrate camera intrinsics** (Part A) → K, D.
2. **Calibrate ToF→camera extrinsics** `[R|t]`. They're rigidly mounted ~cm apart, so:
   - Start from **mechanically-measured** offset/angle (good enough for a first pass), then
   - **refine** by waving a small board/pole and matching the ToF-detected position to its pixel.
   - Extrinsics are **most sensitive along the camera's optical axis** (depth direction) —
     known gotcha from the fusion literature.
3. **Per frame:** for each of the 64 zones, build its 3D point → transform by `[R|t]` →
   `cv2.fisheye.projectPoints` → pixel `(u,v)`. Now each depth zone has a pixel footprint.
4. **Use it.** For 64 sparse points you do NOT need a depth-completion network. Realistic uses:
   - **Overlay** colored depth cells on the video (debug/HUD).
   - **Gate / decorate CV detections** — e.g. a person-detector box gets its distance from the
     ToF zones inside it ("person at 1.8 m, left"); drives the haptic urgency.
   - **PointPainting-lite** — the reverse: tag each ToF zone with the image's semantic label
     (is this 1.2 m blob a *wall* or a *person*?) for smarter alerts. (Phase 3 CV-adaptive thresholds.)

### B3. Leaders in depth↔pixel fusion (the landscape, so we borrow the right ideas)

**Academic — sparse depth + RGB ("depth completion"), KITTI benchmark is the arena**
(KITTI raw LiDAR covers ~6% of pixels — similar *sparsity spirit* to our 64 zones):
- **Sparse-to-Dense** (Ma & Karaman, MIT, 2018) — seminal "sparse depth + RGB → dense depth."
- **CSPN / CSPN++** — convolutional spatial propagation (diffuse sparse depth along image edges).
- **NLSPN** (ECCV 2020) — non-local spatial propagation; strong MAE; widely cited baseline.
- **GuideNet / "Learning Guided Convolutional Network"** — image-guided conv, former KITTI #1.
- **PENet, CompletionFormer** (CVPR 2023, CNN+Transformer), **SemAttNet** — recent SOTA tier.
- Takeaway for us: these are **overkill for 64 points**, but the *guiding principle* —
  "propagate / interpret sparse depth using image structure" — is exactly what B2.4 does lightly.

**Autonomous-driving fusion (LiDAR + camera) — the architecture playbook:**
- **PointPainting** — projects each LiDAR point into the image, paints it with the image's
  semantic class. **Input/point-level fusion; sensitive to calibration error.** (Our B2.4 "lite".)
- **BEVFusion** (MIT Han Lab) — projects camera + LiDAR features independently into a
  Bird's-Eye-View grid, fuses there; **robust to mis-alignment** (no hard per-point match).
- **Frustum PointNets** — use the 2D detection to carve a 3D frustum, search depth within it.

**Industry / shipping fusion (proof the approach works at scale):**
- **Apple** — iPhone/iPad Pro **LiDAR + camera** via ARKit (sparse dToF, same family as ours).
- **Google ARCore Depth API** — depth-from-motion fused with ToF where present.
- **Intel RealSense SDK** — solid reference for **depth↔color alignment / texture-mapping /
  occlusion** (their projection docs are a practical how-to for the exact B1 math).
- **NVIDIA Isaac**, **Mobileye** — production AV LiDAR-camera fusion stacks.

**Cross-calibration tooling worth knowing:** targetless LiDAR-camera auto-calibration nets
(**LCCNet**, **UniCalib**, **DXQ-Net**) — relevant *later* if mechanical extrinsics drift; not needed for v1.

---

## Practical bottom line for the helmet
1. **Calibrate with `cv2.fisheye` + a ChArUco board** → get K, D and the *real* FOV.
2. **Don't rectify the image for fusion** — keep raw, project the 64 ToF zones in with
   `cv2.fisheye.projectPoints` using a measured-then-refined `[R|t]`.
3. **Skip depth-completion networks** — at 64 zones, do projection + detection-gating
   (PointPainting-lite). Revisit BEV-style fusion only if we ever go dense.
4. **Borrow the principle, not the nets:** use image structure to interpret sparse depth.

---

## Sources
**Calibration / fisheye:**
- [OpenCV fisheye module docs](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html)
- [Kenneth Jiang — Calibrate fisheye lens with OpenCV (pt.1](https://medium.com/@kennethjiang/calibrate-fisheye-lens-using-opencv-333b05afa0b0) / [pt.2)](https://medium.com/@kennethjiang/calibrate-fisheye-lens-using-opencv-part-2-13990f1b157f)
- [Fisheye + ChArUco calibration repo (jamiemilsom)](https://github.com/jamiemilsom/Fisheye_ChArUco_Calibration)
- [Tangram Vision — camera models (Kannala-Brandt ≤140°)](https://docs.tangramvision.com/metrical/14.1/calibration_models/cameras/)
- [MATLAB — Fisheye calibration basics](https://www.mathworks.com/help/vision/ug/fisheye-calibration-basics.html)

**Fusion:**
- [LiDAR-Camera Fusion overview (EmergentMind)](https://www.emergentmind.com/topics/lidar-camera-fusion)
- [Papers with Code — KITTI Depth Completion leaderboard](https://paperswithcode.com/sota/depth-completion-on-kitti-depth-completion)
- [Sparse-to-Dense / Sparse-Depth-Completion (van Gansbeke, KITTI #1)](https://github.com/wvangansbeke/Sparse-Depth-Completion)
- [CompletionFormer (CVPR 2023)](https://youmi-zym.github.io/projects/CompletionFormer/)
- [Learning Guided Convolutional Network for Depth Completion](https://arxiv.org/pdf/1908.01238)
- [Intel RealSense — projection, texture-mapping & occlusion (practical projection math)](https://dev.realsenseai.com/docs/projection-texture-mapping-and-occlusion-with-intel-realsense-depth-cameras/)
- [From LiDAR Points to Pixels (projection walkthrough)](https://medium.com/@krushnakr9/from-lidar-points-to-pixels-mapping-3d-point-clouds-to-2d-images-695ec51fbcaa)
