"""
Push a freshly-built firmware image to the ESP over WiFi (no USB needed).

Usage:
    python ota_flash.py                 # uses default host + default bin path
    python ota_flash.py 192.168.1.227   # explicit host

Requires the ESP to be running firmware with the OTA HTTP endpoint enabled
(POST /update with X-OTA-Token header). The token is hard-coded below — keep
in sync with main/wifi_credentials.h on the firmware side.
"""

import sys
import time
import urllib.request
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
DEFAULT_HOST = "192.168.1.227"
OTA_TOKEN    = "helmet-ota-2026"     # must match wifi_credentials.h OTA_TOKEN
BIN_PATH     = Path(__file__).resolve().parent.parent / "build" / "vl53l8cx_esp32.bin"
HTTP_PORT    = 80
# ────────────────────────────────────────────────────────────────────────────


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST

    if not BIN_PATH.exists():
        print(f"!! Firmware binary not found at {BIN_PATH}", file=sys.stderr)
        print(f"   Run 'idf.py build' first.", file=sys.stderr)
        sys.exit(1)

    data = BIN_PATH.read_bytes()
    size_kb = len(data) / 1024
    url = f"http://{host}:{HTTP_PORT}/update"

    print(f"Uploading {size_kb:.1f} KB to {url} ...")
    t0 = time.time()

    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={
            "X-OTA-Token":    OTA_TOKEN,
            "Content-Type":   "application/octet-stream",
            "Content-Length": str(len(data)),
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", errors="ignore").strip()
            dt = time.time() - t0
            print(f"\n[{resp.status}] {body}")
            print(f"Done in {dt:.1f} s  ({size_kb / dt:.0f} KB/s)")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore").strip()
        print(f"\n!! HTTP {e.code}: {body}")
        sys.exit(2)
    except urllib.error.URLError as e:
        print(f"\n!! Could not reach {host}: {e.reason}")
        sys.exit(3)


if __name__ == "__main__":
    main()
