"""Repeatable DYNAMIC yaw-drift test for the mag-free helmet (AR/VR-Stabilized GRV).

Mag-free yaw only drifts while MOVING (gyro integrates motion + residual zero-rate
offset). A still-on-the-table test reads ~0, so to measure real drift we move the
helmet through a CONTROLLED, repeatable motion and check whether yaw returns to its
starting value when the helmet is put back on a physical reference mark.

Protocol (keeps every variable pinned so runs are comparable):
  1. Tape a CENTER mark; align the helmet's forward edge to it (flat on the table).
  2. Put two stops (books) ~90 deg left and right so the sweep angle is physical,
     not eyeballed.
  3. Phone metronome at 60 BPM; one half-sweep (center->stop or stop->center) per
     beat. Keep the helmet FLAT the whole time (pure yaw, no tilt).
  4. Run this script. It:
       - waits for the helmet to be STILL on the mark, averages a clean start yaw;
       - says GO -> you sweep for a fixed time (default 40 s) at the metronome pace;
       - says STOP -> return to the center mark, hold still, it averages the end yaw.
  5. Drift = end_yaw - start_yaw (both measured physically at the center mark).

Hold constant between runs: same stops (angle), same BPM, same motion time, flat
orientation, same start mark. Mag-free => location/magnetic environment doesn't matter.

Usage:  python imu_drift_dynamic.py LABEL [MOTION_SECONDS]
  e.g.  python imu_drift_dynamic.py before_levers 40
"""
import sys, time, math, argparse
import numpy as np
try:
    import serial
except ImportError:
    print("pyserial missing -- run with system python."); sys.exit(1)


def yaw_deg(w, x, y, z):
    return math.degrees(math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z)))


def parse_q(line):
    if not line.startswith("Q:"):
        return None
    try:
        f = [float(v) for v in line[2:].split(",")]
    except ValueError:
        return None
    if len(f) < 4:
        return None
    return yaw_deg(*f[:4])


def lines(s):
    buf = b""
    while True:
        n = s.in_waiting
        d = s.read(n if n else 1)
        if d:
            buf += d
            while b"\n" in buf:
                ln, buf = buf.split(b"\n", 1)
                yield ln.decode("utf-8", "replace").strip()
        else:
            yield None


def wait_still_and_average(gen, label, settle_max=20.0):
    """Wait until yaw is stable (spread < 0.3 deg over 2 s), then return its mean."""
    print("  %s -- hold the helmet STILL on the mark..." % label)
    win = []          # (t, yaw)
    last = 0
    deadline = time.time() + settle_max
    while time.time() < deadline:
        ln = next(gen)
        if ln is None:
            continue
        y = parse_q(ln)
        if y is None:
            continue
        now = time.time()
        win.append((now, y))
        win = [(tt, yy) for (tt, yy) in win if now - tt <= 2.0]
        ys = np.degrees(np.unwrap(np.radians([yy for _, yy in win])))
        spread = (ys.max() - ys.min()) if len(ys) >= 5 else 99.0
        if now - last > 0.2:
            print("\r    yaw=%8.2f deg   spread(2s)=%5.2f deg   " % (y, spread), end="", flush=True)
            last = now
        if len(ys) >= 10 and spread < 0.3:
            mean = float(np.mean(ys))
            print("\n    locked: %.2f deg\n" % mean)
            return mean
    print("\n    (didn't fully settle; using last value %.2f deg)\n" % y)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("motion", nargs="?", type=float, default=40.0)
    ap.add_argument("--port", default="COM10")
    a = ap.parse_args()

    s = serial.Serial(a.port, 115200, timeout=0.1)   # attach, no reset
    gen = lines(s)
    print("\n=== DYNAMIC DRIFT TEST (%s) ===" % a.label)
    print("Helmet FLAT, forward edge on the center mark, two stops set, metronome ready.\n")

    y_start = wait_still_and_average(gen, "START reference")

    print("  Get ready -- hands on the helmet, metronome on. Sweep starts in:")
    for k in range(10, 0, -1):
        print("    %d..." % k); time.sleep(1)
    s.reset_input_buffer()   # drop the backlog that piled up during the countdown

    print("  GO -- sweep flat between the stops at the metronome pace for %.0f s." % a.motion)
    rows = []
    m0 = time.time()
    nextcount = 1
    while time.time() - m0 < a.motion:
        ln = next(gen)
        if ln is None:
            continue
        y = parse_q(ln)
        if y is None:
            continue
        rows.append((time.time() - m0, y))
        el = time.time() - m0
        if el >= nextcount * 5:           # progress every 5 s
            print("    sweeping... %2.0f / %.0f s" % (el, a.motion)); nextcount += 1
    print("  STOP -- return the helmet to the center mark.\n")

    y_end = wait_still_and_average(gen, "END reference")
    s.close()

    drift = y_end - y_start
    mot = np.degrees(np.unwrap(np.radians([r[1] for r in rows]))) if rows else np.array([0.0])
    excursion = (mot.max() - mot.min()) if len(rows) else 0.0

    fn = "imu_drift_%s.csv" % a.label
    with open(fn, "w") as f:
        f.write("phase,t_s,yaw_deg\n")
        f.write("start_ref,0.000,%.4f\n" % y_start)
        for t, y in rows:
            f.write("motion,%.3f,%.4f\n" % (t, y))
        f.write("end_ref,0.000,%.4f\n" % y_end)

    print("==================== DRIFT RESULT (%s) ====================" % a.label)
    print(" start yaw @mark : %+.2f deg" % y_start)
    print(" end yaw   @mark : %+.2f deg" % y_end)
    print(" >> DRIFT        : %+.2f deg  (after %.0f s of motion)" % (drift, a.motion))
    print(" sweep excursion : %.1f deg (peak-to-peak during motion)" % excursion)
    print(" saved           : %s" % fn)
    print("=" * 58)
    print("Recreate EXACTLY (same stops, BPM, motion time, flat) and compare DRIFT.")
    print("Lower |DRIFT| after the calibration levers = they helped.")


if __name__ == "__main__":
    main()
