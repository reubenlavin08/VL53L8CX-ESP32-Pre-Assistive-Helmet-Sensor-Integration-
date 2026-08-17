#!/usr/bin/env python3
"""
camera_tof_overlap.py - where does the ToF fan land inside the camera image?

Uses the MEASURED camera vertical FoV from the 2026-07-30 fisheye calibration
(63.1 deg, RMS 0.30 px), not the old extrapolated 67 deg guess.

The ToF fan should sit comfortably inside the camera's vertical view with margin
top and bottom: near the image edges a fisheye is most distorted and the
calibration is least constrained (our board never reached the extreme corners),
so depth projected there is the least trustworthy.

Writes docs/camera_tof_overlap.png
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "camera_tof_overlap.png")

CAM_VFOV = 63.12       # MEASURED, calibration_720p.txt
TOF_VFOV = 45.0
TOF_TILT = 22.5        # agreed: fan spans 0..45 deg below horizontal
CAM_TILTS = [20.0, 22.5]

tof_top, tof_bot = TOF_TILT - TOF_VFOV / 2, TOF_TILT + TOF_VFOV / 2

print(f"camera vertical FoV : {CAM_VFOV:.2f} deg (measured)")
print(f"ToF fan             : {tof_top:+.1f} to {tof_bot:+.1f} deg below horizontal\n")

fig, axes = plt.subplots(1, len(CAM_TILTS), figsize=(13, 7), sharey=True)
for ax, ct in zip(np.atleast_1d(axes), CAM_TILTS):
    cam_top, cam_bot = ct - CAM_VFOV / 2, ct + CAM_VFOV / 2
    # fraction down the image where a given angle lands
    f_top = (tof_top - cam_top) / CAM_VFOV
    f_bot = (tof_bot - cam_top) / CAM_VFOV
    m_top, m_bot = tof_top - cam_top, cam_bot - tof_bot

    print(f"--- camera downtilt {ct:.1f} deg ---")
    print(f"  camera sees      {cam_top:+.2f} to {cam_bot:+.2f} deg")
    print(f"  margin above ToF {m_top:5.2f} deg   margin below ToF {m_bot:5.2f} deg")
    print(f"  ToF band occupies {f_top*100:.1f}% to {f_bot*100:.1f}% of image height")
    print(f"  -> ToF bottom row sits {100-f_bot*100:.1f}% of the frame above the bottom edge\n")

    # draw the image frame with the ToF band on it
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, ec="k", lw=2))
    ax.add_patch(plt.Rectangle((0, 1 - f_bot), 1, f_bot - f_top,
                               color="#2b8cbe", alpha=0.35, lw=0))
    ax.axhline(1 - f_top, color="#08519c", lw=2)
    ax.axhline(1 - f_bot, color="#08519c", lw=2)
    # horizon line
    f_hor = (0.0 - cam_top) / CAM_VFOV
    ax.axhline(1 - f_hor, color="#d95f02", lw=1.6, ls="--")
    ax.text(0.02, 1 - f_hor + 0.012, "horizon", color="#d95f02", fontsize=9)

    ax.text(0.5, 1 - (f_top + f_bot) / 2, "ToF depth\navailable here",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#08519c")
    ax.text(0.5, 1 - f_top / 2, f"camera only\n{m_top:.1f}° margin",
            ha="center", va="center", fontsize=9, color="#666")
    ax.text(0.5, (1 - f_bot) / 2, f"camera only\n{m_bot:.1f}° margin",
            ha="center", va="center", fontsize=9, color="#666")

    ax.set_title(f"camera downtilt {ct:.1f}°", fontsize=13, fontweight="bold")
    ax.set_xlim(-0.05, 1.05); ax.set_ylim(-0.05, 1.05)
    ax.set_xticks([]); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["bottom", "", "middle", "", "top"])

fig.suptitle(f"Where the ToF fan lands in the camera frame\n"
             f"camera VFoV {CAM_VFOV:.1f}° (measured)  |  ToF fan {tof_top:+.0f}° to {tof_bot:+.0f}°",
             fontsize=13)
fig.tight_layout()
fig.savefig(OUT, dpi=110)
print("wrote", OUT)
