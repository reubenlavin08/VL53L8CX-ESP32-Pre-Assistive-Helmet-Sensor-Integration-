# Project Progress Log

> VL53L8CX × ESP32-S3 Distance Sensor Interface
> Part of an ongoing assistive helmet sensor integration project.

---

## What Has Been Built

### Phase 1 — Firmware (complete)

A working ESP-IDF project that:
- Initialises I2C bus on GPIO1 (SDA) and GPIO2 (SCL) at 1 MHz
- Uploads ST's ULD firmware to the VL53L8CX on boot (~1 s)
- Configures 8×8 zone ranging at 10 Hz in continuous mode
- Streams a compact `DATA:d0,d1,...,d63\n` line to serial every frame
- Clamps invalid or out-of-range zones to `MAX_DISTANCE_MM` (4000 mm) so the host never sees gaps

**Key files:**
| File | Purpose |
|------|---------|
| `main/main.c` | Sensor init, firmware upload, ranging loop, serial output |
| `main/idf_component.yml` | Pulls `rjrp44/vl53l8cx ^4.0.0` from ESP Component Registry |
| `sdkconfig.defaults` | Stack size, I2C timeout, log levels |

**Compile-time toggles in `main.c`:**
| Define | Default | Effect |
|--------|---------|--------|
| `STREAM_DATA` | `1` | Emits `DATA:` lines for the Python visualiser |
| `PRINT_GRID` | `0` | ASCII 8×8 grid in serial monitor |
| `PRINT_CLOSEST_ONLY` | `0` | Single "nearest zone" log line |
| `RANGING_FREQ_HZ` | `10` | 1–15 Hz (8×8 mode) |
| `SENSOR_RESOLUTION` | `VL53L8CX_RESOLUTION_8X8` | Or `_4X4` |
| `MAX_DISTANCE_MM` | `4000` | Clamp value for invalid zones |

---

### Phase 2 — Live 3D Point Cloud Visualiser (complete, v2)

A Python script (`visualizer/visualizer.py`) that:
- Opens the serial port and reads `DATA:` lines in real time
- Precomputes a unit direction vector for each of the 64 zones using the sensor's 45° field of view
- Multiplies each zone's measured distance by its direction vector to produce a true 3D Cartesian point
- Applies exponential moving average (EMA) smoothing per zone to eliminate sensor noise
- Drains the serial buffer each frame to always render the newest data, not a stale backlog
- Renders a live scatter plot (matplotlib, dark theme, viridis colormap, colourbar)
- Scatter object created once — updated in-place each frame, no full redraws, no flicker
- Updates at ~10 Hz, matching the sensor's ranging frequency

<p align="center">
  <img src="images/visualizer_point_cloud.png" width="700" alt="Live 3D point cloud — frame 1916"/>
</p>

```bash
cd visualizer
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python visualizer.py --port COM12
```

**CLI options:**
| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `COM12` | Serial port the ESP32 is on |
| `--baud` | `115200` | Must match ESP-IDF default |
| `--max-mm` | `4000` | Z-axis range and colour scale max |

**Smoothing tuning:**  
`EMA_ALPHA` at the top of `visualizer.py` controls the blend between new and historical readings.  
`0.3` (default) = smooth, ~300–400 ms to track a real change. Lower = smoother, higher = more responsive.

---

## Hardware Setup

### Components
- ESP32-S3-DevKitC-1 (N16R8) on AliExpress expansion adapter
- STMicroelectronics SATEL-VL53L8CX breakout board
- 4× 1 kΩ resistors (wired as 2×2 kΩ pull-ups on SDA and SCL)
- 1× 10 kΩ resistor (pull-up for PWREN)

### Confirmed working wiring
| SATEL Pin | ESP32-S3 Pin | Notes |
|-----------|-------------|-------|
| PWREN | GPIO5 (left, 5th from top) | + 10 kΩ pullup to 3.3V |
| MCLK_SCL | GPIO2 (right, 5th from top) | + 2×1 kΩ in series pullup to 3.3V |
| MOSI_SDA | GPIO1 (right, 4th from top) | + 2×1 kΩ in series pullup to 3.3V |
| NCS | 3.3V | Tied high — selects I2C mode |
| SPI_I2C_N | GND | Tied low — locks I2C mode |
| VDD | 3.3V | Sensor LDO accepts 2.8–5.5V; 3.3V is fine |
| GND | GND | Common ground |

> **Important:** Pull-up resistors connect between the signal line and 3.3V. They are NOT wired in-line between the ESP32 and sensor.

