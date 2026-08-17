# Print settings — helmet sensor pod

Drop the exported 3MF/STL files in this folder and send the whole folder.

---

## Parts and quantities

| Part | Qty | Notes |
|---|---|---|
| ToF sensor case | **2** | mirrored pair — same file, two copies |
| Centre wedge | 1 | |
| Camera mount baseplate | 1 | 22.5° wedge |
| Camera wall | 1 | |

*(update this list to match what's actually in the folder)*

---

## Material

**PLA.** Stiffer than PETG, which is what matters here — the whole assembly holds a
camera and two depth sensors in fixed alignment, and any flex or creep invalidates the
calibration. PETG only if it'll ever sit in a hot car.

---

## Settings

| Setting | Value |
|---|---|
| Nozzle | 0.4 mm |
| Layer height | **0.2 mm** (0.15 mm if hole accuracy matters more than time) |
| **Perimeters / walls** | **4** ← not the default 2 |
| Infill | **25–30%**, gyroid or grid |
| Top / bottom layers | 4–5 |
| Supports | only where an overhang exceeds ~45° |
| Brim | optional, helps on the small parts |

**Perimeters matter far more than infill on parts this size.** Going from 2 to 4 walls
costs minutes and adds a lot of strength; pushing infill to 80% costs hours and adds
little.

---

## ⚠️ Orientation — the single biggest factor

Layers bond weakly to each other, so a printed part is strong **across** layers and weak
**along** them. Orient each part so loads press across layers rather than peeling them
apart.

| Part | Orientation |
|---|---|
| **Camera mount baseplate** | **flat bottom on the bed** — no supports, and the screw loads press across layers |
| **ToF sensor cases** | largest flat face down |
| **Screw bosses** | hole axis **vertical** where possible — rounder, cleaner holes |

**Do not print the 22.5° faces at an angle to the bed** if it can be avoided.

---

## ⚠️ Holes print undersized

A modelled 1.6 mm hole typically comes out **1.4–1.5 mm** on FDM. That's helpful for
self-tapping screws (more material to bite) but it can make driving hard enough to split
a boss.

**Print one test coupon first** — a small block with one Ø1.6 pilot, one Ø5.2 clearance
hole and one M5 nut pocket. Five minutes, and it tells you how much this printer
undersizes before committing a four-hour part.

**Do not scale or "fix" hole sizes** without checking — the clearances were calculated
against specific hardware.

---

## Hardware these parts are designed around

| | |
|---|---|
| Case joint | **M2 × 12** hex socket cap (ISO 4762) |
| Camera mount | **M2** self-tapping into Ø1.6 pilots |
| Baseplate | **M5 × 20** with 1.4 mm washers and 3.8 mm nuts |
| Lid | **M3 heat-set inserts** |

**Do not scale the parts.** Every clearance is sized to these fasteners.
