# 3D Point Cloud Visualiser

Live 3D point cloud rendering of the VL53L8CX sensor's 8×8 distance grid, projected through the sensor's true 45° field of view and coloured by distance using the `viridis` colormap.

## Setup

```bash
cd visualizer
python -m venv venv
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Running

1. Flash the ESP32 with `STREAM_DATA = 1` set in `main/main.c` (this is the default).
2. Make sure `idf.py monitor` is **closed** — only one program can hold the serial port. If monitor is open, press `Ctrl + ]` to close it.
3. Start the visualiser:

```bash
python visualizer.py --port COM12
```

Use `Ctrl + C` in the terminal to stop.

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | `COM12` | Serial port the ESP32 is on |
| `--baud` | `115200` | Must match the ESP-IDF default |
| `--max-mm` | `4000` | Z-axis range and colour scale maximum |

## How it works

Each of the 64 zones has a unique angular position within the sensor's field of view. The visualiser computes a unit direction vector for every zone once at startup, then multiplies each zone's distance by its direction to produce the live 3D point cloud. Invalid zones are clamped to the maximum distance on the ESP32 side, so the cloud never has gaps.
