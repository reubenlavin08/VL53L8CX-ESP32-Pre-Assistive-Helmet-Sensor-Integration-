# Camera Compute Host + Depth-Fusion — Options & Decisions

**Created 2026-06-08** from 3 parallel research agents. Companion to
`camera-and-multisensor-layout.md` and `camera-calibration-and-depth-fusion.md`.
This is the **options + recommendation** doc: where the camera CV runs, and how to fuse
ToF depth with the image. Read this before committing to a Phase 2/3 architecture.

---

## 0. Corrections to earlier docs (verified from primary sources)

Three things I'd gotten wrong or left uncertain, now settled from **ST UM3109 Rev 7** + OmniVision datasheet:

1. **✅ The VL53L8CX HAS a dedicated hardware SYNC pin** — I previously said I wasn't sure it
   existed. It does: **SYNC = ball B1**, an *input*, enabled via
   `vl53l8cx_set_external_sync_pin_enable()`. UM3109 §4.15 says verbatim it's for *"applications
   where there may be interference concerns... multiple VL53L8CX devices or IR image sensors
   within close proximity, or any other electronics emitting 940 nm IR light."* The sensor
   then waits for a **rising edge on SYNC** to start each acquisition. **This is the first-party
   fix for dual-ToF interference — host-trigger the two sensors' SYNC pins offset in time so they
   never emit simultaneously.** (Added in UM3109 Rev 4, Oct 2023 — older manuals omit it.)
   - **Do not confuse with GPIO1/INT (ball A1)** — that's the data-ready *output* interrupt, not sync.

2. **❌ There is NO dedicated "interference detected" status flag** — I'd said the sensor "raises an
   error flag on 940 nm interference." Wrong. Interference instead **degrades the measurement into
   low-confidence `target_status` codes** (low signal rate, high sigma, consistency failures).
   The closest single symptom is **status 12 = "target blurred by another one (due to sharpener)."**

3. **`target_status` table (UM3109 Rev 7, Table 4) — confidence: 5 = 100%, 6 & 9 = 50%, all else <50%:**

   | Code | Meaning | | Code | Meaning |
   |---|---|---|---|---|
   | 0 | data not updated | | 8 | signal rate too low for target |
   | 1 | signal rate too low on SPAD | | **5** | **range VALID (100%)** |
   | 2 | target phase | | 9 | valid, large pulse (merged target?) (50%) |
   | 3 | sigma too high | | 10 | valid, no prev-range target |
   | 4 | target consistency failed | | 11 | measurement consistency failed |
   | 6 | wrap-around not done (50%) | | 12 | **target blurred by another (sharpener)** |
   | 7 | rate consistency failed | | 13 | inconsistent (secondary targets) / 255 = none |

   (Note: the "valid = 5/6/9/12" filter our firmware-adjacent notes use comes from ST *app notes*,
   not UM3109; UM3109 only ranks 5=100% and 6/9=50%.)

4. **OV2710 = rolling shutter — CONFIRMED** from the datasheet (skew/jello on fast head motion is real).
   Sensitivity quoted 3300–3700 mV/lux-sec across sources. Otherwise as documented.

5. **"140°" = diagonal FOV — CONFIRMED** as the industry convention. Naive rectilinear split is
   invalid past ~110–120° (real lens is non-rectilinear); realistic split **H ≈ 110–120°, V ≈ 60–70°**
   — consistent with our ~109°/67° ladder estimate. Exact numbers still require calibration.

---

## PART 1 — Where does the camera CV run? (compute host)

### Can the ESP32 do it? Mostly no.
- **ESP32-S3 as USB-host UVC: hard NO for this camera.** Its USB is **Full-Speed (12 Mbps)**;
  Espressif's UVC host driver caps practical streams at **~320×240@30 or 640×480@15, MJPEG only**.
  1080p won't even enumerate. On-chip detection (`esp-detection espdet_pico`, 1-class, 224×224)
  is **~7 FPS on S3** — a toy. **Not a CV host.**
