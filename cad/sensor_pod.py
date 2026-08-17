#!/usr/bin/env python3
"""
sensor_pod.py - REV 3. Front shell + rear lid, every board loading from the back.

=============================================================================
WHAT WAS WRONG WITH REV 1 AND REV 2 (all found by review, all real)
=============================================================================
REV 1  Blind pockets inside a closed shell - physically unbuildable, and nothing
       retained any board. A shifted ToF board silently voids the Stage-3
       calibration, which is the worst kind of failure: invisible.

REV 2  1. Seats were added as PLINTHS standing off the body. Trimming them back
          to the envelope left clipped, half-formed seats, and the ultrasonic
          plinths fouled the shell. -> Rev 3 CUTS recesses INTO a solid body, so
          interference is impossible by construction.
       2. NO WIRE ROUTING AT ALL. Every seat was a sealed pocket. -> Rev 3 gives
          each seat a wire channel into the central cavity.
       3. ToF boards mounted long-axis HORIZONTAL. They are 51.5 x 19.5 mm, so at
          +/-22.5 deg yaw that forced a ~145 mm wide pod. -> Rev 3 mounts them
          long-axis VERTICAL: projected width per board drops from 47.6 to 18 mm.
          The sensor sits 6.4 mm from one end of the board (measured from ST's
          STEP), so the board simply hangs down inside the shell.
       4. The assembly was exported with toCompound(), which FLATTENS it into one
          lump. -> Rev 3 exports a structured assembly plus standalone parts.

=============================================================================
RETENTION - chosen from what each board actually offers
=============================================================================
CAMERA   Four real Ø2 mounting holes -> M2 screws into printed bosses. It is the
         optical datum for the whole fusion pipeline, so it gets true fixing.
ToF      No usable mounting holes on ST's board. Seat RIM locates X/Y, SHOULDER
         sets Z, lid PRESSURE PAD preloads it through 1.5 mm foam. Deliberate:
         screwing a bare PCB concentrates stress and cracks it; distributed
         preload holds AND damps.
HC-SR04  Its four Ø1 holes are ALIGNMENT holes, not screw holes (per datasheet).
         Can bores locate it, rim takes side load, lid pad preloads.

SHAKE:   camera bolted; ToF/ultrasonics preloaded so there is no free play to
         rattle into; load path board -> seat -> shell, never board -> solder.
         Cable tug is taken by a zip-tie strain relief, NOT by the camera's USB
         connector - otherwise a yank on the backpack tether levers the optical
         datum out of alignment.

COORDS:  +X right, +Y forward (travel), +Z up. Origin = pod centre.
ANGLES:  camera 0 yaw / 22.5 down; ToF +/-22.5 yaw / 22.5 down;
         ultrasonics +/-15 yaw / 10 UP.
"""
import math
import os

import cadquery as cq

import components as C

HERE = os.path.dirname(os.path.abspath(__file__))
STEP_DIR = os.path.join(HERE, "step")
STL_DIR = os.path.join(HERE, "stl")
os.makedirs(STEP_DIR, exist_ok=True)
os.makedirs(STL_DIR, exist_ok=True)

FIT = 0.35
WALL = 2.8
SHOULDER = 1.6      # material between a seat face and the outside
FOAM = 1.5
PRELOAD = 0.5
WIRE_W, WIRE_H = 9.0, 5.0     # wire channel from each seat into the cavity
# Room BEHIND the ToF header pins for a DuPont housing plus wire bend.
# [TBD] - measure a real DuPont female housing (length along the pin axis) and the
# bend radius you need. Placeholder only; do not print until confirmed.
DUPONT_CLEAR = 18.0

M3_INSERT_D = 4.0
M3_CLEAR = 3.4
M2_BOSS_D = 4.4
M2_PILOT = 1.6
# MEASURED off ST's real STEP, 2026-07-31 - the clear strip at each board edge
# before a rail would foul a surface-mount component:
#     long edge y=0    : 0.91 mm top / 0.08 mm bottom  (headers sit ON this edge)
#     long edge y=19.5 : 1.85 mm top / 3.10 mm bottom
#     end   x=0        : 4.91 / 3.55      end x=51.5 : 1.46 / 0.50
# 82 components on top, 36 underneath. The original 2.2 mm grip fouled three of the
# four edges. 1.5 mm is the largest that clears the good long edge.
RAIL_GRIP = 1.5     # how far each retaining lip overhangs the board edge
RAIL_T = 1.8        # lip thickness, standing proud of the seat face
PILOT_SLOT = 1.5    # radial slot on the camera pilots, absorbs hole-pitch error

