# BNO085 IMU bring-up (Phase 3 head-orientation)

Verified working **2026-06-03** on a bench ESP32‑C6 + GY‑BNO08X board, streaming drift‑free
absolute orientation. This is the foundation for **Phase 3 sensor fusion** — fusing the
VL53L8CX distance grid with head orientation so obstacle directions can be mapped into a
stable world/body frame instead of "wherever the head happens to be pointing."

> Bring-up was done on a **C6** (separate project: `C:\esp-projects\mpu6050-c6\`). The
> helmet runs on the **ESP32‑S3** — the config below is correct, but **GPIO pins must be
> reassigned** for the S3 (see "Integration plan").

## Sensor & driver
- **Board:** purple **GY‑BNO08X** (pins: VCC GND SCL SDA ADO CS INT RST PS1 PS0).
- **Transport:** **SPI** (the BNO08x's I²C is unreliable on ESP32 due to a known I²C silicon
  bug — the driver author dropped I²C support; SPI also needs no pull-ups).
- **Driver:** `myles-parfeniuk/esp32_BNO08x` (C++, wraps CEVA's official sh2 HAL). Add via the
  component manager (`idf_component.yml`) or clone into `components/`. It is **C++**, so the
  file that uses it must be `.cpp` with `extern "C" void app_main()`.
- Use report **`imu.rpt.rv`** (full rotation vector — includes the magnetometer → absolute,
  drift-free heading). `get_euler()` → x=roll y=pitch z=yaw (deg); `get_quat()` → real,i,j,k.

## TWO non-obvious gotchas (both required — each one alone gives `sh2_getProdIds() failed`)
1. **PS1 AND PS0 BOTH HIGH (3V3) selects SPI.** The common "PS1=1/PS0=0" is WRONG — that's
   UART‑RVC. Protocol table: `00`=I²C, `01`=UART, `10`=UART‑RVC, `11`=SPI.
2. **MOSI/MISO are SWAPPED vs the silk labels** on GY‑BNO08X: board **ADO = MOSI**
   (host→sensor), board **SDA = MISO** (sensor→host). Wiring them "by the label" fails.

## Verified wiring (C6 pin numbers — reassign for S3)
| BNO085 pin | SPI role | C6 GPIO (bench) |
|---|---|---|
| SCL | SCLK | 4 |
| ADO | **MOSI** | 6 |
| SDA | **MISO** | 5 |
| CS  | chip select | 7 |
| INT | data-ready (required) | 2 |
| RST | reset (required) | 3 |
| PS1 | mode select | 3V3 (HIGH) |
| PS0 | mode select | 3V3 (HIGH) |
| VCC / GND | power | 3V3 / GND |

Config struct (`bno08x_config_t`): `spi_peripheral = SPI2_HOST`, `sclk_speed = 2 MHz`,
the six `io_*` pins above. INT and RST are **not optional** in SPI mode.

## Integration plan (ESP32‑S3 helmet)
- **Pins:** pick six free S3 GPIOs. **Avoid** the haptic pins (GPIO 7/15/16) and the
  VL53L8CX I²C pins. The S3 has SPI2 + SPI3; the VL53L8CX is on I²C, so an SPI host is free.
- **Task:** run the BNO read in its own FreeRTOS task (the library is already multi-tasked /
  INT-driven), publish the latest quaternion to a shared struct guarded like the existing
  ranging data.
- **Fusion (Phase 3):** rotate the per-zone ToF directions by the head quaternion to get a
  body/world-stable obstacle map; feed that into the directional haptic mapping.
- **Calibration:** the magnetometer starts uncalibrated → yaw drifts until a **figure‑8**
  motion calibrates it. Watch the report's `accuracy` field.

## Tooling
- **3D visualizer:** `visualizer/imu_orientation.html` — open in **Chrome/Edge**, click
  Connect, pick the C6/S3 port. Reads the `Q,w,x,y,z` serial stream via the Web Serial API
  and renders live rotation. No Python/server needed.
- Reference firmware that produces the `Q,w,x,y,z` stream: `mpu6050-c6/main/main.cpp`.

## ESP32‑C6 flashing notes (if bringing up on a spare C6)
- A firmware that fails/hangs in init wedges the native USB‑Serial‑JTAG (esptool "Write
  timeout") → only a full **unplug/replug power‑cycle** clears it. Blue LED = download mode.
- C6 logs go to **UART pins by default**; set `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` to get
  output over USB. (The S3 with a USB‑UART bridge doesn't have this issue.)
