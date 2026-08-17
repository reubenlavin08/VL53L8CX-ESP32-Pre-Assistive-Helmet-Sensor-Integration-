# Verify it yourself — every number I gave you, checked in SOLIDWORKS

Don't take any of the figures below on trust. Each one has a procedure next to it.
If your measurement disagrees with mine, **your measurement wins** — tell me and I'll
find my mistake.

Everything I computed came from `cad/solidworks/doubleTOFassem.STEP`, the file you
exported at 16:57 on 2026-08-04. The script is `cad/check_user_assembly.py`.

---

## FIRST — a correction about which axis is "vertical"

You asked about "the same vertical coordinate in the **z-axis**". In your model,
**vertical is Y, not Z.**

**How I know, and how you can check:** I computed the downward pitch two ways.
Treating Y as vertical gives **exactly 22.50°** for both boards — the number you
designed to. Treating Z as vertical gives 67.5°, which is nothing you ever asked
for. Only one of those can be right.

**Check it in SOLIDWORKS:**
1. Look at the little origin triad in the bottom-left corner of the graphics area.
2. Press **Ctrl+7** (Isometric), then **Ctrl+1** (Front).
3. In Front view, the axis pointing **up the screen** is the vertical one. Read its
   label off the triad.

SOLIDWORKS' default Front Plane is the XY plane with **Y up** — which is why it
came out this way. This matters because if you go set the camera's height using a
Z coordinate, you'll move it sideways instead of up.

---

## 1. Are both ToF sensors at the same height? — **YES, exactly**

| | |
|---|---|
| Board A optical centre | (670.045, **294.917**, 1522.646) |
| Board B optical centre | (704.789, **294.917**, 1508.529) |
| Vertical difference | **0.000 mm** |

**Check it yourself:**
1. **Evaluate → Measure**.
2. Click the **top face of the VL53L8CX chip** on board A (the small 6.4 × 3.03 mm
   package near one end — zoom right in, it's the only thing that shape).
3. Ctrl-click the same face on board B.
4. In the Measure box, click the **arrow/dropdown next to the distance readout** and
   turn on **Delta X / Delta Y / Delta Z**.
5. **Delta Y should read 0.00 mm.** Delta X and Delta Z will not be zero — that's
   the 44° splay, and it's correct.

*Why I used the chip's top face:* that's the aperture plane — the surface light
actually enters. Measuring from the PCB instead would be off by 1.75 mm + half the
board thickness.

---

## 2. Pitch — **22.50° down, both boards**

**Check it yourself:**
1. **Evaluate → Measure**.
2. Click the **top face of the VL53L8CX chip**.
3. Ctrl-click the **Top Plane** in the feature tree (expand the assembly's top node
   if you can't see it; if it's hidden, right-click → Show).
4. Read the **Angle** value. It should be **22.50°**, or its complement 67.50°
   depending on which normal SOLIDWORKS picks — both mean the same thing.

Do it for both boards. They should match to two decimals.

---

## 3. Yaw splay — **44.00° between the two, i.e. 22.00° each**

**Check it yourself:**
1. **Evaluate → Measure**.
2. Click the VL53L8CX top face on board A.
3. Ctrl-click the VL53L8CX top face on board B.
4. Read **Angle**: **44.00°**.

That is the *total* angle between them, so each sits 22.00° off the centreline —
exactly what you set. ✓

---

## 4. Baseline between the sensors — **37.50 mm**

**Check it yourself:** same Measure, two chip top faces, read **Distance**
(not Delta) → **37.50 mm**.

⚠️ **This is 3.5 mm wider than the 34 mm in `DESIGN-REFERENCE.md`.** Not an error —
just a consequence of how your slots ended up spaced. The one thing it changes:

**The blind corridor dead ahead closes at 2.15 m instead of 1.95 m.** Between the
sensor and 2.15 m there is a narrow strip straight in front that *neither* ToF
covers. The camera still sees it; it just has no measured distance there.

If you want that back to 1.95 m, bring the two boards 3.5 mm closer together.
I'd leave it — 20 cm of difference in where the corridor closes doesn't change
anything you'd actually notice.

---

## 5. Apertures — **clear, but the test is not yet meaningful**

The 45° cone from each sensor hits **0.000 cm³** of your plastic. But look at *why*:

> nearest plastic to the optical centre: **8.27 mm**

The sensors are looking out into open air. **There is no front wall in front of them
yet** — your three printed bodies are the slot/rail carriers, sitting beside and
behind the boards, not in front. Nothing can obstruct a view when nothing is there.

So: **no aperture problem today, and no aperture verified either.** The moment you
add a front face with a window in it, re-run `python cad/check_user_assembly.py`
and it becomes a real test.

**When you do cut that window, the size it needs is:**

opening = 1.0 mm + 2 × depth × tan(22.5°) = **1.0 + 0.83 × depth**

| Recess depth behind the outer surface | Minimum opening | With 1 mm tolerance |
|---|---|---|
| 2 mm | 2.66 mm | 4.66 mm |
| 4 mm | 4.31 mm | 6.31 mm |
| 6 mm | 5.97 mm | 7.97 mm |
| 10 mm | 9.28 mm | 11.28 mm |

**Check your own version in SOLIDWORKS:**
1. **View → Display → Section View**, pick a plane through the sensor centre.
2. **Measure** from the chip's top face to the wall's **outer** face → that's *depth*.
3. **Measure** the hole across the **outer** face — the outside, not the inside. A
   straight bore is narrowest where it starts.
4. Compare against the table.

---

## 6. Fit — ⚠️ **0.080 mm at two spots**

### Which parts, exactly

They are **not** SMD chips — I was imprecise. They are the **black plastic bodies of
the two 0.1" pin headers** on the **back** of the board (the side away from the ToF
chip). Measured in board-local coordinates:

