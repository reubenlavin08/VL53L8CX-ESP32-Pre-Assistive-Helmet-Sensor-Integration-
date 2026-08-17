"""Capture a BNO085 yaw/heading baseline to test magnetometer (ROTATION_VECTOR) quality.

Why this exists: we switched the IMU from GAME_ROTATION_VECTOR (6-axis, no mag, yaw
drifts) to ROTATION_VECTOR (9-axis, mag-fused). The mag corrects yaw drift IF the
helmet's magnetic environment is clean. The datasheet (3.1.5) gives us a calibration
accuracy status 0..3, and ROTATION_VECTOR also reports an estimated heading accuracy
in radians. This script records both plus the derived yaw so we can A/B the helmet
with motors OFF vs ON.

IMPORTANT sequencing (datasheet 3.2 + 3.4):
  * Do NOT pulse RTS to reset the ESP: this board's serial is USB-Serial-JTAG,
    internal to the ESP32-S3, so an RTS reset RE-ENUMERATES the USB port and the
    open handle goes dead (this was the "stuck on waiting" bug). We just attach to
    the already-running stream. (--reset exists only for a real UART bridge.)
  * Because we don't reset, the IMU KEEPS its calibration across runs -- so you can
    calibrate once, then do motors_off and motors_on back-to-back without redoing
    the figure-8. The firmware only soft-resets the BNO085 on an actual ESP reboot.
  * The magnetometer only calibrates while MOVING through all 3 axes (figure-8:
    ~180 deg and back in roll, pitch, yaw). Sitting still it never reaches High.
  * So: this script attaches, waits while YOU do the figure-8 (watching the status
    climb), then records the STILL baseline. Sit the helmet still + fixed during
    recording so any yaw change is attributable to drift / the motors, not your hand.

Usage:
  python imu_capture.py LABEL [SECONDS]
    LABEL    e.g. motors_off  /  motors_on   (used in the CSV filename)
    SECONDS  recording length after calibration (default 30)
  optional flags: --port COM10  --target 2  --settle 90  --reset

Reads Q:w,x,y,z[,status,headacc_rad] lines (back-compatible with the 4-field form).
"""
import sys, time, math, argparse
import numpy as np
try:
    import serial
except ImportError:
    print("pyserial missing. Run with the ESP-IDF python env (it has pyserial).")
    sys.exit(1)

ACC = {0: "Unreliable", 1: "Low", 2: "Medium", 3: "High"}


def yaw_deg(w, x, y, z):
    """ZYX yaw (heading) from a unit quaternion, in degrees."""
    return math.degrees(math.atan2(2.0 * (w * z + x * y),
                                   1.0 - 2.0 * (y * y + z * z)))


def parse_q(line):
    """Return (yaw_deg, status, headacc_deg) for a Q: line, or None."""
    if not line.startswith("Q:"):
        return None
    try:
        f = [float(v) for v in line[2:].split(",")]
    except ValueError:
        return None
    if len(f) < 4:
        return None
    w, x, y, z = f[:4]
    status = int(f[4]) if len(f) >= 5 else -1
    headacc = math.degrees(f[5]) if len(f) >= 6 else float("nan")
    return yaw_deg(w, x, y, z), status, headacc


def open_port(port, do_reset):
    s = serial.Serial(port, 115200, timeout=0.1)
    if do_reset:
        # USB-Serial-JTAG / EN reset via RTS pulse (same as _imucheck.py)
        try:
            s.setDTR(False); s.setRTS(True); time.sleep(0.15); s.setRTS(False)
        except Exception as e:
            print("reset toggle warn:", e)
    return s


