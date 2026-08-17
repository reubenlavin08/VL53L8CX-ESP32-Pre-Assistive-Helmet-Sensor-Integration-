#!/usr/bin/env python3
"""
components.py - CAD models of every electronic component in the helmet sensor pod.

Build these first so the pod can be checked for fit in Onshape/SolidWorks before
anything is printed. Each part exports its own STEP so you can import them
individually and position them, plus a combined assembly at the locked angles.

MEASUREMENT PROVENANCE - every dimension below is tagged:
  [ST-STEP]  extracted from ST's official SATEL-VL53L8 STEP model  -> exact
  [DS]       from a datasheet
  [CALIPER]  measured by Reuben
  [TBD]      NOT YET KNOWN - placeholder, must be confirmed before printing

Run:  python cad/components.py
Out:  cad/step/*.step  and  cad/stl/*.stl
"""
import os

import cadquery as cq

HERE = os.path.dirname(os.path.abspath(__file__))
STEP_DIR = os.path.join(HERE, "step")
STL_DIR = os.path.join(HERE, "stl")
os.makedirs(STEP_DIR, exist_ok=True)
os.makedirs(STL_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# LOCKED MOUNT GEOMETRY (agreed 2026-07-31)
# ---------------------------------------------------------------------------
TOF_YAW = 22.5      # each ToF swung 22.5 deg out from centre -> 45 deg apart -> 90 deg total
TOF_PITCH = 22.5    # both ToF tilted down; fan spans 0..45 deg below horizontal
CAM_PITCH = 22.5    # camera down 22.5 deg -> ToF band centred in frame, 9.1 deg margin each side
US_PITCH = -10.0    # ultrasonics tilted UP 10 deg (negative pitch = up)
US_YAW = 15.0       # ultrasonics splayed +/-15 deg

# ===========================================================================
# 1. SATEL-VL53L8 ToF breakout
# ===========================================================================
# ALL VALUES [ST-STEP] - measured out of ST's own STEP file, J5866.step.
# Origin: PCB top surface = Z0, board corner = (0,0).
TOF_PCB_L = 51.500          # [ST-STEP] (Reuben's caliper said 51 - agrees)
TOF_PCB_W = 19.500          # [ST-STEP] (caliper said 19 - agrees)
TOF_PCB_T = 1.578           # [ST-STEP] PCB thickness

# The VL53L8CX package, as placed on the board.
TOF_CHIP_X0, TOF_CHIP_X1 = 4.910, 7.940     # [ST-STEP] 3.030 mm = package WIDTH
TOF_CHIP_Y0, TOF_CHIP_Y1 = 6.550, 12.950    # [ST-STEP] 6.400 mm = package LENGTH
TOF_CHIP_Z1 = 1.750                          # [ST-STEP] top of package above PCB top

# Optical axis. [DS] DS14161 Fig.28: along the 6.400 length the Rx axis is 1.480 from
# one end and the Tx axis 4.000 further on; across the 3.030 width the optical axis is
# 1.615 from a long edge (hence the documented 0.100 mm offset from package centre,
# which the ST-STEP placement reproduces exactly - a good cross-check).
# NOTE: which END carries Rx cannot be read from the STEP bounding boxes alone (Rx is at
# the end with the "L8" marking). This is a ~1.5 mm positional ambiguity ONLY - it does
# not affect AIMING at all, since aim is set by the mount face angle, not by a 1.5 mm
# offset at metre distances. It matters only slightly for the Stage-3 ToF->camera
# extrinsic, where it is small against a centimetre-scale baseline.
TOF_OPTICAL_X = 6.425       # package centre in the width direction, +/-0.100
TOF_OPTICAL_Y = 9.750       # package centre in the length direction, +/-1.5 (Rx/Tx end unknown)

# Through-hole pin headers - THESE DRIVE THE POD'S INTERNAL CLEARANCES.
TOF_PIN_BELOW = 10.060      # [ST-STEP] pins protrude this far BELOW the PCB
# [ST-STEP] WHERE the pins actually are - extracted from ST's model, 2026-07-31.
# The headers are NOT spread over the board: they hug ONE LONG EDGE in a narrow
# strip. Everything else under the PCB is solder pads, max 2.13 mm proud. Modelling
# them as a full-board 10 mm block (as the first version did) buries them in plastic
# and makes the connectors unreachable.
TOF_HDR_Y0, TOF_HDR_Y1 = 0.080, 2.620    # the 2.54 mm strip along one long edge
TOF_HDR_X0, TOF_HDR_X1 = 12.770, 51.000  # how far the headers run along the length
TOF_PAD_BELOW = 2.130                    # everything else below the PCB
TOF_TOP_CLEAR = 2.640                    # tallest thing on the TOP face (y 3.5-17.65)
TOF_PIN_ABOVE = 8.482       # [ST-STEP] tallest thing ABOVE the PCB (a header)
TOF_STACK_Z0 = -10.060      # [ST-STEP] full envelope, PCB top = 0
TOF_STACK_Z1 = 8.482        # [ST-STEP]

# ST ships this model - prefer importing it over the simplified block below.
ST_STEP = os.path.join(HERE, "..", "docs", "datasheets", "tof",
                       "satel-step", "J5866.step")


def tof_satel(simplified=True):
    """SATEL-VL53L8 breakout.

    simplified=True gives a light block model (fast, good for clearance checks).
    simplified=False loads ST's real STEP (accurate, heavy - 117 solids).
    """
    if not simplified and os.path.exists(ST_STEP):
        return cq.importers.importStep(ST_STEP)

    pcb = (cq.Workplane("XY")
           .box(TOF_PCB_L, TOF_PCB_W, TOF_PCB_T, centered=(False, False, False))
           .translate((0, 0, -TOF_PCB_T)))
    chip = (cq.Workplane("XY")
            .box(TOF_CHIP_X1 - TOF_CHIP_X0, TOF_CHIP_Y1 - TOF_CHIP_Y0, TOF_CHIP_Z1,
                 centered=(False, False, False))
            .translate((TOF_CHIP_X0, TOF_CHIP_Y0, 0)))
    # Accurate keep-outs: a deep header rib along ONE long edge, plus a shallow
    # pad layer everywhere else. See TOF_HDR_* above.
    hdr = (cq.Workplane("XY")
           .box(TOF_HDR_X1 - TOF_HDR_X0, TOF_HDR_Y1 - TOF_HDR_Y0,
                TOF_PIN_BELOW, centered=(False, False, False))
           .translate((TOF_HDR_X0, TOF_HDR_Y0, -TOF_PCB_T - TOF_PIN_BELOW)))
    pads = (cq.Workplane("XY")
            .box(TOF_PCB_L, TOF_PCB_W, TOF_PAD_BELOW, centered=(False, False, False))
            .translate((0, 0, -TOF_PCB_T - TOF_PAD_BELOW)))
    return pcb.union(chip).union(hdr).union(pads)


# ===========================================================================
# 2. HBV-1716WA camera
# ===========================================================================
CAM_PCB = 38.00             # [CALIPER] 38 x 38 mm, confirmed 2026-07-31
CAM_PCB_T = 1.69            # [CALIPER] measured 2026-07-31
CAM_HOLE_PITCH = 28.2       # [CALIPER] 2026-07-31, derived properly: inner-edge to
                            # inner-edge measured 25.9, + one hole diameter (2.3)
                            # = 28.2 centre-to-centre. Confirms the ~28 datasheet
                            # figure and RULES OUT the reseller drawing's 32.
                            # Pilot holes are still SLOTTED +/-1.5 mm for assembly slop.
CAM_HOLE_D = 2.3            # [CALIPER] measured 2026-07-31.
                            # M2 screws pass with ~0.3 mm clearance, which stacks
                            # with the slotted pilots for plenty of assembly slop.
CAM_DEPTH = 25.9            # [CALIPER] 2026-07-31, lens cap OFF (28.5 with it on).
                            # Closest to the reseller drawing's 25 and rules out the
                            # sibling datasheet's ~17.5 - the camera is deeper than
                            # that source claimed. Drives how far the lens must sit
                            # proud of the pod front face to avoid vignetting the
                            # 144 deg diagonal field.
CAM_LENS_H = 25.9 - 1.69    # barrel height above the PCB top = depth - PCB thickness
CAM_LENS_D = 17.1           # [CALIPER] 2026-07-31. Note this is the HOLDER outer
                            # diameter, well over the 14 mm typical of a bare M12
                            # barrel - another reason not to have trusted a guess.


def camera_hbv1716wa():
    """HBV-1716WA / OV2710. PCB top surface = Z0, board centred on origin.

    The optical axis is assumed centred on the board - VERIFY, since the mount aims
    the LENS axis, not the board centre.
    """
    pcb = (cq.Workplane("XY")
           .box(CAM_PCB, CAM_PCB, CAM_PCB_T, centered=(True, True, False))
           .translate((0, 0, -CAM_PCB_T))
           .faces(">Z").workplane()
           .rarray(CAM_HOLE_PITCH, CAM_HOLE_PITCH, 2, 2)
           .hole(CAM_HOLE_D))
    lens = (cq.Workplane("XY").circle(CAM_LENS_D / 2)
            .extrude(CAM_LENS_H))
    return pcb.union(lens)


# ===========================================================================
# 3. HC-SR04 ultrasonic
# ===========================================================================
US_PCB_L = 45.0             # [DS] spec tables say 45 x 20 (the drawing says 43 - conflict)
US_PCB_W = 20.0             # [DS]
US_PCB_T = 1.2              # [TBD] typical for clones, 1.0-1.6
US_CAN_D = 16.0             # [DS] TCT40-16T/R transducer datasheet
US_CAN_H = 12.0             # [DS]
US_CAN_PITCH = 26.0         # [TBD] scaled off the drawing, NOT dimensioned - measure
US_HDR_BELOW = 8.5          # [DS] 4-pin 2.54 header protrudes behind the PCB


def hcsr04():
    """HC-SR04. PCB front face = Z0, cans project in +Z, header in -Z.

    NOTE: the 4 corner Ø1 mm holes are ALIGNMENT holes, not screw holes - do not
    design an M2/M3 fixing to them. Clamp the board or clip over the cans instead.
    NOTE: the HC-SR04P variant puts the header on the OPPOSITE face.
    """
    pcb = (cq.Workplane("XY")
           .box(US_PCB_L, US_PCB_W, US_PCB_T, centered=(True, True, False))
           .translate((0, 0, -US_PCB_T)))
    cans = (cq.Workplane("XY")
            .pushPoints([(-US_CAN_PITCH / 2, 0), (US_CAN_PITCH / 2, 0)])
            .circle(US_CAN_D / 2).extrude(US_CAN_H))
    hdr = (cq.Workplane("XY")
           .box(10.2, 2.54, US_HDR_BELOW, centered=(True, True, False))
           .translate((0, 0, -US_PCB_T - US_HDR_BELOW)))
    return pcb.union(cans).union(hdr)


# ===========================================================================
# Export
# ===========================================================================
PARTS = {
    "tof_satel_vl53l8": tof_satel(simplified=True),
    "camera_hbv1716wa": camera_hbv1716wa(),
    "hcsr04": hcsr04(),
}

if __name__ == "__main__":
    for name, part in PARTS.items():
        s = os.path.join(STEP_DIR, f"{name}.step")
        t = os.path.join(STL_DIR, f"{name}.stl")
        cq.exporters.export(part, s)
        cq.exporters.export(part, t)
        bb = part.val().BoundingBox()
        print(f"{name:24s}  {bb.xlen:6.2f} x {bb.ylen:6.2f} x {bb.zlen:6.2f} mm  -> {s}")
    print(f"\nSTEP files in {STEP_DIR}")
    print("Import these into Onshape to check fit.")
    print("\nLOCKED ANGLES:")
    print(f"  ToF   : +/-{TOF_YAW}deg yaw, {TOF_PITCH}deg down")
    print(f"  Camera: 0deg yaw, {CAM_PITCH}deg down")
    print(f"  Ultras: +/-{US_YAW}deg yaw, {abs(US_PITCH)}deg UP")
