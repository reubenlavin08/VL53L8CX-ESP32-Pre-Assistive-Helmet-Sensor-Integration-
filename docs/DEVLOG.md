# Assistive Helmet — Engineering Devlog

A running log of the build: problems, root causes, fixes, and lessons. Newest first.

---

## 2026-06-06 — Dual-sensor integration, debug switch, visualizer overhaul, IMU bring-up

### System state at end of session
- **Two VL53L8CX ToF sensors** live on separate I²C buses:
  - Bottom (`I2C_NUM_1`, SDA=GPIO1, SCL=GPIO2), mounted ~30° **down** → ground/low obstacles.
  - Top (`I2C_NUM_0`, SDA=GPIO41, SCL=GPIO42), mounted ~5° **up** → head/overhead.
  - No address collision (both at 0x29 but on separate buses). Shared directional haptics + buzzer.
- **BNO085 IMU** wired onto the bottom I²C bus, **detected at 0x4B** (driver not yet written).
- Streams `DATA:` (bottom), `DATAT:` (top), `SIGMA:`, `STATUS:` over TCP:3333 + UART; `/api/status` JSON + phone heatmap viewer at `http://<ip>`.
- Desktop 3-D visualizer (`visualizer/visualizer_dual.py`) overhauled (see below).

### Haptic-pause debug switch (GPIO17)
- **Goal:** a physical switch to silence motors + buzzer while debugging the sensor.
- **Design:** SPDT, COM→GPIO17, one outer→GND, third pin empty; firmware uses the ESP's **internal pull-up**, so `HIGH=on`, `LOW(GND)=paused`. Switch carries **no power rail** — only ground — by design.
- **Problem:** with the switch wired COM→GPIO17, one outer→GND, one outer→**3.3V**, flipping it intermittently **bricked the ESP until a full power-cycle.**
- **Root cause:** putting both 3.3V *and* GND on the switch means a make-before-break (or bouncing) contact momentarily **shorts 3.3V→GND through the switch → brownout → USB-Serial-JTAG wedges → only a power-cycle recovers.**
- **Fix:** remove the 3.3V wire entirely. With the internal pull-up supplying "high," the switch can only ever connect GPIO17 to GND or let it float high — nothing to short. **Lesson:** a logic-level switch should never bridge a power rail; let the MCU's pull-up provide the high side.

### Firmware gotcha: `HAPTIC_TEST` left enabled
- **Problem:** after flashing, the device ran a motor-pulse test and **skipped sensor ranging entirely** ("sensor ranging SKIPPED").
- **Root cause:** `#define HAPTIC_TEST 1` had been left on from a 2026-06-05 motor-ID session ("set back to 0 after" — never done).
- **Fix:** set `HAPTIC_TEST 0` / `HAPTIC_ID_MODE 0`. **Lesson:** temporary build flags need a hard "revert" checkpoint; a stray `1` cost a confusing debugging detour.

### Visualizer overhaul (desktop 3-D)
- **Launch gotcha:** the PyQtGraph window *did* launch from the agent's tooling but opened **behind** other windows (and in a non-foreground session), so it looked like "it never launched." **Fix:** verify via Win32 `EnumWindows` (the window title also reports stream state) and force-foreground it; don't assume a launch failure. Burned ~an hour misdiagnosing this as session-0 GUI isolation.
- **Lag at >500 frames:** per-frame Qt signal accumulation. **Fix:** reader thread writes a shared "latest frame" dict; the GUI timer pulls only the newest → fixed cost, no backlog.
- **"Noisy bumps" / hard to read:** raw per-zone distance jumps were amplified by a connect-the-dots surface mesh. **Fix:** the firmware already streams `SIGMA:`/`STATUS:` per zone — now the viz **drops low-confidence zones** (STATUS ∉ {5,6,9}) and **high-noise zones** (SIGMA > threshold) *before* rendering, plus stronger temporal EMA.
- **Readability research:** ST/RealSense/LiDAR practice all flatten to fixed 2-D (heatmap / range-image / top-down) for *live* reading; a free-floating 3-D point cloud is good for offline scanning, poor for at-a-glance distance. Kept the 3-D (user preference) but added depth aids.
- **Final 3-D form (user-directed):** clean points at measured positions + **trace rays** from the helmet to each point (length = distance, no inter-point net); faint FoV frustums; head model + floor plane; hot→cool distance colormap; **preset-view buttons** (Front / 3⁄4 / Top / Side); FPS + nearest-L/R readout. Note: forward axis = GL +Y, so "front" camera sits on +Y looking back.
- **TCP-client clog:** repeated viz relaunches + device resets left stale TCP clients on the ESP (MAX 4) → new viz got ~1 FPS. **Fix:** device reset clears the client table; run a single viz instance.

### IMU bring-up (BNO085 over I²C)
- **Protocol selection:** the BNO085 picks I²C/UART/SPI from strap pins **PS1/PS0, read only at power-on.** I²C = **PS1=0, PS0=0** (both GND). (Prior SPI work used PS1=1/PS0=1.)
- **Problem:** not detected on the bus despite "correct" wiring.
- **Root causes (two):**
  1. Wired to GPIO1/2 (**bottom** bus) while the probe only checked GPIO41/42 (**top** bus) — added a probe to both buses.
  2. PS pins left from the earlier SPI config → chip booted in the wrong protocol. And an **ESP soft-reset does not power-cycle the IMU**, so the wrong mode persisted until a true power-cycle re-latched the PS pins.
- **Fix:** PS1=PS0=GND + full power-cycle → **BNO085 ACKs at 0x4B.**
- **Board-mapping lesson:** the cheap GY-BNO08X clone has an **unreliable silkscreen** — SDA/SCL had to be swapped from the labels, and ADO reads 0x4B despite being grounded (onboard pull-up or inverted mapping). **The I²C probe is ground-truth; trust the address that ACKs (0x4B), not the silkscreen.**
- **Driver status:** SH-2/SHTP is required (no simple register read on BNO085). CEVA `sh2` C sources copied to `components/bno08x/sh2/`. The available `esp32_BNO08x` library is **SPI-only**, so the I²C SHTP transport (HAL: open/read/write/getTimeUs, with SHTP header-peek + chunked cargo reads) must be written from scratch. **Next session.**

### Backlog logged
- **ToF↔ToF mutual interference** (two sensors' 940 nm emissions cross-talking) — investigate right after the IMU works. See `photos/test_rig/future_test_ideas.md`.