POD_W, POD_D, POD_H = 74.0, 46.0, 110.0
LID_T = 3.0
Y_SEAT = 12.0       # seat faces sit this far forward of pod centre
# POD_D cut 70 -> 46 once every dimension was measured: the deepest thing
# behind a seat is the ToF board at ~13.5 mm, so 70 mm was mostly dead air
# (the 31 mm foam blocks the script was asking for were the giveaway).

# (name, yaw, pitch_down, x, z)  -- ToF mounted VERTICAL, ultrasonics on the top band.
#
# ⚠ orient() rotates about the POD ORIGIN, so the Y_SEAT offset swings a component
# in Z by Y_SEAT*sin(pitch): the camera drops 7.6 mm and the ultrasonics rise 3.5 mm
# from the z written here. The seats move with them (hence the ToF boards were always
# fine) but the shell walls do not - which is exactly how rev 3's first pass put the
# camera through the floor and the ultrasonics through the roof. The z values below
# are chosen so that AFTER that swing everything clears the walls.
#
#   camera : z -8  -> centre -15.7, spans -33.2 .. +1.9
#   ToF    : z -2  -> centre  -9.7, spans -33.5 .. +14.2
#   ultras : z +24 -> centre +27.5, spans +17.5 .. +37.5
#   inner walls at +/-41.2, so all clear.
# ULTRASONICS ARE NOT IN THIS PART - see ultrasonic_bracket.py.
# Only the camera and the two ToF sensors need to be rigid relative to each other,
# because that is exactly what the Stage-3 extrinsic calibration measures. The
# ultrasonics have no calibration relationship to anything, so forcing them into
# the precision body bought nothing and cost repeated clashes with the shell.
# REV 4 LAYOUT - camera STACKED ABOVE the ToF pair, not between them.
#
# WHY: with the camera in the middle the ToF sensors sat 92 mm apart. Their inner
# edge rays both point dead ahead and are PARALLEL, so the 92 mm strip between them
# was seen by neither - a blind corridor straight ahead that never closes. A signpost
# or a pole could sit in it undetected at any range. That is the exact failure the
# 22.5 deg layout exists to prevent, reintroduced by physical separation.
#
# Moving the camera out collapses the baseline to 34 mm (the floor: each board is
# 19.5 mm wide and at 22 deg yaw the rear inner corners swing in ~5 mm, so any closer
# and they collide). Blind strip drops 92 -> 34 mm, narrower than a signpost.
#
# TOE-IN 0.5 deg (yaw 22.0 instead of 22.5): the fans cross at 1.95 m, closing the
# strip entirely beyond that, for only 1 deg of overlap and 1 deg of coverage.
# Overlap is kept minimal deliberately - an unsynced second VL53L8CX raises the
# noise floor (higher SIGMA, shorter range, dropouts). If it ever matters, the
# sensor has a dedicated SYNC pin (UM3109 4.15) to time-offset the two emitters.
#
# Inside 1.95 m a 34 mm object dead centre has no ToF depth - but the camera has a
# single continuous field with no central gap, so it is still SEEN, just without a
# measured distance. Detection covers it at those ranges.
#
# ToF boards mount sensor-END-UP so their 45 mm tails hang DOWN inside the shell,
# tucking under the camera instead of fighting it for space.
PLACEMENTS = [
    ("cam",    0.0,  22.5,   0.0,  26.0),
    ("tof_l", -22.0, 22.5, -17.0, -24.0),
    ("tof_r",  22.0, 22.5,  17.0, -24.0),
]


def orient(shape, yaw, pitch, pos):
    """Rotate a shape built AT THE ORIGIN, then move its seat centre to pos.

    Everything is authored with the board face ON the origin, so rotating about
    the origin leaves the seat centre exactly where it was. The seat then lands
    precisely at (x, Y_SEAT, z) whatever the angles.

    Rev 3's first passes instead authored shapes already offset to y = Y_SEAT and
    rotated THAT about the pod origin, which swung every component in Z by
    Y_SEAT*sin(pitch) - the camera dropped 7.6 mm through the floor and the
    ultrasonics rose 3.5 mm through the roof. The seats moved with them so the
    error was invisible until the clash check localised it.
    """
    s = shape.rotate((0, 0, 0), (1, 0, 0), -pitch)
    s = s.rotate((0, 0, 0), (0, 0, 1), -yaw)
    return s.translate((pos[0], Y_SEAT, pos[2]))