| | Header 1 | Header 2 |
|---|---|---|
| Along the 51.5 mm length | 0.49 → 28.55 mm | 30.97 → 38.71 mm |
| Length | 28.07 mm (11 pins × 2.54) | 7.75 mm (3 pins × 2.54) |
| Across the 19.5 mm width | 16.98 → 19.52 mm | 16.98 → 19.52 mm |
| Below the PCB back face | 0.10 → 2.64 mm | 0.10 → 2.64 mm |
| **Gap to your plastic** | **0.080 mm** | **0.080 mm** |

Both hug the **same long edge** (the W≈19.5 side) and both hang **2.64 mm below the
board**. Identical on both ToF boards, which makes sense — same part, same slot.

The metal pins go a further 10.06 mm down and are separate solids; they're not the
pinch. It's the plastic shroud.

### What's actually happening

Your 1 mm margin is measured off the **PCB outline**, and against the PCB it's
holding perfectly — 1.000 mm all round, exactly as designed. ✓

The problem is that the header shroud **sticks out past the PCB in a direction your
outline offset never accounted for**: down, off the back face. Your slot floor
passes under the board and arrives 0.080 mm from those shrouds.

So this isn't a mistake in your margin. It's a feature the margin doesn't cover.

### Why 0.35 mm — and you're right to push back

0.35 mm is **not a universal number**. It's the figure for *one specific case*: a
sliding fit on FDM. Here's where it comes from:

| Source of error | Typical size |
|---|---|
| FDM dimensional accuracy | ±0.10 – 0.20 mm |
| Elephant's foot (first layers squish out) | 0.05 – 0.15 mm |
| Extrusion width overshoot on inside corners | 0.05 – 0.10 mm |
| **Realistic worst case stack-up** | **~0.3 mm** |

0.35 mm isn't "space I want" — it's "the amount the print will differ from the model."
At 0.080 mm nominal, a normal-quality print lands you at **negative** clearance:
the faces touch, and the board won't slide in.

**The number changes with the process and the job:**

| Situation | Clearance |
|---|---|
| FDM, sliding fit (this one) | 0.30 – 0.40 mm |
| FDM, press fit / never moves | 0.10 – 0.20 mm |
| Resin (SLA/MSLA), sliding | 0.10 – 0.15 mm |
| Resin, press fit | 0.05 mm |

**So the honest answer:** if you're printing resin, 0.15 mm is enough and 0.080 is
still slightly too tight. If FDM, you want 0.3 mm+. Either way 0.080 is under the
line — but by much less than my first message implied.

And note this is a **slide-in** joint down the board's full length. Clearance that
would be fine on a face that just sits there has to hold over 28 mm of travel here.

### How to measure it yourself

**Evaluate → Clearance Verification** — this is the right tool, not Interference
Detection. Interference only finds solids that actually *overlap*; yours don't, they
just come close, so Interference Detection reports nothing and you'd think you're fine.

1. **Evaluate → Clearance Verification**
2. **Selected items**: click the SATEL board, then Ctrl-click your slot part
3. **Acceptable clearance**: type **0.35** (or whatever you settle on above)
4. **Calculate**

Everything it lists is *closer than* your threshold. Click each result and it
highlights the two faces in the graphics area, so you can see exactly where.

**To measure one spot by hand instead:** **Evaluate → Measure**, click the header's
outer face, Ctrl-click your slot's inner face, read **Distance**. Set the dropdown to
**Minimum Distance** — the default centre-to-centre reading is not what you want here.

### The fix

Don't widen the whole slot — you'd lose the location accuracy the 1 mm outline is
giving you. Instead **cut a local relief pocket** where the two shrouds run:

- along the length: **0 → 39 mm** (covers both, with a bit of run-out)
- across the width: the **16.5 → 20 mm** band
- depth: **0.5 mm** into your slot floor

The PCB outline keeps doing the locating; the headers just get somewhere to go.

---

