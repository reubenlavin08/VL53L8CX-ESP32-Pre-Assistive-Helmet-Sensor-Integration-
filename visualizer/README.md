<h1 align="center">VL53L8CX Live 3D Point Cloud Visualiser</h1>

<p align="center">
  <em>PyQtGraph + OpenGL renderer for the ESP32's <code>DATA:</code> stream — animated ToF rays, side colour-bar, 6-DOF Kabsch pose estimation, and a world-frame point memory that wraps around the sensor as it pans.</em>
</p>

---

<p align="center">
  <video src="progress_demo_v6.mp4"
         controls muted autoplay loop playsinline width="820">
  </video>
</p>
<p align="center"><em>v6 — accumulated past observations slide off to the side as the sensor rotates; the cone effectively wraps around. Trail behind the sensor fades from invisible at the tail to bright yellow at the head.</em></p>

---

## What you're looking at

| Element | What it is |
|---|---|
| **64 bright dots in a cone** | Live measurements, one per zone, coloured by distance (viridis: purple = close, yellow = far). |
| **Animated coloured beams from the sensor** | One ToF ray per zone, faded from the lens out to its endpoint, in the same hue as the point. They pulse with the live data — physically what a multizone ToF sensor is doing. |
| **Faded surrounding cloud** | Past observations in **world frame**, transformed back into the current sensor frame each tick and faded by age (~6 s memory). As you rotate, they slide off to the side instead of staying glued to the front. |
| **Yellow line behind the sensor** | Estimated 6-DOF trajectory of the sensor's origin (last ~5 s), per-vertex alpha-faded so old segments disappear. |
| **Sensor body + lens ring at origin** | Flat dark rectangle modelling the SATEL-VL53L8CX face, with a bright lens circle and "VL53L8CX" label. |
| **Pale frustum** | The sensor's actual 45° × 45° field of view (per ST datasheet — 65° diagonal). |
| **Side colour bar** | Distance scale in mm. |
| **Status bar** | Live frame count, valid-zones / 64, mean valid distance, cumulative pose translation + rotation, and the per-frame rejection count. |

---

## Quick start

```bash
cd visualizer
python -m venv venv
venv\Scripts\activate           # Windows  (Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt

python visualizer.py --port COM12
```

> Make sure `idf.py monitor` is **closed** before starting — only one program can hold the COM port at a time.

| Flag | Default | Description |
|---|---|---|
| `--port` | `COM12` | Serial port the ESP32 is on |
| `--baud` | `115200` | Matches the ESP-IDF console default |
| `--max-mm` | `4000` | Z-axis range + colour-scale max (mm) |

**Hotkey:** press **`R`** in the visualiser window to reset the cumulative pose and clear the trail + accumulated cloud.

---

## How it works

### 1. Serial protocol
The ESP32 streams one compact line per frame:
```
DATA:820,815,801,790,...,(64 values total)
```
Invalid zones are clamped to `MAX_DISTANCE_MM` (= 4000 mm) on the firmware side so the host always gets exactly 64 values. The visualiser detects the clamp and renders those zones with `α = 0`, hiding them.

### 2. Threaded pipeline
Serial reads run in a dedicated `QThread`; new frames are delivered to the GUI via a Qt signal. Each cycle drains everything currently buffered and keeps only the **newest** valid `DATA:` line — this kills the "rendering one frame stale" failure mode of the original implementation.

### 3. Geometric projection
The VL53L8CX is **65° diagonal / 45° per axis**. Each of 8 zones along an axis subtends `45° ÷ 8 = 5.625°`. A unit direction vector is precomputed for every zone:

```text
h_angle = (col − 3.5) × 5.625°       v_angle = (row − 3.5) × 5.625°
x =  sin(h_angle)
y = −sin(v_angle)                     (row 0 is the top of the sensor view)
z =  cos(h_angle) × cos(v_angle)      (sensor boresight = +Z)
```

Multiplying each unit vector by its zone's measured distance gives the 3D point.

### 4. EMA smoothing (α = 0.6)
Raw zones jitter ±10–30 mm frame-to-frame on a static scene. Per-zone exponential moving average:

```python
smoothed[v] = 0.6 * new[v] + 0.4 * smoothed[v]
```

α = 0.6 settles to 95 % of a step in `−ln(0.05) ÷ −ln(1 − 0.6) ≈ 3` samples — about 200 ms at 15 Hz. Tunable in `visualizer.py`.

### 5. 6-DOF relative pose (Kabsch / Procrustes)

Closed-form rigid registration on consecutive 64-point clouds. Given paired sets P (frame k−1) and Q (frame k):

```text
1.  Pc, Qc      = P − mean(P), Q − mean(Q)
2.  H           = Pc.T @ Qc
3.  U, S, Vt    = svd(H)
4.  d           = sign(det(Vt.T @ U.T))         # reflection guard
5.  R           = Vt.T @ diag(1, 1, d) @ U.T
6.  t           = mean(Q) − R @ mean(P)
```

The fitted (R, t) maps a world point's old-frame coords to its new-frame coords. The **sensor's** per-frame motion is the inverse: `δR = R.T`, `δt = −R.T @ t`. World-frame cumulative pose composes as `T_world(k) = T_world(k-1) · δ`.

We rely on **same-zone correspondence under the small-motion assumption** — at 15 Hz (~67 ms per frame) zone *i* in two consecutive frames still observes approximately the same world point. Wrong correspondence (fast motion) shows up as huge fitted Δt or ΔR; the estimator gates on `≤ 300 mm` and `≤ 20°` per frame and breaks the chain instead of corrupting cumulative state.

### 6. World-frame point memory (v6)

Each frame, valid sensor-frame points are transformed via `world_p = R_world · sensor_p + t_world` and pushed into a rolling 6-second deque. For rendering, every entry is transformed *back* into the current sensor frame and given an alpha proportional to its age (newest = ~0.35, oldest = 0). The visual effect: as the sensor pans, old observations stay fixed in space and slide around.

---

## Honest limits

- 64 points × ±10–30 mm noise is sparse and noisy for ICP-style registration. Expect drift, especially in **yaw** (rotation around gravity is unobservable from a flat-floor depth map — no algorithm can recover it from depth alone).
- 0/64 valid zones (covered sensor, loose connection) → estimator pauses cleanly.
- The 6-second memory cap keeps drift damage local. With an IMU added later, the same code becomes a usable sparse 3D map.

For full development context — every visualiser iteration, every fix, the evidence behind each decision — see [`../PROGRESS.md`](../PROGRESS.md).

---

## Hardware this runs on

| Component | Detail |
|---|---|
| Sensor | STMicroelectronics SATEL-VL53L8CX (8×8, 65° diagonal, 1–15 Hz) |
| Microcontroller | ESP32-S3-DevKitC-1 (N16R8) |
| Serial chip | CH343 USB-UART, appears as `COM12` |
| Connection | UART USB port (left, on DevKitC-1) |
| Baud rate | 115 200 |
| Ranging config | 8 × 8 zones, **15 Hz**, continuous mode |
