"""Live side-by-side view of both ToF sensors, so you can identify which
physical sensor is A and which is B.

    python tof_id_viewer.py --port COM9

Wave your hand in front of ONE sensor. Whichever panel lights up close/red is
that sensor. Then tell Claude which is physically LEFT (viewing the pod from
the front, i.e. standing where the sensors aim and looking back at them).

WHY THIS MATTERS: the CAD gives separate transforms for tof_left and tof_right.
Apply the left transform to the right sensor's data and every depth point lands
mirrored across the image -- while every geometric self-check still passes. It
is not detectable downstream, so it has to be nailed down here.

Reads GRID:<name>,d0,d1,...  lines from the tof_pin_test firmware. -1 = invalid.
"""
import argparse
import collections
import sys
import threading

import numpy as np

try:
    import serial
except ImportError:
    sys.exit("pyserial missing.  pip install pyserial")

try:
    import matplotlib
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("matplotlib missing.  pip install matplotlib")

SIDE = 4
NZ = SIDE * SIDE
MAX_MM = 2000.0          # colour scale top; closer = hotter

latest = {"A": None, "B": None}
counts = collections.Counter()
lock = threading.Lock()
running = True


def reader(port, baud):
    """Background serial reader. Keeps only the newest grid per sensor."""
    global running
    try:
        sp = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"could not open {port}: {e}")
        running = False
        return
    print(f"reading {port} @ {baud}")
    buf = b""
    while running:
        try:
            buf += sp.read(sp.in_waiting or 1)
        except Exception:
            break
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            s = line.decode("utf-8", "replace").strip()
            if not s.startswith("GRID:"):
                continue
            parts = s[5:].split(",")
            if len(parts) != NZ + 1:
                continue
            name = parts[0]
            try:
                vals = [int(v) for v in parts[1:]]
            except ValueError:
                continue
            with lock:
                latest[name] = np.array(vals, float).reshape(SIDE, SIDE)
                counts[name] += 1
    sp.close()


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    args = ap.parse_args()

    t = threading.Thread(target=reader, args=(args.port, args.baud), daemon=True)
    t.start()

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    fig.suptitle("Wave at ONE sensor — whichever panel reacts is that sensor",
                 fontsize=13, fontweight="bold")

    labels = {
        "A": "SENSOR  A\nSDA=6  SCL=7  PWREN=4   (I2C_NUM_0)",
        "B": "SENSOR  B\nSDA=15 SCL=16 PWREN=5   (I2C_NUM_1)",
    }

    ims, texts = {}, {}
    blank = np.full((SIDE, SIDE), np.nan)
    cmap = matplotlib.colormaps["turbo"].copy()
    cmap.set_bad("#202020")          # invalid zones render dark grey

    for ax, key in zip(axes, ("A", "B")):
        im = ax.imshow(blank, cmap=cmap, vmin=0, vmax=MAX_MM, interpolation="nearest")
        ax.set_title(labels[key], fontsize=10, family="monospace")
        ax.set_xticks(range(SIDE))
        ax.set_yticks(range(SIDE))
        ax.grid(color="white", linewidth=0.5, alpha=0.3)
        ims[key] = im
        texts[key] = [[ax.text(c, r, "", ha="center", va="center",
                               fontsize=9, fontweight="bold")
                       for c in range(SIDE)] for r in range(SIDE)]
    fig.colorbar(ims["B"], ax=axes, label="distance (mm) — hot = close",
                 fraction=0.03)

    def update(_):
        with lock:
            snap = {k: (v.copy() if v is not None else None)
                    for k, v in latest.items()}
            seen = dict(counts)
        for key in ("A", "B"):
            g = snap[key]
            if g is None:
                ims[key].set_data(blank)
                continue
            masked = np.where(g < 0, np.nan, g)
            ims[key].set_data(masked)
            nvalid = int(np.count_nonzero(~np.isnan(masked)))
            axes["AB".index(key)].set_xlabel(
                f"{nvalid}/{NZ} valid   ·   {seen.get(key, 0)} frames",
                fontsize=9, family="monospace")
            for r in range(SIDE):
                for c in range(SIDE):
                    v = masked[r, c]
                    txt = "—" if np.isnan(v) else f"{int(v)}"
                    # dark text on the hot (light) end of turbo, white elsewhere
                    col = "black" if (not np.isnan(v) and v < MAX_MM * 0.45) else "white"
                    texts[key][r][c].set_text(txt)
                    texts[key][r][c].set_color(col)
        return []

    # cache_frame_data=False: the data is live, not a fixed sequence
    _anim = matplotlib.animation.FuncAnimation(
        fig, update, interval=100, blit=False, cache_frame_data=False)

    try:
        plt.show()
    finally:
        running = False


if __name__ == "__main__":
    import matplotlib.animation  # noqa: F401  (needed before FuncAnimation)
    main()