---

## Problems Encountered and Fixed

### 1. OneDrive permission error during `idf.py set-target fullclean`
**Symptom:** `PermissionError [WinError 5] Access is denied` when ESP-IDF tried to delete build artefacts.  
**Cause:** OneDrive was locking files in the project folder on the Desktop.  
**Fix:** Moved the project to `C:\esp-projects\vl53l8cx_esp32\` (outside OneDrive sync).

---

### 2. Wrong target — `esp32` instead of `esp32s3`
**Symptom:** Build configured for the wrong chip family.  
**Fix:** `idf.py set-target esp32s3` — this triggers a full clean and reconfigures CMake for the S3.

---

### 3. `VL53L8CX_Platform` field names were wrong
**Symptom:** Compiler errors: `has no member named 'i2c_port'`, `'scl_pin'`, `'sda_pin'`, `'pwren_pin'`.  
**Cause:** The library's actual `platform.h` uses different field names than ST's generic documentation suggests.  
**Fix:** Read the downloaded `platform.h` directly. Correct fields are:
- `sensor.platform.handle` — `i2c_master_dev_handle_t`
- `sensor.platform.bus_config` — `i2c_master_bus_config_t`
- `sensor.platform.reset_gpio` — `gpio_num_t`

---

### 4. Silent hang after "interface starting"
**Symptom:** ESP32 logged `VL53L8CX interface starting`, then nothing — no error, no sensor detected message.  
**Cause:** The library's I2C read/write timeout defaults to `-1` (infinite wait). The sensor wasn't responding, so the task blocked forever.  
**Fix:** Added to `sdkconfig.defaults`:
```
CONFIG_VL53L8CX_I2C_TIMEOUT=y
CONFIG_VL53L8CX_I2C_TIMEOUT_VALUE=1000
```

---

### 5. 5V pin measuring only 2.1V
**Symptom:** Multimeter on the ESP32's 5V pin read 2.1V instead of 5V.  
**Cause:** The AliExpress expansion adapter board does not route the USB 5V rail to the 5V header pin. Additionally, the native USB port (right side) does not power the board the same way the UART port does.  
**Fix:** Powered the sensor from the 3.3V pin instead. The SATEL-VL53L8CX's onboard LDO accepts 2.8–5.5V input, so 3.3V works correctly.

---

### 6. Sensor still not detected — root wiring issue
**Symptom:** Even with 3.3V power and correct pull-ups, sensor not detected.  
**Cause:** SDA and SCL jumper wires were plugged into the wrong rows on the breadboard — into the row for `RXN1` instead of `GPIO1` and `GPIO2`.  
**Fix:** Moved the wires to the correct GPIO rows. On the DevKitC-1, GPIO1 is the 4th pin from the top on the right side, GPIO2 is the 5th pin from the top on the right side.

---

### 7. `idf.py monitor` blocks the serial port
**Symptom:** Python visualiser throws `SerialException: could not open port COM12`.  
**Cause:** ESP-IDF monitor holds the COM port open exclusively.  
**Fix:** Close monitor with `Ctrl + ]` before running the Python visualiser. Only one program can hold the port at a time.

---

## Important Lessons Learned

- **Read the actual downloaded source.** The library's `platform.h` and example `main.c` are in `C:\esp-projects\vl53l8cx_esp32\managed_components\rjrp44__vl53l8cx\` after first build. Always check there rather than relying on generic ST documentation.
- **I2C timeouts are disabled by default.** Without `CONFIG_VL53L8CX_I2C_TIMEOUT`, a missing or mis-wired sensor causes a silent hang, not an error.
- **Pull-up resistors are parallel, not series.** They connect from the signal node up to Vcc. A correct pull-up topology lets either device pull the line low while the resistor pulls it back high when released.
- **Use the UART USB port (left) for flashing.** The native USB port (right) is for USB-OTG. The 5V pin only outputs correctly from the UART port.
- **The DATA: prefix pattern is clean.** By prefixing streaming data with `DATA:`, the Python parser can ignore all `I (nnn) TAG: ...` ESP_LOG lines without needing to suppress them in firmware.

---

## Visualiser Issues Encountered and Fixed (v2)

### Issue 1: Points flickering and occasionally disappearing
**Root cause:** `ax.clear()` was called every frame. This destroys and recreates every matplotlib artist — axes, labels, tick marks, pane backgrounds, grid lines — 10 times per second. When a single redraw took longer than 100 ms (the sensor's frame interval), the serial buffer backed up with unread `DATA:` lines. The next `readline()` then returned a partial or empty line, `parse_data_line` returned `None`, the render was skipped entirely, and the points appeared to vanish.

**Fix:** Create the scatter object once before the loop. Update its data in-place each frame:
```python
sc._offsets3d = (xs, ys, zs)   # move points
sc.set_array(smoothed)          # recolour by distance
fig.canvas.draw_idle()          # redraw only what changed
```
All axis styling (limits, labels, pane colours, view angle) is set once before the loop and never touched again.

---

### Issue 2: Serial buffer backlog — always rendering stale data
**Root cause:** If matplotlib rendering takes >100 ms, unread frames pile up in the OS serial buffer. The visualiser was always rendering the *oldest* buffered frame, not the current one — meaning the display could be several frames behind reality.

**Fix:** After receiving one valid frame, drain `ser.in_waiting` bytes immediately to discard stale frames and keep only the newest:
```python
while ser.in_waiting:
    newer = ser.readline().decode("utf-8", errors="ignore").strip()
    parsed = parse_data_line(newer)
    if parsed is not None:
        distances = parsed   # always keep the most recent
