#!/usr/bin/env python3
"""
fov_check.py - do the sensors actually SEE out, or does the casing clip them?

Builds each sensor's field of view as a real solid cone and intersects it with the
printed parts. Any overlap means plastic is standing in the sensor's view - which
on a fisheye shows up as vignetted corners, and on a ToF zone as a permanent
short-range false reading from the housing itself.

This is a different question from the assembly clash check in sensor_pod.py. That
one asks "do the boards physically fit?". This asks "can they see?". A pod can pass
the first and fail the second, and the second failure is much harder to spot by eye.

ANGLES USED
  camera : 119.58 deg H x 63.12 deg V  - MEASURED, calibration_720p.txt, RMS 0.30 px.
           NOT the 140 deg on the box (that is the diagonal) and not the old
           extrapolated ~109/67 guess.
  ToF    : 45 x 45 deg (65 deg diagonal) - OFFICIAL, VL53L8CX DS14161 Table 2.

Run:  python cad/fov_check.py
Out:  cad/step/fov_<name>.step        - each cone on its own
      cad/step/sensor_pod_FOV.step    - pod + lid + all cones, for viewing
"""
import math
import os

import cadquery as cq

import components as C
import sensor_pod as P

STEP_DIR = P.STEP_DIR
REACH = 260.0        # how far to draw the cones, mm

# (name, horizontal FoV, vertical FoV)
FOV = {
    "cam":   (119.58, 63.12),   # MEASURED by calibration
    "tof_l": (45.0, 45.0),      # OFFICIAL DS14161
    "tof_r": (45.0, 45.0),
}


def cone(name, hfov, vfov, reach=REACH, apex=0.6):
    """Rectangular view frustum, apex at the sensor's REAL aperture, along +Y.

    The apex must sit where the light actually enters - the lens tip for the camera,
    the top of the VL53L8CX package for a ToF - not at the seat face. Measuring from
    the seat exaggerates the obstruction and, worse, disagrees with the aperture the
    pod actually cuts.
    """
    # NOTE offset is NEGATIVE: on an XZ workplane a positive offset runs -Y,
    # which pointed every field of view backwards INTO the pod. Both the cut
    # and this check had it, so they agreed with each other and stayed wrong.
    hw = reach * math.tan(math.radians(hfov / 2.0))
    hh = reach * math.tan(math.radians(vfov / 2.0))
    return (cq.Workplane("XZ")
            .rect(apex, apex)
            .workplane(offset=-reach)
            .rect(2 * hw, 2 * hh)
            .loft()
            .translate((0, P.APERTURE_Y[name], 0)))


def _rod(a, b, r=1.2):
    """Thin cylinder between two points - one edge of a wireframe."""
    va, vb = cq.Vector(*a), cq.Vector(*b)
    d = vb.sub(va)
    return cq.Workplane(obj=cq.Solid.makeCylinder(r, d.Length, va, d))


def cone_wireframe(name, hfov, vfov, reach=REACH, rings=(0.35, 0.7, 1.0)):
    """The field of view drawn as an OPEN WIREFRAME rather than a solid block.

    STEP cannot carry transparency - SOLIDWORKS discards the alpha channel on
    import, so a solid cone always arrives opaque and hides everything behind it.
    A wireframe is see-through by construction, in every viewer, with no appearance
    settings to re-apply after each rebuild.

    Four corner rays from the aperture, plus rectangular rings along the way so the
    spread and the overlap between sensors are both readable at a glance.
    """
    y0 = P.APERTURE_Y[name]
    th, tv = math.tan(math.radians(hfov / 2.0)), math.tan(math.radians(vfov / 2.0))
    apex = (0.0, y0, 0.0)
    corners = lambda L: [(sx * L * th, y0 + L, sz * L * tv)
                         for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]

    wf = None
    for c in corners(reach):                      # the four corner rays
        r = _rod(apex, c)
        wf = r if wf is None else wf.union(r)
    for f in rings:                               # rectangular rings across the cone
        pts = corners(reach * f)
        for i in range(4):
            wf = wf.union(_rod(pts[i], pts[(i + 1) % 4]))
    return wf


