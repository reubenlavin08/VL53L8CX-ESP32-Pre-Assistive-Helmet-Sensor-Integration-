# MASTER HANDOFF — everything known about the sensor pod build

**Written 2026-08-07 00:15.** Single source of truth for the CAD/mechanical side of the
helmet fusion project. Supersedes scattered notes. Read this first.

Provenance tags used throughout:
`[ST-STEP]` from ST's official CAD · `[DS]` from a datasheet · `[CALIPER]` measured by
Reuben · `[MEASURED]` derived from calibration · `[VERIFIED]` confirmed against the
exported STEP geometry · `[TBD]` not yet known

---

# 1. THE GOAL

**ToF ↔ camera sensor fusion.** Project VL53L8CX depth zones onto camera pixels so every
detected object carries a distance in metres.

| Stage | What | State |
|---|---|---|
| 1 | Camera bring-up | ✅ done |
| 2 | Camera intrinsic calibration | ✅ done, RMS 0.30 px |
| 3 | ToF↔camera **extrinsics** ([R\|t]) | ❌ not started — the real next milestone |
| 4 | Live fusion | ❌ not started |

Everything in this document is the mechanical work that Stage 3 depends on: the sensors
must be rigidly located and their geometry known.

---

# 2. HARDWARE DIMENSIONS

## 2.1 SATEL-VL53L8 ToF breakout — all [ST-STEP], exact

| Dimension | Value |
|---|---|
| PCB | **51.500 × 19.500 × 1.578 mm** |
| VL53L8CX package | 6.400 × 3.030 × 1.750 mm, optical LGA16 |
| Package position on board | X 4.910–7.940, Y 6.550–12.950 |
| **Sensor centre from the near END** | **6.400 mm** |
| Sensor centre across the width | 9.750 mm (centred) |
| Package height above PCB (= aperture plane) | **1.750 mm** |
| Detection FoV | **45° × 45°** (65° diagonal) — [DS] DS14161 Table 2 |

**Optical axis is NOT the package centre** — [DS] DS14161 Fig. 28:
- Rx axis 1.480 mm from one end, Tx 4.000 mm further along
- Optical axis 1.615 mm from the long edge → 0.100 mm off package centre
- AN5939 §4: design apertures to the **optical** centre

### Keep-outs

| | Value |
|---|---|
| **Headers (deep)** | strip y 0.08–2.62, running x 12.77–51.00, protruding **10.060 mm** below PCB |
| Everything else below PCB | solder pads only, max 2.130 mm |
| Tallest thing above PCB | 8.480 mm (a header); general clutter to 2.640 mm |

### Clear strip at each edge (82 components on top, 36 underneath)

| Edge | Clear on TOP | Clear on BOTTOM |
|---|---|---|
| Long edge y=0 | 0.91 mm | **0.08 mm** ← headers on this edge |
| Long edge y=19.5 | 1.85 mm | 3.10 mm |
| End x=0 | 4.91 mm | 3.55 mm |
| End x=51.5 | 1.46 mm | 0.50 mm |

**Consequence:** a retaining lip can only grip the y=19.5 edge, ~1.5 mm max. On the
header edge use a channel that captures the header rib instead.

### The two header shrouds — the pinch points found 2026-08-05

Black plastic bodies of two 0.1" headers on the **back** of the board, in board-local
coordinates:

| | Header 1 | Header 2 |
|---|---|---|
| Along the 51.5 mm length | 0.49 → 28.55 mm | 30.97 → 38.71 mm |
| Length | 28.07 mm (11 × 2.54) | 7.75 mm (3 × 2.54) |
| Across the 19.5 mm width | 16.98 → 19.52 mm | 16.98 → 19.52 mm |
| Below the PCB back face | 0.10 → 2.64 mm | 0.10 → 2.64 mm |

Both hug the same long edge and hang **2.64 mm below the board**. Metal pins go a
further 10.06 mm down as separate solids.

## 2.2 HBV-1716WA camera — all [CALIPER] 2026-07-31

| Dimension | Value | Note |
|---|---|---|
| PCB | **38.0 × 38.0 mm** | |
| PCB thickness | **1.69 mm** | |
| Mounting holes | **Ø2.3 mm**, **28.2 mm** pitch | derived: 25.9 inner-edge + 2.3 |
| ⚠️ Re-measured 2026-08-05 as | **~2.1 mm** → pitch 28.0 | **UNRESOLVED — measure once more** |
| Depth, PCB back → lens front | **25.9 mm** | cap off (28.5 with cap) |
| Lens barrel outer Ø | **17.1 mm** | 3 mm bigger than the usual M12 assumption |
| Barrel height above PCB | **24.21 mm** | = 25.9 − 1.69 |

