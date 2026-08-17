# WIRING — verified 2026-08-11/12

Written after a full teardown/remount onto the bike helmet + 3D-printed pod, when
nobody remembered how anything was wired.

**Everything marked ✅ VERIFIED was proven on hardware this session** — both ToF
sensors were brought up from scratch on new pins and streamed live distances.

> **Trust order:** this file > the ELF/source > other docs. `docs/imu-bno085-bringup.md`
> describes an **ESP32-C6 SPI bench rig** and is NOT the current wiring — see §2.

---

# 1. ToF sensors — ✅ VERIFIED WORKING

Two SATEL-VL53L8CX, one per I²C bus. Both answered at **0x29**, uploaded ULD
firmware, and ranged.

```
[A] SDA=6  SCL=7  : 0x29    *** RANGING OK ***  PWREN=4
[B] SDA=15 SCL=16 : 0x29    *** RANGING OK ***  PWREN=5
```

## Current pin assignment (after the remount)

| | Sensor A | Sensor B |
|---|---|---|
| `MOSI_SDA` | **GPIO6** | **GPIO15** |
| `MCLK_SCL` | **GPIO7** | **GPIO16** |
| `PWREN` | **GPIO4** | **GPIO5** |
| Bus | `I2C_NUM_0` | `I2C_NUM_1` |

**SDA/SCL are NOT swapped from the silkscreen on these boards.** Tested both
orientations; the by-the-label wiring is correct.

## Every pin on the SATEL board