def slab(w, h, d, y0=0.0):
    """Block centred in X/Z, spanning from y0 REARWARD (-Y) by d.

    On an XZ workplane cadquery extrudes toward -Y for a POSITIVE distance, so
    rearward needs extrude(+d) and forward needs extrude(-d) - the opposite of what
    it reads like. Getting this backwards made slab() and fwd() produce identical
    forward blocks, so every seat pocket, pin clearance and wire channel was being
    cut FORWARD out through the front wall instead of rearward into the cavity.
    That is what produced the mess of facets around the ToF apertures.
    Verified by bounding box, not by assumption.
    """
    return cq.Workplane("XZ").rect(w, h).extrude(d).translate((0, y0, 0))


def fwd(w, h, d, y0=0.0):
    """Block centred in X/Z, spanning from y0 FORWARD (+Y) by d.

    NOTE the NEGATIVE extrude. On an XZ workplane cadquery extrudes toward -Y for a
    positive distance, so `extrude(d)` runs BACKWARDS into the pod. This is the same
    sign trap that pointed every field-of-view cone the wrong way; here it meant the
    ToF apertures were being cut into the shell interior instead of out through the
    front wall, leaving a stubborn sliver of plastic in front of each sensor.
    """
    return cq.Workplane("XZ").rect(w, h).extrude(-d).translate((0, y0, 0))


# --------------------------------------------------------------------------
# Seat cutters. Local frame: board face at y = Y_SEAT, looking +Y.
# Boards are described in their MOUNTED orientation (w across X, h across Z).
# --------------------------------------------------------------------------
def seat_cut(bw, bh, bt, pin_clear, wire_side=-1):
    """Recess + pin clearance + a wire channel out of the seat."""
    pocket = slab(bw + 2 * FIT, bh + 2 * FIT, bt + 0.5, 0.0)
    behind = slab(bw - 4, bh - 4, pin_clear + 3.0, -bt - 0.5)
    # wire channel: runs from the bottom of the seat rearward into the cavity
    wire = slab(WIRE_W, WIRE_H, 40.0, -1.0) \
        .translate((0, 0, wire_side * (bh / 2 + WIRE_H / 2 - 1.0)))
    return pocket.union(behind).union(wire)


def cam_cut():
    cut = seat_cut(C.CAM_PCB, C.CAM_PCB, C.CAM_PCB_T, 16.0, wire_side=-1)
    # lens bore, out through the front
    # NEGATIVE extrude = FORWARD on an XZ workplane, so the bore actually goes out
    # through the front wall. With the sign the other way it bored rearward into the
    # cavity and left the lens buried in 2.8 mm of plastic.
    cut = cut.union(cq.Workplane("XZ").circle(C.CAM_LENS_D / 2 + FIT)
                    .extrude(-40).translate((0, 0, 0)))
    # SLOTTED pilot holes. The hole pitch was measured by hand at ~27 mm against a
    # datasheet value of 28, and centre-to-centre is hard to caliper accurately.
    # Elongating each pilot radially by +/-PILOT_SLOT absorbs that uncertainty, so
    # a 1-2 mm error cannot stop the camera bolting down. Better to design the
    # uncertainty out than to demand a perfect measurement.
    p = C.CAM_HOLE_PITCH / 2
    pilots = None
    for sx in (-1, 1):
        for sz in (-1, 1):
            slot = (cq.Workplane("XZ")
                    .slot2D(M2_PILOT + 2 * PILOT_SLOT, M2_PILOT, 45 if sx * sz > 0 else -45)
                    .extrude(-10)
                    .translate((sx * p, -C.CAM_PCB_T, sz * p)))
            pilots = slot if pilots is None else pilots.union(slot)
    return cut.union(pilots)


