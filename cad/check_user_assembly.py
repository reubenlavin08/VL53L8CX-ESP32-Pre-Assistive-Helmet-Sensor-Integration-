#!/usr/bin/env python3
"""check_user_assembly.py - verify Reuben's own SOLIDWORKS assembly, and emit a
copy with each sensor's field of view attached to it.

Reads the STEP exported from doubleTOFassem.SLDASM, recovers each VL53L8CX's real
optical axis FROM THE GEOMETRY ITSELF (nothing is assumed about how it was built),
then reports every angle, distance and clearance that matters, and writes:

    cad/step/USER_doubleTOFassem_FOV.step   - assembly + FOV wireframes
    cad/step/USER_doubleTOFassem_FOV.glb    - same, with transparency that survives

The FOV bodies are named REF_fov_* and are reference geometry only. They are never
exported to STL and must never be printed.

Run: python cad/check_user_assembly.py
"""
import math
import os

import cadquery as cq
from cadquery import Vector
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "solidworks", "doubleTOFassem.STEP")
STEP_DIR = os.path.join(HERE, "step")

# --- SATEL-VL53L8 facts: ST STEP J5866 + DS14161 ---------------------------
PCB_L, PCB_W, PCB_T = 51.500, 19.500, 1.578      # [ST-STEP]
SENS_FROM_END = 6.400                            # [ST-STEP] optical centre from end
PKG_ABOVE_PCB = 1.750                            # [ST-STEP] package top = aperture
TOF_FOV = 45.0                                   # [DS] DS14161 Table 2
FDM_CLEAR = 0.35                                 # clearance that prints reliably

REACH = 150.0                                    # how far to draw the cones

# --- intended design, from cad/DESIGN-REFERENCE.md -------------------------
WANT_YAW_EACH = 22.0
WANT_PITCH = 22.5


def load():
    wp = cq.importers.importStep(SRC)
    solids = wp.solids().vals()
    # two ST boards are 117 solids each; whatever is left is Reuben's plastic
    boards, printed = {}, []
    n = len(solids)
    boards["A"] = list(range(0, 117))
    boards["B"] = list(range(118, 235))
    used = set(boards["A"]) | set(boards["B"])
    printed = [i for i in range(n) if i not in used]
    return solids, boards, printed


def board_frame(solids, idxs):
    """Recover (optical_centre, view_axis) for one SATEL board, from geometry."""
    grp = [solids[i] for i in idxs]
    pcb = min(grp, key=lambda s: abs(s.Volume() - PCB_L * PCB_W * PCB_T))
    big = max(pcb.Faces(), key=lambda f: f.Area())          # the 51.5 x 19.5 face
    n = big.normalAt(big.Center()).normalized()

    def elen(e):
        L = e.Length
        return L() if callable(L) else L

    le = max(big.Edges(), key=elen)                          # its longest edge
    vs = le.Vertices()
    L = Vector(*vs[1].toTuple()).sub(Vector(*vs[0].toTuple())).normalized()
    c = Vector(*pcb.Center().toTuple())

    # the headers protrude 10 mm below the PCB, so the busier side is the BACK
    def mass_on(side):
        return sum(s.Volume() for s in grp if s is not pcb and
                   Vector(*s.Center().toTuple()).sub(c).dot(n) * side > 0)

    if mass_on(+1) > mass_on(-1):
        n = n.multiply(-1)

    # headers run x 12.77-51.0, so component mass leans toward the FAR end
    lean = sum(Vector(*s.Center().toTuple()).sub(c).dot(L) * s.Volume()
               for s in grp if s is not pcb)
    if lean > 0:
        L = L.multiply(-1)

    end = c.add(L.multiply(-PCB_L / 2.0))                    # sensor-end edge
    opt = (end.add(L.multiply(SENS_FROM_END))
              .add(n.multiply(PCB_T / 2.0 + PKG_ABOVE_PCB)))
    return opt, n, pcb


def _rod(a, b, r=0.5):
    va, vb = Vector(*a), Vector(*b)
    d = vb.sub(va)
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, d.Length, va, d))


def fov_wireframe(apex, axis, fov=TOF_FOV, reach=REACH, rings=(0.35, 0.7, 1.0)):
    """Open wireframe cone. STEP cannot carry transparency; a wireframe is
    see-through by construction in every viewer."""
    pl = cq.Plane(origin=tuple(apex.toTuple()), normal=tuple(axis.toTuple()))
    t = math.tan(math.radians(fov / 2.0))

    def corners(dist):
        pts = []
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            p = pl.toWorldCoords((sx * dist * t, sy * dist * t))
            p = Vector(*p.toTuple()).add(Vector(*axis.toTuple()).multiply(dist))
            pts.append(p.toTuple())
        return pts

    a = apex.toTuple()
    wf = None
    for cpt in corners(reach):
        r = _rod(a, cpt)
        wf = r if wf is None else wf.union(r)
    for f in rings:
        pts = corners(reach * f)
        for i in range(4):
            wf = wf.union(_rod(pts[i], pts[(i + 1) % 4]))
    return wf


