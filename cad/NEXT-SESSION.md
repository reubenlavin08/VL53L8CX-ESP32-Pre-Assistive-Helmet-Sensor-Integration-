# Next session — pick up here

## ⭐ PRIMARY FILE

```
cad/solidworks/Assem1double tof test fov.SLDASM
```

**This is the one that matters.** It uses the rigid-group arrangement: both ToF
sensors yawed **level** ±22.5° from centre, grouped into a sub-assembly, then the
**whole group tilted 22.5° down**.

**Back it up every session:** `powershell -File cad\backup_solidworks.ps1`
(dated snapshot, folder structure preserved, keeps the newest 20, names the primary
file explicitly so a miss is loud).

### Why this arrangement wins — verified 2026-08-05

Yawing while level leaves both fans' inner boundary planes **vertical and
coincident**. Tilting the whole group is a rigid rotation, and rigid rotations
preserve relative angles — so the planes stay coincident.

```
ToF L inner-plane normal (+1.00000, -0.00000, +0.00000)
ToF R inner-plane normal (-1.00000, -0.00000, +0.00000)
angle between them: 0.0000°  ->  seam EXACTLY ZERO
```

Seam is edge-to-edge at −5°, −10°, −22.5°, −30° and −40° elevation. No gap at the
top, no wasted overlap at the bottom.

**The old order (pitch each sensor, then yaw each about world vertical) does not do
this** — it tilts the two inner planes differently, giving a 2.02° gap at head height
and up to 12° of wasted overlap near the floor. Same two angles, different order,
completely different result. `docs/tof_rigid_group_check.py` and
`docs/tof_seam_vs_elevation.py`.

**Corner ray elevations in this arrangement** (measured 35.66° in CAD, theory 35.66°):

| Corner | Elevation |
|---|---|
| top-outer | +4.44° |
| top-inner | −1.56° |
| bottom-outer | **−35.66°** |
| bottom-inner | −43.44° |

Small cost vs the old build: the top edge is no longer perfectly level (+4.44° to
−1.56° instead of a flat 0.00°).

---


**Saved 2026-08-05 15:35.** Backup: `cad/solidworks/backup_2026-08-05_1535/` (19 files,
folder structure preserved). `doubleTOFassem.SLDASM` saved clean at 15:35:02, 1007 KB.

---

## Where things stand after 2026-08-05

**Built today:** `Midplane` (pod symmetry plane, verified 90° to Top), `22.5 top plane`
(**verified correct** — 88.52° to a ToF face, matching theory to two decimals), a
`camera wall` part, the camera bore, four M2 bosses, and `cam_with_28mmholes.SLDPRT`.

**~~The centerV 1.49° defect~~ — RETRACTED, there is no defect.** I had claimed
centerV's faces should read 67.50°/22.50°. That target was an assumption, not a
measurement: I'd taken centerV for a wall parallel to the camera wall. It isn't — it's
a **wedge filling the void** left after rotating the two sensors 22° apart, so its
faces are whatever that void demands. 68.99°/21.01° is correct geometry, and its yaw
is 22.00°, exactly on the bisector.

**Verified 2026-08-05 16:00 against the exported STEP: every part touches at 0.000 mm.**
centerV↔TOFSLOT A, centerV↔TOFSLOT B, centerV↔camera wall, camera wall↔both TOFSLOTs —
all zero. No gaps anywhere. The earlier 1.04 mm gap and 1.49° wedge are gone.

**Lesson worth keeping:** measure the geometry, don't assert what it should be. Every
time this session that a face's "correct" angle was assumed rather than derived, the
assumption was the thing that was wrong.

**Verification targets** (all confirmed by calculation, `docs/dihedral_calculator.py`):

| Plane / face | vs Top | vs Front | vs Right |
|---|---|---|---|
| Slanted top (roof) | **22.50°** | 69.22° | 81.76° |
| Camera mounting wall | **67.50°** | 31.06° | 69.75° |
| Pod symmetry plane | 90.00° | 68.00° | 22.00° |

Joint dihedrals: camera wall ↔ ToF angled front **159.69°**; camera wall ↔ ToF vertical
face **148.94°**; ToF angled ↔ ToF vertical **157.50°**; left ToF ↔ right ToF **139.50°**.

**Rule learned the hard way:** the **Top Plane angle measures tilt alone** and is
yaw-independent — it's the clean number to set and check against. Front/Right Plane
angles mix tilt and yaw, which is why they come out as 31.06° and 69.22°.

**Root friction:** the assembly's world axes are locked to the LEFT ToF sensor (inserted
first, auto-fixed at origin), so world Z is 22° off the pod centreline. Every plane,
sketch and view inherits that skew. Options are (a) live with it using the datum set,
(b) realign the assembly — risky, or (c) rebuild the pod as a **single part**, which is
what it should be since it prints as one object. **Decide after seeing a STEP.**

**Screw hardware settled:** M2 self-tappers for the camera (mounted once, rigidity is
what matters) into **Ø1.6 mm × 8 mm** pilot holes, bosses **≥ 5.6 mm** across. M3
heat-set inserts for the lid only. Camera PCB holes measure **2.1 mm** — re-measure
once to settle 2.1 vs the earlier 2.3, since it changes the pitch (28.0 vs 28.2).