- **ESP32-P4: can *capture* the camera, can't *understand* it.** USB 2.0 **High-Speed (480 Mbps)** +
  **hardware MJPEG decode → 1080p@30**. But even on the P4, a full multi-class YOLO runs **~0.6 FPS**;
  only `espdet_pico` (1-class, 224×224) hits ~18 FPS. **Good camera co-processor, not a brain.**

### The host ladder (mid-2026 street prices)

| Option | ~Cost | Power | Weight | CV horsepower | ↔ ESP32-S3 | Wearable fit |
|---|---|---|---|---|---|---|
| **ESP32-P4** | $10–35 | ~0.3–1.5 W | ~5–15 g | HW MJPEG/H.264 1080p30 *capture*; only 1-class `espdet_pico` ~18 FPS | native MCU: UART/SPI/I2C | great power/weight, **weak CV** |
| OpenMV RT1062 | $80–100 | ~0.5–1 W | ~15–20 g | M7; FOMO blob/"person-ish" detection ~realtime QVGA; no YOLO; uses *its own* cam | UART/SPI/I2C native | good IF FOMO-class is enough |
| Pi Zero 2 W | $15–20 | ~1.5–3 W | ~11 g | CPU-only ~**1.7 FPS** SSD-Lite | GPIO/USB/WiFi | marginal (too slow) |
| Pi 4 | $45–55 | ~3–7 W | ~46 g | CPU-only ~2–3 FPS YOLOv8n | GPIO/USB/WiFi | needs accelerator |
| Pi 5 | $60–80 | ~3–9 W | ~46 g | CPU-only ~2–4 FPS; great accel host | GPIO/USB/WiFi | good base + accel |
| **Pi 5 + Hailo-8L (13 TOPS)** | **~$130** | **~10 W** | ~66 g | **YOLOv8s 25–35 FPS live**; fisheye undistort + fusion all fine in OpenCV | UART/WiFi to S3 | **best CV-per-watt; needs a power bank** |
| Pi 5 + Coral USB (4 TOPS) | ~$120–150 | ~5–10 W | ~66 g | MobileNet-SSD 100+ FPS; mature but dated model zoo / aging drivers | UART/WiFi | good, proven |
| Jetson Orin Nano (Super) | ~$249 | **7–25 W** | heavy +heatsink | 67 TOPS; YOLOv8n 40–66 FPS; full CUDA/depth nets | UART/USB/WiFi | most power, **worst wear fit (backpack)** |
| Smartphone (reuse old) | $0 | internal | phone | NPU runs YOLO realtime; has own cam+IMU | BLE/WiFi | strong & free; USB-cam integration is the friction |
| Tethered laptop | $0 | wall | bench only | anything @30+ FPS | USB cam + serial | **best for dev / ground truth** |

Battery math: a 10 000 mAh (~37 Wh) bank runs a 10 W Pi5+Hailo for **~3 h**, a 25 W Jetson ~1.5 h,
a ~1 W P4/OpenMV for **a day+**.