| Pin | Connect to | |
|---|---|---|
| **VDD** | **5V** | not 3.3 V |
| **GND** | GND | |
| **MOSI_SDA** | its SDA GPIO | + 2 kΩ → 3.3 V |
| **MCLK_SCL** | its SCL GPIO | + 2 kΩ → 3.3 V |
| **PWREN** | its PWREN GPIO | + 10 kΩ → 3.3 V |
| **NCS** | 3.3 V | tie high = I²C mode |
| **SPI_I2C_N** | GND | tie low = I²C mode |
| `MISO` | — | nothing (SPI only) |
| `LPn` | — | nothing |
| `GPIO1`, `GPIO2` *(sensor's own)* | — | nothing |
| `3V3`, `1V8 / CORE_1V8`, `IOVDD` | — | nothing (regulator outputs) |

**7 pins wired, 8 empty, per sensor.**

⚠️ **The SATEL board has its own pins named GPIO1 and GPIO2 — they are not the
ESP's.** Matching them by name gives a sensor that powers up and never answers.

## Why two buses

Both sensors are fixed at **0x29** and changing it needs `LPn` juggling. Separate
buses avoids the collision entirely.

---

# 2. BNO085 IMU — I²C, not SPI

**Settled definitively.** The flashed ELF contains `bno08x_init`, `sh2_open`,
`i2c_master_transmit` ×7, `i2c_master_receive` ×3, and **zero SPI symbols**. A
repo-wide sweep for `driver/spi_master.h`, `spi_bus_initialize`,
`spi_device_transmit`, `SPI2_HOST` matches **nothing**. There is no SPI code in
this project.

Confirmed physically: **PS1 = PS0 = GND**, which is the I²C strapping (`00`).

**SPI was real but older, and on an ESP32-C6 bench rig** — that's what
`docs/imu-bno085-bringup.md` documents. It was rewritten for I²C on the shared
bus when the IMU moved to the S3.

| BNO085 pin | Connect to | |
|---|---|---|
| VCC | 3.3 V | |
| GND | GND | |
| SDA | bottom-bus SDA | shares the bus with a ToF |
| SCL | bottom-bus SCL | |
| ADO | GND | → address **0x4A** |
| **PS1** | **GND** | ✅ verified |
| **PS0** | **GND** | ✅ verified |
| CS | 3.3 V | |
| INT | **nothing** | INT pad unreliable; driver polls (`int_gpio = -1`) |
| RST | **nothing** | |

**Address is 0x4A, not 0x4B.** 0x4B ACKs a write but never decodes SHTP.
`docs/DEVLOG.md:234` still says 0x4B and is **stale**; line 123 corrects it.

**PS1/PS0 latch only at power-on.** A soft reset or reflash won't re-read them —
fully unplug after changing straps.

**No extra pullups when adding the IMU** — it taps the existing bus pair.

⚠️ Unverified: the SDA/SCL swap DEVLOG claims for the GY-BNO08X clone. Not in the
code, so it couldn't be checked. **Try by-the-label first**; only swap if the
probe finds nothing.

---

# 3. Pull-up resistors

**6 total. All in parallel, each bridging its own signal to the same 3.3 V rail.
Nothing is in series along a bus line.**

```
              3.3 V rail
   ┌────┬────┬────┬────┬────┬────┐
 [2k]  [2k]  [2k]  [2k] [10k] [10k]
   │     │     │     │    │     │
  SDA   SCL   SDA   SCL  PWREN PWREN
  └── bus A ──┘└── bus B ┘
```

| Lines | Value |
|---|---|
| All four SDA/SCL | **2 kΩ** |
| Both PWREN | **10 kΩ** |

## The 2 kΩ are built from 1 kΩ pairs in SERIES

Series **adds**: 1k + 1k = 2 kΩ ✅
Parallel **halves**: 1k ∥ 1k = 500 Ω ❌ — 4× too strong, bus won't reach a valid low.

**Check with a meter across a finished pair: ~2 kΩ good, ~500 Ω rewire.**

2 kΩ instead of the nominal 2.2 kΩ is fine — 10% off in the helpful direction,
1.65 mA per line.

## A pullup attaches to the NET, not to a component

The GPIO and the sensor pin are one piece of copper, so the resistor can sit at
either end or in the middle — electrically identical. There is no single
correct-looking physical arrangement.

**One pair per BUS, not per device.** The bus shared with the IMU still gets only
one 2 kΩ pair.

## Colour codes

| Value | 4-band | 5-band |
|---|---|---|
| **1 kΩ** | brown black red gold | brown black black brown brown |
| **2.2 kΩ** | red red red gold | red red black brown brown |
| **10 kΩ** | brown black **orange** gold | brown black black **red** brown |

⚠️ Band 4 red-vs-brown is the classic misread and is the only difference between
1 kΩ and 10 kΩ in 5-band. **Measure, don't read.**

---

# 4. PWREN

**Active-high enable.** `platform.c:74-85` with `CONFIG_VL53L8CX_RESET_PIN_LOW=y`
(`sdkconfig:2174`):

```c
gpio_set_direction(reset_gpio, GPIO_MODE_OUTPUT);
gpio_set_level(reset_gpio, 0);   // 100 ms — held in reset
gpio_set_level(reset_gpio, 1);   // 100 ms — enabled
```

| PWREN | Sensor |
|---|---|
| LOW | held in reset, invisible on the bus |
| HIGH | running |

**Why the 10 kΩ if the ESP drives it:** from power-on until the firmware runs the
GPIO is a floating input and PWREN would be undefined. The pullup holds the
sensor enabled through boot. Once the pin becomes push-pull it overrides 10 kΩ
easily — they never fight.

**Don't tie PWREN straight to 3.3 V** — the ESP must be able to pull it low.

**A sensor with floating or low PWREN looks exactly like a broken SDA line.**
Check it first.

---

# 5. Power rails

| Rail | Feeds |
|---|---|
| **5 V** | both ToF `VDD` |
| **3.3 V** | both ToF `NCS` · BNO085 `VCC` + `CS` · **all 6 pullups** |
| **GND** | both ToF `SPI_I2C_N` · BNO085 `ADO`, `PS1`, `PS0` · switch outer leg · common |

## ⚠️ Every pullup goes to 3.3 V, never 5 V

ESP32-S3 GPIOs are **not 5 V tolerant** (abs max ~3.6 V). A pullup on the 5 V
rail feeds 5 V into the GPIO through 2 kΩ — damages the pin, and it can half-work
first.

## ⚠️ The right-side native USB port does not power 5 V properly

**This cost a full debug cycle on 2026-08-11.** Both sensors were invisible on
both buses — every scan came back empty — purely because they had no power.

**Use the left-side UART USB port**, or supply 5 V another way.

**Symptom to recognise:** *both* buses scanning empty at once. Two independently
wired sensors failing identically points at something **shared** — power, ground,
or the 3.3 V rail — never at the data pins.

---

# 6. Other ESP32-S3 connections

| Pin | Connected to | |
|---|---|---|
| GPIO6 | *(now ToF A SDA)* | **was buzzer** |
| GPIO7 | *(now ToF A SCL)* | **was haptic CENTER / forehead** |
| GPIO15 | *(now ToF B SDA)* | **was haptic RIGHT temple** |
| GPIO16 | *(now ToF B SCL)* | **was haptic LEFT temple** |
| GPIO17 | Pause switch, SPDT common | internal pull-up; HIGH = on, LOW = paused |

Pause switch: COM → GPIO17, **one** outer leg → GND, third leg unconnected.

⚠️ **Unrecorded:** whether the three motors are driven directly or through
transistors, and whether there are flyback diodes. An S3 pin sources ~40 mA; a
coin ERM pulls 60–100 mA at start, so direct drive would be out of spec. **Check
the physical build before reconnecting them.**

---

# 7. ⚠️ FIRMWARE DOES NOT MATCH THIS WIRING YET

`main/main.c` still has the **pre-teardown** pins:

| | Firmware expects | Actually wired |
|---|---|---|
| Sensor A | SDA 1, SCL 2, PWREN 5 | **SDA 6, SCL 7, PWREN 4** |
| Sensor B | SDA 41, SCL 42, PWREN 40 | **SDA 15, SCL 16, PWREN 5** |

**And the ToF sensors now occupy the buzzer + all three haptic pins** (`main.c:57,
80-82`). Both subsystems cannot coexist on this wiring.

**Clean swap available:** GPIO1, 2, 41, 42 are now free — move the buzzer and
three motors there, and update the ToF defines at `main.c:50-56`.

Also stale: the code calls the sensors "top" (~5° up) and "bottom" (~30° down),
the **old stacked** arrangement. The CAD pod is now a **left/right ±22.5° pair**,
so `MOUNT_PITCH_DEG` and the per-column haptic mapping are both wrong for the
current geometry.

---

# 8. Test tool — `tof_pin_test/`

Standalone ESP-IDF project. **Does not touch the helmet firmware.** Reuses the
already-downloaded driver via `EXTRA_COMPONENT_DIRS`, so it builds offline.

- Loops forever, retrying every 3 s — **rewire live and watch it come up**
- Tries **both SDA/SCL orientations** on each bus and reports which won
- Full 0x08–0x77 address scan per bus
- Per-sensor failure — one bad sensor doesn't hide the other
  *(the helmet firmware `vTaskDelete`s the whole ranging task on any failure,
  which is why it can't tell you which sensor is bad)*
- Streams a 4×4 grid; `----` = no valid target

```
cd C:\esp-projects\vl53l8cx_esp32\tof_pin_test
idf.py -p COM9 flash monitor
```

Edit the pin defines at the top of `main/main.c` when the wiring moves.

## ⚠️ Native USB port: stuck in download mode

Software reset via DTR/RTS on the USB-Serial-JTAG port repeatedly landed the chip
in `boot:0x21 (DOWNLOAD)` — "waiting for download", app never runs, port silent.

**Fix: physically unplug and replug the USB cable.** A real power cycle is the
only thing that reliably clears it. Don't hand-roll DTR/RTS toggling on this port;
use `idf.py monitor` or a replug.

---

# 9. Bring-up order

Wire and verify **one device at a time**. A sensor init failure kills the whole
ranging task, so wiring everything at once means a single fault silences all of it.

1. **Sensor A alone** → boot, expect `0x29` + `RANGING OK`
2. **Sensor B** → same
3. **IMU** on the shared bus → power-cycle → `ACK at 0x4A` + `ready on bottom bus`
4. Haptics, buzzer, switch last

---

# 10. Open / unverified

1. **`VDD` vs a separate `5V` pin** on the SATEL carrier — which one is fed
2. **Full carrier board vs the break-off mini-PCB.** `docs/SENSOR-MOUNTING-FACTS.md:29`
   says the 12-pad mini-PCB has **no PWREN** — its pads are `AVDD, IOVDD, GPIO2,
   GPIO1, SCL, I2C_N, SDA, MISO, LPn, CORE_1V8, NCS, DUT_GND`. If the pod holds
   the mini-PCB, §1 is wrong: feed AVDD + IOVDD directly instead of 5 V.
3. **Motor drive circuit** — transistors? flyback diodes?
4. **BNO085 SDA/SCL swap** — DEVLOG claims it; unverified
5. **Zone dropout** — 3–5 of 16 zones per frame read `----`. Plausible for far or
   dark targets; if it persists against a close wall, revisit the pullups.
6. **Three uncommitted files** — `main/main.c`, `components/bno08x/bno08x.c`,
   `components/bno08x/include/bno08x.h` sit modified on top of `cafc9f5`. **They
   are the only copy of the working I²C IMU driver.**
