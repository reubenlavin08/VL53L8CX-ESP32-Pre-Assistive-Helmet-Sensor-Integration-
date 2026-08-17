#!/usr/bin/env python3
"""explode_animation.py - render an exploded-assembly animation from the STEP export.

SOLIDWORKS' own exploded view cannot be authored from outside the application, so
this builds the same thing straight from the exported geometry: every part slides out
along the direction it ACTUALLY assembles, which is what makes an exploded view worth
looking at. Parts scattered radially look tidy and tell you nothing.

Assembly directions used (all in the pod's own frame, not world):
  SATEL boards   slide out BACKWARD along their length - how they leave the rails
  ToF slots      swing out sideways along their own aim
  camera         straight FORWARD along its optical axis
  camera wall    lifts UP, off the roof
  centerV        stays put - it is the datum everything hangs on

The FOV cones are deliberately EXCLUDED. They are reference geometry, not parts.

Run: python cad/explode_animation.py
Out: cad/render/explode_*.png  frames
     cad/render/explode.gif    the animation
"""
import math
import os

import numpy as np
import cadquery as cq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

STEP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "solidworks", "doubleTOFassem.STEP")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render")
os.makedirs(OUT, exist_ok=True)

# --- pod frame, from the verified geometry --------------------------------
d = np.array([0.3746, 0.0, 0.9272])           # bisector, horizontal
d /= np.linalg.norm(d)
cp, sp = math.cos(math.radians(22.5)), math.sin(math.radians(22.5))
N = cp * d + sp * np.array([0.0, -1.0, 0.0])  # camera axis, 22.5 deg down
U = sp * d + cp * np.array([0.0, 1.0, 0.0])   # pod up
R = np.array([0.9272, 0.0, -0.3746])          # pod right

AX_A = np.array([0.0, -0.3827, 0.9239])       # ToF A aim
AX_B = np.array([0.6418, -0.3827, 0.6646])    # ToF B aim

# solid index ranges -> (label, colour, explode direction, distance mm)
GROUPS = [
    ("SATEL board L", list(range(0, 117)),   "#1f8b4c", -AX_A, 70.0),
    ("SATEL board R", list(range(118, 235)), "#1f8b4c", -AX_B, 70.0),
    ("ToF slot L",    [117],                 "#9aa3ad", -R + 0.3 * N, 55.0),
    ("ToF slot R",    [235],                 "#9aa3ad",  R + 0.3 * N, 55.0),
    ("centre body",   [236],                 "#c2c8d0",  np.zeros(3), 0.0),
    ("camera wall",   [237],                 "#8f98a3",  U, 60.0),
    ("camera",        [240],                 "#d1662a",  N, 95.0),
]
SKIP = {238, 239}          # FOV cones - reference only, never shown as parts

print(f"reading {STEP}")
solids = cq.importers.importStep(STEP).solids().vals()
print(f"{len(solids)} solids; excluding FOV cones {sorted(SKIP)}")

print("tessellating...")
meshes = []
for label, idxs, colour, direction, dist in GROUPS:
    tris = []
    for i in idxs:
        if i in SKIP or i >= len(solids):
            continue
        try:
            verts, faces = solids[i].tessellate(1.2)
        except Exception:
            continue
        V = np.array([[v.x, v.y, v.z] for v in verts])
        for f in faces:
            tris.append(V[list(f)])
    if not tris:
        continue
    nd = np.linalg.norm(direction)
    unit = direction / nd if nd > 1e-9 else np.zeros(3)
    meshes.append((label, np.array(tris), colour, unit, dist))
    print(f"  {label:16s} {len(tris):6d} triangles")

allpts = np.vstack([m[1].reshape(-1, 3) for m in meshes])
ctr = (allpts.min(0) + allpts.max(0)) / 2
span = float((allpts.max(0) - allpts.min(0)).max())
reach = span * 1.5

FRAMES = 72


def ease(t):
    """Smooth in and out - a linear slide looks mechanical and cheap."""
    return 0.5 - 0.5 * math.cos(math.pi * t)


print(f"rendering {FRAMES} frames...")
paths = []
for k in range(FRAMES):
    # out for the first half, hold, back in - so the GIF loops cleanly
    u = k / (FRAMES - 1)
    if u < 0.40:
        t = ease(u / 0.40)
    elif u < 0.60:
        t = 1.0
    else:
        t = ease(1.0 - (u - 0.60) / 0.40)

    fig = plt.figure(figsize=(9, 7), dpi=110)
    ax = fig.add_subplot(111, projection="3d")
    for label, tris, colour, unit, dist in meshes:
        moved = tris + unit * dist * t
        # NOTE: passing edgecolors="none" here breaks matplotlib's shading - it
        # builds an empty colour array and the broadcast fails. Use linewidths=0.
        pc = Poly3DCollection(moved, facecolors=colour, linewidths=0,
                              alpha=1.0, shade=True)
        ax.add_collection3d(pc)

    ax.set_xlim(ctr[0] - reach / 2, ctr[0] + reach / 2)
    ax.set_ylim(ctr[1] - reach / 2, ctr[1] + reach / 2)
    ax.set_zlim(ctr[2] - reach / 2, ctr[2] + reach / 2)
    ax.set_box_aspect((1, 1, 1))
    ax.view_init(elev=18, azim=-62)
    ax.set_axis_off()
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0)

    p = os.path.join(OUT, f"explode_{k:03d}.png")
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)
    if k % 12 == 0:
        print(f"  frame {k}/{FRAMES}")

print("assembling GIF...")
try:
    from PIL import Image
    imgs = [Image.open(p) for p in paths]
    gif = os.path.join(OUT, "explode.gif")
    imgs[0].save(gif, save_all=True, append_images=imgs[1:],
                 duration=55, loop=0, optimize=True)
    print(f"wrote {gif}")
except Exception as e:
    print(f"GIF assembly failed ({e}); the PNG frames are in {OUT}")

print(f"\n{len(paths)} frames in {OUT}")
