# ADDENDUM — supersedes parts of MASTER-HANDOFF.md

**Written 2026-08-07 00:25.** Covers work from **2026-08-05 evening → 2026-08-07**,
which is missing from `MASTER-HANDOFF.md`. That file was written from the OLD assembly
(`doubleTOFassem.SLDASM`) and describes geometry that has since been superseded.

**Read this alongside it. Where they disagree, THIS FILE IS NEWER.**

`MASTER-HANDOFF.md` remains correct and authoritative for: hardware dimensions,
camera calibration, the 1080p diagnosis, and the list of previously-false beliefs.

---

# WHICH FILE IS LIVE

```
✅ LIVE:       cad/solidworks/Assem1double tof test fov.SLDASM   (1839 KB, 2026-08-07 00:03)
❌ SUPERSEDED: cad/solidworks/doubleTOFassem.SLDASM              (935 KB, 2026-08-05 23:13)
```

The live file was created **2026-08-05 ~23:49** when the sensor arrangement was
rebuilt. `MASTER-HANDOFF.md` describes the superseded one throughout.

Also stale and causing reference confusion — same part filenames in several places:
`fov_review/`, `explode_copy/`, `experiment_copy/`.

**Back up with:** `powershell -File cad\backup_solidworks.ps1`
(dated, structure-preserving, warns on unsaved changes, keeps newest 20)

---

# ⚠️ SUPERSEDED FIGURES

| Item | MASTER-HANDOFF.md says | **CURRENT** |
|---|---|---|
| ToF yaw | 22.0° out each (44.00° total) | **±22.5° each (45.00° total)** |
| Baseline | 37.50 mm | **35.3 mm** |
| Seam at head height | 2.02° gap — open issue | **ZERO — solved** |
| Overlap at the axes | 5.03° | **zero** |
| Proposed fix for the seam | 9.88° sensor roll | **not needed — do not apply** |
| Blind corridor | closes with toe-in | **35.3 mm at ALL ranges (accepted)** |

---

# 1. THE FIX — rigid-group construction

**This is the most important thing in this document.** It solved the 2.02° gap that
`MASTER-HANDOFF.md` still lists as an open issue.

```
1. both ToF sensors LEVEL, yawed ±22.5° from centre
2. group them into one rigid sub-assembly
3. tilt the WHOLE group 22.5° down
```

**Why it works:** yawing while level leaves both fans' inner boundary planes
**vertical and coincident**. Tilting the whole group is a rigid rotation, and rigid
rotations preserve every relative angle — so they stay coincident at all elevations.

**[VERIFIED] 2026-08-05** (`docs/tof_rigid_group_check.py`):
```
ToF L inner-plane normal (+1.00000, -0.00000, +0.00000)
ToF R inner-plane normal (-1.00000, -0.00000, +0.00000)
angle between them: 0.0000°   ->  seam EXACTLY ZERO
```
Edge-to-edge at −5°, −10°, −22.5°, −30° and −40° elevation.

**❌ The old order — pitch each sensor down, THEN yaw each about world vertical —
produces the 2.02° gap.** Same two angles, different order, completely different
result. `docs/tof_seam_vs_elevation.py` quantifies the old behaviour:

| Elevation | Old-order seam |
|---|---|
| 0° (head height) | **2.02° GAP** |
| −10° | 0.98° overlap |
| −22.5° | 5.03° overlap |
| −40° | 12.33° overlap |

**Reuben found this himself**, from noticing the cones diverging at the top in a
render. The rebuild was his idea and it is better than the 9.88° roll I had proposed
— that was a correction for a problem this construction eliminates at the source.

**Do not apply the 9.88° roll.** It's superseded.

---

# 2. YAW LOCKED AT ±22.5° (45.00° total)

**Decided by Reuben 2026-08-06** after being shown the alternatives.

At exactly 45° the two fans' inner edges meet on the centreline — no angular overlap,
no angular gap. It is the unique crossover: below it they overlap, above it they part.

### Consequence, accepted with eyes open

The sensors are **35.3 mm apart**, so even angularly-touching fans start 35.3 mm
behind each other. At exactly 45° the inner rays are **parallel** and the blind
corridor **never closes**:

