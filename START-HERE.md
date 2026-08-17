# START HERE — helmet sensor pod

**If you are a fresh Claude session with no context, read these three files before doing
anything else.**

```
1.  cad/MASTER-HANDOFF.md      <- everything. dimensions, angles, decisions, traps.
2.  cad/VERIFY-IT-YOURSELF.md  <- how to check every number in SOLIDWORKS yourself
3.  cad/NEXT-SESSION.md         <- shorter session-to-session notes
```

Two Claude sessions worked on this in parallel on 2026-08-04→07. They were consolidated
into `MASTER-HANDOFF.md` on 2026-08-07 00:30. **That file is the single source of truth.**
Anything that contradicts it is older.

---

## The 60-second version

**Goal:** ToF ↔ camera sensor fusion for an assistive helmet. Project VL53L8CX depth zones
onto camera pixels so every detected object carries a distance in metres.

**Stages 1–2 done** (camera bring-up, intrinsic calibration, RMS 0.30 px).
**Stages 3–4 not started** — extrinsics and live fusion. That is the actual goal, and all
the CAD work exists to serve it.

**The pod:** two SATEL-VL53L8 ToF boards at **±22.5° yaw / 22.5° down**, an HBV-1716WA
camera on the bisector at **0° yaw / 22.5° down**, in a 3D-printed housing that mounts to
a bike helmet via a K&F BH25 ball head.

**The single most important geometric fact:**

> Yaw both ToF sensors **level** to ±22.5°, **group** them, and only then tilt the whole
> group 22.5° down. This gives an **exactly zero seam at every elevation**.
> Pitching each sensor first and then yawing it — same two numbers, different order —
> leaves a 2.02° blind gap at head height and 12° of wasted overlap at the floor.
> Verified: `docs/tof_rigid_group_verify.py`

**Measured camera FOV: 119.58° × 63.12°** (not the ~109/67 that appears in older notes —
that was an extrapolation and it is wrong).

---

## Working files

| | |
|---|---|
| Primary assembly | `cad/solidworks/Assem1double tof test fov.SLDASM` |
| Back up before touching it | `powershell -File cad\backup_solidworks.ps1` |
| Verify exported geometry | `python cad/check_user_assembly.py` |

---

## Read this before giving Reuben any number

**Measure the geometry; do not assert what it should be.** Across this project, every
time a "correct" value was assumed rather than derived, the assumption was the thing that
was wrong. §8 of the handoff lists eight beliefs that turned out false — including three
of the coverage figures, which came from treating yaw and pitch as separable. **They are
not separable.** Compound rotations do not add.

The reliable loop is: **export a STEP → measure it → compare against a computed target.**

---

## Top open items

1. **0.080 mm pinch** at two header shrouds — boards won't slide in. Relief pocket
   0→39 mm along the length, 16.5→20 mm band, 0.5 mm deep.
2. **Mark all FOV cones as Envelope** — they are ~790 cm³ solid bodies and will appear in
   any STL exported from the assembly.
3. **Measure a DuPont housing** — the camera board clears the ToF header pins by only
   10.82 mm and a housing eats into that. Last remaining `[TBD]`.
4. **Re-measure a camera PCB hole** — 2.1 vs 2.3 mm changes the pitch (28.0 vs 28.2).
5. **`Part13`'s `3DSketch1` still has external refs to the TOFSLOT parts** — every TOFSLOT
   edit re-breaks it plus a mate and a sketch. Four reference cascades so far. Lock the
   refs or rebuild the sketch without them.
6. **Open the camera bore** from Ø17.30 to **Ø17.80** — currently only 0.10 mm radial
   clearance on a Ø17.10 barrel, which will not print.
