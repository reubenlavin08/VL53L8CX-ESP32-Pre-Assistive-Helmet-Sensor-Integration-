"""
Capture ESP32 serial output for diagnostics.

Pulses DTR/RTS to reset the chip, then dumps all serial output for N seconds.
Used to grab boot logs + verbose OTA traces.

Usage:
    python serial_capture.py [port] [duration_sec] [--no-reset]
"""

import argparse
import serial
import sys
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port",     default="COM10")
    p.add_argument("--baud",     type=int, default=115200)
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--no-reset", action="store_true",
                   help="Don't pulse DTR/RTS; just listen to whatever's already running")
    args = p.parse_args()

    print(f"# Opening {args.port} @ {args.baud}", flush=True)
    ser = serial.Serial(args.port, args.baud, timeout=0.5)

    if not args.no_reset:
        # ESP32 reset sequence: pulse RTS while DTR is high
        # (RTS=1 → reset asserted; pulse it then release to boot)
        print("# Pulsing reset (RTS) ...", flush=True)
        ser.dtr = False
        ser.rts = True
        time.sleep(0.1)
        ser.rts = False
        time.sleep(0.05)

    print(f"# Capturing for {args.duration} s", flush=True)
    start = time.time()
    while time.time() - start < args.duration:
        try:
            raw = ser.readline()
        except serial.SerialException as e:
            print(f"# Serial read error: {e}", flush=True)
            break
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if line:
            print(line, flush=True)

    ser.close()
    print("# Done.", flush=True)


if __name__ == "__main__":
    main()
