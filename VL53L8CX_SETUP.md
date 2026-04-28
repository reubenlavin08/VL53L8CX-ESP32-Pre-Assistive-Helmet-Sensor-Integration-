# VL53L8CX × ESP32 — Setup Summary

## Completed Tasks

- [x] Located the RJRP44 VL53L8CX ESP-IDF library (v4.0.0) on the ESP Component Registry
- [x] Created ESP-IDF project structure (`CMakeLists.txt`, `sdkconfig.defaults`)
- [x] Wrote `idf_component.yml` to auto-fetch the library on build
- [x] Wrote `main.c` — full sensor interface with I2C init, ULD firmware upload, 8×8 ranging loop, and ASCII distance grid output
- [x] Pre-configured stack size fix in `sdkconfig.defaults` (8192 bytes)

---

## Project File Structure

```
vl53l8cx_esp32/
├── CMakeLists.txt
├── sdkconfig.defaults
└── main/
    ├── CMakeLists.txt
    ├── idf_component.yml
    └── main.c
```

---

## Wiring Chart — SATEL-VL53L8CX Breakout → ESP32

| SATEL Pin   | ESP32 Pin | Notes                            |
|-------------|-----------|----------------------------------|
| PWREN       | GPIO 5    | + 10 kΩ pullup resistor to 3.3V  |
| MCLK_SCL    | GPIO 2    | + 2.2 kΩ pullup resistor to 3.3V |
| MOSI_SDA    | GPIO 1    | + 2.2 kΩ pullup resistor to 3.3V |
| NCS         | 3.3V      | Tie directly high (I2C mode)     |
| SPI_I2C_N   | GND       | Tie directly to GND (I2C select) |
| VDD         | 5V        | Power supply                     |
| GND         | GND       | Common ground                    |

> **Note:** The external pullup resistors are required — do not rely on ESP32 internal pullups for this sensor.

---

## Computer Setup Steps

### Step 1 — Install ESP-IDF (v5.0 or later)

1. Download the ESP-IDF installer for Windows from:  
   https://dl.espressif.com/dl/esp-idf/
2. Run the installer and follow the prompts (installs Python, CMake, Ninja, and the toolchain automatically)
3. After install, open the **ESP-IDF Command Prompt** (added to your Start Menu) — use this terminal for all commands below

Verify your install:
```bash
idf.py --version
```
Expected output: `ESP-IDF v5.x.x`

---

### Step 2 — Install the USB-to-Serial Driver

Most ESP32 dev boards use a CP2102 or CH340 USB chip. Install the correct driver:

- **CP2102** (common on Espressif devkits): https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
- **CH340** (common on cheap clones): https://www.wch-ic.com/downloads/CH341SER_EXE.html

After installing, plug in your ESP32. Open **Device Manager** (`Win + X → Device Manager`) and confirm it shows up under **Ports (COM & LPT)** — note the COM number (e.g., `COM5`).

---

### Step 3 — Copy the Project to Your Machine

Copy the `vl53l8cx_esp32/` folder anywhere on your computer, for example:
```
C:\Projects\vl53l8cx_esp32\
```

---

### Step 4 — Open the ESP-IDF Command Prompt and Navigate to the Project

```bash
cd C:\Projects\vl53l8cx_esp32
```

---

### Step 5 — Set Your ESP32 Target Chip

Run the command matching your specific board:

```bash
# Standard ESP32
idf.py set-target esp32

# ESP32-S3
idf.py set-target esp32s3

# ESP32-C3
idf.py set-target esp32c3
```

---

### Step 6 — Pull the VL53L8CX Library

The `idf_component.yml` file handles this automatically on first build, but you can also run it manually:

```bash
idf.py add-dependency "rjrp44/vl53l8cx^4.0.0"
```

---

### Step 7 — Adjust GPIO Pins (if needed)

Open `main/main.c` and update these three lines at the top to match your actual wiring:

```c
#define GPIO_SDA    GPIO_NUM_1   // MOSI_SDA pin
#define GPIO_SCL    GPIO_NUM_2   // MCLK_SCL pin
#define GPIO_PWREN  GPIO_NUM_5   // PWREN pin
```

---

### Step 8 — Build the Project

```bash
idf.py build
```

The first build downloads the library and uploads ST's ULD firmware blob — this takes 1–3 minutes. Subsequent builds are much faster.

---

### Step 9 — Flash and Monitor

Replace `COM5` with your actual COM port number from Step 2:

```bash
idf.py -p COM5 flash monitor
```

The serial monitor opens automatically after flashing. You should see:

```
I (xxx) VL53L8CX: Sensor detected
I (xxx) VL53L8CX: Uploading ULD firmware (takes ~1 s)...
I (xxx) VL53L8CX: Sensor ready: 8x8 resolution, 10 Hz
I (xxx) VL53L8CX: Ranging started
I (xxx) VL53L8CX: Frame #1

--- Distance grid (mm) ---
  820  815  801  790  785  780  775  770
  ...
```

Press **Ctrl + ]** to exit the monitor.

---

## Sensor Configuration Quick Reference

These defines in `main/main.c` control sensor behaviour:

| Define               | Default                              | Options                                      |
|----------------------|--------------------------------------|----------------------------------------------|
| `SENSOR_RESOLUTION`  | `VL53L8CX_RESOLUTION_8X8`           | `VL53L8CX_RESOLUTION_4X4`                   |
| `RANGING_FREQ_HZ`    | `10`                                 | 1–15 Hz (8×8) or 1–60 Hz (4×4)              |
| `RANGING_MODE`       | `VL53L8CX_RANGING_MODE_CONTINUOUS`  | `VL53L8CX_RANGING_MODE_AUTONOMOUS`           |
| `PRINT_GRID`         | `1`                                  | `0` to disable the ASCII grid                |
| `PRINT_CLOSEST_ONLY` | `0`                                  | `1` to only log the single nearest zone      |

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Sensor not detected` | Wiring issue or no power | Check PWREN, I2C pullups, NCS tied to 3.3V, SPI_I2C_N to GND |
| Stack overflow crash | Main stack too small | Already fixed in `sdkconfig.defaults` — rebuild after cleaning |
| `idf.py` not found | ESP-IDF not in PATH | Use the ESP-IDF Command Prompt, not a regular terminal |
| No COM port in Device Manager | Driver missing | Install CP2102 or CH340 driver (Step 2) |
| Build errors on library | IDF version too old | Must use ESP-IDF v5.0 or later |

---

## References

- [RJRP44/VL53L8CX-Library on GitHub](https://github.com/RJRP44/VL53L8CX-Library)
- [rjrp44/vl53l8cx on ESP Component Registry](https://components.espressif.com/components/rjrp44/vl53l8cx)
- [ST VL53L8CX Product Page](https://www.st.com/en/imaging-and-photonics-solutions/vl53l8cx.html)
- [ESP-IDF Programming Guide](https://docs.espressif.com/projects/esp-idf/en/latest/)