**No official datasheet exists for this camera** — verified negative. hbvcamera.com has
no downloads section and lists no 140°/"WA" variant. "HBV-1716WA" is a reseller SKU.
Every published figure found was wrong: hole pitch (32 claimed), depth (17.5 claimed),
barrel Ø (~14 assumed). **Trust only the caliper numbers above.**

Corroboration found 2026-08-05: two independent sources state the 1716 family has "four
2 mm holes in a 28 mm square pattern", agreeing with the caliper measurement.

**No manufacturer CAD exists either** — searched GrabCAD, TraceParts, HBVCAM. Only
user-contributed models of *other* HBV boards. We generate our own from the calipers.

### Calibrated optics — `camera/calibration_720p.npz` / `.txt`

```
MJPG 1280x720, cv2.fisheye, RMS 0.3006 px, 19 views
fx = 669.823  fy = 670.075   cx = 620.953  cy = 335.169
D  = [-0.079359, -0.006644, 0.016116, -0.007523]

MEASURED FOV:  H 119.58°   V 63.12°   D 144.02°
```

**K is resolution-dependent — always capture at 1280×720 or recalibrate.**

⚠️ **The old ~109°H / 67°V figure is an EXTRAPOLATION from sibling modules and is
WRONG.** Superseded by the calibration. The box's "140°" is the *diagonal*; our measured
diagonal is 144.02°, which corroborates it.

### 1080p is broken on this unit

MJPEG 1920×1080 returns all-zero frames. Root cause documented: the firmware declares
uncompressed bitrates in its MJPEG descriptor (`dwMaxBitRate 995328000` = the YUY2
figure copy-pasted in), so the host tries to reserve 3–10× the bandwidth needed and
allocation fails. This is what Linux patches with `UVC_QUIRK_FIX_BANDWIDTH`; Windows has
no equivalent. **Decision: capture at MJPEG 1280×720 @30.** Full analysis in
`docs/datasheets/camera/HBV-1716WA-VERIFIED-SPECS.md`.

---

# 3. GEOMETRY — ANGLES AND POSITIONS

## 3.0 ⭐ THE CENTRAL RESULT — rigid-group construction

**Merged from the second Claude session 2026-08-07. Independently verified here:
`docs/tof_rigid_group_verify.py`.**

**The ORDER of rotations matters, and gets you a completely different sensor
arrangement from the same two angle numbers.**

| Construction | Inner boundary planes | Seam |
|---|---|---|
| **OLD** — pitch each sensor 22.5° down, then yaw it about world vertical | 17.1263° apart | varies with elevation: **2.02° gap at head height**, 12° wasted overlap at the floor |
| **NEW** — yaw both sensors **LEVEL** to ±22.5°, **group** them, then tilt the whole group 22.5° down about one axis | **0.0000° apart — coincident** | **exactly zero at every elevation** |

Verified normals for the new construction: **+(1,0,0)** and **−(1,0,0)**.

**Why it works:** with a 45° fan the half-width is 22.5°. Yaw a sensor 22.5° off centre
while it's still level and its inner edge lands at exactly 0° — on the centreline. Do
that to both and their inner boundary planes are *the same plane*. A rigid tilt of the
whole group is one rotation applied to both, so a shared plane stays shared.

⚠️ **This requires yaw = FoV/2 = 22.5° EXACTLY.** At the previously-built 22.0° the edges
overlap 1° before the tilt and the construction loses its exactness.

**THE COST — accepted:** the two inner edges are now **parallel** (both at 0° azimuth), so
they never converge. A corridor as wide as the **baseline (35.3 mm)** is seen by neither
sensor **at any range**. **Shrink it by moving the sensors closer together, not by
changing the angle.**

**This supersedes the 9.88° roll solution** in §4.4 — the roll made the seam constant but
tilted the fan edges. The rigid group achieves zero seam with the edges left level.

## 3.1 The locked mount geometry

| Part | Yaw | Pitch |
|---|---|---|
| Camera | **0°** (on the bisector) | **22.5° down** |
| ToF left | **22.5° out** | 22.5° down |
| ToF right | **22.5° out** | 22.5° down |

**Baseline between ToF optical centres: 35.3 mm** (current design).

### As-built values in the older `doubleTOFassem.STEP`, for reference

[VERIFIED] against the 2026-08-05 export, **before** the rigid-group rework:
ToF A yaw 0.00°, ToF B yaw 44.00° (= ±22.0°), both pitch 22.50°, baseline **37.50 mm**,
camera wall face 67.50° tilt / 22.00° yaw. All exact for that build.