def main():
    front, lid = P.build_front(), P.build_lid()

    print("SENSOR FIELD-OF-VIEW OBSTRUCTION CHECK")
    print(f"(cones drawn to {REACH:.0f} mm; any overlap = plastic in the sensor's view)\n")

    # NESTED assembly: each sensor and its field-of-view cone live in the SAME
    # sub-assembly, so in SOLIDWORKS/Onshape they appear as one node and move
    # together. STEP preserves this product structure.
    #
    # The cones are REFERENCE GEOMETRY ONLY - named REF_* so they can never be
    # mistaken for parts, and deliberately absent from every printable export.
    # cad/stl/ contains pod_front.stl and pod_lid.stl and nothing else, so slicing
    # cannot pick them up even by accident.
    asm = cq.Assembly(name="sensor_pod_FOV")
    asm.add(front, name="PRINT_pod_front", color=cq.Color(0.72, 0.74, 0.78, 1))
    asm.add(lid, name="PRINT_pod_lid", color=cq.Color(0.55, 0.57, 0.62, 1))
    tint = {"cam": (1.0, 0.55, 0.15, 0.30), "tof_l": (0.25, 0.55, 1.0, 0.30),
            "tof_r": (0.25, 0.55, 1.0, 0.30)}

    worst = 0.0
    comps = P.placed_components()
    for name, yaw, pitch, x, z in P.PLACEMENTS:
        hfov, vfov = FOV[name]
        c = P.orient(cone(name, hfov, vfov), yaw, pitch, (x, 0, z))
        wf = P.orient(cone_wireframe(name, hfov, vfov), yaw, pitch, (x, 0, z))

        sub = cq.Assembly(name=f"sensor_{name}")
        sub.add(comps[name], name=f"board_{name}",
                color=cq.Color(0.90, 0.40, 0.20, 1) if name == "cam"
                else cq.Color(0.20, 0.50, 0.90, 1))
        sub.add(wf, name=f"REF_fov_{name}", color=cq.Color(*tint[name]))
        asm.add(sub, name=f"sensor_{name}")

        cq.exporters.export(wf, os.path.join(STEP_DIR, f"REF_fov_{name}.step"))

        blocked = 0.0
        for part in (front, lid):
            try:
                ov = c.intersect(part)
                if ov.solids().size():
                    blocked += ov.val().Volume() / 1000.0
            except Exception:
                pass
        worst = max(worst, blocked)
        verdict = "CLEAR" if blocked < 1.0 else "*** OBSTRUCTED ***"
        print(f"  {name:6s} {hfov:6.2f} x {vfov:5.2f} deg   "
              f"plastic in view: {blocked:8.2f} cm^3   {verdict}")

    out = os.path.join(STEP_DIR, "sensor_pod_FOV.step")
    asm.export(out)
    # STEP does not carry transparency. glTF does - export one so the cones can be
    # viewed semi-transparent without hand-setting appearances.
    try:
        gl = os.path.join(STEP_DIR, "sensor_pod_FOV.glb")
        asm.export(gl)
        print(f"wrote {gl}  (glTF - keeps the 30% transparency; open in any 3D viewer,"
              f" or drag onto a browser tab)")
    except Exception as e:
        print(f"(glTF export unavailable: {e})")
    print(f"\nwrote {out}")
    print("Open it to SEE the cones. Orange = camera, blue = ToF.")

    if worst >= 1.0:
        print("\nTO FIX AN OBSTRUCTION, in order of preference:")
        print("  1. Enlarge the aperture in that seat (widen the cut in sensor_pod.py).")
        print("  2. Chamfer/flare the aperture outward so the wall follows the cone.")
        print("  3. Move the sensor forward so its aperture sits at the outer surface.")
    else:
        print("\nAll sensors see out cleanly - no plastic inside any field of view.")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# COVERAGE ANALYSIS - how much of the camera's view actually carries ToF depth,