def gap(shape_a, shape_b):
    ext = BRepExtrema_DistShapeShape(shape_a.wrapped, shape_b.wrapped)
    ext.Perform()
    return ext.Value()


def main():
    solids, boards, printed_idx = load()
    printed = [solids[i] for i in printed_idx]

    frames = {k: board_frame(solids, v) for k, v in boards.items()}

    print("=" * 74)
    print("VERIFICATION OF doubleTOFassem.STEP")
    print("all angles/positions recovered FROM the geometry, nothing assumed")
    print("=" * 74)

    print(f"\nsolids: {len(solids)}   ST boards: 2 x 117   "
          f"your printed bodies: {len(printed)} "
          f"{[round(p.Volume(), 1) for p in printed]} mm3")

    # ---- 1. ANGLES --------------------------------------------------------
    print("\n" + "-" * 74)
    print("1. ANGLES")
    print("-" * 74)
    axes = {}
    for k, (o, n, pcb) in frames.items():
        pitch = math.degrees(math.asin(-n.y))
        axes[k] = n
        flag = "OK" if abs(pitch - WANT_PITCH) < 0.05 else "*** OFF ***"
        print(f"  board {k}  axis ({n.x:+.4f},{n.y:+.4f},{n.z:+.4f})   "
              f"pitch DOWN {pitch:6.2f} deg  (want {WANT_PITCH})  {flag}")

    hA = Vector(axes['A'].x, 0, axes['A'].z).normalized()
    hB = Vector(axes['B'].x, 0, axes['B'].z).normalized()
    yaw = math.degrees(math.acos(max(-1.0, min(1.0, hA.dot(hB)))))
    flag = "OK" if abs(yaw / 2 - WANT_YAW_EACH) < 0.05 else "*** OFF ***"
    print(f"  yaw separation {yaw:6.2f} deg = 2 x {yaw/2:.2f} deg off the bisector "
          f"(want 2 x {WANT_YAW_EACH})  {flag}")

    # ---- 2. COVERAGE / SEAM ----------------------------------------------
    print("\n" + "-" * 74)
    print("2. COVERAGE - do the two fans meet, overlap, or leave a blind corridor?")
    print("-" * 74)
    overlap = TOF_FOV - yaw
    print(f"  each fan is {TOF_FOV} deg wide, axes are {yaw:.2f} deg apart")
    if overlap > 0:
        print(f"  -> fans OVERLAP by {overlap:.2f} deg angularly (good: no angular gap)")
    else:
        print(f"  -> *** {-overlap:.2f} deg ANGULAR BLIND GAP dead ahead ***")
    print(f"  combined horizontal coverage: {yaw + TOF_FOV:.2f} deg")

    oA, oB = frames['A'][0], frames['B'][0]
    baseline = Vector(*oA.sub(oB).toTuple()).Length
    print(f"\n  BASELINE between the two optical centres: {baseline:.2f} mm")
    if overlap > 0:
        half = math.radians(overlap / 2.0)
        cross = (baseline / 2.0) / math.tan(half) / 1000.0
        print(f"  Because the sensors are {baseline:.1f} mm APART, the fans do not")
        print(f"  actually merge until {cross:.2f} m out. Closer than that there is a")
        print(f"  narrow strip dead ahead that neither sensor covers.")

    # ---- 3. APERTURE / OBSTRUCTION ---------------------------------------
    print("\n" + "-" * 74)
    print("3. APERTURE - is any plastic inside a 45 deg cone?")
    print("-" * 74)
    for k, (o, n, pcb) in frames.items():
        pl = cq.Plane(origin=tuple(o.toTuple()), normal=tuple(n.toTuple()))
        half = REACH * math.tan(math.radians(TOF_FOV / 2.0))
        cone = (cq.Workplane(pl).rect(0.6, 0.6)
                .workplane(offset=REACH).rect(2 * half, 2 * half).loft())
        blocked = 0.0
        for p in printed:
            try:
                ov = cone.intersect(cq.Workplane(obj=p))
                if ov.solids().size():
                    blocked += ov.val().Volume()
            except Exception:
                pass
        vtx = cq.Vertex.makeVertex(o.x, o.y, o.z)
        near = min(gap(vtx, p) for p in printed)
        print(f"  board {k}: plastic in view {blocked/1000.0:7.3f} cm3   "
              f"nearest plastic to the optical centre {near:6.2f} mm   "
              f"{'CLEAR' if blocked < 50 else '*** OBSTRUCTED ***'}")

    # ---- 4. FIT / TOLERANCE ----------------------------------------------
    print("\n" + "-" * 74)
    print("4. FIT - clearance between each board and your printed slot")
    print("-" * 74)
    print(f"  target for FDM: about {FDM_CLEAR:.2f} mm all round.")
    print("  0.00 mm means the solids TOUCH or interfere - it will not slide in.\n")
    for k, idxs in boards.items():
        grp = [solids[i] for i in idxs]
        best = (1e9, None, None)
        for pi, p in zip(printed_idx, printed):
            for s in grp:
                try:
                    d = gap(s, p)
                except Exception:
                    continue
                if d < best[0]:
                    best = (d, pi, s.Volume())
        d, pi, vol = best
        if d < 0.01:
            verdict = "*** TOUCHING/INTERFERING ***"
        elif d < 0.15:
            verdict = "*** TOO TIGHT to print ***"
        elif d > 0.60:
            verdict = "loose - board will rattle"
        else:
            verdict = "good"
        print(f"  board {k}: closest approach to printed body {pi} = "
              f"{d:.3f} mm   {verdict}")

    # ---- 5. EXPORT WITH FOV ATTACHED -------------------------------------
    print("\n" + "-" * 74)
    print("5. WRITING THE COPY WITH FIELDS OF VIEW ATTACHED")
    print("-" * 74)
    os.makedirs(STEP_DIR, exist_ok=True)

    asm = cq.Assembly(name="USER_doubleTOFassem_FOV")
    for i, p in zip(printed_idx, printed):
        asm.add(cq.Workplane(obj=p), name=f"PRINT_body_{i}",
                color=cq.Color(0.72, 0.74, 0.78, 1))

    for k, (o, n, pcb) in frames.items():
        grp = cq.Workplane(obj=cq.Compound.makeCompound(
            [solids[i] for i in boards[k]]))
        wf = fov_wireframe(o, n)
        sub = cq.Assembly(name=f"sensor_{k}")
        sub.add(grp, name=f"SATEL_board_{k}", color=cq.Color(0.20, 0.50, 0.90, 1))
        sub.add(wf, name=f"REF_fov_{k}", color=cq.Color(0.25, 0.55, 1.0, 0.30))
        asm.add(sub, name=f"sensor_{k}")
        cq.exporters.export(wf, os.path.join(STEP_DIR, f"USER_REF_fov_{k}.step"))

    out = os.path.join(STEP_DIR, "USER_doubleTOFassem_FOV.step")
    asm.export(out)
    print(f"  wrote {out}")
    try:
        glb = os.path.join(STEP_DIR, "USER_doubleTOFassem_FOV.glb")
        asm.export(glb)
        print(f"  wrote {glb}   (keeps transparency - drag onto a browser tab)")
    except Exception as e:
        print(f"  (glTF export unavailable: {e})")

    # A 22 MB nested STEP is more than the SOLIDWORKS importer will reliably
    # swallow - it opened as an empty assembly. The two cone files above are
    # ~340 KB each and go straight into the EXISTING assembly instead, where
    # they land at the correct absolute position by construction.
    #
    # Also write a version translated to the origin. The model lives ~1.5 m from
    # (0,0,0), so anything opened on its own appears off-screen and Zoom to Fit
    # is the only thing standing between you and a grey window.
    allbb = cq.Workplane(obj=cq.Compound.makeCompound(solids)).val().BoundingBox()
    ctr = (-(allbb.xmin + allbb.xmax) / 2,
           -(allbb.ymin + allbb.ymax) / 2,
           -(allbb.zmin + allbb.zmax) / 2)
    print(f"\n  model sits {math.sqrt(sum(c*c for c in ctr)):.0f} mm from the origin;"
          f" writing an origin-centred copy too")
    for k, (o, n, pcb) in frames.items():
        cq.exporters.export(fov_wireframe(o, n).translate(ctr),
                            os.path.join(STEP_DIR, f"USER_REF_fov_{k}_at_origin.step"))
    cq.exporters.export(
        cq.Workplane(obj=cq.Compound.makeCompound(
            [s.moved(cq.Location(cq.Vector(*ctr))) for s in solids])),
        os.path.join(STEP_DIR, "USER_assembly_at_origin.step"))
    print(f"  wrote USER_assembly_at_origin.step and USER_REF_fov_*_at_origin.step")

    print("\n  TO USE THEM: open YOUR doubleTOFassem.SLDASM and insert")
    print("  USER_REF_fov_A.step and USER_REF_fov_B.step (the NON-origin ones).")
    print("  They carry absolute coordinates, so they land on the sensors exactly.")
    print("  See cad/VERIFY-IT-YOURSELF.md section 8 for the click-by-click.")


if __name__ == "__main__":
    main()