def read_lines(s):
    """Generator yielding decoded text lines from the serial port."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("seconds", nargs="?", type=float, default=30.0)
    ap.add_argument("--port", default="COM10")
    ap.add_argument("--target", type=int, default=3,
                    help="accuracy REQUIRED before recording (default 3=High); gates the test")
    ap.add_argument("--calib", type=float, default=12.0,
                    help="minimum figure-8 seconds before the accuracy gate can pass (default 12)")
    ap.add_argument("--maxcalib", type=float, default=60.0,
                    help="give up reaching target after this many seconds, record with a warning")
    ap.add_argument("--settle", type=float, default=12.0,
                    help="max seconds to let yaw stabilize (still) before recording (default 12)")
    ap.add_argument("--reset", action="store_true",
                    help="pulse RTS to reset on open -- BREAKS USB-Serial-JTAG "
                         "(re-enumerates the port); only for a real UART bridge")
    a = ap.parse_args()

    print("Attaching to %s (no reset -- USB-Serial-JTAG keeps running) ..." % a.port)
    s = open_port(a.port, a.reset)
    lines = read_lines(s)

    # ---- wait for the first Q: report -------------------------------------
    print("Waiting for IMU reports (boot ~3-6 s)...")
    t0 = time.time()
    while True:
        ln = next(lines)
        if ln is None:
            if time.time() - t0 > 25:
                print("No Q: lines after 25 s. Is the IMU up? Check the boot log.")
                s.close(); return
            continue
        p = parse_q(ln)
        if p:
            break
    if p[1] == -1:
        print("WARNING: Q lines have no status field -> firmware not reflashed with the")
        print("         ROTATION_VECTOR change. Rebuild + flash first.")

    # ---- CALIBRATE phase: figure-8 UNTIL accuracy reaches the target -------
    # Gate on reaching `target` (default High) so both A/B runs record at the
    # SAME confidence -- otherwise one run at High vs one at Low isn't comparable.
    print("\n=== CALIBRATE ===  Figure-8 the helmet (nod/shake/tilt ~180 deg, all 3 axes)")
    print("    NEAR the final recording spot. Keep moving until accuracy = %s." % ACC.get(a.target, a.target))
    print("    (minimum %.0f s; gives up after %.0f s)\n" % (a.calib, a.maxcalib))
    cstart = time.time()
    last_print = 0
    st = 0; hacc = float("nan"); reached = False
    while True:
        ln = next(lines)
        if ln is None:
            if time.time() - cstart > a.maxcalib:
                break
            continue
        p = parse_q(ln)
        if not p:
            continue
        _, st, hacc = p
        elapsed = time.time() - cstart
        if time.time() - last_print > 0.2:
            print("\r  figure-8: %4.1f s  |  accuracy=%-9s  heading_acc=%5.1f deg  (need %s)   "
                  % (elapsed, ACC.get(st, st), hacc, ACC.get(a.target, a.target)), end="", flush=True)
            last_print = time.time()
        if elapsed >= a.calib and st >= a.target:
            reached = True
            break
        if elapsed >= a.maxcalib:
            break
    if reached:
        print("\n  reached %s. Calibrated.\n" % ACC.get(st, st))
    else:
        print("\n  WARNING: could not reach %s (stuck at %s) after %.0f s." % (
            ACC.get(a.target, a.target), ACC.get(st, st), a.maxcalib))
        print("           The magnetic environment may be too dirty here, OR keep moving")
        print("           more vigorously. Recording anyway, but it'll be flagged INVALID.\n")

    # ---- SETTLE phase: hold STILL, let the fusion converge -----------------
    # The figure-8 leaves the orientation still converging; if we record now the
    # startup transient looks like drift. Hold still until yaw stops moving.
    print("=== SETTLE ===  Put the helmet DOWN and hold it STILL...")
    sstart = time.time()
    win = []                      # (t, yaw) over a sliding ~3 s window
    last_print = 0
    stable = False
    while time.time() - sstart < a.settle:
        ln = next(lines)
        if ln is None:
            continue
        p = parse_q(ln)
        if not p:
            continue
        now = time.time()
        win.append((now, p[0]))
        win = [(tt, yy) for (tt, yy) in win if now - tt <= 3.0]
        ys = np.degrees(np.unwrap(np.radians([yy for _, yy in win])))
        spread = (ys.max() - ys.min()) if len(ys) >= 5 else 99.0
        if now - last_print > 0.2:
            print("\r  settling: yaw=%7.2f deg  |  last-3s spread=%5.2f deg   "
                  % (p[0], spread), end="", flush=True)
            last_print = now
        # stable = yaw moved < 0.3 deg over the last 3 s, after >=4 s of settling
        if (now - sstart) >= 4.0 and len(ys) >= 10 and spread < 0.3:
            stable = True
            break
    print("\n  %s (settled).\n" % ("stable" if stable else "settle time elapsed -- proceeding"))

    # ---- RECORD phase: keep the helmet STILL (already settled) -------------
    print("=== RECORD ===  Keep holding STILL (for motors_on: confirm they're buzzing).")
    for k in (3, 2, 1):
        print("  recording in %d..." % k); time.sleep(1)
    print("  RECORDING %.0f s -- do not move the helmet (motors: %s)\n"
          % (a.seconds, a.label))

    rows = []   # (t, yaw, status, headacc)
    rec0 = time.time()
    while time.time() - rec0 < a.seconds:
        ln = next(lines)
        if ln is None:
            continue
        p = parse_q(ln)
        if not p:
            continue
        rows.append((time.time() - rec0, p[0], p[1], p[2]))
    s.close()

    if len(rows) < 5:
        print("Too few samples (%d). Aborting." % len(rows))
        return

    t = np.array([r[0] for r in rows])
    yaw = np.degrees(np.unwrap(np.radians([r[1] for r in rows])))
    status = np.array([r[2] for r in rows])
    hacc = np.array([r[3] for r in rows])
    span = t[-1] - t[0]

    # Robust drift = slope of a linear fit (deg/min), not end-minus-start (which
    # a single jump or a leftover settle transient would distort). Fit over the
    # whole record AND over the last 2/3 (extra-settled) as a cross-check.
    slope_full = np.polyfit(t, yaw, 1)[0] * 60.0
    i2 = len(t) // 3
    slope_tail = np.polyfit(t[i2:], yaw[i2:], 1)[0] * 60.0 if len(t) - i2 > 5 else float("nan")
    jumps = np.abs(np.diff(yaw))
    maxjump = jumps.max() if len(jumps) else 0.0
    all_high = bool((status == 3).all())
    dist = {k: int((status == k).sum()) for k in sorted(set(status.tolist()))}

    # save CSV
    fn = "imu_capture_%s.csv" % a.label
    with open(fn, "w") as f:
        f.write("t_s,yaw_deg,status,head_acc_deg\n")
        for r in rows:
            f.write("%.3f,%.4f,%d,%.3f\n" % r)

    print("==================== SUMMARY (%s) ====================" % a.label)
    print(" samples       : %d over %.1f s (%.0f Hz)" % (len(rows), span, len(rows) / span))
    print(" yaw drift slope: %+.2f deg/min (full)   %+.2f deg/min (last 2/3)" % (slope_full, slope_tail))
    print(" yaw std / range: %.2f / %.2f deg" % (yaw.std(), yaw.max() - yaw.min()))
    print(" max step jump  : %.2f deg  (large -> mag correction snaps)" % maxjump)
    print(" accuracy dist  : " + ", ".join("%s=%d" % (ACC.get(k, k), v) for k, v in dist.items()))
    print(" heading acc    : mean %.1f deg, worst %.1f deg" % (np.nanmean(hacc), np.nanmax(hacc)))
    print(" saved          : %s" % fn)
    if not all_high:
        print(" >> INVALID for A/B: accuracy was not High for the whole record.")
        print("    Recalibrate to High before comparing motors-off vs motors-on.")
    print("=" * 56)
    print("Read: at steady High accuracy, low drift-slope + small jumps = mag is clean.")
    print("Compare motors-off vs motors-on ONLY when both recorded fully at High.")


if __name__ == "__main__":
    main()
