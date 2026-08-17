#!/usr/bin/env python3
"""
tof_tilt_chart.py - side-view coverage geometry for the helmet ToF downtilt.

Compares candidate downtilt angles for a VL53L8CX (45 deg vertical FoV) worn at
head height. Produces docs/tof_tilt_chart.png plus a printed distance table.

All distances scale linearly with mount height, so the shape of the answer does
not depend on getting the height exactly right.
"""
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tof_tilt_chart.png")

H = 1.60          # sensor height above ground, metres (helmet-mounted)
VFOV = 45.0       # VL53L8CX vertical field of view, degrees
MAX_RANGE = 4.0   # practical max range, metres (visualiser is capped at 4000 mm)
TILTS = [22.5, 45.0]

def ground_hit(angle_deg):
    """Horizontal distance where a ray angle_deg below horizontal meets the floor."""
    if angle_deg <= 0.01:
        return np.inf
    d = H / np.tan(np.radians(angle_deg))
    return d

def height_at(angle_deg, d):
    """Height of the ray at horizontal distance d."""
    return H - d * np.tan(np.radians(angle_deg))

print(f"Sensor height {H:.2f} m,  vertical FoV {VFOV:.0f} deg,  max range {MAX_RANGE:.1f} m\n")
rows = []
for t in TILTS:
    top, bot = t - VFOV / 2, t + VFOV / 2
    g_top, g_bot = ground_hit(top), ground_hit(bot)
    rows.append((t, top, bot, g_top, g_bot))
    print(f"--- downtilt {t:.1f} deg ---")
    print(f"  fan spans {top:+.1f} to {bot:+.1f} deg below horizontal")
    print(f"  floor covered from {g_bot:.2f} m out to "
          f"{'infinity' if np.isinf(g_top) else f'{g_top:.2f} m'} "
          f"(range-limited to {MAX_RANGE:.1f} m)")
    for d in (1.0, 1.5, 2.0, 3.0, 4.0):
        hi = height_at(top, d)
        lo = height_at(bot, d)
        hi_s = f"{min(hi, H):.2f}" if hi > 0 else "floor"
        lo_s = f"{lo:.2f}" if lo > 0 else "floor"
        print(f"    at {d:.1f} m ahead: sees heights {lo_s} m -> {hi_s} m")
    print()

fig, axes = plt.subplots(1, len(TILTS), figsize=(15, 6), sharey=True, sharex=True)
for ax, (t, top, bot, g_top, g_bot) in zip(axes, rows):
    ax.axhline(0, color="#333", lw=2)                       # ground
    ax.plot([0, 5.2], [H, H], "--", color="#999", lw=1)      # sensor height line
    ax.plot(0, H, "o", color="k", ms=9)

    # the fan, clipped at max range
    ang = np.linspace(top, bot, 60)
    xs = MAX_RANGE * np.cos(np.radians(ang))
    ys = H - MAX_RANGE * np.sin(np.radians(ang))
    ax.fill(np.concatenate([[0], xs]), np.concatenate([[H], ys]),
            color="#2b8cbe", alpha=0.28, lw=0)
    for a, style in ((top, "-"), (bot, "-"), (t, ":")):
        d = min(MAX_RANGE, ground_hit(a) if a > 0 else MAX_RANGE)
        ax.plot([0, d * np.cos(np.radians(a))], [H, H - d * np.sin(np.radians(a))],
                style, color="#08519c", lw=2)

    # a person standing at 2 m, to show what is and is not seen
    px = 2.0
    ax.plot([px, px], [0, 1.75], color="#d95f02", lw=7, solid_capstyle="butt", alpha=0.85)
    seen_lo = max(0.0, height_at(bot, px))
    seen_hi = min(1.75, max(0.0, height_at(top, px)))
    if seen_hi > seen_lo:
        ax.plot([px, px], [seen_lo, seen_hi], color="#1a9641", lw=7,
                solid_capstyle="butt")
    ax.text(px + 0.12, 1.80, "person at 2 m", fontsize=9, color="#333")
    ax.text(px + 0.12, 1.62, f"seen {seen_lo:.2f}-{seen_hi:.2f} m",
            fontsize=9, color="#1a9641" if seen_hi > seen_lo else "#d95f02")

    ax.set_title(f"downtilt {t:.1f}°   (fan {top:+.1f}° to {bot:+.1f}°)",
                 fontsize=13, fontweight="bold")
    ax.set_xlim(-0.2, 5.2); ax.set_ylim(-0.15, 2.3)
    ax.set_xlabel("distance ahead (m)")
    ax.grid(alpha=0.25)
axes[0].set_ylabel("height (m)")
fig.suptitle(f"VL53L8CX vertical coverage — {VFOV:.0f}° FoV, worn at {H:.2f} m "
             f"(green = part of a person actually detected)", fontsize=13)
fig.tight_layout()
fig.savefig(OUT, dpi=110)
print("wrote", OUT)
