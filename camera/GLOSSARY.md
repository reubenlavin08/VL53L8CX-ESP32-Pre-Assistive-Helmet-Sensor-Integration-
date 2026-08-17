# Every term, and why we're doing each stage

**Location:** `C:\esp-projects\vl53l8cx_esp32\camera\GLOSSARY.md`

Plain English first, technical name after. Nothing here assumes prior knowledge.

---

## THE GOAL, in one sentence

Your ToF sensor knows **distances but not what things are**. Your camera knows **what things are but not how far**. **Fusion** = connecting them, so every object the camera sees also carries a distance in metres.

Concretely: for each of the 16 ToF measurements, work out **which pixel of the camera image it corresponds to**. Then "obstacle at 1.2 m" and "that's a person" become the same fact.

Everything below exists to make that one connection possible.

---

## THE CORE PROBLEM

The camera turns **3D directions into 2D pixels**. A point somewhere in space lands at some pixel. To connect ToF to pixels, we must be able to compute that landing spot.

Two things stop us:

1. **We don't know the camera's internal geometry.** How much does it magnify? Where exactly is the image centre? How much does the wide lens bend light? → **Stage 2 measures this.**
2. **We don't know where the ToF sensor sits relative to the camera.** They're a few cm apart at slightly different angles. → **Stage 3 measures this.**

Once we have both, **Stage 4** is just arithmetic.

---

## TERMS

### Camera basics

**Pixel** — one dot in the image. Your camera makes 1280 × 720 = 921,600 of them per frame.

**Frame** — one still picture. 30 frames per second = video.

**UVC (USB Video Class)** — the universal standard all webcams speak. Why yours needed no driver: Windows already knows the language.

**MJPEG (Motion JPEG)** — video compression where each frame is a separate JPEG. Your camera can send raw (**YUY2**) only at low resolution, so at 1280×720 it must compress with MJPEG.

**Camera index** — the number OpenCV uses to pick a camera. Built-in webcam = 0, your HBV = 1.

**OpenCV** — the standard computer-vision library. `cv2` in Python.

### Lens and field of view

**Field of view (FOV)** — how wide an angle the camera sees. Yours is **140° diagonal** (corner to corner). The **horizontal** and **vertical** numbers are *not* documented for your lens — Stage 2 measures them.

**Fisheye** — a very wide lens. To fit 140° onto a flat sensor it must **bend straight lines into curves**, worst at the edges. You can see this in your own test image: the desk edge bows.

**Distortion** — that bending. Not a defect; it's how wide lenses work. We measure it so we can compute around it.

**Focus** — the lens is a screw thread. Turning it moves the glass closer to or further from the sensor, changing what distance looks sharp. **Fixed-focus**: one setting, roughly 30 cm to infinity, no autofocus.

**Why lock the focus (Stage 1)** — turning the barrel changes the lens-to-sensor distance, which is *exactly the thing* Stage 2 measures. Move it after calibrating and every number is wrong. You *can* refocus later — you'd just have to redo Stage 2. So: focus first, lock, then calibrate.

### Stage 2 terms — the lens model

**Intrinsics** — the camera's *internal* properties. "Intrinsic" = inherent to the camera itself, independent of where it's pointed. Two parts, **K** and **D**.

**K (the camera matrix)** — four useful numbers:
- **fx, fy — focal length in pixels.** How strongly the camera magnifies. Bigger = more zoomed in, narrower view.
- **cx, cy — the optical centre.** Where the lens's axis actually hits the sensor. Never exactly the middle of the image; manufacturing is never perfect. Usually a few pixels off.

Written as a grid:
```
K = [ fx   0   cx ]
    [  0  fy   cy ]
    [  0   0    1 ]
```
The zeros and the 1 are structural padding so it multiplies cleanly — only those four numbers carry information.

**D (distortion coefficients)** — four numbers `k1, k2, k3, k4` describing how much the lens bends light outward at each angle.

**Calibration** — measuring K and D by photographing an object of *known* geometry.

**Checkerboard / calibration target** — the printed board. We use it because we know its geometry **exactly** (a flat grid of 20 mm squares) and because **corners where four squares meet are the easiest feature in all of computer vision to locate precisely** — high contrast in two directions, findable to a fraction of a pixel.

**Inner corners** — the X-junctions where 4 squares meet. Only these count; the outer edge of the board has no junctions. A 9×12 grid of squares has **8×11 = 88 inner corners**. That's why the board is called "8×11".

**Zhang's method** — the standard calibration technique (Zhengyou Zhang, Microsoft Research, 2000): photograph one flat known board from many angles, solve for the camera. It's what `cv2.fisheye.calibrate` does.

**Why tilting is required, not a problem** — the thing that confused you earlier. Held flat-on and square to the camera, a *small board close* and a *big board far* produce nearly identical images. Focal length and distance trade off and can't be separated. **Tilting breaks the tie:** a tilted plane foreshortens (the far edge looks smaller) in a way that depends on focal length *alone*. So tilt is what makes the answer unique. **Flat-on views are the useless ones.**

**Why many photos** — one photo has more unknowns than equations. Each new view adds equations while K and D stay the same. About 20 views over-constrains it and averages out noise.