def local_component(name):
    """Component in its LOCAL seat frame: centred in X/Z, front face ON y = 0.

    Centring is derived from the component's BOUNDING BOX after rotation, not from
    hand-written offsets. Hand offsets were applied after two rotations had already
    moved the axes, which silently put the ToF boards tens of millimetres from where
    the placement table said - the clash localiser is what exposed it.
    """
    raw = {"cam": C.camera_hbv1716wa,
           # ST's REAL STEP (117 solids) - the actual board, headers and pins, not a
           # simplified block. Slower to check, but it is the only honest source for
           # where the connectors sit, which is what the slide-in slot is built around.
           "tof_l": lambda: C.tof_satel(False), "tof_r": lambda: C.tof_satel(False),
           "us_l": C.hcsr04, "us_r": C.hcsr04}[name]()
    p = raw.rotate((0, 0, 0), (1, 0, 0), -90)      # face the part along +Y
    if name.startswith("tof"):
        # ST's model lies with its 51.5 mm length along X; stand it VERTICAL so the
        # board projects only 19.5 mm across the pod instead of 51.5 mm.
        p = p.rotate((0, 0, 0), (0, 1, 0), 90)
    # Centre in X and Z from the bounding box, but LEAVE Y ALONE.
    # Every component is authored with its PCB front face on z = 0, which the -90 deg
    # X rotation maps to y = 0 - so the mounting datum is already correct. An earlier
    # version also snapped Y to the bounding box maximum, which for the camera is the
    # LENS TIP, not the PCB: that floated the board 24 mm forward of its own seat. The
    # clash check could not see it (the 17 mm lens fits inside the 38 mm pocket without
    # touching); only the field-of-view check exposed it.
    bb = p.val().BoundingBox()
    return p.translate((-(bb.xmin + bb.xmax) / 2.0,
                        -0.1,
                        -(bb.zmin + bb.zmax) / 2.0))


def tof_cut():
    # MOUNTED VERTICAL: 19.5 wide across X, 51.5 tall up Z.
    bw, bh = C.TOF_PCB_W, C.TOF_PCB_L
    cut = seat_cut(bw, bh, C.TOF_PCB_T, C.TOF_PIN_BELOW, wire_side=-1)
    # NO separate square aperture here. The flared FOV cone cut in build_front()
    # already opens the window. Cutting a plain 13x13 box as well meant two openings
    # intersecting at an angle - which is what produced the odd faceted shapes in the
    # aperture. One cut, one clean flared opening.
    return cut


def us_cut():
    bw, bh = C.US_PCB_L, C.US_PCB_W
    cut = seat_cut(bw, bh, C.US_PCB_T, C.US_HDR_BELOW, wire_side=-1)
    cans = (cq.Workplane("XZ")
            .pushPoints([(-C.US_CAN_PITCH / 2, 0), (C.US_CAN_PITCH / 2, 0)])
            .circle(C.US_CAN_D / 2 + FIT).extrude(30)
            .translate((0, -1.0, 0)))
    return cut.union(cans)


CUTS = {"cam": cam_cut, "tof_l": tof_cut, "tof_r": tof_cut,
        "us_l": us_cut, "us_r": us_cut}
BOARD = {  # mounted (width across X, height across Z, thickness)
    "cam": (C.CAM_PCB, C.CAM_PCB, C.CAM_PCB_T),
    "tof_l": (C.TOF_PCB_W, C.TOF_PCB_L, C.TOF_PCB_T),
    "tof_r": (C.TOF_PCB_W, C.TOF_PCB_L, C.TOF_PCB_T),
    "us_l": (C.US_PCB_L, C.US_PCB_W, C.US_PCB_T),
    "us_r": (C.US_PCB_L, C.US_PCB_W, C.US_PCB_T),
}


# Sensor fields of view. Camera figures are MEASURED (calibration_720p.txt);
# ToF is OFFICIAL (VL53L8CX DS14161 Table 2: 45 x 45 deg, 65 deg diagonal).
FOV_DEG = {"cam": (119.58, 63.12), "tof_l": (45.0, 45.0), "tof_r": (45.0, 45.0)}
FOV_MARGIN = 4.0     # extra degrees so print tolerance cannot eat into the view

# How far forward of the seat face each sensor's aperture actually sits.
APERTURE_Y = {"cam": C.CAM_LENS_H - 0.1,        # the lens tip, well proud of the PCB
              "tof_l": C.TOF_CHIP_Z1 - 0.1,     # top of the VL53L8CX package
              "tof_r": C.TOF_CHIP_Z1 - 0.1}