### Recommendation (you already have an S3 doing ToF + haptics)
**Keep the companion-computer split:** ESP32-S3 stays the deterministic **reflex/haptic safety
controller**; a separate board does heavy vision and sends back *high-level* results ("person,
bearing −20°, 1.4 m") over **UART** (you already speak serial) or WiFi. You don't rewrite firmware.

- **Dev now:** prototype the whole CV pipeline on your **laptop** (USB cam → laptop → S3 over serial).
  Zero spend, full-speed iteration, doubles as ground truth.
- **Wearable brain:** **Raspberry Pi 5 (4 GB) + Hailo-8L AI HAT+ (~$130, ~10 W).** Only sub-$150 /
  sub-10 W option that does real-time multi-class detection + fisheye undistort + ToF fusion in
  plain OpenCV/Python. Plug the HBV-1716WA straight in (UVC, no driver work).
- **Only if you must hit ~1 W:** add an **ESP32-P4** as a camera co-processor (captures 1080p,
  1-class detection or just streams frames, talks UART/SPI to the S3).
- **Avoid for head-wear:** Jetson Orin Nano (25 W + bulk) and bare Pi's without an accelerator (~2 FPS = unsafe).

---

## PART 2 — How to fuse the ToF depth with the image

**Framing facts:** (a) the ToF is *not* sparse LiDAR — it's a **structured 16/64-cell angular grid**
with known per-zone angles + sigma + status; that structure is your asset and makes heavy
LiDAR-completion nets the wrong tool. (b) **FOV mismatch:** camera 140° vs ToF ~45° → ToF only
covers the **central ~1/3 (horizontal)** of the frame; the periphery is **vision-only**.

| # | Approach | Output | Compute (Pi-class) | Calib. sensitivity | Right-sized for 16–64 zones? |
|---|---|---|---|---|---|
| 1 | **Geometric overlay** — project each zone into the image | annotated distance dots | negligible | moderate | **Yes — foundation** |
| 2 | **Detection-gating / PointPainting-lite** — 2D detector, depth from overlapping zones | "person, 1.4 m, left" | detector-bound (~5–30 FPS) | **low (box-level)** | **Yes — best value** |
| 3 | Depth-completion NN (NLSPN/CompletionFormer/GuideNet) | dense depth map | heavy (needs accel) | high | **No — wrong design point.** Use ToF-specific CFPNet/ToFormer if ever |
| 4 | BEV / occupancy grid | top-down free/occupied | cheap→heavy | low | overkill now; nice later layer (maps to L/C/R haptics) |
| 5a | **Mono-depth + ToF anchor** (Depth Anything V2 / MiDaS) | **dense METRIC depth, full 140°** | medium–heavy (NN) | **low (global fit)** | **Yes — strong; covers periphery ToF can't see** |
| 5b | ToF-as-confidence (vision proposes, ToF confirms) | trust-gated alerts | cheap | low | yes |
| 5c | Late/decision fusion (independent ToF reflex + vision) | merged alerts | cheap | **none for reflex path** | yes — robust safety net |
| 5d | Semantic-depth (suppress "floor" class etc.) | class-filtered depth | detector-bound | low | refinement only |

### The standout new option: **mono-depth + ToF metric anchoring (5a)**
MiDaS / Depth Anything output *relative* (affine-invariant) depth — right shape, unknown scale+shift.
**Your 16–64 ToF zones are exactly the metric anchors to solve that**: least-squares fit a global
scale+shift (in inverse-depth) so predicted depth matches the ToF zones → a **dense metric depth map
across the WHOLE 140° frame, including the periphery the ToF can't reach.** Robust to extrinsic error
(global fit). Depth Anything V2-small / MiDaS-small run on a Pi (faster with the Hailo). **Caveat for a
safety device:** it's a learned guess — keep the raw ToF reflex (5c) as the authoritative "something
is close" trigger; use mono-depth for richer context, not the sole safety signal.

### Recommended progression (build in this order)
- **Phase A — Geometric overlay (1), fisheye-native + ToF reflex (5c).** Calibrate fisheye intrinsics
  (`cv::fisheye`), coarse mechanical+manual extrinsic, project the zones with `cv::fisheye::projectPoints`
  onto the *raw* fisheye. Pair with a ToF-only reflex alert so you have a working safety device on day one
  with zero dependence on calibration.
- **Phase B — Detection-gating (2)** + floor-suppression (5d). Lightweight 2D detector; each box gets a
  distance from overlapping zones; feed straight into the existing **LEFT/CENTER/RIGHT haptic** mapping.
  Highest value-per-effort — this is where it becomes genuinely useful.
- **Phase C — Mono-depth + ToF anchor (5a).** Adds dense metric depth across the full 140°. Undistort only
  a central sub-window for NN inference; keep the Phase-A ToF reflex as the safety layer.
- **Defer/skip:** generic LiDAR completion nets (3) and full learned BEV (4).

### Extrinsic calibration of a SPARSE ToF → camera (you can't checkerboard 64 zones)
1. **Mechanical/CAD prior** — rigid mount, read nominal R|t from geometry. Baseline is ~cm, obstacles
   are meters → **translation ~negligible; you're really only solving rotation (a few °).**
2. **Use the known per-zone angles** — each zone already maps to a 3D ray for free (no point-cloud target
   detection needed); calibration = find the 3-DOF rotation aligning rays to the image.
3. **Moving-single-target refine** — wave one easily-segmented object through the overlap at varied
   depths; per frame match its image centroid ↔ the zone(s) seeing it; least-squares the rotation.
4. **Fastest for a student: manual slider nudge** — run the live overlay, hold a target, hand-tune
   yaw/pitch/roll until the dots land on it. Refine numerically later.

### Fisheye: project, don't rectify (confirmed)
For 140°, **keep the raw fisheye and project ToF points via `cv::fisheye::projectPoints`** (Kannala-
Brandt). Undistorting 140°→rectilinear either crops most of your FOV or hideously stretches corners.
Bonus: the ToF only covers the **central, least-distorted** part of the frame, so a 2D detector there
sees benign distortion. (Exception: if a mono-depth net wants rectilinear input, undistort only a
central ~90° virtual-pinhole sub-window for inference.)

---

## Sources
**Compute host:** [ESP USB-Stream UVC limits](https://docs.espressif.com/projects/esp-iot-solution/en/latest/usb/usb_host/usb_stream.html) · [ESP32-P4 product page](https://www.espressif.com/en/products/socs/esp32-p4) · [esp-detection FPS](https://github.com/espressif/esp-detection) · [Jeff Geerling Pi5+Hailo-8L](https://www.jeffgeerling.com/blog/2024/testing-raspberry-pis-ai-kit-13-tops-70/) · [Seeed Pi5+Hailo YOLOv8](https://wiki.seeedstudio.com/benchmark_on_rpi5_and_cm4_running_yolov8s_with_rpi_ai_kit/) · [Coral benchmarks](https://www.coral.ai/docs/edgetpu/benchmarks/) · [Jetson Orin Nano Super](https://www.ultralytics.com/blog/ultralytics-yolo11-on-nvidia-jetson-orin-nano-super-fast-and-efficient)
**Fusion:** [PointPainting](https://arxiv.org/abs/1911.10150) · [CFPNet — lightweight-ToF completion](https://arxiv.org/pdf/2411.04480) · [ToFormer](https://arxiv.org/pdf/2603.20669) · [SparseFormer (beats NLSPN at few points)](https://arxiv.org/pdf/2206.04557) · [2.5D ToF↔camera extrinsic calib](https://jaesik.info/publications/data/11_iros.pdf) · [OpenCV fisheye docs](https://docs.opencv.org/4.x/db/d58/group__calib3d__fisheye.html) · [Mono visual-inertial depth (scale+shift anchoring)](https://arxiv.org/pdf/2303.12134) · [Depth Anything V2](https://towardsdatascience.com/monocular-depth-estimation-with-depth-anything-v2-54b6775abc9f/) · [WoodScape (distortion-aware vs undistort)](https://arxiv.org/pdf/1905.01489)
**Verified facts:** [ST UM3109 Rev 7](https://www.st.com/resource/en/user_manual/um3109-a-guide-for-using-the-vl53l8cx-lowpower-highperformance-timeofflight-multizone-ranging-sensor-stmicroelectronics.pdf) (SYNC pin §4.15, target_status Table 4, modes §4.5) · [OV2710 datasheet](https://www.ovt.com/products/ov2710/)