```

---

### Issue 3: Raw sensor noise causing jumpy points
**Cause:** The VL53L8CX returns readings that vary ±10–30 mm frame-to-frame on a static scene. Rendering raw values directly made individual points visibly jump each frame.

**Fix:** Exponential moving average (EMA) per zone:
```python
EMA_ALPHA = 0.3
smoothed = EMA_ALPHA * distances + (1.0 - EMA_ALPHA) * smoothed
```
Weight 0.3 on the new frame, 0.7 on the running average. Eliminates noise flicker while still tracking real movement in roughly 3–4 frames (~300–400 ms lag).

---

## Visualiser v3 — PyQtGraph rewrite

v2 fixed the flicker and stale-data problems but two complaints remained:

1. **Mouse-drag rotation was sluggish.** `mplot3d` is software-rendered, and every drag event had to wait its turn behind the data loop's `draw_idle()`. The 3D scatter was effectively starving the GUI thread.
2. **Frame-render lag was still ~one frame stale.** v2's drain ran *after* `readline()`, so when a redraw exceeded the 100 ms frame interval the next iteration's `readline()` pulled the OLDEST queued line, then drained anything queued after that. Net result: the visualiser was always rendering one frame behind the sensor.

### Fixes

| Fix | Evidence |
|---|---|
| Renderer swapped from `mplot3d` → PyQtGraph (`GLViewWidget` + `GLScatterPlotItem`) | Qt + OpenGL is GPU-accelerated; rotation is no longer coupled to data redraws. |
| Serial reader moved to a `QThread`; new frames delivered via Qt signal | `readline()` no longer blocks the GUI event loop. Mouse events get serviced even mid-frame. |
| Drain order flipped: drain *first*, then process the newest valid `DATA:` line | Provable from the code — the previous `readline → drain` order always pulled the oldest queued frame. |
| `EMA_ALPHA` 0.3 → 0.6 | EMA settles 95% in `−ln(0.05) / −ln(1−α)` samples. 0.3 = ~9 frames (~900 ms at 10 Hz), 0.6 = ~3 frames (~300 ms). |
| Phantom back-wall hidden (firmware sentinel == `MAX_DISTANCE_MM` masked to NaN, drawn with α=0) | Firmware [`main.c`](main/main.c) clamps invalid zones to 4000 mm so the host never sees gaps; the visualiser must filter them or they look like a real wall. |

### Spec note (and a correction)

VL53L8CX FoV per the ST datasheet is **65° diagonal, 45° horizontal/vertical**. Earlier triage suggested the 45°/8 = 5.625° per-zone constant might be wrong; verifying against ST's product page and the data brief confirms the constant is correct. Comment added in source so this isn't "re-fixed" later.

---

## Visualiser v4 — scientific look + sensor model + animated ToF rays

v3 was responsive but visually plainer than the matplotlib version. v4 brings back the scientific look and adds physical context:

- **Side colour bar** (viridis, mm scale) restored as a `pyqtgraph.GraphicsLayoutWidget` next to the GL view, with a labelled right axis.
- **X / Depth / Y axis arrows** in red / green / blue from the origin, with text labels (`GLTextItem`) at the endpoints and tick text every 1000 mm along the depth axis.
- **Sensor body** modelled as a flat dark `GLMeshItem` rectangle at the origin with a bright `GLLinePlotItem` lens ring and a "VL53L8CX" label.
- **45°×45° FoV frustum** (4 corner rays + back square) marking the actual physical cone the sensor sees.
- **Animated ToF beams** — one `GLLinePlotItem` line per zone, origin → endpoint, updated every frame. Each beam is coloured by the same viridis hue as its endpoint and uses an alpha gradient (10% at the lens, 55% at the point) so it reads as light emitted from the sensor. Invalid zones drop to α=0. The beams visibly pulse with the live data, which is exactly what a multizone ToF sensor is doing physically.
- **Status bar** showing live frame count, valid-zone count out of 64, and mean valid distance.

### Demo clips

- `visualizer/progress_demo.mp4` — 10-second before/after clip cut from screen captures: 3 seconds of the v1/v2 matplotlib version, 7 seconds of the v3/v4 PyQtGraph version. Shows the rotation responsiveness gain and the new sensor + ray visualisation.
- `visualizer/progress_demo_v4.mp4` — 5-second focused capture of the v4 view in motion (sensor body + frustum + animated ToF rays at 15 Hz post-firmware bump).
- `visualizer/progress_demo_v6.mp4` — 10-second capture of the final v6 view: world-frame point memory wrapping around the sensor as it pans, fading trajectory trail, and the live ToF rays at 15 Hz.

### Things that did NOT need fixing (despite earlier suspicion)

- Direction-vector normalisation: max magnitude error at the corner zones is ~0.8% — negligible.
- FoV constant: confirmed correct (45° per axis).

---

## Firmware bump — 15 Hz ranging

Bumped `RANGING_FREQ_HZ` in `main/main.c` from 10 to 15 — the datasheet maximum for 8×8 mode. Frame interval drops from 100 ms to ~67 ms, giving the visualiser 50 % more samples per second and shrinking the EMA's wall-clock settle time accordingly. Confirmed by sniffing `DATA:` lines on COM12 — measured 15.2 Hz. Power and serial bandwidth headroom are both still comfortable at 115 200 baud.

---

## Visualiser v5 — experimental 6-DOF relative pose estimation

Pure-experiment addition. With only the VL53L8CX (no IMU yet), the only way to estimate sensor motion is to use the depth data itself. v5 implements per-frame rigid registration on the 64-point cloud, integrates the result, and draws the trajectory.

### Algorithm — Kabsch / Procrustes / SVD

For each new frame, given paired point sets P (frame k−1) and Q (frame k):

1. Subtract centroids: `Pc = P − mean(P)`, `Qc = Q − mean(Q)`.
2. Cross-covariance: `H = Pc.T @ Qc`.
3. SVD: `U, S, Vt = svd(H)`.
4. Reflection guard: `d = sign(det(Vt.T @ U.T))`, `R = Vt.T @ diag(1, 1, d) @ U.T`.
5. Translation: `t = mean(Q) − R @ mean(P)`.

This yields the rotation + translation that best aligns Q to P. The sensor's per-frame motion δT is the inverse: `δR = R.T`, `δt = −R.T @ t`. World-frame cumulative pose composes as `T_world(k) = T_world(k-1) · δT`.

### Same-zone correspondence + small-motion assumption

We pair zone *i* in frame k−1 with zone *i* in frame k. That's the correct pairing **only** under the small-motion assumption — between frames at 15 Hz (~67 ms) each zone still observes approximately the same world point. Fast motion breaks this; large fitted Δt or ΔR almost always means broken correspondence rather than real motion, so the estimator gates on:

- `max_translation_mm = 300 mm/frame`
- `max_rotation_deg = 20°/frame`

Gated frames break the chain (cumulative pose holds steady) instead of corrupting it.

### Visualisation

A `GLLinePlotItem` traces the cumulative path of the sensor's origin in world frame, with a small head sphere marking the current position. Every frame the trail is transformed into the *current* sensor frame so it appears to flow behind the sensor as it moves through space. Status bar reads out cumulative translation (mm), cumulative rotation (deg), and the per-frame rejection count. **R** resets the pose and clears the trail.

### Honest limits

- 64 points is sparse for ICP-style work; expect noticeable drift over time.
- No yaw reference: rotating the sensor around gravity is unobservable from depth alone (the floor's depth map doesn't change). The estimator will report some drift here that is mostly noise.
- 0/64 valid zones (e.g. covered sensor, loose connection) → estimator pauses cleanly.
- This is not a substitute for the planned IMU integration in Phase 3 — it's a proof of concept that the depth data alone carries motion information.

---

## Visualiser v6 — world-frame point memory + fading trail

Two visual issues with v5:

- The live point cloud was always pinned in front of the sensor in a 45° cone. Looked the same regardless of how the sensor moved — past observations weren't preserved.
- The trajectory trail kept growing forever, eventually becoming a thick yellow tangle that obscured the scene.

### Fixes

**Accumulated world-frame cloud.** Each frame, the valid sensor-frame points are transformed into world frame using the v5 pose estimate (`world_p = R_world · sensor_p + t_world`) and pushed into a rolling deque (~6 s × 15 Hz = 90 frames). For rendering, every entry is transformed back into the *current* sensor frame each tick and given an alpha proportional to its age (newest = ~0.35, oldest = ~0). The visual effect: as the sensor pans, old observations stay where they were physically measured and slide off to the side instead of staying glued to the front cone — the cone effectively wraps around the sensor.

**Fading trajectory trail.** The trail is now capped at ~5 s of history (75 points at 15 Hz). Each vertex carries its own alpha — `linspace(0.05, 0.95, n)` from tail to head — so the line fades from invisible at the back to bright yellow at the sensor's current position. No more growing tangle.

**R key clears both** the trail and the accumulated cloud.

### Caveats

The accumulated cloud's quality is bounded by the pose estimator. If the pose drifts (which it will, especially in yaw), past observations smear by the drift amount when the sensor returns near a previously-scanned region. The 6-second cap keeps drift damage local — anything older has faded out by then. With an IMU added later, drift drops sharply and the same code becomes a useful sparse 3D map.

---

## Status — paused on hardware

**v6 is the final visualiser iteration on the current hardware.** With only the VL53L8CX (no IMU, no second sensor, no compass), every avenue for improvement has been pushed as far as the depth data alone allows:

- 15 Hz is the datasheet maximum for 8×8 mode.
- 64 zones at ±10–30 mm noise is the sensor's resolution and accuracy ceiling.
- Yaw is unobservable from depth alone, so the v5 pose estimator drifts on rotation around gravity. No firmware or visualiser change can fix this — it is a sensing-physics limit, not a software one.
- The accumulated world-frame cloud in v6 is bounded by that same drift.

Further visualiser work is **paused until the IMU arrives.** Once the IMU is wired onto the same I2C bus, the next iteration will fuse accelerometer + gyro into the pose estimator (gravity gives absolute pitch + roll, gyro integration plus accel-gravity correction tightens yaw), which unlocks:

- A genuine 3D scan that holds shape over time without drift.
- Heading-stable trajectory, sufficient for helmet-tracking experiments.
- The interpolated topographic surface and proximity overlay ideas below — both currently bottlenecked by drift, not by rendering.

## Planned Next Steps (queued for IMU integration)

1. **Sensor fusion** — accelerometer/gyro + ToF, replacing the depth-only Kabsch estimator with a complementary or Madgwick filter.

2. **Interpolated topographic surface** — bicubic interpolation across the 8×8 grid, rendered as a smooth 3D mesh with viridis colouring and contour lines every 100 mm.

3. **Silhouette / proximity detection overlay** — highlight zones below a configurable threshold distance to indicate objects or obstacles.

4. **Integration into assistive helmet** — combine with additional sensors (wider-angle ToF or ultrasonic) for fuller spatial awareness.

---

## Commit History

| Commit | Description |
|--------|-------------|
| `dd5b9ab` | Initial working interface for VL53L8CX on ESP32-S3 |
| `fb2a326` | Add hardware photos and update README with images |
| `d19ec5a` | Add streaming data output and 3D point cloud visualiser |
| `6f3ee04` | Add PROGRESS.md documenting project history and lessons learned |
| `598f134` | Fix visualiser flicker, buffer backlog, and point noise (v2) |
| `041fb81` | Add point cloud screenshot and rewrite visualizer README |
| `1190a8f` | Document v2 visualiser improvements in PROGRESS.md |
| `cf574b6` | Visualiser v3: rewrite on PyQtGraph + threaded serial reader |
| `62f33f0` | Visualiser v4: scientific axes + sensor model + animated ToF rays |
| `20c5d68` | Document v3 + v4 visualiser iterations and add progress demo clip |
| `568aa5c` | Bump VL53L8CX ranging frequency 10 → 15 Hz (firmware) |
| `4520f99` | Visualiser v5: experimental 6-DOF relative pose estimation (Kabsch) |
| `5462d60` | Document v5 + 15 Hz bump and add v4 motion demo clip |
| *(next)*  | Visualiser v6: world-frame point memory + fading trail |