| Range | 35.3 mm corridor subtends |
|---|---|
| 0.5 m | **4.04°** |
| 1 m | 2.02° |
| 2 m | 1.01° |
| 4 m | **0.51°** (≈ 6 camera pixels) |

**Reuben chose this for predictability** — identical coverage at every range, nothing
to characterise. **The lever to shrink it is the BASELINE, not the angle.**

Alternatives if revisited (`docs/tof_overlap_at_range.py`):

| Separation | Toe-in each | Corridor closes at |
|---|---|---|
| 43.0° | +1.000° | 1.07 m |
| 44.0° | +0.500° | 2.15 m |
| 44.5° | +0.250° | 4.30 m |
| **45.00°** | 0 | **never** ← chosen |

**Baseline 35.3 mm** [VERIFIED] — Measure returned dX 3.53 cm, dY 0.01, dZ −0.03.
Purely lateral, which independently confirms the inner rays are parallel.

---

# 3. CORNER-RAY ELEVATIONS (rigid-group)

Reuben measured **35.66°** in CAD; theory gives **35.66°**. Exact agreement.

| Corner | Elevation |
|---|---|
| top-outer | **+4.44°** |
| top-inner | −1.56° |
| bottom-outer | **−35.66°** |
| bottom-inner | −43.44° |

⚠️ **An EDGE is not the field's descent angle.** Corner rays descend less steeply than
the bottom face, because part of their travel is sideways. To measure descent, select
the bottom **FACE**.

Small cost vs the old build: the top edge is no longer perfectly level (it ran from
+4.44° to −1.56°, where before all four top corners sat at exactly 0.00°).

---

# 4. FOV CONE DIMENSIONS

### ToF — draft extrude (only the depth is typed)
`far edge = start square + 0.82843 × reach`

| Reach | Far square (1 mm start) |
|---|---|
| 150 mm | **125.26 mm** [VERIFIED in CAD] |
| 1 m | 829.4 mm |
| 4 m | 3314.7 mm |

⚠️ Draft **22.5°**, not 45° — the spec is the total edge-to-edge angle; draft is from
the centreline. ⚠️ **"Draft outward" unticked gives a spike, not a cone.**

### Camera — LOFT (draft can't do it, the half-angles differ)
```
W = start + reach × 3.434964      tan(59.79°) = 1.717482
H = start + reach × 1.228484      tan(31.56°) = 0.614242
```

| Reach | Width | Height |
|---|---|---|
| 1 m | **3437.0 mm** | **1229.5 mm** |
| 4 m | **13741.9 mm** | **4914.9 mm** |

⚠️ At 4 m that's **13.7 × 4.9 metres** against a 75 mm pod. Suppress it by default.
⚠️ The wide dimension must align with the **1280** axis.

**Loft "self-intersecting geometry"** = twisted connectors. Click both rectangles near
the **same corner**. Build at 1 m first, then edit the plane offset.

### ⚠️ CONES ARE SOLID BODIES — 790 cm³ EACH
They WILL land in an STL export. **Mark them Envelope** (Component Properties →
Envelope). **Still not done.**

---

# 5. FASTENERS — fully specified 2026-08-06

## Case joint: front **7 mm** + **1 mm** gap + back **6 mm** = **14 mm**

*(walls were extended from 6/1/5 to 7/1/6 to allow a full counterbore)*

| Feature | Size |
|---|---|
| Counterbore, outer front face | **Ø4.4 × 2.4 mm** |
| Clearance hole, front wall | **Ø2.4 mm** through |
| Pilot hole, back wall | **Ø1.6 mm** THROUGH |
| Screw | **M2 × 12** hex socket cap, ISO 4762 |

**THE RULE: clearance hole in the NEAR part, thread ONLY in the FAR part.** Thread
both and the screw can never pull them together.

**Length excludes the head.** M2 × 12 = 12 mm shank + 2 mm head = **14 mm overall**,
matching the stack exactly. (Countersunk screws are the exception.)

**Back pilot must be THROUGH** — with a 2.4 mm counterbore the tip lands at 14.4 mm in
a 14 mm stack, so a blind hole bottoms out and strips the plastic thread.

