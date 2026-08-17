# Sensor-Pixel-Camera Fusion — Executive Summary (step by step)

**Goal:** project the 16 ToF depth zones onto the camera's video pixels, so every part of the
image carries a true distance. Build = **A geometric overlay → B detection-gating → C mono-depth**.
Do them in order; A is the foundation everything else sits on.

**Where you are:** camera not yet brought up. Fusion can't start until the camera is live and
calibrated. Steps below are in strict do-this-first order.

---

## STAGE 0 — Camera alive (do first, ~30 min)
1. Plug the HBV-1716WA into USB. It's UVC (plug-and-play, no driver).
2. Run `camera/camera_check.py` → live window opens. Press `s` to snapshot, `q` to quit.
3. Confirm: image is sharp (adjust the lens focus ring, then **tape it** so it never moves),
   1080p, MJPEG. Focus MUST be locked before calibration — refocusing invalidates it.
   **Output of this stage:** a working, focus-locked camera.

## STAGE 1 — Calibrate the lens (intrinsics, ~1 hr)
*Why:* a 140° fisheye bends straight lines. Calibration measures exactly how, so we can map
angles↔pixels correctly. Without this, projected ToF zones land in the wrong place at the edges.
1. Print a **plain flat checkerboard** (I generate/source the PDF). Glue to rigid board — must be flat.
2. Run capture script → grab ~20 shots, checkerboard tilted/rotated/near/far, **filling the
   center** of the frame (center 90° is all that must be perfect — it's where the ToF sensors see).
3. Run calibrate script → `cv2.fisheye.calibrate` → outputs **K** (intrinsics) + **D** (distortion).
   Target reprojection error < 0.5 px. K also gives you the REAL field of view (replaces the ~109°/67° guess).
   **Output:** `K`, `D` saved to file.

## STAGE 2 — Calibrate ToF→camera alignment (extrinsics, ~1 hr)
*Why:* the ToF sensor and camera sit a few cm apart at slightly different angles. `[R|t]` is the
rigid transform that says "a point the ToF sees HERE shows up THERE in the image."
1. Measure the mechanical offset + tilt between ToF and camera (ruler + mount angles) → first-pass `[R|t]`.
2. Refine: wave a single object (pole/board) in view; nudge `[R|t]` until the ToF-detected
   position lines up with where the object appears in the image.
   **Output:** `[R|t]` saved to file.

## STAGE 3 — Project + overlay (Fusion A, the payoff, ~1 hr)
*This is the actual fusion.* Per video frame:
1. For each of the 16 ToF zones: distance × its known ray direction = a 3D point.
2. Transform that point by `[R|t]` → then `cv2.fisheye.projectPoints` (K,D) → a pixel (u,v).
3. Draw a colored depth cell at that pixel on the live video.
   **Output:** live video with 16 depth patches overlaid — "wall at 1.2 m here, floor at 2 m there."
   **This is fusion working.** B and C come later.

---

## Later (not now)
- **Fusion B — detection-gating:** run a 2D object detector, read each box's distance from the
  ToF zones inside it → "person, 1.8 m, left" → haptics. Best practical value.
- **Fusion C — mono-depth:** Depth Anything V2 anchored by ToF scale → dense metric depth across
  the full 140°, including where ToF can't see.

## The one decision blocking Stage 0
Camera needs a compute host. ESP32 can't run this — vision runs on your **laptop first** (dev),
Raspberry Pi 5 + Hailo later (wearable). For now: **laptop.** No hardware to buy to start.

## Full technical detail
`docs/camera-calibration-and-depth-fusion.md` (Part A calibration, Part B projection math + fusion SOTA).
