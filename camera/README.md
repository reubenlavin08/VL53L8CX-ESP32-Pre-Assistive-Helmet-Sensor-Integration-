# Camera folder — what everything is and where

**This folder:** `C:\esp-projects\vl53l8cx_esp32\camera\`

Open a terminal there:
```
cd C:\esp-projects\vl53l8cx_esp32
```
Every command below is run from that folder (`vl53l8cx_esp32`, not `camera`).

---

## THE STAGE MAP — one numbering, replaces everything earlier

I previously used two conflicting schemes ("Stage 1" and "Step 3" for the same thing). **This is the only one now.**

| # | Stage | What it produces | Status |
|---|---|---|---|
| **0** | Camera alive | A picture on screen | ✅ **DONE** |
| **1** | Focus + lock the lens | A lens that can never shift | 🔵 in progress |
| **2** | Calibrate the lens (*intrinsics*) | **K** and **D** | ⬜ next (morning) |
| **3** | Align ToF to camera (*extrinsics*) | **[R\|t]** | ⬜ |
| **4** | Project + overlay | **FUSION WORKING** — depth painted on video | ⬜ |
| **5** | Detection-gating | "person, 1.8 m, left" → haptics | ⬜ later |
| **6** | Mono-depth | Dense metric depth across the full 140° | ⬜ later |

**Stage 4 is the goal you asked for.** 5 and 6 are upgrades on top of it.

Every term in bold is defined in **`GLOSSARY.md`** (same folder).

---

## Files, with full paths

### Read these
| File | What it's for |
|---|---|
| `C:\esp-projects\vl53l8cx_esp32\camera\README.md` | This file — the index |
| `C:\esp-projects\vl53l8cx_esp32\camera\GLOSSARY.md` | **Every term explained, plus why each stage exists** |
| `C:\esp-projects\vl53l8cx_esp32\camera\CALIBRATION-RUNBOOK.md` | **Stage 2 step-by-step — follow this in the morning** |
| `C:\esp-projects\vl53l8cx_esp32\docs\fusion-executive-summary.md` | The whole plan, one page |
| `C:\esp-projects\vl53l8cx_esp32\docs\datasheets\camera\HBV-1716WA-VERIFIED-SPECS.md` | Hardware facts, marked official vs inferred |

### Print this
| File | What it's for |
|---|---|
| `C:\esp-projects\vl53l8cx_esp32\camera\checkerboard_8x11_20mm.pdf` | **The calibration target. Print at 100%.** |

### Run these
| Command (from `C:\esp-projects\vl53l8cx_esp32`) | Stage | What it does |
|---|---|---|
| `python camera\camera_focus.py 1` | 1 | Live view + 1:1 magnifier for focusing. **Judge with your eyes on the inset.** |
| `python camera\capture_calib.py` | 2 | Collects checkerboard photos, tracks coverage |
| `python camera\calibrate_fisheye.py` | 2 | Fits the lens model → **K**, **D** |
| `python camera\make_checkerboard.py` | — | Regenerates the PDF (already done, only if you change square size) |
| `python camera\camera_live.py 1` | — | Plain live view, `m` cycles modes |
| `python camera\camera_check.py` | — | Probes which camera index is which |

The `1` after `camera_focus.py` / `camera_live.py` is the **camera index** — your HBV is index 1, your laptop's built-in webcam is index 0.

### Produced by the scripts (they don't exist yet)
| File | Made by | Contains |
|---|---|---|
| `camera\calib_shots\calib_000.png` … | `capture_calib.py` | Your checkerboard photos |
| `camera\calibration_720p.npz` | `calibrate_fisheye.py` | **K and D — the actual deliverable** |
| `camera\calibration_720p.txt` | `calibrate_fisheye.py` | Readable report + **measured field of view** |
| `camera\undistort_preview.jpg` | `calibrate_fisheye.py` | Before/after picture to eyeball |
| `camera\snapshots\` | focus/live tools | Any snapshots you save with `s` |

---

## If something breaks

**"Could not open camera index 1"** — something else is holding the camera. Close other camera apps, or:
```
Get-Process python,ffmpeg -ErrorAction SilentlyContinue | Stop-Process -Force
```

**Camera vanished entirely** — unplug, wait, replug. Check it's back:
```
Get-PnpDevice -Class Camera | Where-Object { $_.InstanceId -like "*VID_0AC8*" }
```
`Present : True` = it's there. (Drop-outs during bring-up turned out to be manual unplugs.)

**Module too hot to hold a finger on** — unplug and let it cool. Above ~50 °C the sensor leaves its stable-image range (OV2710 datasheet, Table 8-2).