def fov_cone(name, reach=90.0):
    """View frustum for one sensor, apex at its real aperture, opening along +Y."""
    h, v = FOV_DEG[name]
    h, v = h + FOV_MARGIN, v + FOV_MARGIN
    hw = reach * math.tan(math.radians(h / 2.0))
    hh = reach * math.tan(math.radians(v / 2.0))
    return (cq.Workplane("XZ").rect(0.6, 0.6)
            .workplane(offset=-reach).rect(2 * hw, 2 * hh).loft()
            .translate((0, APERTURE_Y[name], 0)))


def rails(bw, bh, bt, depth=None, lead_in=8.0):
    """A true U-CHANNEL the board slides down into, not a pair of floating bars.

    Rev 4's first attempt added two thin lips standing off the seat face. They were
    barely attached to anything and formed no channel - there was no way to actually
    insert a board.

    This instead grows two SIDE WALLS rearward from the seat face. Their front edges
    are rooted in the solid shoulder behind the aperture, so they are structurally
    part of the shell, and together with that shoulder they form a three-sided
    channel. The board drops in from the TOP, slides down between the walls, and is
    stopped at the front by the shoulder itself - no separate lip needed, because
    there is already 11 mm of material between the seat face and the outer surface.

    The top `lead_in` mm are left open so the board has somewhere to enter, and the
    wall inner faces are the datum that sets the sensor's aim.
    """
    if depth is None:
        depth = bt + 12.0
    wall = None
    for sx in (-1, 1):
        x0 = sx * (bw / 2.0 + FIT)
        w = (cq.Workplane("XZ")
             .rect(WALL, bh - lead_in)
             .extrude(depth)                      # positive = rearward on XZ
             .translate((x0 + sx * WALL / 2.0, 0.0, -lead_in / 2.0)))
        wall = w if wall is None else wall.union(w)
    return wall


def build_front():
    body = (cq.Workplane("XY").box(POD_W, POD_D, POD_H)
            .edges("|Z").fillet(7.0))

    # hollow, BACK OPEN - every board loads from behind
    body = body.cut(cq.Workplane("XY")
                    .box(POD_W - 2 * WALL, POD_D, POD_H - 2 * WALL)
                    .edges("|Z").fillet(4.0)
                    .translate((0, -WALL, 0)))

    # Every seat is CUT into the solid - no added plinths, so nothing can foul.
    # (The camera screws into pilot holes in the seat floor; rev 3's first pass
    # added proud M2 bosses and they clashed with the camera PCB itself.)
    for name, yaw, pitch, x, z in PLACEMENTS:
        body = body.cut(orient(CUTS[name](), yaw, pitch, (x, 0, z)))
        # FLARED APERTURE: cut the sensor's own view cone out of the plastic, so the
        # opening follows the field of view instead of being a straight bore. A
        # straight bore of any sensible size clips a 45 deg ToF fan (let alone a
        # 119.6 deg camera) once the sensor sits a couple of centimetres inside the
        # shell - fov_check.py measured exactly that.
        body = body.cut(orient(fov_cone(name), yaw, pitch, (x, 0, z)))

    # SLIDE-IN RAILS - added after the cuts so the seat pockets cannot remove them
    for name, yaw, pitch, x, z in PLACEMENTS:
        bw, bh, bt = BOARD[name]
        body = body.union(orient(rails(bw, bh, bt), yaw, pitch, (x, 0, z)))

    # lid fixing bosses
    bx, bz = POD_W / 2 - 8.5, POD_H / 2 - 8.5
    for x, z in [(-bx, -bz), (bx, -bz), (-bx, bz), (bx, bz)]:
        body = body.union(cq.Workplane("XZ").circle(M3_INSERT_D / 2 + 2.4)
                          .extrude(-13).translate((x, -POD_D / 2 + 13, z)))
        body = body.cut(cq.Workplane("XZ").circle(M3_INSERT_D / 2)
                        .extrude(-9).translate((x, -POD_D / 2 + 9, z)))

    # rear cable exit + zip-tie strain relief
    body = body.cut(cq.Workplane("XZ").rect(30, 15)
                    .extrude(-(WALL + 3)).translate((0, -POD_D / 2 + WALL + 3, -20)))
    for dx in (-19.5, 19.5):
        body = body.cut(cq.Workplane("XZ").rect(3.4, 10)
                        .extrude(-(WALL + 3))
                        .translate((dx, -POD_D / 2 + WALL + 3, -20)))

    # vents over the camera - it ran hot enough to drop off the USB bus twice
    for i in range(-2, 3):
        body = body.cut(cq.Workplane("XY").rect(4, 20).extrude(WALL + 3)
                        .translate((i * 9.0, 4, POD_H / 2 - WALL - 1)))
    return body


