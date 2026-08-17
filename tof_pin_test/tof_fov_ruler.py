"""Measure the ToF's real zone angles directly. No camera, no solver, no model.

    python tof_pin_test/tof_fov_ruler.py --port COM9 --sensor A

WHY: the planar calibration fits an effective field of ~34 deg where the
datasheet says 45 (and its own 65 deg diagonal implies ~47). That 25% gap sits
inside the fusion model, and it is not academic:

    two sensors at +/-22.5 deg with 45 deg fields  -> inner edges meet at 0 deg
    the same pair with 34 deg fields               -> ~11 deg BLIND WEDGE ahead

So it must be settled physically, not by the solver that produced it.

WHAT THIS SHOWS: each zone is scored ON-BOARD or OFF-BOARD, and that verdict is
averaged over the last STABLE_N frames. Highlighting the single nearest zone was
useless -- on a flat board every zone reads nearly the same and noise makes the
minimum hop around. What matters is which zones have fallen off the EDGE, and
that is stable.

A zone is OFF-BOARD when its distance sits far from the robust median of the
others (median +/- max(60 mm, 5*MAD)), or reads invalid. A zone ranging the room
behind the board is out by hundreds of mm, so the test is not delicate.

METHOD
  1. Aim the sensor SQUARE-ON at the board (it is mounted 22.5 deg out and
     22.5 deg down, so the pod itself must be turned toward the board).
  2. Back the board away until the outer columns turn red and STAY red.
  3. That distance, with the board width, gives the field angle directly:
        half_angle = atan( (board_width/2) / distance )
"""
import argparse
import collections
import threading

import cv2
import numpy as np
import serial

SIDE = 4
NZ = SIDE * SIDE
STABLE_N = 25          # frames averaged for the on/off verdict
OFF_FLOOR_MM = 60.0    # minimum deviation that counts as "off the board"

latest = {"A": None, "B": None}
lock = threading.Lock()
running = True


def reader(port, baud):
    global running
    try:
        sp = serial.Serial(port, baud, timeout=1)
    except Exception as e:
        print(f"serial: {e}")
        running = False
        return
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
            p = s[5:].split(",")
            if len(p) != NZ + 1:
                continue
            try:
                v = np.array([int(x) for x in p[1:]], float).reshape(SIDE, SIDE)
            except ValueError:
                continue
            with lock:
                latest[p[0]] = v
    sp.close()


def split_near_far(g):
    """Two-surface mode: a card slid in front of the board.

    Returns (near_mask, z_near, z_far) or None if the scene is a single surface.
    Each COLUMN flips from far to near as the card's edge crosses that column's
    CENTRE -- 50% coverage is where the strongest return switches over. So the
    lateral offset at which column c flips measures that column's centre angle
    directly, which is precisely what the ray model parameterises. A straight
    card is used rather than a pen because at 800 mm a zone is ~160 mm across
    and a pen fills under 1% of it; the board behind wins every time.
    """
    v = g > 0
    if v.sum() < 6:
        return None
    d = g[v]
    lo, hi = float(d.min()), float(d.max())
    if hi - lo < 120.0:                 # single surface, nothing to split
        return None
    mid = 0.5 * (lo + hi)
    near = v & (g < mid)
    far = v & (g >= mid)
    if near.sum() < 1 or far.sum() < 1:
        return None
    return near, float(np.median(g[near])), float(np.median(g[far]))


def score(g):
    """-> (off_board bool grid, robust board distance mm)."""
    valid = g > 0
    off = ~valid
    if valid.sum() < 4:
        return off, 0.0
    d = g[valid]
    m = float(np.median(d))
    mad = float(np.median(np.abs(d - m))) or 1.0
    tol = max(OFF_FLOOR_MM, 5.0 * mad)
    off = off | (np.abs(g - m) > tol)
    on = valid & ~off
    return off, (float(np.median(g[on])) if on.any() else m)


