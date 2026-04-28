"""
VL53L8CX live 3D point cloud visualiser — v2.

Improvements over v1:
  - Scatter updated in-place (no ax.clear() per frame) → no flicker or
    disappearing points.  ax.clear() was destroying and rebuilding every
    matplotlib artist 10× per second; when that took >100 ms the serial
    buffer backed up and the next readline() returned a partial line,
    causing a skipped frame that looked like points vanishing.
  - Serial buffer drain: after receiving one valid frame we flush any
    backlogged frames so the render always shows the newest data, not
    something 200–300 ms stale.
  - Exponential moving average (EMA_ALPHA=0.3) per zone: raw sensor
    readings vary ±10–30 mm frame-to-frame; the EMA kills that noise
    and gives smooth, stable point motion.

Usage:
    python visualizer.py --port COM12

Make sure `idf.py monitor` is NOT running — only one program can hold the
serial port open at a time.
"""

import argparse
import sys

import matplotlib.pyplot as plt
import numpy as np
import serial
from matplotlib import cm
from matplotlib.colors import Normalize


# ── Sensor geometry ──────────────────────────────────────────────────────
ZONES_PER_SIDE = 8
TOTAL_ZONES    = ZONES_PER_SIDE * ZONES_PER_SIDE
FOV_DEG        = 45.0
ANGLE_PER_ZONE = np.radians(FOV_DEG / ZONES_PER_SIDE)

# ── Smoothing ────────────────────────────────────────────────────────────
EMA_ALPHA = 0.3    # weight given to the newest frame  (0 = frozen, 1 = raw)


def precompute_zone_directions():
    """
    For each of the 64 zones, return the unit vector pointing from the
    sensor through the centre of that zone.
    """
    directions = np.zeros((TOTAL_ZONES, 3))
    centre_offset = (ZONES_PER_SIDE - 1) / 2.0
    for row in range(ZONES_PER_SIDE):
        for col in range(ZONES_PER_SIDE):
            h_angle = (col - centre_offset) * ANGLE_PER_ZONE
            v_angle = (row - centre_offset) * ANGLE_PER_ZONE
            x = np.sin(h_angle)
            y = -np.sin(v_angle)
            z = np.cos(h_angle) * np.cos(v_angle)
            directions[row * ZONES_PER_SIDE + col] = (x, y, z)
    return directions


def parse_data_line(line):
    """Return a numpy array of 64 distances, or None if the line is invalid."""
    if not line.startswith("DATA:"):
        return None
    try:
        values = [int(v) for v in line[5:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=float)


def main():
    parser = argparse.ArgumentParser(description="VL53L8CX 3D point cloud")
    parser.add_argument("--port", default="COM12", help="Serial port")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--max-mm", type=int, default=4000,
                        help="Z-axis maximum (and colour scale max)")
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        print(f"ERROR: could not open {args.port}: {exc}", file=sys.stderr)
        print("If idf.py monitor is running, close it first (Ctrl+]).",
              file=sys.stderr)
        sys.exit(1)

    print(f"Listening on {args.port} @ {args.baud} baud...")

    directions = precompute_zone_directions()
    norm = Normalize(vmin=0, vmax=args.max_mm)
    cmap = cm.viridis

    plt.ion()
    fig = plt.figure(figsize=(10, 8), facecolor="#0a0a0a")
    ax  = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#0a0a0a")

    # ── Axes styled once — never cleared ─────────────────────────────────
    ax.set_xlim(-args.max_mm * 0.5,  args.max_mm * 0.5)
    ax.set_ylim(0,                   args.max_mm)
    ax.set_zlim(-args.max_mm * 0.5,  args.max_mm * 0.5)
    ax.set_xlabel("X (mm)",     color="white")
    ax.set_ylabel("Depth (mm)", color="white")
    ax.set_zlabel("Y (mm)",     color="white")
    ax.tick_params(colors="white")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((0.04, 0.04, 0.04, 1.0))
        axis._axinfo["grid"]["color"] = (1, 1, 1, 0.08)
    ax.view_init(elev=18, azim=-65)

    # Colourbar built once
    sm = cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.1)
    cbar.set_label("Distance (mm)", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(plt.getp(cbar.ax.axes, "yticklabels"), color="white")

    # ── Scatter created once with placeholder data ────────────────────────
    dummy = np.zeros(TOTAL_ZONES)
    sc = ax.scatter(
        dummy, dummy, dummy,
        c=dummy, cmap=cmap, norm=norm,
        s=60, depthshade=True, edgecolors="none",
    )

    title = ax.set_title("VL53L8CX live point cloud   (waiting for data...)",
                         color="white", pad=14)

    smoothed    = None
    frame_count = 0

    try:
        while True:
            # ── Read one line ─────────────────────────────────────────────
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            distances = parse_data_line(line)
            if distances is None:
                continue

            # ── Drain any backlogged frames — always render the newest ─────
            while ser.in_waiting:
                newer = ser.readline().decode("utf-8", errors="ignore").strip()
                parsed = parse_data_line(newer)
                if parsed is not None:
                    distances = parsed

            # ── Exponential moving average per zone ───────────────────────
            if smoothed is None:
                smoothed = distances.copy()
            else:
                smoothed = EMA_ALPHA * distances + (1.0 - EMA_ALPHA) * smoothed

            # ── Project into 3D ───────────────────────────────────────────
            points = directions * smoothed[:, np.newaxis]

            # ── Update scatter in-place — no ax.clear() ───────────────────
            sc._offsets3d = (points[:, 0], points[:, 2], points[:, 1])
            sc.set_array(smoothed)

            frame_count += 1
            title.set_text(
                f"VL53L8CX live point cloud   (frame {frame_count})"
            )

            fig.canvas.draw_idle()
            plt.pause(0.001)

    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        ser.close()
        plt.ioff()
        plt.close()


if __name__ == "__main__":
    main()
