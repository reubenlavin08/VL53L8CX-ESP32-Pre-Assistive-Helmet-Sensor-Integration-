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

### Phase 2 — Live 3D Point Cloud Visualiser (complete)

A Python script (`visualizer/visualizer.py`) that:
- Opens the serial port and reads `DATA:` lines in real time
- Precomputes a unit direction vector for each of the 64 zones using the sensor's 45° field of view
- Multiplies each zone's measured distance by its direction vector to produce a true 3D Cartesian point
- Renders a live scatter plot (matplotlib, dark theme, viridis colormap, colourbar)
- Updates at ~10 Hz, matching the sensor's ranging frequency

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

## Planned Next Steps

1. **Interpolated topographic surface** — bicubic interpolation across the 8×8 grid, rendered as a smooth 3D mesh with viridis colouring and contour lines every 100 mm.

2. **Silhouette / proximity detection overlay** — highlight zones below a configurable threshold distance to indicate objects or obstacles.

3. **Integration into assistive helmet** — combine with additional sensors (IMU, wider-angle ToF or ultrasonic) for fuller spatial awareness.

---

## Commit History

| Commit | Description |
|--------|-------------|
| `0954ae0` | Initial working interface for VL53L8CX on ESP32-S3 |
| `7d34ae4` | Add hardware photos and update README with images |
| `e349eb8` | Add streaming data output and 3D point cloud visualiser |
| `ee2c36d` | Add PROGRESS.md documenting project history and lessons learned |
| *(next)* | Fix visualiser flicker, buffer backlog, and point noise (v2) |