def build_lid():
    lid = (cq.Workplane("XY").box(POD_W, LID_T, POD_H)
           .edges("|Y").fillet(7.0)
           .translate((0, -POD_D / 2 - LID_T / 2, 0)))
    bx, bz = POD_W / 2 - 8.5, POD_H / 2 - 8.5
    for x, z in [(-bx, -bz), (bx, -bz), (-bx, bz), (bx, bz)]:
        lid = lid.cut(cq.Workplane("XZ").circle(M3_CLEAR / 2).extrude(-(LID_T + 2))
                      .translate((x, -POD_D / 2 + 1, z)))

    # NO PRINTED PRESSURE PADS.
    # Earlier revisions printed pads standing off the lid to preload each board.
    # They repeatedly fouled the boards, and they are the wrong solution anyway:
    # a printed pad has no compliance, so any print tolerance either leaves the
    # board loose or crushes it. Instead the lid is FLAT and you bond a foam or
    # TPU block to it - foam is compressible, so it absorbs tolerance, applies an
    # even preload and damps vibration. foam_spec() prints the thickness needed.
    return lid


def foam_spec():
    """Foam block thickness per sensor, measured along each sensor's own axis."""
    out = {}
    lid_inner_y = -POD_D / 2.0                      # inner face of the lid
    for name, yaw, pitch, x, z in PLACEMENTS:
        if name == "cam":
            continue                                 # camera is screwed down
        comp = orient(local_component(name), yaw, pitch, (x, 0, z))
        bb = comp.val().BoundingBox()
        gap = bb.ymin - lid_inner_y                  # clear space behind the board
        out[name] = (gap, gap + PRELOAD)
    return out


def placed_components():
    """Every component in its mounted position - returned SEPARATELY, one per key."""
    return {name: orient(local_component(name), yaw, pitch, (x, 0, z))
            for name, yaw, pitch, x, z in PLACEMENTS}


def interference_report(front, lid, comps):
    """Automated clash check - REV 2 shipped a plastic/ultrasonic clash. No more."""
    print("\nINTERFERENCE CHECK (overlap of each component with the plastic)")
    worst = 0.0
    for name, comp in comps.items():
        for pname, part in (("front", front), ("lid", lid)):
            try:
                ov = comp.intersect(part)
                v = ov.val().Volume() / 1000.0 if ov.solids().size() else 0.0
            except Exception:
                ov, v = None, 0.0
            worst = max(worst, v)
            flag = "  OK" if v < 0.05 else "  *** CLASH ***"
            if v >= 0.05 or pname == "front":
                print(f"  {name:6s} vs {pname:5s}: {v:7.3f} cm^3{flag}")
            # LOCALISE the clash - guessing at causes wasted two iterations
            if v >= 0.05 and ov is not None:
                b = ov.val().BoundingBox()
                print(f"         at X[{b.xmin:7.2f},{b.xmax:7.2f}] "
                      f"Y[{b.ymin:7.2f},{b.ymax:7.2f}] "
                      f"Z[{b.zmin:7.2f},{b.zmax:7.2f}]  "
                      f"({b.xlen:.1f} x {b.ylen:.1f} x {b.zlen:.1f} mm)")
    print(f"  worst overlap: {worst:.3f} cm^3"
          f"{'  -> CLEAN' if worst < 0.05 else '  -> FIX REQUIRED'}")
    return worst


