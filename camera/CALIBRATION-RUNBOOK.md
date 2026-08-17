# STAGE 2 — Calibrate the camera (morning runbook)

Everything is written and syntax-checked. Follow top to bottom. ~30 min, most of it printing and waving a board around.

**Prerequisite from Stage 1:** the lens barrel is focused and **locked** (nail polish / Kapton), with a witness mark drawn across the joint. If it isn't locked, do that first — recalibration is the price of skipping it.

---

## 1. Print the board (5 min)

File: `camera/checkerboard_8x11_20mm.pdf`

- Print **at 100% / "Actual size"**. **Not** "Fit to page" / "Shrink to fit" — that silently resizes the squares and every measurement downstream is wrong.
- **Matte paper only.** Glossy reflects and the corner detector fails on the glare.
- **Verify with a real ruler:** the printed scale bar must measure **exactly 100 mm**. If it doesn't, reprint. (If your printer can't do it, measure the bar and tell me — I'll adjust `SQUARE_MM` instead.)
- **Glue it to something rigid and flat** — foam-core, clipboard, stiff cardboard. **Flatness matters more than print quality.** A curled page bends the geometry the whole method assumes is flat, and no amount of extra images fixes that.

One sheet is enough. You'll move it around rather than print several.

## 2. Capture the images (10–15 min)

```
python camera/capture_calib.py
```

Hold the board up and move it around in front of the camera.

- Green overlay on the corners = detected.
- It **auto-captures** when the board is found, held still, and in a screen region not yet covered. Green flash = saved. SPACE forces a capture.
- **Coverage grid, 3×3 in the corners of the view.** Red = 0 shots, orange = 1, green = 2+. **Get all nine green.** The edge and corner cells are what pin down the fisheye distortion — the centre alone gives a model that's guessing out at the rim.
- **Vary the tilt a lot.** Steep angles, rotations, both directions. **Flat-on square-to-the-camera shots are the useless ones** (see below).
- **Vary the distance** — board filling most of the frame, and small in a corner. The readout shows what fraction of the frame it fills.
- Target **20+ keepers**, all nine cells green. Press `q` when done.

Keys: `SPACE` force-capture · `d` delete last · `r` reset · `q` finish

## 3. Calibrate (30 seconds)

```
python camera/calibrate_fisheye.py
```

Reads the images, fits the lens model, writes:
- `camera/calibration_720p.npz` — **K and D, the actual deliverable**
- `camera/calibration_720p.txt` — readable report, includes the **measured** FOV
- `camera/undistort_preview.jpg` — before/after, to eyeball

**Judge it by the RMS reprojection error:**

| RMS | Meaning |
|---|---|
| **< 0.5 px** | Good. Use it. |
| 0.5–1.0 px | Usable. More/steadier views would improve it. |
| > 1.0 px | Something's wrong — board not flat, focus shifted, blurry frames. |

Per-image errors are printed worst-first. One bad frame dragging the fit is easy to spot: delete it from `camera/calib_shots/` and re-run.

Open `undistort_preview.jpg` — in the right-hand image the board edges should be **straight**.

## 4. Tell me the numbers

Send me the RMS and the measured HFOV/VFOV. That's the first time we'll have **real** field-of-view numbers instead of the extrapolated ~109°/67° guess.

Then we go to **Stage 3 — ToF-camera alignment (extrinsics)**, and then **Stage 4, the actual fusion overlay.**

---

## Why any of this works (the part worth understanding)

We know the board's real geometry exactly: a flat grid of 20 mm squares. So for each photo OpenCV can ask: *given that this known flat grid landed on these particular pixels, where was the camera and what must the lens be doing to light?*

One photo leaves too many unknowns. Many photos of the **same** board from **different** angles over-constrain the problem until only one lens model fits them all. That model is **K** (focal length in pixels + true optical centre) and **D** (how the lens bends light outward). This is **Zhang's method**.

**Why tilting is required, not a problem.** Held flat-on and square, "small board close" and "big board far" produce nearly identical images — focal length and distance trade off and can't be separated. Tilting breaks the tie: a tilted plane foreshortens in a way that depends on focal length *alone*. **Tilt is what makes the answer unique.**

**Why `cv2.fisheye`.** The standard pinhole model assumes a ray at angle θ lands at `f·tan(θ)` from centre. At 140° `tan(θ)` blows up and the fit fails or skews badly. The fisheye (Kannala-Brandt) model uses θ directly plus four correction terms and stays well-behaved to the edge. Rule of thumb: **above ~120°, use fisheye.**

**Videos, if you want them first:**
- Cyrill Stachniss — *Intrinsic Camera Calibration* (5 min): https://www.youtube.com/watch?v=26nV4oDLiqc
- Cyrill Stachniss — *Zhang's Method*: https://www.youtube.com/watch?v=-9He7Nu3u8s

---

## Notes
- All capture is at **MJPG 1280×720**. 1080p is unusable on this module (firmware bug — `docs/datasheets/camera/HBV-1716WA-VERIFIED-SPECS.md`). **K is resolution-dependent** — change resolution and this calibration is void.
- If the module gets too hot to hold a finger on, unplug and let it cool. Above ~50 °C the OV2710 leaves its stable-image band (datasheet Table 8-2), (The earlier USB drop-outs were manual unplugs, not a fault - resolved 2026-07-31.)
- We do **not** undistort the image for fusion. The preview is only a sanity check. Fusion keeps the raw fisheye frame and projects ToF zones into it with `cv2.fisheye.projectPoints` — wastes no field of view, resamples nothing.
