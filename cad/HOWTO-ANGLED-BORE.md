# Cutting the camera bore at 22.5°, without typing 22.5

Same principle as the FOV cones: **borrow the angle from the geometry instead of
entering it.** Every angle you type is a number you can get wrong; every angle you
inherit from a face is correct by construction.

---

## The problem

The camera sits at 22.5° down. Its lens barrel is a Ø17.1 mm cylinder pointing along
that tilted axis. You need a hole through your housing wall that is **coaxial with
the barrel** — not perpendicular to the wall.

Cut it perpendicular to the wall and the barrel binds. Cut it at a typed 22.5° and
you're relying on the wall being at exactly the angle you assumed.

---

## Method — 5 steps

**Prerequisite:** the camera model must be in the assembly, positioned. If it isn't,
insert `cad/step/camera_hbv1716wa.step` and mate it first. The bore is derived from
the barrel, so the barrel has to exist.

### 1. Make a plane square to the lens
**Reference Geometry → Plane** → click the camera's **PCB front face** (or the lens
tip face — either works, both are square to the optical axis).

Set offset to anything convenient, or zero. **The plane arrives at 22.5° for free**,
because the camera is already at 22.5°.

### 2. Sketch on that plane

### 3. Steal the barrel's exact circle
Click the **barrel's circular edge** → **Convert Entities**.

This projects the real Ø17.1 mm circle into your sketch, **on the real axis**. Not a
circle you drew at coordinates you measured — *the* circle, linked to the part. If
the camera ever moves, this follows.

### 4. Add clearance
With the circle selected → **Offset Entities** → **0.35 mm**, direction **outward**.

That gives Ø17.8. Reasoning: 0.35 mm radial is the FDM figure from
`VERIFY-IT-YOURSELF.md` §6, and FDM holes print *undersized* anyway, so erring
generous is right for a bore.

Delete the original converted circle, or make it construction geometry — you want to
extrude the offset one.

### 5. Cut it
**Features → Extruded Cut → Through All**

Direction is automatically normal to your sketch plane, which is the lens axis.
Done.

The opening in the wall comes out as an **ellipse**, because a round hole through an
angled wall is an ellipse. That's correct — don't try to "fix" it.

---

## Check it

1. **Evaluate → Measure**, click the **bore's cylindrical face**, then the
   **barrel's cylindrical face**. Angle should read **0.00°** — coaxial.
2. **Section View** through the lens axis: you should see clear air all the way
   around the barrel, no pinch on either side of the wall.
3. Bore diameter **17.80 mm**.

---

## Related: keep the lens tip proud

Recessing the lens is the expensive mistake. At 119.58° horizontal, the half-angle is
59.79° and tan = 1.7175, so **every 1 mm of recess costs 3.4 mm of opening width**.

| Lens tip recessed by | Opening width needed | Opening height needed |
|---|---|---|
| 0 mm | 17.1 mm (just the bore) | 17.1 mm |
| 1 mm | 20.5 mm | 18.3 mm |
| 2 mm | 24.0 mm | 19.6 mm |
| 3 mm | 27.4 mm | 20.8 mm |
| 5 mm | 34.3 mm | 23.2 mm |

If the tip sits **at or proud of** the outer surface, none of this applies — the wall
physically cannot clip a field that starts in front of it. Just the Ø17.8 bore.

**Design rule: the lens tip is the forward-most point of the whole pod.**

---

## Where to put the camera — the two constraints

Full working: `python docs/camera_placement_check.py`

### A. Camera body must stay out of the ToF cones

Each ToF opens 22.5° upward. At Z mm forward of its aperture, the cone top is at
`0.41421 × Z`. The camera's worst point is its bottom edge, 19 mm below the lens axis
(38 mm square board).

> **lens axis height > 19 + 0.4142 × forward protrusion**

| Camera forward of ToF | Minimum lens-axis height |
|---|---|
| 0 mm | 19.0 mm |
| 10 mm | 23.1 mm |
| 20 mm | 27.3 mm |
| 30 mm | 31.4 mm |
| 50 mm | 39.7 mm |

### B. ToF boards must stay out of the camera's view — the harder one

The camera is 119.58° wide. Anything Z mm **forward of the lens tip** must be more
than `1.7175 × Z` sideways or it's in shot.

| Forward of lens tip | Must be sideways by |
|---|---|
| 5 mm | 8.6 mm |
| 10 mm | 17.2 mm |
| 20 mm | 34.3 mm |

A 51.5 mm ToF board sitting 10 mm in front of the lens would need to be 17.2 mm
clear sideways. It won't be — you'd get board in the corner of every frame.

**Which is why the answer to "is it fine for the lens to be in front of the ToF?" is
yes, and it's the right choice.** Nothing behind the lens tip plane can ever enter
the view, because the field only opens forward. That one rule satisfies constraint B
with no arithmetic at all.

Both constraints are met together by stacking the camera **above** the ToF pair with
the **lens tip proud of everything**:

| Position | ToF cones |
|---|---|
| 25 mm up, 0 mm forward | clear (needs ≥ 19.0) |
| 30 mm up, 20 mm forward | clear (needs ≥ 27.3) |
| 35 mm up, 35 mm forward | clear (needs ≥ 33.5) |
| 40 mm up, 50 mm forward | clear (needs ≥ 39.7) |

### Does the forward offset hurt the fusion?

**No.** It's just the Z component of the same translation vector Stage 3 already
solves for — a fixed constant, measured once, removed exactly. Same as the height.

It causes *occlusion*, not error: the camera peeks a few mm further around a near
object than the ToF does. Irrelevant for "is something in the way".

**What matters is rigidity.** Whatever offset you build, it must not change after you
calibrate.

---

## Measuring where the lens actually falls

The lens tip is **24.21 mm** in front of the camera PCB's front face
(25.90 total depth − 1.69 board). Barrel Ø**17.1 mm**. All [CALIPER].

1. **Evaluate → Measure**
2. Click the **lens tip face** (the flat annulus at the front of the barrel)
3. Ctrl-click a **ToF chip's top face**
4. Open the **Delta X/Y/Z** readout

Delta along the sight line = forward protrusion. Delta perpendicular = height offset.
Put those two numbers into the tables above.
