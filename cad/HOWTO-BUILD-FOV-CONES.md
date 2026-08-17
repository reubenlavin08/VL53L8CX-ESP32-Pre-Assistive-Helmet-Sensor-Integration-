# Building the field-of-view cones yourself, in SOLIDWORKS

The whole trick: **don't type any angles.** Sketch on the sensor's own face, and
SOLIDWORKS derives the direction from the geometry. Type an angle and you're
trusting your arithmetic; borrow the face and you're trusting the model.

This also makes the cone **move with the sensor** automatically. No mates.

---

## The idea first, in plain terms

A time-of-flight sensor sees a square pyramid of space spreading out from its
window. The VL53L8CX's is **45° wide and 45° tall** (ST DS14161, Table 2).

"45° wide" means 22.5° either side of straight ahead. So if you start with a tiny
square at the sensor window and push it forward while flaring every side outward at
**22.5°**, you have drawn exactly what the sensor can see.

SOLIDWORKS has that exact operation built in: **Extrude with Draft.** Draft angle is
measured from the push direction — so a 22.5° outward draft *is* the 45° field.

That is the whole build. One sketch, one extrude.

> **Why 22.5 and not 45?** The 45° spec is the *total* angle, edge to edge. Draft is
> measured from the centreline. Half of 45 is 22.5. Getting this backwards gives you
> a 90° cone and everything downstream looks wrong.

---

## Build it — 8 steps

Work in **`fov_review\doubleTOFassem_FOVREVIEW.SLDASM`**, not your main file.

### 1. Start a new part inside the assembly
**Insert → Component → New Part**

Your cursor becomes a crosshair — SOLIDWORKS is asking where to put its first sketch.

### 2. Click the ToF chip's top face
Zoom right in on one SATEL board. The **VL53L8CX** is the small black package near
one end — **6.4 × 3.03 mm**, the only thing that shape on the board. Click its
**top face** (the flat one facing out, away from the PCB).

You are now editing a new part, in-context, with a sketch open on that face.

**This single click is what does all the work.** That face is the aperture plane, so
its normal is the optical axis. Both the 22.5° down-pitch and the 22° out-yaw are
now inherited from the board itself. Nothing to type, nothing to get wrong.

### 3. Sketch a small square on it
Draw a **1 mm × 1 mm** square roughly over the chip.

Now centre it properly:
- Ctrl-click the square's **centre point** and the chip face's silhouette
- or dimension it symmetric about the face's midpoint

1 mm is about the size of the real optical window, so this isn't a fudge — it's the
aperture.

### 4. Exit the sketch
Click the **exit-sketch corner** (top-right of the graphics area) or press **Ctrl+Q**.

### 5. Extrude it with draft
**Features → Extruded Boss/Base**

| Setting | Value |
|---|---|
| Direction | **away from the board** (use the flip arrow if it goes into the PCB) |
| End condition | **Blind** |
| Depth | **150 mm** |
| **Draft** | **ON** — click the draft icon |
| **Draft angle** | **22.5°** |
| **Draft outward** | ✅ **ticked** |

⚠️ **"Draft outward" is the one people miss.** Unticked, the pyramid tapers *inward*
and you get a spike instead of a view cone. If it looks like a needle, that's this.

Click ✓.

### 6. Leave the part
Click the **confirmation corner → Edit Component** to return to the assembly.

### 7. Make it transparent
Right-click the new part in the tree → the **beach-ball (Appearances)** icon →
**Transparency** slider to about **75%**.

### 8. Make it reference-only, so it can never be printed
Right-click the part → **Component Properties** → tick **Envelope**.

An Envelope component is SOLIDWORKS' own reference-geometry flag: excluded from the
bill of materials, excluded from mass properties, ignored by exports. That's the
"ghost part, material = air" idea you described — it's a real built-in feature.

Rename it in the tree to **`REF_fov_tof_A`** so it's obvious what it is.

### Repeat for the second sensor.

---

## Check your work — 3 measurements

Don't trust it because it looks right. Cones look right from almost any angle.

**a) Is the spread actually 45°?**
**Evaluate → Measure** → click **two opposite slanted faces** of the pyramid.
Angle should read **45.00°**.

**b) Is it pointing where the sensor points?**
**Measure** → the pyramid's **flat end face** (the big one, 150 mm out), then the
**chip's top face**. Angle should read **0.00°** — they're parallel, which is only
true if the cone is square to the sensor.

**c) Is it the right size at the far end?**
Click one edge of the big flat end face and read **Length**. For a 1 mm starting
square extruded 150 mm, it should be **125.26 mm** (SOLIDWORKS shows `12.53cm` if
your units are CGS).

> Where that comes from:
> `far edge = starting square + 2 × reach × tan(22.5°)`
> `= 1.0 + 2 × 150 × 0.41421 = 1.0 + 124.26 =` **125.26 mm**
>
> ⚠️ **Don't forget the starting square.** The spread alone is 124.26 mm, but the
> extrude begins from a 1 mm square rather than a point, so the finished edge is
> 1 mm longer. Sketch a different starting square and this number moves with it.
>
> If you measure ~300 mm, your draft was 45° instead of 22.5°. If you measure ~62 mm,
> the draft got applied to one side only.