**Kannala-Brandt / `cv2.fisheye`** — the fisheye lens model. The ordinary model assumes a ray at angle θ lands at distance `f · tan(θ)` from centre. At 140°, θ approaches 70°, `tan` explodes, and the fit fails. The fisheye model uses θ directly plus four correction terms and stays stable to the edge. **Rule of thumb: above ~120°, use fisheye.**

**Reprojection error** — the quality score. Take each corner you detected. Use the fitted model to *predict* where it should be. Measure the gap in pixels. **RMS** (root-mean-square) averages all those gaps.
- **under 0.5 px = good**, 0.5–1.0 = usable, over 1.0 = something's wrong.
It's "how well does my model reproduce reality" — small gap = model is right.

**Undistort** — using D to straighten the curved image. We generate one preview to check the fit visually, but **we do not undistort for fusion** — straightening a 140° image throws away field of view and resamples every pixel. Instead we keep the raw image and bend the *ToF points* to match it. Cheaper and lossless.

### Stage 3 terms — where the sensors are relative to each other

**Extrinsics** — the camera's *external* situation: where it is and which way it points relative to something else. Here: relative to the ToF sensor. Written **[R|t]**.

**R (rotation)** — a 3×3 grid of numbers encoding "the ToF is rotated this much relative to the camera."

**t (translation)** — three numbers: "the ToF is this many cm over, up, and forward from the camera."

**Rigid transform** — rotation + translation, no stretching. Correct here because both are bolted to the same helmet and can't deform relative to each other.

**Why we can't checkerboard the ToF** — the ToF has 16 fat cone-shaped zones, not pixels. It can't "see" a checkerboard. So: measure the mounting offset with a ruler for a first guess, then refine by waving one object and nudging until the ToF's reported position lines up with where the object appears in the image.

### Stage 4 terms — the actual fusion

**Zone** — one ToF measurement cell. Yours is a **4×4 grid = 16 zones**, each covering about 11.25° of angle, each returning one distance.

**Ray / unit ray** — the direction a zone points. Known from its position in the grid. So `distance × direction` = a **3D point** in the ToF's own frame of reference.

**Projection** — computing which pixel a 3D point lands on. The whole chain:

```
zone distance + zone direction  ->  3D point (ToF frame)
        apply [R|t]             ->  3D point (camera frame)
   cv2.fisheye.projectPoints    ->  pixel (u, v)
```

The textbook version of the middle step, written plainly:
```
Z * [u, v, 1]  =  K * [R|t] * [X, Y, Z, 1]
```
Meaning: take the 3D point, move it into the camera's frame with `[R|t]`, apply the camera's internals with `K`, and you get the pixel. For our fisheye we swap the plain `K` multiply for `cv2.fisheye.projectPoints` so the lens bending is included — otherwise points land wrong at the edges.

**That's the fusion.** Everything before it exists to make those two substitutions possible.

### Stage 5 and 6 terms

**Object detector** — a neural network that draws boxes around things and labels them ("person", "chair").

**Detection-gating / PointPainting-lite (Stage 5)** — run the detector, then read the distance from whichever ToF zones fall inside each box. Output: "person, 1.8 m, on your left" → drives haptic urgency. **Best value for effort** of anything after Stage 4.

**Monocular depth (Stage 6)** — a network that estimates depth from a single image. It gets *relative* depth right ("that's further than that") but has no true scale. Anchor it with a few real ToF distances and you get **dense metric depth across the entire 140°**, including the periphery the ToF can't reach.

---

## WHY EACH STAGE EXISTS — the short version

| Stage | Why it must happen |
|---|---|
| 0 Camera alive | Can't do anything without a picture. |
| 1 Focus + lock | Stage 2 measures the lens-to-sensor distance. Move it later and everything is void. |
| 2 Calibrate (K, D) | Without K and D you cannot compute which pixel a direction lands on. Everything else depends on this. |
| 3 Align (R, t) | The ToF and camera are in different places. Without this you'd project depth as if they were the same object — and be wrong by centimetres, which is many pixels. |
| 4 Project + overlay | The payoff. Depth attached to pixels. |
| 5 Detection-gating | Turns "1.2 m ahead" into "person 1.2 m ahead" — an actually useful alert. |
| 6 Mono-depth | Extends depth into the 140° periphery the ToF never sees. |

---

## THE HARDWARE FACTS THAT BIT US

**Your camera has no official datasheet.** Verified — HBVCAM publishes nothing for the "WA" variant; it's a reseller SKU. So its horizontal and vertical FOV are genuinely unknown, and Stage 2 is the only way to learn them. Full record: `C:\esp-projects\vl53l8cx_esp32\docs\datasheets\camera\HBV-1716WA-VERIFIED-SPECS.md`

**1080p is broken on your unit** — firmware bug, not our software. The module tells the computer it needs about ten times more USB bandwidth than it really does (it copied the *uncompressed* number into the *compressed* slot), so Windows can't reserve enough and the stream never starts. Proved it with ffmpeg, which bypasses all our code. **We use 1280×720.** Costs nothing — object detectors shrink images to ~640 px anyway.

**K depends on resolution.** Calibrate at 720p, and 720p is what you must capture at forever after. Change resolution → recalibrate.

**Heat:** stable image quality 0–50 °C, still functions to 70 °C (OV2710 datasheet Table 8-2). (The USB drop-outs seen during bring-up were manual unplugs, not a fault - resolved 2026-07-31.) If it's too hot to hold a finger on, let it cool.