**If a figure elsewhere in this document says ±22.0° or 37.50 mm, it describes the older
geometry.** The current design is ±22.5° and 35.3 mm.

**Optical centres in assembly world coordinates:**
```
ToF A   (670.045, 294.917, 1522.646)   axis (-0.0000, -0.3827, +0.9239)
ToF B   (704.789, 294.917, 1508.529)   axis (+0.6418, -0.3827, +0.6646)
midpoint(687.417, 294.917, 1515.588)
```
Both at **identical height** (Y = 294.917) and coplanar in forward distance to **0.068 mm**.

## 3.2 The pod's own frame (in world coordinates)

```
bisector (horizontal)  d = (0.3746,  0.0,     0.9272)
camera axis            N = (0.34609, -0.38268, 0.85661)   22.5° below horizontal
pod "up"               U = (0.14336, +0.92388, 0.35482)   perpendicular to N
pod "right"            R = (0.92718,  0.0,    -0.37461)   horizontal
```

⚠️ **World Z is NOT the pod's forward direction.** The assembly's axes are locked to the
**left ToF sensor** because it was inserted first and auto-fixed at the origin. ToF A's
axis has zero yaw in world, so world "forward" is the left sensor's aim, and the pod
centreline sits **22° off it**. This caused most of the friction on 2026-08-05.

## 3.3 Plane angles — the reference table

**The Top Plane angle measures TILT ALONE and is yaw-independent. It is the clean number
to set and check against.** Front/Right Plane angles mix tilt and yaw.

| Plane | vs Top | vs Front | vs Right |
|---|---|---|---|
| Slanted top (roof) | **22.50°** | 69.22° | 81.76° |
| Camera mounting wall | **67.50°** | 31.06° | 69.75° |
| Pod symmetry plane | **90.00°** | 68.00° | 22.00° |

**Identity that always holds** (direction cosines):
```
cos²(angle to Front) + cos²(angle to Top) + cos²(angle to Right) = 1
```
Two angles fix the third. **One angle never fixes another** — a plane 67.5° from the
Front Plane can be anywhere from 22.5° to 90° from the Top Plane.

## 3.4 Dihedral angles at the joints

Formula — this is the compound-angle relation, `docs/dihedral_calculator.py`:
```
panel normal:  n = ( sin(yaw)·cos(pitch), −sin(pitch), cos(yaw)·cos(pitch) )
angle between: cos θ = n₁ · n₂
dihedral:      180 − θ
```

| Panel A (yaw, pitch) | Panel B | Between normals | Dihedral |
|---|---|---|---|
| camera wall (0, 22.5) | ToF front angled (22, 22.5) | 20.31° | **159.69°** |
| camera wall (0, 22.5) | ToF side vertical (22, 0) | 31.06° | **148.94°** |
| ToF front angled (22, 22.5) | ToF side vertical (22, 0) | 22.50° | **157.50°** |
| camera wall (0, 22.5) | flat vertical front (0, 0) | 22.50° | **157.50°** |
| left ToF front (−22, 22.5) | right ToF front (22, 22.5) | 40.50° | **139.50°** |

**Yaw and pitch compose, they do not add.** Two panels 22° apart in yaw meet at 158° if
both vertical, but at **159.69°** once both are also pitched 22.5° down. Shared pitch
**opens** the joint: 0°→158.00, 22.5°→159.69, 45°→164.49, 60°→169.05.

---

# 4. COVERAGE ANALYSIS — AND A MAJOR CORRECTION

## 4.1 What the separable estimate said (WRONG — do not reuse)

The original analysis treated horizontal and vertical fields as independent ranges:
camera vertical −9.06° to +54.06°, ToF 0° to +45°, therefore 9.06° margin each side, and
44° separation with 45° fans giving 1° of overlap.

**All three of those numbers are wrong.** Yaw and pitch are not separable — the same
compound-rotation effect as the dihedral problem.

## 4.2 The exact containment result — `docs/fov_containment_exact.py`

Testing the ToF cones' four corner rays in the camera's own frame (valid because a square
cone is the convex hull of its corners and the camera frustum is convex):

| | Separable estimate | **Exact** |
|---|---|---|
| Vertical margin | +9.06° | **−0.02°** |
| Horizontal margin | +15.29° | **+14.58°** |

**The two outer-bottom corners fall 0.02° outside the image.** That is 0.23 px — nothing
in itself. **What matters is that the vertical margin is ZERO, not nine degrees.** There
is no headroom; any mounting error puts real depth outside the frame.

