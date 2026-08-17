# READ ME FIRST — helmet sensor pod

**If you are a fresh Claude session on this project, read these two files, in this
order, before doing anything:**

```
1.  cad/MASTER-HANDOFF.md            hardware, calibration, background
2.  cad/MASTER-HANDOFF-ADDENDUM.md   the CURRENT geometry — NEWER, wins on conflicts
3.  cad/ADDENDUM-2026-08-07.md       camera mount baseplate, M5 fasteners, new SW traps
4.  cad/SESSION-HANDOFF-2026-08-16.md  ← NEWEST. Read this before doing anything.
5.  cad/extrinsics_measured.json     MEASURED sensor geometry — the fusion inputs
6.  docs/WIRING.md                   verified wiring, all three devices
```

**Start with the 2026-08-16 handoff.** Both ToF sensors are now calibrated to the camera.
The open problem is a **~8 mm systematic residual** that no rigid transform absorbs, and
the next step is **building the fusion overlay** — which is both the deliverable and the
best remaining diagnostic. Full narrative in `docs/DEVLOG.md` (2026-08-16 entry).

⚠️ **Two things that will mislead you if you skip the handoff:**
- **Sensor A = wearer's LEFT = CAD `tof_right`.** Two opposite "left" conventions are in
  play. Getting it backwards mirrors every depth point while all self-checks still pass.
- **The field of view is 45°, settled by physical measurement.** The solver keeps
  preferring ~34° — that is a bug in the pipeline, not the sensor. Do not let it float.

All are needed. None is complete alone. Later files win on conflicts.

---

## The measured geometry (2026-08-16)

**`cad/extrinsics_measured.json` is the source of truth for Stage 3/4 geometry.**
Both ToF boresights measured from CAD vertices and confirmed within **0.003°** of
the designed ±22.5° / 22.5°. Sensor frames are full right-handed bases; roll is
resolved. Verify any time — it re-derives every stored value from the raw points:

```
python docs/extrinsics_solve.py
```

Still open in that file: the **camera** (not measured), the **SPAD-in-package
offset** (a datasheet number, invisible in CAD), and **grid orientation**
(assumed board-aligned, unconfirmed against UM3109).

⚠️ **Those are CAD nominals, not a calibration.** Print tolerance, board slop,
die placement and lens-axis error are all invisible to CAD, and at 4 m **1° =
70 mm**. Real extrinsics come from a planar-target calibration.

---

## Why there are two files

Two Claude sessions ran in parallel on 2026-08-05→07 and each wrote a handoff. The
second overwrote the first. Rather than merge and risk losing detail, they're kept
separate with a clear precedence rule:

| File | Written from | Authoritative for |
|---|---|---|
| `MASTER-HANDOFF.md` | the **old** assembly `doubleTOFassem.SLDASM` | hardware dimensions, camera calibration, the 1080p diagnosis, previously-false beliefs |
| `MASTER-HANDOFF-ADDENDUM.md` | the **live** assembly `Assem1double tof test fov.SLDASM` | **all current geometry, angles, fasteners, open items** |

**Where they disagree, the ADDENDUM is correct.** It covers work done after the other
file was written.

---

## The five things to know before touching anything

**1. The live file**
```
✅ cad/solidworks/Assem1double tof test fov.SLDASM
❌ cad/solidworks/doubleTOFassem.SLDASM          superseded
```
`MASTER-HANDOFF.md` describes the superseded one throughout.

**2. Back up every session**
```
powershell -File cad\backup_solidworks.ps1
```

**3. The geometry that changed** — ADDENDUM has the detail

| | Old file says | **Current** |
|---|---|---|
| ToF yaw | 22.0° each (44° total) | **±22.5° each (45.00° total)** |
| Baseline | 37.50 mm | **35.3 mm** |
| Seam at head height | 2.02° gap, open issue | **ZERO — solved** |
| Fix for the seam | apply a 9.88° roll | **not needed, do not apply** |

**4. The key result — rigid-group construction**
Yaw both ToF sensors **level** ±22.5°, group them, then tilt the **whole group** 22.5°
down. Gives an exactly zero seam at every elevation (inner-plane normals +1,0,0 and
−1,0,0, angle 0.0000°). The old order — pitch each sensor then yaw about world
vertical — is what produced the 2.02° gap. Same angles, different order.

**5. The trap that broke the model four times**
References pointing at things that later change. Never Break external refs on an
in-context part; never reference faces where a datum plane will do; never let the base
structure reference the parts mounted to it. ADDENDUM §7 has all of it.

---

## Immediate open items

1. **0.080 mm pinch** at the two header shrouds — boards won't slide in
2. **Mark FOV cones as Envelope** — 790 cm³ solids that will print
3. **Measure a DuPont housing** — only 10.82 mm of clearance behind the camera board
4. **Re-measure a camera PCB hole** — 2.1 vs 2.3 mm
5. **Strip external refs from Part13** — every TOFSLOT edit re-breaks the assembly
6. **Open the camera bore** Ø17.30 → Ø17.80

Full list with numbers: ADDENDUM §8.

---

## The actual goal, not yet started

**Stage 3: ToF↔camera extrinsics** → **Stage 4: live fusion.** Everything so far is
the mechanical work Stage 3 depends on — the sensors must be rigidly located and their
geometry known.

---

## Housekeeping worth doing early

`fov_review/`, `explode_copy/` and `experiment_copy/` contain parts with the **same
filenames** as the live ones. SOLIDWORKS resolves references by search order, not by
folder, so it can silently bind to the wrong copy. This caused a working session's
worth of confusion. **Consolidate or delete them.**