def main():
    global running
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="COM9")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--sensor", default="A", choices=["A", "B"])
    ap.add_argument("--board-mm", type=float, default=508.0,
                    help="board width in mm (20 in = 508)")
    args = ap.parse_args()

    threading.Thread(target=reader, args=(args.port, args.baud), daemon=True).start()
    hist = collections.deque(maxlen=STABLE_N)
    zbuf = collections.deque(maxlen=STABLE_N)

    cell, top, bot = 104, 62, 210
    W = SIDE * cell + 470
    print("\nAim SQUARE-ON at the board. Back it away until the outer columns")
    print("turn red and stay red. Q quits.\n")

    while running:
        with lock:
            g = None if latest[args.sensor] is None else latest[args.sensor].copy()
        img = np.full((SIDE * cell + top + bot, W, 3), 24, np.uint8)
        cv2.putText(img, f"SENSOR {args.sensor}  -  zone field ruler", (12, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (240, 240, 240), 2, cv2.LINE_AA)
        cv2.putText(img, f"verdict averaged over last {STABLE_N} frames", (12, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1, cv2.LINE_AA)

        if g is not None:
            off, z = score(g)
            hist.append(off.astype(float))
            zbuf.append(z)
        if hist:
            frac = np.mean(np.stack(hist), axis=0)     # 0 = always on board, 1 = always off
            z = float(np.median(zbuf))
            gg = g if g is not None else np.zeros((SIDE, SIDE))

            # PEN / INTRUDER: a zone reading clearly NEARER than the board.
            # Only meaningful when something really is in front -- highlighting the
            # plain minimum is useless on a flat board, where noise picks a random
            # winner every frame.
            sf = split_near_far(g) if g is not None else None
            intr = None
            if g is not None and z > 0:
                near = (g > 0) & (g < z - 80.0)
                if near.any():
                    gm = np.where(near, g, np.inf)
                    intr = np.unravel_index(np.argmin(gm), gm.shape)


            for r in range(SIDE):
                for c in range(SIDE):
                    x, y = c * cell + 12, r * cell + top
                    f = frac[r, c]
                    if sf is not None:
                        col = (170, 90, 40) if sf[0][r, c] else (60, 120, 60)
                    elif f > 0.7:  col = (40, 40, 215)     # off the board
                    elif f > 0.25: col = (40, 170, 225)    # flickering at the edge
                    else:          col = (60, 150, 60)     # on the board
                    cv2.rectangle(img, (x, y), (x + cell - 5, y + cell - 5), col, -1)
                    if intr == (r, c):
                        cv2.rectangle(img, (x, y), (x + cell - 5, y + cell - 5),
                                      (255, 255, 255), 3)
                    t = "--" if gg[r, c] <= 0 else f"{int(gg[r, c])}"
                    cv2.putText(img, t, (x + 10, y + cell // 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
                                cv2.LINE_AA)
                    cv2.putText(img, f"off {f*100:3.0f}%", (x + 10, y + cell // 2 + 24),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (235, 235, 235), 1,
                                cv2.LINE_AA)
                cv2.putText(img, f"r{r}", (SIDE * cell + 18, r * cell + top + cell // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1, cv2.LINE_AA)
            for c in range(SIDE):
                nof = int((frac[:, c] > 0.7).sum())
                cv2.putText(img, f"c{c}", (c * cell + 48, top - 26),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (80, 80, 255) if nof else (140, 220, 140), 1, cv2.LINE_AA)
                cv2.putText(img, f"{nof}off", (c * cell + 34, top - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                            (80, 80, 255) if nof else (120, 160, 120), 1, cv2.LINE_AA)

            y0 = SIDE * cell + top + 34
            allon = int((frac > 0.7).sum()) == 0
            cv2.putText(img, f"board distance z = {z:.0f} mm", (14, y0),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2, cv2.LINE_AA)
            cv2.putText(img,
                        "ALL 16 ON BOARD - back it away further" if allon
                        else f"{int((frac>0.7).sum())} zones OFF the board  <-- read the distance NOW",
                        (14, y0 + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.72,
                        (80, 220, 80) if allon else (80, 200, 255), 2, cv2.LINE_AA)

            # what each hypothesis predicts for THIS board width
            half = args.board_mm / 2.0
            for k, (lab, fov) in enumerate((("datasheet 45", 45.0), ("solver fit 34.2", 34.24))):
                dcrit = half / np.tan(np.deg2rad(fov / 2.0))
                cv2.putText(img,
                            f"{lab:>16}: zones leave a {args.board_mm:.0f} mm board at "
                            f"z = {dcrit:.0f} mm",
                            (14, y0 + 76 + k * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                            (120, 220, 120) if k == 0 else (120, 180, 255), 1, cv2.LINE_AA)
            if sf is not None:
                nearm, zn, zf = sf
                cols = "".join("N" if nearm[:, c].sum() > SIDE / 2 else "." for c in range(SIDE))
                cv2.putText(img, f"EDGE MODE  near {zn:.0f}mm   far {zf:.0f}mm   columns [{cols}]",
                            (14, y0 + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                            (255, 200, 120), 2, cv2.LINE_AA)
                for k, fov in ((0, 45.0), (1, 34.24)):
                    off = [zf * np.tan(np.deg2rad((c - 1.5) * fov / 4.0)) for c in range(SIDE)]
                    txt = "  ".join(f"c{c}:{off[c]:+5.0f}" for c in range(SIDE))
                    cv2.putText(img, f"  col centres at {fov:.0f} deg:  {txt} mm",
                                (14, y0 + 138 + k * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (120, 220, 120) if k == 0 else (120, 180, 255), 1, cv2.LINE_AA)
            elif intr is not None:
                cv2.putText(img, f"PEN detected -> column c{intr[1]}, row r{intr[0]}",
                            (14, y0 + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (255, 255, 255), 2, cv2.LINE_AA)
            else:
                cv2.putText(img, "no pen in the field (slide it back in)",
                            (14, y0 + 108), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (140, 140, 140), 1, cv2.LINE_AA)
            if z > 0:
                for k, fov in ((0, 45.0), (1, 34.24)):
                    e = z * np.tan(np.deg2rad(fov / 2.0))
                    cv2.putText(img, f"  field edge at {fov:.0f} deg = {e:.0f} mm from boresight",
                                (14, y0 + 170 + k * 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                                (120, 220, 120) if k == 0 else (120, 180, 255), 1, cv2.LINE_AA)
                ang = np.degrees(np.arctan(half / z)) * 2
                cv2.putText(img,
                            f"if they are JUST leaving now, full field = {ang:.1f} deg",
                            (14, y0 + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                            (200, 200, 90), 2, cv2.LINE_AA)

        cv2.imshow("ToF zone field ruler", img)
        if (cv2.waitKey(30) & 0xFF) == ord("q"):
            break

    running = False
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