The band is also **off-centre**: corners run +22.50° (top) to −31.58° (bottom), so ToF
coverage sits **4.54° below** the camera axis. All spare room is at the top, unused.

**Option if margin is ever needed:** camera at ~27° down instead of 22.5° centres the
band, giving ~4.5° each side instead of 9 and 0. Camera's top ray still stays above
horizontal. Cost: rebuilding the camera wall at 63°.

## 4.3 The seam between the two ToF fans — `docs/tof_seam_vs_elevation.py`

**The seam is not constant with elevation.** Each fan's 22.5° half-width is measured in
the *sensor's* horizontal plane; pitch it 22.5° down and that plane isn't level, so the
fan's width in world azimuth **widens going down and narrows going up**.

| Elevation | Seam |
|---|---|
| **0° (level — head height)** | **2.02° GAP** |
| −2° | 1.42° gap |
| −5° | 0.53° gap |
| −10° | 0.98° overlap |
| −22.5° (the sensor axes) | 5.03° overlap |
| −30° | 7.83° overlap |
| −40° | 12.33° overlap |

**There is a 2° blind wedge dead ahead at eye level**, closing around −7°, and heavy
wasted overlap below. This is a real defect, spotted by Reuben from the CAD.

⚠️ The −44° row in the script output is a **sampling artifact**, not a real gap.

**NOT a fix: rolling the sensors is not enough on its own.** Their fan edges are already
level — all four top corners verified at **y = 0.000 mm**, edge tilt 0.0000°. The azimuth
width of a square pyramid varies with elevation whenever the axis is pitched, whatever
the roll.

## 4.4 The roll solution — SUPERSEDED by §3.0, kept for the record

⚠️ **Do not build this.** The rigid-group construction in §3.0 achieves a zero seam
without the cost described at the end of this section. Retained because the maths is
sound and the failure mode is instructive.

`docs/tof_roll_solution.py`

Rolling each sensor about its own optical axis makes its inner boundary plane **vertical**,
which removes the elevation dependence entirely.

```
sin θ = −tan(FoV/2) · tan(pitch) = −tan(22.5°)·tan(22.5°) = −0.171573
θ = 9.88°, mirrored (one +, one −)
```

**Verified:** both inner faces come out exactly vertical (0.0000° off), and the seam
becomes **constant at every elevation** (4.94° overlap at −5° through −40°).

**To get exactly zero seam, also widen the yaw separation from 44° to 48.94°** — the two
vertical planes are 4.94° apart; opening the yaw by that much makes them coincide. Result
would be no gap and no overlap anywhere.

**Cost, and it is real:** rolling tilts the fan's top edge. Currently the top edges are
perfectly level so the fans reach head height across their full width. Rolled, the upper
boundary becomes a zigzag. **Not yet quantified — the open question is how much azimuth
each option covers at 0° elevation.** Decide on numbers, not description.

## 4.5 Camera–ToF offset — `docs/camera_height_offset.py`, `camera_placement_check.py`

**Parallax is not an error.** It is a fixed constant that Stage 3 measures once and
removes exactly. A 50 mm offset measured to ±2 mm is **exactly as accurate** as a 10 mm
offset measured to ±2 mm — 1.3 px residual at 1 m either way. Offset size does not
degrade accuracy.

What the offset does cost:

| Offset | ToF fan fully in frame beyond | Occlusion band at 0.5 m |
|---|---|---|
| 30 mm | 0.19 m | 6 mm |
| 50 mm | 0.31 m | 10 mm |
| 80 mm | 0.50 m | 16 mm |

**What actually matters, in order:**
1. **RIGIDITY.** A 1 mm shift after calibration hurts more than a 50 mm offset ever will.
2. Solve the offset in the Stage 3 calibration rather than trusting a ruler.
3. Keep camera and ToF at the same 22.5° pitch.

**Two interference constraints:**
- Camera body must stay out of the ToF cones: `lens axis height > 19 + 0.4142 × forward protrusion`
- ToF boards must stay out of the camera's 119.58° view: anything Z mm forward of the lens tip must be `1.7175 × Z` sideways

**Both vanish if the lens tip sits level with or proud of the ToF apertures**, because the
whole camera body is then behind that plane and a field only opens forward. **This is the
design rule.** Verified by rasterising the real board geometry through the calibrated
fisheye model:

| Lens tip placement | Frame filled by own ToF boards |
|---|---|
| Up along the camera's own axis (correct) | **0.00%** |
| Same world Z, straight up in Y (wrong) | **20–44%** |