**Counterbore, not chamfer** — a socket cap head is a cylinder.

### M2 ISO 4762
| | Max | Min |
|---|---|---|
| p pitch | 0.4 | |
| dk head Ø | 3.80 | 3.62 |
| k head height | 2.00 | 1.86 |
| s hex socket | 1.56 | 1.52 |
| t socket depth | | 1.00 |

Hex key **1.5 mm**.

## Camera mount
**M2 self-tapping** into **Ø1.6 × 8 mm** pilots. **Bosses ≥ 5.6 mm OD** (2 mm material
each side, or the boss splits). Mounted once, so rigidity beats reusability.

## Lid
**M3 heat-set inserts** — opened repeatedly. Hole size from the insert manufacturer's
datasheet (Ruthex / CNC Kitchen publish them).

## Pilot rule
`pilot = major − pitch = 0.8 × major` → M2: **1.6 mm**

## Screw kit — CONFIRMED SUITABLE
Senyard 1415 pcs, 304 stainless, hex socket. **M2 in 4/8/12/16 mm, 120 pcs** (~30
each). Has the M2×12 for the case joint and M2×8 for the camera mount. Its chart
states head figures are "a single batch of manual measurement" — hence Ø4.4 × 2.4
rather than the ISO nominal.

## FDM
Sliding fit **0.30–0.40 mm** · press fit 0.10–0.20 · resin 0.10–0.15.
⚠️ **Small holes print undersized** (1.6 → 1.4–1.5). **Test print one boss first.**

---

# 6. CAMERA BORE

**Ø17.80 mm** (barrel 17.10 + 0.35 radial). ⚠️ A **Ø17.30** bore was cut at one point —
0.10 mm radial, too tight for FDM. Must be opened.

Cut by sketching on a plane square to the lens → **Convert Entities** on the barrel's
circular edge → **Offset Entities 0.35 mm** → **Extruded Cut Through All**. The opening
comes out an **ellipse** in an angled wall; that's correct.

**Keep the lens tip proud** — every 1 mm of recess costs **3.4 mm** of opening width.

---

# 7. ⚠️ ADDITIONAL SOLIDWORKS TRAPS (2026-08-06)

Four separate cascades occurred. All four were references pointing at something that
later changed.

1. **"Break All" on external references DESTROYS in-context features.** It killed a
   part's `22.5 top plane` and every feature built on it. **Lock ≠ Break** — Lock
   suspends updating but keeps the reference (so it still blocks a second context);
   Break removes it and takes the dependent geometry with it.
2. **"Propagate feature to parts"** on an assembly feature caused a cascade. Assembly
   features can only **REMOVE** material — there is no assembly-level boss.
3. **In-context parts CANNOT be transplanted between assemblies.** Breaking the link
   doesn't rehome a part. **Rebuild it in the new assembly** — that's what fixed the
   FOV cones, in about three minutes each.
4. **Reference DATUM PLANES, never faces.** Faces get renumbered when material is
   added and consumed when a boss merges over them.
5. **Nothing should reference the parts mounted to it.** A sketch in the base part
   referencing the sensors means *every sensor edit breaks the base*. This is the
   currently-unfixed defect — see Open Items.
6. **Tree suffixes:** `->` external ref · `-> x` broken · `-> ?` out of date.
7. **When a sketch dangles, redrawing is faster than repairing.**

### Geometry gotchas
- **An angled plane needs a LINE to hinge on** plus a plane for the angle. Two planar
  references is invalid.
- **The hinge must be horizontal** or the angle-to-horizontal won't equal what you type.
- **Mid-plane between two NON-parallel faces has TWO solutions**, perpendicular to each
  other. Flip only reverses the normal.
- **Coincident makes PLANES coincide, not faces touch** — the part can still slide
  anywhere in that plane.
- **Width mate needs roughly parallel pairs** — on a pyramid's diverging faces it
  solves to something valid and wrong.
- **Three mutually perpendicular FACE pairs** fully define a part. Avoid edges.