**Still blocked on:** a STEP export. Face identifications keep shifting between
messages, and each face pair has a different correct answer, so measuring the real
geometry is the only way to end the guessing.

---

## The decision made at the end of the session

**Rebuild the camera mount on a 22.5° angled wall instead of the straight wall.**

Reuben's reasoning: an angled wall gives the camera far more support. That's right, and
there are two more reasons it's the better build:

1. **The mounting face ends up square to the camera.** On a straight wall the camera
   board meets the wall at 22.5°, so any screw bosses have to be wedges and the board
   is only touching along an edge. On an angled wall the board sits flat against it.
2. **The bore becomes a true circle, not an ellipse.** A round barrel through an
   angled wall cuts an ellipse; through a square wall it's a plain circular hole. Easier
   to cut, easier to check, and the wall thickness around it is even the whole way round.

**What exists right now:** the bore is cut in a **straight (vertical) wall**, Ø17.30
(radius 8.65). The camera is not yet mated.

---

## Do these, in order

1. **Build the 22.5° wall.**
   Plane recipe that works (the one that failed used two planar references — an angled
   plane needs a LINE to hinge on):
   - Reference Geometry → **Plane**
   - **First Reference: a horizontal EDGE** running left-right across the pod front
   - **Second Reference: Top Plane**, click the **Angle** icon, type **22.5**
   - Verify the edge is horizontal first: Measure it vs Top Plane → must be 0.00°

2. **Re-cut the bore on the new wall — Ø17.80, not Ø17.30.**
   Barrel is Ø17.10 [CALIPER]. The current 8.65 mm radius leaves only **0.10 mm radial**,
   below what FDM can hold. Use **radius 8.90**.
   Best method: sketch on the angled wall → click the barrel's circular edge →
   **Convert Entities** → **Offset Entities 0.35 mm** outward → **Extruded Cut, Through All**.

3. **Mate the camera — three mates:**
   - **Concentric**: barrel outer cylindrical face ↔ bore inner cylindrical face
   - **Lock Rotation** on that concentric mate (roll is solved by Stage 3 calibration and
     quantized by the 4-screw pattern anyway — eyeballing is fine here)
   - **Distance 1.00 mm**: lens tip face proud of the casing outer face
   `CAMERA-MODEL<1>` should lose its `(-)` in the tree when fully constrained.

4. **Verify:** Measure lens tip face → ToF chip top face, read **Delta X/Y/Z**.

---

## Numbers to hit

| | |
|---|---|
| Camera pitch | **22.5° down**, same as the ToF |
| Camera yaw | **0°** — on the bisector, not angled out |
| Lens tip forward offset vs ToF apertures | **0 mm or slightly proud** |
| Lens axis height above the ToF sight line | **30–40 mm** |
| Bore | **Ø17.80** (radius 8.90) |

**Target lens tip, if you want to place by coordinate instead** (h = 30 mm):
`(691.718, 322.633, 1526.232)`

⚠️ **Do NOT set the lens tip to the same world Z as the ToF.** Verified by rasterising the
real board geometry through the calibrated fisheye model: same-Z puts **20–44% of the
frame** behind your own ToF boards. Moving up along the camera's own axis costs **0.00%**.
See `docs/camera_target_position.py`.

---

## Still open

- **Measure a DuPont housing** — the last `[TBD]`. Camera PCB clears the ToF header pin
  tips by only **10.82 mm**, and a female DuPont housing plus wire bend eats into that.
  This is the number most likely to bite.
- **Relieve the two 0.080 mm pinch points** — the plastic bodies of the two 0.1" headers
  on the back of each ToF board. Local pocket, 0 → 39 mm along the length, 16.5 → 20 mm
  band, 0.5 mm deep. See `VERIFY-IT-YOURSELF.md` §6.
- **Re-run the obstruction check** once the front wall exists:
  `python cad/check_user_assembly.py` (re-export the STEP first). It currently reports
  both sensors clear only because nothing is in front of them yet.
- **Cone B** — cone A verified at 125.26 mm far edge. B not built.
- Ultrasonic bracket, helmet interface, electronics box.
- **Stage 3 (ToF↔camera extrinsics) → Stage 4 (live fusion)** — the actual goal.

---

## Reference docs written this session

| File | What's in it |
|---|---|
| `cad/VERIFY-IT-YOURSELF.md` | every measured number + how to check it in SOLIDWORKS |
| `cad/HOWTO-BUILD-FOV-CONES.md` | building FOV cones by inheriting the angle |
| `cad/HOWTO-ANGLED-BORE.md` | the bore, and where the camera can go |
| `docs/camera_target_position.py` | exact lens tip target, and the same-Z trap |
| `docs/camera_placement_check.py` | the two interference constraints |
| `docs/camera_height_offset.py` | why height barely matters |
| `cad/check_user_assembly.py` | verifies your STEP: angles, fit, apertures |