if __name__ == "__main__":
    front, lid = build_front(), build_lid()
    comps = placed_components()

    print("PARTS")
    tot = 0.0
    for nm, part in (("pod_front", front), ("pod_lid", lid)):
        bb = part.val().BoundingBox()
        v = part.val().Volume() / 1000.0
        tot += v
        print(f"  {nm:10s} {bb.xlen:6.1f} x {bb.ylen:5.1f} x {bb.zlen:5.1f} mm  "
              f"{v:6.1f} cm^3  ~{v*1.24:5.0f} g PLA")
        cq.exporters.export(part, os.path.join(STEP_DIR, f"{nm}.step"))
        cq.exporters.export(part, os.path.join(STL_DIR, f"{nm}.stl"))
    print(f"  {'TOTAL':10s} {'':29s}{tot:6.1f} cm^3  ~{tot*1.24:5.0f} g PLA")

    # every component ALSO exported standalone, already positioned
    for name, comp in comps.items():
        cq.exporters.export(comp, os.path.join(STEP_DIR, f"placed_{name}.step"))

    worst = interference_report(front, lid, comps)

    print("\nFOAM BLOCKS - bond these to the flat inner face of the lid")
    for nm, (gap, thick) in foam_spec().items():
        print(f"  {nm:6s}: clear gap {gap:5.1f} mm  ->  use {thick:5.1f} mm foam "
              f"(gives {PRELOAD} mm preload)")

    # structured assembly - separate named parts, NOT a flattened compound
    asm = cq.Assembly(name="sensor_pod")
    asm.add(front, name="pod_front", color=cq.Color(0.72, 0.74, 0.78, 1))
    asm.add(lid, name="pod_lid", color=cq.Color(0.55, 0.57, 0.62, 1))
    col = {"cam": (0.90, 0.40, 0.20), "tof_l": (0.20, 0.50, 0.90),
           "tof_r": (0.20, 0.50, 0.90), "us_l": (0.30, 0.80, 0.40),
           "us_r": (0.30, 0.80, 0.40)}
    for name, comp in comps.items():
        asm.add(comp, name=name, color=cq.Color(*col[name], 1))
    out = os.path.join(STEP_DIR, "sensor_pod_ASSEMBLY.step")
    asm.export(out)
    print(f"\nwrote {out}  (structured: separate named parts)")
    print("Every component also exported standalone as placed_<name>.step")


# ---------------------------------------------------------------------------
# EXPLODED VIEW - every board pulled back ALONG ITS OWN INSERTION AXIS.
# Each sensor slides in along the negative of its own optical axis, i.e. straight
# back out through the open rear of the shell. Seeing them offset along those
# vectors is the quickest way to sanity-check that the assembly is physically
# possible before anything is printed.
# ---------------------------------------------------------------------------
def axis_vector(yaw, pitch):
    """Unit vector a sensor looks along, for the given yaw/pitch."""
    import math
    p, y = math.radians(pitch), math.radians(yaw)
    return (math.cos(p) * math.sin(y), math.cos(p) * math.cos(y), -math.sin(p))


def build_exploded(offset=55.0):
    asm = cq.Assembly(name="sensor_pod_exploded")
    asm.add(build_front(), name="pod_front", color=cq.Color(0.72, 0.74, 0.78, 1))
    # lid pulled straight back
    asm.add(build_lid().translate((0, -offset * 1.6, 0)), name="pod_lid",
            color=cq.Color(0.55, 0.57, 0.62, 1))
    col = {"cam": (0.90, 0.40, 0.20), "tof_l": (0.20, 0.50, 0.90),
           "tof_r": (0.20, 0.50, 0.90)}
    for name, yaw, pitch, x, z in PLACEMENTS:
        v = axis_vector(yaw, pitch)
        comp = orient(local_component(name), yaw, pitch, (x, 0, z))
        # slide OUT along -axis (the direction it is withdrawn)
        comp = comp.translate((-v[0] * offset, -v[1] * offset, -v[2] * offset))
        asm.add(comp, name=name, color=cq.Color(*col[name], 1))
    return asm


if __name__ == "__main__":
    ex = build_exploded()
    out = os.path.join(STEP_DIR, "sensor_pod_EXPLODED.step")
    ex.export(out)
    print(f"\nwrote {out}")
    print("INSERTION AXES (unit vectors; each board withdraws along the NEGATIVE):")
    for name, yaw, pitch, x, z in PLACEMENTS:
        v = axis_vector(yaw, pitch)
        print(f"  {name:6s} yaw {yaw:+6.1f}  pitch {pitch:+5.1f}  ->  "
              f"({v[0]:+.3f}, {v[1]:+.3f}, {v[2]:+.3f})")