**d) Does it move with the sensor?**
Drag the ToF board slightly. The cone should follow, then **Ctrl+Z**. If it doesn't
follow, the in-context reference didn't take — delete and redo from step 1, making
sure you clicked the chip face and not a plane.

---

## How long should the cone be? (why 150 mm and not 4000)

**150 mm is a drawing choice, not a spec.** The sensor really does range to 400 cm.
I picked 150 mm so the cone and the hardware fit on screen together.

| Reach | Spread alone | **Far edge, from a 1 mm square** | What it looks like |
|---|---|---|---|
| 100 mm | 82.84 mm | **83.84 mm** | about the size of the pod |
| **150 mm** | 124.26 mm | **125.26 mm** | pod still clearly visible |
| 300 mm | 248.53 mm | **249.53 mm** | pod getting small |
| 1000 mm | 828.43 mm | **829.43 mm** | pod is a speck |
| **4000 mm** | 3313.71 mm | **3314.71 mm** | a 3.3 m square — pod is 1/44th of the view |

Formula: `far edge = starting square + 0.82843 × reach`

The **far edge** column is what SOLIDWORKS reports when you measure the end face.

### The part that actually matters

**For checking whether the housing blocks the sensor, the length is irrelevant.**

The cone has perfectly straight sides. If the plastic clips the field, it clips it
**within the first few millimetres**, right at the aperture. Extending the cone from
150 mm to 4000 mm cannot reveal a new collision — there is no plastic out at 3 m.

So for the question the cone exists to answer, 150 mm is not a shortcut. It is the
complete answer, and 4000 mm is the same answer drawn 27× larger.

### When 4000 mm IS the right length

Different question — *coverage*: where do the two fans cross, does the pair clear a
doorway, how much floor is covered at walking distance. Then you want real range.

**Best of both:** build it at 150 mm, then just edit the extrude depth to 4000 when
you want the room view and back again. It's one number in one feature — double-click
the extrude in the tree, retype the depth, rebuild. Nothing else changes.

### About that 400 cm — it's real, but conditional

Verified from ST's own documents, not the marketing line:

- **UM3109 p1:** "8x8 zones (64 zones) and can work at fast speeds (60 Hz) up to
  400 cm"
- **SATEL-VL53L8 datasheet p1:** "accurate ranging up to 400 cm with a 65° diagonal
  FoV"

⚠️ But **UM3109 Table 2** (p9) gives the frequency limits, and they are not the same
for both resolutions:

| Resolution | Min freq | **Max freq** |
|---|---|---|
| 4×4 (16 zones) | 1 Hz | **60 Hz** |
| **8×8 (64 zones)** | 1 Hz | **15 Hz** |

So the "60 Hz" in that headline sentence belongs to **4×4**. In the 8×8 mode you're
using, the ceiling is **15 Hz**.

Also **UM3109 §4.5**: max ranging distance and ambient immunity are better in
**Continuous** mode, but the default is **Autonomous** (VCSEL only fires part of the
time, to save power). 400 cm is a best case — continuous mode, a good reflective
target, low ambient IR. Outdoors in sunlight against dark clothing you will get far
less. Treat 400 cm as the ceiling, not the working figure.

---

## The camera cone — different, and here's why

The camera is **119.58° × 63.12°** (measured, `camera/calibration_720p.txt`, RMS
0.30 px). Those two numbers are different, so **draft will not work** — draft applies
the same angle all the way round.

Use a **Loft** between two rectangles instead:

1. Sketch on the **lens tip face**: a small rectangle, roughly 2 × 1 mm.
2. **Reference Geometry → Plane**, offset **150 mm** from that face, out in front.
3. Sketch on the new plane: a rectangle **514.76 mm wide × 184.12 mm tall**,
   centred on the same axis.
4. **Features → Lofted Boss/Base**, pick the two rectangles.

> Where those come from:
> width = 2 × 150 × tan(119.58/2) = 2 × 150 × 1.71586 = **514.76 mm**
> height = 2 × 150 × tan(63.12/2) = 2 × 150 × 0.61374 = **184.12 mm**

⚠️ Make sure the wide dimension lines up with the camera's **wide** axis. A sensor
rotated 90° is the classic way to get a cone that's confidently, precisely wrong.

**Check:** Measure between two opposite side faces → **119.58°**. Top and bottom →
**63.12°**.

---

## One thing the cone will not tell you

A field-of-view cone shows where the sensor *could* see. It doesn't show what it can
*actually* see once the housing is around it — for that, the cone has to be
intersected with the plastic.

That's what `cad/check_user_assembly.py` does. Re-export a STEP and run it whenever
you change the enclosure. Right now it reports both sensors clear, but only because
there's no front wall in front of them yet.
