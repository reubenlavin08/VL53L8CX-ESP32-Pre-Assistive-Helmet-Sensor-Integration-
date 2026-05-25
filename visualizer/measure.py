"""
VL53L8CX tuning measurement script.

Captures N frames of paired DATA:/SIGMA: lines from the ESP32 firmware over
EITHER a USB serial port OR a WiFi TCP connection, computes per-zone statistics
(mean distance, our measured standard deviation across frames, valid yield,
mean sensor-reported sigma_mm), and writes both a stdout summary + a CSV log
row per zone per run.

The CSV accumulates across runs — one file is your full experiment log.

Usage (wired):
    python measure.py --port COM10 --frames 200 --config "baseline-15hz-8x8-wired"

Usage (WiFi):
    python measure.py --host 192.168.1.228 --frames 200 --config "baseline-15hz-8x8-wifi"
"""

import argparse
import csv
import socket
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import serial


# Match the firmware's SENSOR_RESOLUTION: 64 for 8x8, 16 for 4x4.
TOTAL_ZONES = 64
INVALID_DISTANCE_MM = 4000   # firmware sentinel for filtered zones


def parse_data_line(line):
    if not line.startswith("DATA:"):
        return None
    try:
        values = [int(v) for v in line[5:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=int)


def parse_sigma_line(line):
    if not line.startswith("SIGMA:"):
        return None
    try:
        values = [int(v) for v in line[6:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=int)


def parse_status_line(line):
    if not line.startswith("STATUS:"):
        return None
    try:
        values = [int(v) for v in line[7:].split(",")]
    except ValueError:
        return None
    if len(values) != TOTAL_ZONES:
        return None
    return np.asarray(values, dtype=int)


def open_source(args):
    """Returns (source_label, line_iterator) for either serial or TCP."""
    if args.host:
        sock = socket.create_connection((args.host, args.tcp_port), timeout=5)
        sock.settimeout(5)
        label = f"tcp://{args.host}:{args.tcp_port}"
        # Wrap as a binary file so we can call .readline() like with serial
        f = sock.makefile("rb")
        def gen():
            try:
                while True:
                    raw = f.readline()
                    if not raw:
                        break
                    yield raw.decode("utf-8", errors="ignore").strip()
            finally:
                f.close()
                sock.close()
        return label, gen()
    else:
        ser = serial.Serial(args.port, args.baud, timeout=2)
        ser.reset_input_buffer()
        label = f"{args.port}@{args.baud}"
        def gen():
            try:
                while True:
                    yield ser.readline().decode("utf-8", errors="ignore").strip()
            finally:
                ser.close()
        return label, gen()


def capture_frames(args, n_frames):
    """Read DATA: + SIGMA: + STATUS: triples until n_frames complete triples.
    A frame counts only when all three arrive in order with matching zone counts."""
    distances = []
    sigmas    = []
    statuses  = []
    label, lines = open_source(args)
    cur_data  = None
    cur_sigma = None
    captured = 0

    print(f"Capturing {n_frames} frames from {label}...")
    for line in lines:
        if not line:
            continue
        d = parse_data_line(line)
        s = parse_sigma_line(line)
        t = parse_status_line(line)
        if d is not None:
            cur_data = d
            cur_sigma = None
        elif s is not None and cur_data is not None:
            cur_sigma = s
        elif t is not None and cur_data is not None and cur_sigma is not None:
            distances.append(cur_data)
            sigmas.append(cur_sigma)
            statuses.append(t)
            cur_data = cur_sigma = None
            captured += 1
            if captured % 20 == 0 or captured == n_frames:
                print(f"  {captured}/{n_frames}")
            if captured >= n_frames:
                break

    return np.array(distances), np.array(sigmas), np.array(statuses)


def compute_stats(distances, sigmas, threshold_mm):
    """
    distances: (n_frames, 64) ints, INVALID_DISTANCE_MM = filtered zone
    sigmas:    (n_frames, 64) ints, sensor-reported range_sigma_mm
    Returns (per_zone_list, frame_level_dict).
      per_zone_list: 64 dicts with mean_mm, our_sigma_mm, yield, sensor sigma.
      frame_level_dict: detection_rate (% of frames where any zone < threshold).
    """
    n_frames, n_zones = distances.shape
    per_zone = []

    for z in range(n_zones):
        zone_d = distances[:, z]
        zone_s = sigmas[:, z]
        valid = zone_d != INVALID_DISTANCE_MM
        n_valid = int(valid.sum())
        yld = n_valid / n_frames

        if n_valid >= 2:
            mean_d = float(zone_d[valid].mean())
            our_sigma = float(zone_d[valid].std(ddof=1))
            mean_ssig = float(zone_s[valid].mean())
        else:
            mean_d = our_sigma = mean_ssig = float("nan")

        per_zone.append({
            "zone": z,
            "n_total": n_frames,
            "n_valid": n_valid,
            "mean_mm": mean_d,
            "our_sigma_mm": our_sigma,
            "valid_yield": yld,
            "mean_sensor_sigma_mm": mean_ssig,
        })

    # Frame-level alert behavior: per frame, does any zone read below threshold?
    # This is the firmware's actual buzzer-trigger condition.
    # We treat INVALID (=4000) as "no detection" (zone filtered out / too far).
    nearest_per_frame = distances.copy().astype(float)
    nearest_per_frame[nearest_per_frame == INVALID_DISTANCE_MM] = np.nan
    # nanmin across zones — if all zones invalid, result is nan (no detection)
    with np.errstate(all="ignore"):
        nearest = np.nanmin(nearest_per_frame, axis=1)
    n_below = int(np.sum(nearest < threshold_mm))   # nan < x is False
    n_any_valid = int(np.sum(~np.isnan(nearest)))
    detection_rate = n_below / n_frames

    frame_level = {
        "threshold_mm": threshold_mm,
        "n_frames": n_frames,
        "n_below_threshold": n_below,
        "detection_rate": detection_rate,
        "any_valid_rate": n_any_valid / n_frames,
    }

    return per_zone, frame_level


def print_summary(config, results, frame_level):
    valid_rows = [r for r in results if not np.isnan(r["our_sigma_mm"])]
    if not valid_rows:
        print(f"\n{config}  |  NO VALID ZONES — check wiring / mode")
        print(f"    detection rate < {frame_level['threshold_mm']} mm = "
              f"{frame_level['detection_rate'] * 100:6.1f} %")
        return

    our_sigmas    = [r["our_sigma_mm"]         for r in valid_rows]
    sensor_sigmas = [r["mean_sensor_sigma_mm"] for r in valid_rows]
    overall_yield = float(np.mean([r["valid_yield"] for r in results]))

    print()
    print(f"  {config}")
    print(f"    DETECTION RATE < {frame_level['threshold_mm']} mm  = "
          f"{frame_level['detection_rate'] * 100:6.1f} %  "
          f"({frame_level['n_below_threshold']}/{frame_level['n_frames']} frames)")
    print(f"    any-valid-zone rate             = {frame_level['any_valid_rate'] * 100:6.1f} %")
    print(f"    median (our sigma across zones)     = {np.median(our_sigmas):7.2f} mm")
    print(f"    median (sensor sigma_mm)        = {np.median(sensor_sigmas):7.2f} mm")
    print(f"    overall valid yield             = {overall_yield * 100:6.1f} %")
    print(f"    zones reporting / total         = {len(valid_rows)} / {TOTAL_ZONES}")


def write_csv(csv_path, config, results, frame_level):
    """Two CSVs:
      <csv_path>: per-zone detail (one row per zone per run)
      <csv_path>.summary.csv: one row per run with frame-level metrics
    """
    path = Path(csv_path)
    write_header = not path.exists()
    ts = datetime.now().isoformat(timespec="seconds")

    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow([
                "timestamp", "config", "zone",
                "n_total", "n_valid",
                "mean_mm", "our_sigma_mm",
                "valid_yield", "mean_sensor_sigma_mm",
            ])
        for r in results:
            w.writerow([
                ts, config, r["zone"],
                r["n_total"], r["n_valid"],
                f"{r['mean_mm']:.2f}"             if not np.isnan(r['mean_mm']) else "",
                f"{r['our_sigma_mm']:.2f}"        if not np.isnan(r['our_sigma_mm']) else "",
                f"{r['valid_yield']:.3f}",
                f"{r['mean_sensor_sigma_mm']:.2f}" if not np.isnan(r['mean_sensor_sigma_mm']) else "",
            ])

    # Frame-level summary (one row per run — easy to rank configs)
    summary_path = path.with_suffix(".summary.csv")
    write_sum_header = not summary_path.exists()
    valid_rows = [r for r in results if not np.isnan(r["our_sigma_mm"])]
    median_our_sigma    = float(np.median([r["our_sigma_mm"]         for r in valid_rows])) if valid_rows else float("nan")
    median_sensor_sigma = float(np.median([r["mean_sensor_sigma_mm"] for r in valid_rows])) if valid_rows else float("nan")
    overall_yield       = float(np.mean([r["valid_yield"] for r in results]))
    with summary_path.open("a", newline="") as f:
        w = csv.writer(f)
        if write_sum_header:
            w.writerow([
                "timestamp", "config",
                "threshold_mm", "detection_rate", "n_below", "n_frames",
                "any_valid_rate",
                "median_our_sigma_mm", "median_sensor_sigma_mm",
                "overall_valid_yield", "zones_reporting",
            ])
        w.writerow([
            ts, config,
            frame_level["threshold_mm"],
            f"{frame_level['detection_rate']:.4f}",
            frame_level["n_below_threshold"], frame_level["n_frames"],
            f"{frame_level['any_valid_rate']:.4f}",
            f"{median_our_sigma:.2f}"    if not np.isnan(median_our_sigma)    else "",
            f"{median_sensor_sigma:.2f}" if not np.isnan(median_sensor_sigma) else "",
            f"{overall_yield:.4f}",
            len(valid_rows),
        ])


def main():
    p = argparse.ArgumentParser(description="VL53L8CX tuning measurement.")
    # Serial source (default)
    p.add_argument("--port",    default="COM10", help="serial port (used when --host not given)")
    p.add_argument("--baud",    type=int, default=115200)
    # WiFi source (alternative)
    p.add_argument("--host",    default=None, help="ESP IP address — if given, use TCP instead of serial")
    p.add_argument("--tcp-port", type=int, default=3333)
    # Common
    p.add_argument("--frames",    type=int, default=200)
    p.add_argument("--threshold", type=int, default=600,
                   help="alert threshold (mm) — must match firmware OBSTACLE_THRESHOLD_MM")
    p.add_argument("--zones",     type=int, default=None,
                   help="override TOTAL_ZONES (64 for 8x8, 16 for 4x4). Default = constant in file.")
    p.add_argument("--config",  required=True, help="label for this run, e.g. 'A1-8x8-10hz-sharp0'")
    p.add_argument("--csv",     default="measurements.csv")
    p.add_argument("--raw-dir", default="raw_frames",
                   help="directory to write raw per-frame CSVs (one file per run)")
    args = p.parse_args()

    # Allow resolution switch via CLI without editing the file.
    if args.zones is not None:
        global TOTAL_ZONES
        TOTAL_ZONES = args.zones

    distances, sigmas, statuses = capture_frames(args, args.frames)
    results, frame_level = compute_stats(distances, sigmas, args.threshold)
    print_summary(args.config, results, frame_level)
    write_csv(args.csv, args.config, results, frame_level)
    print(f"\n  CSV row(s) appended to: {Path(args.csv).resolve()}")
    print(f"  Summary row appended to: {Path(args.csv).with_suffix('.summary.csv').resolve()}")

    # Raw per-frame log — every distance + sigma + status value, never thrown away.
    raw_dir = Path(args.raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    ts_compact = datetime.now().strftime("%Y%m%d-%H%M%S")
    raw_path = raw_dir / f"{args.config}_{ts_compact}.csv"
    with raw_path.open("w", newline="") as f:
        w = csv.writer(f)
        header = ["frame"]
        header += [f"dist_z{z}"   for z in range(TOTAL_ZONES)]
        header += [f"sigma_z{z}"  for z in range(TOTAL_ZONES)]
        header += [f"status_z{z}" for z in range(TOTAL_ZONES)]
        w.writerow(header)
        for i in range(distances.shape[0]):
            row = [i]
            row += list(distances[i].tolist())
            row += list(sigmas[i].tolist())
            row += list(statuses[i].tolist())
            w.writerow(row)
    print(f"  Raw frames written to:  {raw_path.resolve()}")

    # Status-code distribution summary — what failure modes did we see?
    if statuses.size > 0:
        unique, counts = np.unique(statuses.flatten(), return_counts=True)
        total = statuses.size
        print(f"\n  STATUS distribution ({total} zone-readings):")
        for code, count in sorted(zip(unique.tolist(), counts.tolist()),
                                  key=lambda x: -x[1]):
            print(f"    status {code:3d}: {count:6d}  ({100*count/total:5.1f}%)")


if __name__ == "__main__":
    main()