### Commands
`F` zoom fit · `F9` tree · `Ctrl+8` Normal To · `Alt+←/→` roll view · `S` shortcut bar ·
`Ctrl+Q` forced rebuild · **Intersection Curve** (where the sketch plane cuts a face) ·
**Up To Surface** · **Thin Feature** · **Make Independent** · Evaluate → **Clearance
Verification** (Interference Detection only finds actual overlaps).

Two documents **cannot share a filename** in one session — the second open is silently
ignored. **Virtual components** (square brackets in the tree) aren't files on disk and
backup scripts can't see them individually.

---

# 8. OPEN ITEMS (current, supersedes the older list)

### Blocking
1. **⚠️ 0.080 mm pinch at the two header shrouds** — boards will not slide in. Relief
   pocket: 0 → 39 mm along the length, the 16.5 → 20 mm band, **0.5 mm deep**.
2. **⚠️ Mark all FOV cones Envelope** — 790 cm³ solids that will print.
3. **⚠️ Measure a DuPont housing** — camera board clears the ToF pin tips by only
   **10.82 mm**, and a female housing plus wire bend eats into that. Last `[TBD]`.
4. **⚠️ Re-measure a camera PCB hole** — 2.1 vs 2.3 mm changes the pitch (28.0 vs 28.2).
5. **⚠️ Broken references in the live assembly** — `3DSketch1` in Part13 (the structural
   piece both ToF sensors mate to) still references TOFSLOT geometry. **Every TOFSLOT
   edit re-breaks it**, plus a coincident mate and a profile sketch. Fix by stripping
   the external refs from Part13 — not by repairing them one at a time.
6. **Open the camera bore** from Ø17.30 to **Ø17.80**.

### Housekeeping
7. Consolidate/delete `fov_review/`, `explode_copy/`, `experiment_copy/` and the
   superseded `doubleTOFassem.SLDASM`.
8. Re-derive the camera lens-tip target coordinates for the new assembly — those in
   `MASTER-HANDOFF.md` §3.1 are from the old one.

### Still to design
9. Ultrasonic bracket · helmet interface (bike helmet, needs vent photos) ·
   electronics box (ESP32-S3 DevKitC-1, haptic drivers, IMU, ToF pull-ups, USB hub;
   **no battery**, always tethered to a laptop in a backpack).

### The actual goal
10. **Stage 3: ToF↔camera extrinsics** → **Stage 4: live fusion.** Not started.

---

# 9. SCRIPTS ADDED THIS SESSION

| File | What it does |
|---|---|
| `docs/tof_rigid_group_check.py` | **proves the rigid-group arrangement gives a zero seam** |
| `docs/tof_seam_vs_elevation.py` | quantifies the OLD order's gap-at-top / overlap-at-bottom |
| `docs/tof_overlap_at_range.py` | blind corridor vs separation angle and range |
| `docs/tof_roll_solution.py` | the 9.88° roll — **superseded, kept for the maths** |
| `docs/fov_containment_exact.py` | exact four-corner camera containment test |
| `docs/dihedral_calculator.py` | compound-angle joints |
| `docs/camera_target_position.py` | lens tip target + the world-Z trap |
| `docs/camera_placement_check.py` | the two interference constraints |
| `docs/camera_height_offset.py` | why mounting height barely matters |
| `cad/explode_animation.py` | renders `cad/render/explode.gif` |
| `cad/backup_solidworks.ps1` | **the backup script** |

---

# 10. PRINCIPLES

1. **Measure the geometry; never assert what it should be.** A claimed 1.49° defect in
   `centerV` turned out to be correct wedge geometry — the *target* was assumed, not
   derived. Reuben caught it.
2. **Export a STEP and measure it.** Reasoning from face descriptions cost hours;
   measuring real geometry resolved things in one pass, every time.
3. **Never use separable (independent H and V) estimates for a yawed AND pitched
   cone.** It was wrong twice — the 9.06° margin (really −0.02°) and the 1° overlap
   (really a 2.02° gap). Always test the four corner rays.
4. **Inherit angles from geometry, don't type them.** Sketch on the sensor's own face
   and position, direction, pitch and yaw all come for free.
5. **Build order can matter more than the angles themselves** — the rigid-group result
   is the proof.