## 7. Camera height above the ToF — **3–5 cm is fine**

Full numbers: `python docs/camera_height_offset.py`

**The counter-intuitive part:** parallax is *not* an error. It's a fixed geometric
constant. Stage 3 measures it once, and the fusion maths removes it exactly. A 50 mm
offset measured to ±2 mm is **exactly as accurate** as a 10 mm offset measured to
±2 mm — 1.3 px of residual at 1 m either way. Offset size doesn't degrade anything.

What the offset *does* cost, and both are small:

| Offset | ToF fan fully in frame beyond | Occlusion band at 0.5 m |
|---|---|---|
| 30 mm | 0.19 m | 6 mm |
| 50 mm | 0.31 m | 10 mm |
| 80 mm | 0.50 m | 16 mm |

At 50 mm, everything past 31 cm is fully covered — closer than the sensor's useful
warning range anyway.

**What actually matters, in order:**
1. **Rigidity.** If the camera shifts 1 mm relative to the ToF after you calibrate,
   that hurts more than a 50 mm offset ever will. Build it stiff.
2. **Solve the offset in the Stage 3 calibration**, don't trust a ruler.
3. **Keep both at the same 22.5° pitch.** That's what centres the ToF band in the
   frame with symmetric 9.06° margins.

**So: put the camera wherever the mount is stiffest and the wiring is cleanest.**
Height is not the constraint you thought it was.

**Check the margin claim yourself:** the camera's vertical view is 63.12°
(measured, `camera/calibration_720p.txt`), the ToF's is 45° (ST DS14161 Table 2).
Both pitched 22.5°. (63.12 − 45) / 2 = **9.06°** spare each side. Frame-exit
distance = offset ÷ tan(9.06°) = offset ÷ 0.1595.

---

## 8. Getting the fields of view into YOUR assembly

**What went wrong the first time:** I exported the whole thing — your two ST boards,
your three printed bodies and both cones — as one 22 MB nested STEP. SOLIDWORKS
opened it as an **empty assembly**. The file is fine (I re-imported it: 239 solids,
all present), the importer just didn't swallow it. Pressing F did nothing because
there was genuinely nothing there to zoom to.

**The better route** — put the cones into the assembly you already have:

| File | Size | Use |
|---|---|---|
| `step\USER_REF_fov_A.step` | 344 KB | insert into your assembly |
| `step\USER_REF_fov_B.step` | 331 KB | insert into your assembly |
| `step\USER_assembly_at_origin.step` | 23 MB | fallback, everything, moved to origin |

The two cone files carry **absolute coordinates**, so they land on their sensors
exactly — no mating, no alignment.

**Do this in the COPY, not your working file.** There is now an isolated copy at:

```
cad\solidworks\fov_review\doubleTOFassem.SLDASM
```

Every part it needs was copied alongside it, plus both cone files. Your real
`cad\solidworks\doubleTOFassem.SLDASM` is untouched (still stamped 01:21 AM).

⚠️ **One caveat:** SOLIDWORKS stores reference paths inside the assembly, so the copy
may still load the *original* part files rather than the ones sitting next to it.
That's harmless **as long as you only insert components and never edit a part inside
this copy** — inserting changes the assembly file only, and the assembly file is the
copy. If you want to edit geometry, do it in your real file.

**Click by click:**

1. Open **`fov_review\doubleTOFassem.SLDASM`** (the copy — already opening).
2. **Insert → Component → Existing Part/Assembly**
3. **Browse** → set the file-type dropdown to **STEP (\*.step;\*.stp)** → pick
   `USER_REF_fov_A.step`
4. ⚠️ **Click the green ✓ in the PropertyManager. Do NOT click in the graphics area.**
   Clicking in the graphics area drops it wherever your cursor was. The ✓ places it
   at the assembly origin, which is what preserves its absolute position.
5. Repeat for `USER_REF_fov_B.step`.

**Make them see-through:** right-click the component → the **beach-ball
(Appearances)** icon → **Transparency** slider to about 70%.

**Make them reference-only** (this is the "ghost part" you asked about):
right-click the component → **Component Properties** → tick **Envelope**. An envelope
component is reference geometry by SOLIDWORKS' own definition — excluded from the
BOM, excluded from mass properties, and never treated as a real part. That is the
built-in version of what you described.

**Sanity check that they landed right:** the cone's sharp tip should sit exactly on
the ToF chip's top face. If it's floating in space, you clicked in the graphics area
at step 4 — undo and use the ✓.

---

## Re-running the whole check

```
python cad/check_user_assembly.py
```

Re-export the STEP from SOLIDWORKS first (**File → Save As → STEP**, same filename),
then run it. It writes `cad/step/USER_doubleTOFassem_FOV.step` — your assembly with
the 45° fields of view attached to each sensor as wireframe cones, nested inside the
sensor nodes so they move together. They're named `REF_fov_*` and are never printed.
