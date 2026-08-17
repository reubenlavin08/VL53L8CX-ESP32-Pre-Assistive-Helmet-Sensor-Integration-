# Extrinsics input — measured points

Fill in the XYZ numbers. Everything else is computed from them.

**Measure in the DEFAULT assembly frame.** Don't measure relative to `CS_CAM` —
just click points and read raw X/Y/Z. The camera frame is built from the numbers
afterwards.

---

# How to read a point's XYZ

1. `Tools → Evaluate → Measure`
2. **Set units to mm** — the dropdown at the bottom of the dialog. The status bar
   was showing `CGS` (centimetres); everything here assumes **mm**.
3. Click a **corner** of the part
4. Read **X, Y, Z** off the dialog
5. Click empty space to clear, then click the next corner

**Corners are vertices — directly clickable.** No Point feature, no Face Center,
no axis needed. That's why this method is used instead of face centres.

---

# What to click: three corners of the front face

For each sensor, click **three corners of the front (optical) face**, going
**clockwise as seen from the front** — i.e. standing where the sensor is looking,
facing back at it.

Three corners of a rectangle give:

| From | I get |
|---|---|
| the three points' plane | the **boresight** direction |
| the first edge's direction | the **roll** |
| midpoint of the diagonal | the **centre** |

That's the full 6 DOF. Nothing else needed.

**Name the first corner by a physical landmark** — "the corner nearest the ribbon
connector", "the corner by the mounting hole". Anything repeatable. Then just go
clockwise from there.

---

# ToF SENSOR — LEFT

First corner is near: `________________________`

| | X | Y | Z |
|---|---|---|---|
| **L-a** (first) | | | |
| **L-b** (clockwise) | | | |
| **L-c** (clockwise) | | | |

# ToF SENSOR — RIGHT

First corner is near: `________________________`

| | X | Y | Z |
|---|---|---|---|
| **R-a** (first) | | | |
| **R-b** (clockwise) | | | |
| **R-c** (clockwise) | | | |

# CAMERA

The lens is round, so use the **camera PCB** for orientation plus the lens centre
point you already made.

First corner is near: `________________________`

| | X | Y | Z |
|---|---|---|---|
| **C-a** (first, PCB corner) | | | |
| **C-b** (clockwise) | | | |
| **C-c** (clockwise) | | | |
| **C-lens** (`Point1`, lens face centre) | | | |

The three PCB corners give the board plane and the roll; the lens axis is normal
to the board. `Point1` puts the origin on the optical axis rather than the board
centre.

---

## ⚠️ Same rotation direction on all three

Clockwise-from-the-front, every time. If one device gets measured
anticlockwise, its frame comes out **mirrored** — and the maths still solves
cleanly, so nothing looks wrong until depth lands on the wrong half of the image.

**Consistency matters more than which corner you start at.**

---

## Sanity checks before sending

- Distance **L-a → L-b** should equal the sensor package's real edge length.
  If it's out, a corner was clicked on the pod wall instead of the sensor.
- **C-lens → L-centre** and **C-lens → R-centre** should be roughly equal — the
  sensors are symmetric about the camera.

---

## Optional but useful: the boresight angles

While you're in there, measure each sensor's front face against the **Front, Top
and Right planes** — three angles per sensor.

Not needed for the maths. Valuable because they're **directly comparable to the
design**: ±22.5° yaw, 22.5° group tilt. A boresight that reads 24° when you
designed 22.5° is instantly visible, whereas a mis-clicked XYZ is invisible until
the maths falls over.

Free error check on each set:

```
cos²(Front) + cos²(Top) + cos²(Right) = 1
```

⚠️ Angles have **no sign** — 67.5° to the Front plane reads the same tilted
forward or back. That's why the corners are the source of truth and the angles are
only a check.

---

# What happens next

From these numbers:

- rigid transform ToF-left → camera and ToF-right → camera (6 DOF each)
- actual yaw/pitch/roll of each sensor vs the designed ±22.5° / 22.5°
- a direction-cosine check that catches a mis-clicked corner before it silently
  corrupts the calibration

⚠️ **This is the CAD nominal, not the calibration.** It's the initialisation and
the sanity check. Real extrinsics come from data — print tolerance, board slop in
the slots, SPAD die placement inside the package, and lens-axis-vs-housing error
are all invisible to CAD, and at 4 m **1° of error = 70 mm**.

The measured calibration uses a planar target: hold a large flat board at 6–10
poses, fit a plane to all 64 ToF points, get the same plane from the camera via
the checkerboard, then solve for the transform making the plane pairs agree. The
8×8 grid is too coarse (~5.6°/zone) to localise a point target, which is why it's
planes rather than corners.