⚠️ **"Same forward position" ≠ "same Z coordinate."** The sensors look 22.5° down, so the
plane of equal forward distance is tilted 22.5°. Moving straight up in world Y slides the
lens tip **0.383 × h BACKWARDS** along the sight line. Move along **U**, not Y.

**Target lens tip at h = 30 mm along U:** `(691.718, 322.633, 1526.232)`

---

# 5. MANUFACTURING / FIT

| | |
|---|---|
| FDM clearance around a PCB | 0.35 mm (accuracy ±0.2 + elephant's foot + corner overshoot ≈ 0.3) |
| Resin clearance, sliding | 0.10–0.15 mm |
| FDM press fit | 0.10–0.20 mm |
| Wall | 2.8 mm = 3 perimeters at 0.4 mm nozzle |
| Camera bore | **Ø17.80** (radius **8.90**) — barrel is Ø17.10 |
| ⚠️ Currently modelled at | Ø17.30 (r 8.65) — only 0.10 mm radial, **will not print** |
| Camera pilot holes | **Ø1.6 mm × 8 mm deep** for M2 self-tappers |
| Boss OD around a 1.6 mm hole | **≥ 5.6 mm** (2 mm of material each side) |
| Behind each ToF | 10.06 mm of pin, then a DuPont housing — **[TBD], measure one** |

**Screw decisions:**
- **Camera: M2 self-tapping** into Ø1.6 pilots. Mounted once; rigidity matters, not
  reusability. Pilot = major − pitch = 2.0 − 0.4 = 1.6 mm. Buy M2 × 6 or 8.
- **Lid: M3 heat-set inserts.** Opened repeatedly; self-tappers strip in 5–10 cycles.
- Hole diameter for inserts **must come from the insert manufacturer's datasheet** —
  varies by brand. Ruthex and CNC Kitchen publish theirs.

**Camera PCB clears the ToF header pin tips by 10.82 mm** — verified, gap grows with
height (10.8→12.4 mm from h=15 to h=50). **But that excludes DuPont housings**, which add
~10–15 mm plus wire bend. This is the number most likely to bite.

**Depth stack-up back from the ToF aperture plane:**
```
ToF chip top (aperture)     0.00 mm
ToF PCB front face          1.75
ToF PCB back face           3.33
ToF header pin tips        13.39
CAMERA PCB front face      24.21
CAMERA PCB back face       25.90
```

---

# 6. HELMET MOUNT — decided 2026-08-06/07

**Helmet is a mounting platform, NOT protective equipment.** Users walk around. Drilling
through it is acceptable and is the chosen approach. This was explicitly confirmed.

**Chosen product: K&F Concept BH25** low-profile ball head, $32.99 CAD, Amazon.ca
ASIN **B08VW91D74**.

| Spec | Value |
|---|---|
| Top thread | **1/4"-20** |
| Bottom thread | **3/8"-16**, ships with a 3/8"→1/4" converter |
| Load | listed 22 lb in title, **8.17 kg in the detail table** — take 8 kg |
| Weight | **204 g** — heaviest single item in the build |
| Ball diameter | 25 mm |
| Body | aluminium alloy, CNC |
| Includes | QR plate (**proprietary, not Arca**), horizontal + vertical bubble levels |

**Why a ball head over two-axis, revising an earlier recommendation:** the theoretical
argument favoured two-axis (independent locks, no yaw drift, better creep resistance).
Overruled on practical grounds — one bundle that definitely fits beats a better mount
assembled from parts that might not, and 8 kg of clamping on a ~200 g pod will not creep.
Set it once and scribe a line across the joint.

**QR plate details** (from the product photo): flip-handle **1/4"-20** screw sitting in a
**slot** (not a fixed hole), anti-slip rubber pad, corner "safety bolts".

**Attachment decisions:**
- **Through-bolt everything.** Strongest of the three options — plastic is clamped in
  compression between metal, never carries thread load. Beats heat-set inserts, which
  beat self-tapping.
- **Thread size is irrelevant for the through-bolt** — the plate's slot is just a
  clearance hole. **Use M5 from the M2–M5 kit already purchased.** 5 mm shank in a
  ~6.5 mm slot, M5 washer ~10 mm OD is wider than the slot. No imperial hardware needed.
- ⚠️ **The screw head must sit flush in the plate's underside countersink**, or the plate
  won't seat in the clamp. Use a **countersunk M5**, or measure the recess.
- ⚠️ **Remove the rubber pad, or design the pod to bear on metal.** Rubber is
  compressible; the pod could rock a degree or two and quietly void the calibration.
- **Anti-rotation needed** — a single bolt lets the pod spin. Use the slot for a second
  screw, or a dowel pin, or the corner safety bolts if they stand proud.

**To measure when it arrives:** slot length (can two screws fit?), slot width, countersink
depth, screw protrusion above the plate (expect 4–6 mm), whether the flip screw is
removable, whether the panoramic base has play (one reviewer got a loose one — that would
be a return).

**Mount to-do list:**
1. Buy helmet; photograph and measure vent slots
2. Bolt the BH25 through the shell — bolt + fender washer inside
3. Pod bolted to the QR plate, M5 through-bolt + washer + nut, hex pocket in the pod
4. **BNO085 mounted rigidly to the POD**, on the pod side of the adjustment joint — on
   the helmet side it would report the helmet's angle, not the sensors'
5. Index mark across the ball joint to see if it has shifted
6. Cable strain relief at the pod, second anchor on the helmet
7. Weigh the assembly
8. **Re-run Stage 3 extrinsic calibration after the mount is final**

---

# 7. SOLIDWORKS — STATE, TECHNIQUES, AND TRAPS

## 7.1 Files (`cad/solidworks/`)

| File | Note |
|---|---|
| `Assem1double tof test fov.SLDASM` | ⭐ **PRIMARY FILE.** 1839 KB, 2026-08-07 00:03. Contains the rigid-group rework. |
| `doubleTOFassem.SLDASM` | 935 KB, 2026-08-05 23:13 — previous main, superseded |
| `backup_solidworks.ps1` | in `cad/` — run `powershell -File cad\backup_solidworks.ps1` |
| `doubleTOFassem.STEP` | 6551 KB, 2026-08-05 15:38 — last export analysed |
| `TOFSLOT_1mmMARGINS_withrefs_andflattop.SLDPRT` | the ToF case, **2 instances of one file** |
| `Copy of centerV.SLDPRT` | the wedge filling the space between the cases |
| `cam_with_28mmholes.SLDPRT` | camera model, 28.0 mm pitch |
| `camera_hbv1716wa_pitch28.SLDPRT` | generated model, 28.0 pitch |
| `FOV_TOF_L.SLDPRT` / `FOV_TOF_R.SLDPRT` | the ToF cones |
| `SATEL-BOARD.SLDPRT` | ST's board, converted from `J5866.step` |
| `explode_copy/` | safe copy for exploded views |
| `fov_review/` | earlier isolated copy |
| `backup_2026-08-07_0016/` | **latest backup, 48 files, structure preserved** |

⚠️ **The FOV cones are SOLID BODIES, ~790 cm³ each.** They will appear in any STL exported
from the assembly. **Mark them Envelope** (right-click → Component Properties → Envelope)
before any print export. This is still outstanding.

## 7.2 Techniques that work — use these

**Inherit angles, never type them.** Every angle typed is one that can be wrong; an angle
borrowed from a face is correct by construction and stays correct if things move.
- Sketch **on the ToF chip's top face** to build a cone → pitch and yaw come for free
- **Convert Entities** to project an existing edge into a sketch
- **Intersection Curve** (in the Convert Entities dropdown) to get the line where the
  sketch plane cuts a face — for when nothing lies in the plane
- **Reference Geometry → Plane → select a FACE, offset 0** for a coincident plane
- **Up To Surface** end condition instead of a Blind depth

**FOV cone, ToF (square 45×45):** sketch a 1 mm square on the chip face → **Extruded Boss,
Blind, 150 mm, Draft ON, 22.5°, Draft outward ✅**.
- 22.5 not 45 — the spec is total, draft is from the centreline
- "Draft outward" unticked gives a spike, not a cone
- **Far edge = starting square + 0.82843 × reach.** At 150 mm from a 1 mm square:
  **125.26 mm** (displays as 12.53 cm in CGS). Verified correct in the model.

**FOV cone, camera (119.58 × 63.12, not square → draft won't work):** **Loft** between two
rectangles.
- `W = start + 2 × reach × 1.71586`, `H = start + 2 × reach × 0.61374`
- 50 mm → 171.6 × 61.4 · 150 mm → 514.8 × 184.1
- **Aspect check: W/H = 2.796**, independent of reach
- The wide axis must be the camera's 1280 axis

**Angled plane:** needs **TWO references, one of which is a LINE**.
- First Reference: a **horizontal EDGE** (the hinge — it carries the pod's yaw)
- Second Reference: **Top Plane** + **Angle**
- Selecting two planar references gives "Current combination of references and
  constraints are not valid"
- ⚠️ The hinge must be **horizontal**, or the resulting tilt is less than what you typed

**Symmetry plane:** mid-plane between the two ToF chip faces. ⚠️ Two non-parallel planes
have **TWO** bisectors, perpendicular to each other; "flip" only reverses the normal, it
doesn't switch bisectors. **Test: 90.00° to Top Plane** means you have the vertical one.

**Cutting across parts:** Insert → Assembly Feature → Cut. ⚠️ **Do NOT tick "Propagate
feature to parts"** — see §7.4.

## 7.3 Small UI things learned

| Problem | Fix |
|---|---|
| Feature tree gone | **F9** |
| CommandManager auto-collapsing | pushpin at the far right of the tab row |
| Grey window, nothing visible | model sits ~1.7 m from the origin — press **F** (Zoom to Fit) |
| Sketching on a tilted plane is disorienting | **Ctrl+8** (Normal To) |
| Ctrl+8 gives the wrong roll | **Alt + ←/→** rolls the view; then save a custom View Orientation |
| Reference planes not clickable | **View → Hide/Show → Planes** |
| Can't find another open document | **Window** menu, or Ctrl+Tab |
| Two files with the same name | SOLIDWORKS silently refuses the second — rename |
| Measure gives Distance not Angle | one selection is a point/edge, not a face/plane |
| Inside Measure, no Ctrl needed | selections accumulate on plain clicks |
| Select reference planes | click them **in the tree**, not the graphics area |
| Units | status bar bottom-right, or Tools → Options → Document Properties → Units → **MMGS** |
| Instant3D on | can move geometry with a stray drag — turn off for precision work |
| Exploded view lives in | the **ConfigurationManager** tab, not the FeatureManager |
| Sub-assembly explodes as one lump | tick **"Select sub-assembly's parts"** |
| STEP inserted into an assembly can't be floated | 3D Interconnect keeps it linked — **Save As .SLDPRT** first |

## 7.4 Traps that cost real time — do not repeat

**"Propagate feature to parts" broke the model.** Writing an assembly cut into the part
files deleted faces that in-context sketches and the `Parallel1`/`Angle1` mates
referenced. Cascading dangling references. **Recovered by not saving and undoing.**
**Keep assembly cuts at assembly level and export STL from the ASSEMBLY**, not from
individual parts.

**Edit Feature, never delete-and-recreate.** Editing a plane in place keeps everything
downstream attached. Deleting it makes every dependent feature dangle.

**Two instances of one part file take the same cut in part space** — which arrives rotated
differently in each instance. Use **Make Independent**, or an assembly-level cut.

**Backups: copy with folder structure preserved.** Early backups used a flat copy with
`-Force`, so same-named files from different folders overwrote each other
(`CAMERA-MODEL.SLDPRT` from `fov_review` clobbered the main one). Backups from
`2026-08-05_1042` onward preserve structure.

**Assembly world axes are locked to whatever is inserted first.** The left ToF was
auto-fixed at the origin, so world Z is its aim, 22° off the pod centreline. Next time:
insert the *symmetric centre* component first, or mate the first component explicitly to
the assembly planes rather than letting it auto-fix.

## 7.5 Verification method that actually works

**Export a STEP and measure the real geometry.** Every time this session that a face's
"correct" angle was *assumed* rather than *derived*, the assumption was what was wrong.

`python cad/check_user_assembly.py` reads `cad/solidworks/doubleTOFassem.STEP` and
reports angles, coverage, apertures and fit. Re-export before running.

---

# 8. CORRECTIONS MADE — things previously believed that are FALSE

1. **~109°H / 67°V camera FOV** — extrapolated guess. Real: **119.58 × 63.12**.
2. **9.06° vertical margin** — separable approximation. Real: **−0.02°**.
3. **1° ToF overlap** — same approximation. Real: **5.03°** at the axes, and a **2.02°
   GAP** at level.
4. **"centerV is 1.49° wrong"** — RETRACTED. Its faces were assumed to need 67.50/22.50;
   it's a wedge filling a void and its angles are whatever that void demands. **Verified:
   all parts touch at 0.000 mm, no gaps anywhere.**
5. **Far edge 124.26 mm for a 150 mm cone** — omitted the 1 mm starting square. Real:
   **125.26 mm**.
6. **"Pitch axis = symmetry plane ∩ Top Plane"** — that intersection runs *forward*, not
   left-right. The hinge is the line joining corresponding vertices on the two boards.
7. **"Rolling the sensors fixes the seam"** (first version) — sign error made it worse.
   Corrected roll is **9.88°**; the mechanism works but the top edge tilts as a result.
8. **`CAP_PROP_CONVERT_RGB=0` proves no data left the camera** — invalid; OpenCV's DSHOW
   backend pins to RGB24. Re-proved with `ffmpeg -c:v copy`.

---

# 9. OPEN ITEMS

**Blocking Stage 3:**
- [ ] Finish the pod: camera mount, lid, wire routing
- [ ] Ultrasonic bracket (HC-SR04 on top — not started)
- [ ] Electronics box: DevKitC-1 + USB hub + haptics + IMU + ToF pull-ups. **No battery —
      always tethered to the laptop in a backpack**
- [ ] Helmet interface per §6

**Decisions pending:**
- [ ] Camera at 22.5° (current, zero vertical margin) or 27° (centred, 4.5° each side)
- [ ] Camera hole pitch: 28.0 or 28.2 — **re-measure one hole**
- [ ] Whether to shrink the 35.3 mm baseline to narrow the blind corridor

**~~The ToF seam~~ — RESOLVED** by the rigid-group construction, §3.0. Zero seam at every
elevation, verified. The remaining consequence is the constant 35.3 mm blind corridor,
which is accepted.

**⚠️ Known live defect — reference fragility:** `Part13`'s `3DSketch1` still holds
external references to the TOFSLOT parts. **Every TOFSLOT edit re-breaks it, plus a mate
and a sketch.** Four separate reference cascades have been triggered so far. Either lock
the external refs (right-click → List External Refs → Lock All) once the geometry is
settled, or rebuild that sketch without component references.

**Small and concrete:**
- [ ] Open the camera bore from Ø17.30 to **Ø17.80**
- [ ] Mark all three FOV cones as **Envelope**
- [ ] Measure a DuPont housing — the last `[TBD]`
- [ ] Relieve the two 0.080 mm header pinch points: pocket 0→39 mm along the length,
      16.5→20 mm band, 0.5 mm deep
- [ ] Measure lens tip → casing outer face; tip must be proud
- [ ] Test-print one boss before committing to a full pod print

---

# 10. FILE INDEX

**Analysis scripts — `docs/`**

| Script | Answers |
|---|---|
| `fov_containment_exact.py` | do the ToF fans really fit in the image? (exact corner test) |
| `tof_seam_vs_elevation.py` | where the fans gap and where they overlap |
| `tof_roll_solution.py` | the 9.88° roll that makes the seam constant |
| `dihedral_calculator.py` | what angle two angled panels meet at |
| `camera_target_position.py` | exact lens tip target, and the same-Z trap |
| `camera_placement_check.py` | the two interference constraints |
| `camera_height_offset.py` | why mounting height barely matters |
| `aperture_calculator.py` | how big each sensor's window must be |
| `camera_tof_baseline.py` | parallax vs baseline |
| `tof_tilt_chart.py`, `tof_central_gap.py`, `tof_overlap_at_range.py` | earlier coverage work |

**CAD — `cad/`**

| File | Purpose |
|---|---|
| `check_user_assembly.py` | verifies the exported STEP: angles, fit, apertures, writes FOV cones |
| `components.py` | every dimension, provenance-tagged |
| `sensor_pod.py` | the generated pod (superseded by Reuben's own SOLIDWORKS build) |
| `fov_check.py` | cone ∩ plastic obstruction check |
| `explode_animation.py` | renders the exploded GIF from the STEP |
| `DESIGN-REFERENCE.md` | measured numbers + SOLIDWORKS how-to |
| `VERIFY-IT-YOURSELF.md` | every number + how to check it yourself |
| `HOWTO-BUILD-FOV-CONES.md` | building cones by inheriting the angle |
| `HOWTO-ANGLED-BORE.md` | the camera bore and placement constraints |
| `NEXT-SESSION.md` | shorter session-to-session notes |
| `render/explode.gif` | 72-frame exploded animation |

**Datasheets — `docs/datasheets/`**
- `camera/HBV-1716WA-VERIFIED-SPECS.md` — the full 1080p investigation
- `camera/OV2710_CSP3_full_datasheet_v1.1.pdf`
- `tof/satel-step/J5866.step` — ST's official board CAD, 117 solids

**ST documents (in `~/Downloads`)**
- `um3109-...pdf` — UM3109 user manual. §4.4 Table 2: **4×4 max 60 Hz, 8×8 max 15 Hz**.
  §4.5: Continuous mode gives better max range than the default Autonomous. §4.9 target
  order default STRONGEST. §4.10 two targets need **600 mm** separation to resolve.
- `satel-vl53l8.pdf` — "accurate ranging up to 400 cm with a 65° diagonal FoV"

**400 cm is a ceiling, not a working figure** — best case is continuous mode, good
reflective target, low ambient IR.