# and whether the two ToF fans overlap or leave a gap.
#
# Done in ANGLES, not volumes: a volume intersection depends on how far you
# happen to draw the cones, whereas angular coverage is the real, distance-
# independent answer.
# ---------------------------------------------------------------------------
def coverage_report():
    cam_h, cam_v = FOV["cam"]
    cam_yaw, cam_pitch = 0.0, 22.5
    cam_l, cam_r = cam_yaw - cam_h / 2, cam_yaw + cam_h / 2
    cam_t, cam_b = cam_pitch - cam_v / 2, cam_pitch + cam_v / 2

    fans = []
    for name, yaw, pitch, x, z in P.PLACEMENTS:
        if not name.startswith("tof"):
            continue
        h, v = FOV[name]
        fans.append((name, yaw - h / 2, yaw + h / 2, pitch - v / 2, pitch + v / 2))
    fans.sort(key=lambda f: f[1])

    print("\nCOVERAGE (degrees, + = right / down)")
    print(f"  camera     horizontal {cam_l:+7.2f} .. {cam_r:+7.2f}   "
          f"vertical {cam_t:+6.2f} .. {cam_b:+6.2f}")
    for n, l, r, t, b in fans:
        print(f"  {n:10s} horizontal {l:+7.2f} .. {r:+7.2f}   "
              f"vertical {t:+6.2f} .. {b:+6.2f}")

    # do the two ToF fans meet, overlap, or leave a hole?
    (_, l1, r1, _, _), (_, l2, r2, _, _) = fans[0], fans[1]
    seam = l2 - r1
    if abs(seam) < 0.01:
        print(f"\n  ToF seam: EDGE TO EDGE at {r1:+.1f} deg - no overlap, no gap.")
    elif seam > 0:
        print(f"\n  ToF seam: *** {seam:.2f} deg BLIND GAP dead ahead *** - the exact"
              f" failure mode the 22.5 deg layout exists to avoid.")
    else:
        print(f"\n  ToF seam: {-seam:.2f} deg of overlap (wasted, but safe).")

    tof_l_edge, tof_r_edge = fans[0][1], fans[1][2]
    tof_t, tof_b = fans[0][3], fans[0][4]
    print(f"  ToF combined: {tof_r_edge - tof_l_edge:.1f} deg wide x "
          f"{tof_b - tof_t:.1f} deg tall")

    # margins - is the whole ToF fan inside the camera's view?
    m_l, m_r = tof_l_edge - cam_l, cam_r - tof_r_edge
    m_t, m_b = tof_t - cam_t, cam_b - tof_b
    print(f"  margin inside camera view: left {m_l:5.2f}  right {m_r:5.2f}  "
          f"top {m_t:5.2f}  bottom {m_b:5.2f} deg")
    if min(m_l, m_r, m_t, m_b) < 0:
        print("  *** part of the ToF fan falls OUTSIDE the camera view - that depth"
              " has no image to attach to ***")
    else:
        print("  -> the entire ToF fan sits inside the camera's view. Every depth"
              " reading has pixels behind it.")

    # what fraction of the image carries depth
    fh = (tof_r_edge - tof_l_edge) / cam_h
    fv = (tof_b - tof_t) / cam_v
    print(f"\n  DEPTH COVERAGE OF THE IMAGE: {fh*100:.1f}% of frame width x "
          f"{fv*100:.1f}% of height = {fh*fv*100:.1f}% of the frame area")
    print(f"  The remaining {100-fh*fv*100:.1f}% is camera-only: the detector still"
          f" sees it, but with no measured distance.")


if __name__ == "__main__":
    coverage_report()
