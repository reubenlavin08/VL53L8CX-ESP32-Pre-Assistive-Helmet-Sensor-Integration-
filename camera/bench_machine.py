"""One-shot machine benchmark: specs + the perf numbers that matter for
Iris (YOLO-World detect, JPEG encode, camera open). Run on each candidate
field machine; results append to docs/BENCH-MACHINES.md as a row.

    venv\\Scripts\\python.exe camera\\bench_machine.py
"""

import json
import pathlib
import platform
import subprocess
import time

import cv2
import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
DOC = _HERE.parent / "docs" / "BENCH-MACHINES.md"


def specs():
    s = {"host": platform.node(), "os": platform.platform(),
         "python": platform.python_version()}
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor).Name; "
             "[math]::Round((Get-CimInstance Win32_ComputerSystem)."
             "TotalPhysicalMemory/1GB,1); "
             "(Get-CimInstance Win32_VideoController).Name -join ' | '"],
            capture_output=True, text=True, timeout=30)
        cpu, ram, gpu = [x.strip() for x in r.stdout.strip().splitlines()[:3]]
        s.update(cpu=cpu, ram_gb=float(ram), gpu=gpu)
    except Exception as e:
        s["spec_err"] = str(e)
    try:
        import torch
        s["torch"] = torch.__version__
        s["cuda"] = torch.cuda.get_device_name(0) \
            if torch.cuda.is_available() else "none"
    except Exception:
        s["torch"] = "n/a"
    return s


def bench_yolo():
    """YOLO-World small, 640px, same model + prompt set as door mode."""
    from ultralytics import YOLOWorld
    m = YOLOWorld(str(_HERE / "yolov8s-worldv2.pt"))
    m.set_classes(["door", "glass door", "doorway", "double door"])
    img = np.random.randint(0, 255, (720, 1280, 3), np.uint8)
    m.predict(img, imgsz=640, verbose=False)          # warmup + trace
    m.predict(img, imgsz=640, verbose=False)
    ts = []
    for _ in range(20):
        t0 = time.perf_counter()
        m.predict(img, imgsz=640, verbose=False)
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return {"yolo_med_ms": round(ts[len(ts) // 2], 1),
            "yolo_p90_ms": round(ts[int(len(ts) * .9)], 1)}


def bench_encode():
    img = np.random.randint(0, 255, (720, 1280, 3), np.uint8)
    t0 = time.perf_counter()
    for _ in range(50):
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return {"jpeg_ms": round((time.perf_counter() - t0) * 1000 / 50, 2)}


def bench_camera():
    """Open + first-frame latency for every DirectShow camera present."""
    out = {}
    try:
        from pygrabber.dshow_graph import FilterGraph
        names = FilterGraph().get_input_devices()
    except Exception:
        names = []
    for i, n in enumerate(names):
        t0 = time.perf_counter()
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok, _ = cap.read()
        out[n] = round((time.perf_counter() - t0) * 1000) if ok else "FAIL"
        cap.release()
    return {"cameras": out}


if __name__ == "__main__":
    r = specs()
    for fn in (bench_yolo, bench_encode, bench_camera):
        try:
            r.update(fn())
        except Exception as e:
            r[fn.__name__ + "_err"] = str(e)[:120]
    print(json.dumps(r, indent=2))
    stamp = time.strftime("%Y-%m-%d %H:%M")
    row = (f"\n## {r['host']} — {stamp}\n\n```json\n"
           + json.dumps(r, indent=2) + "\n```\n")
    if not DOC.exists():
        DOC.write_text("# Machine benchmarks (field-laptop shootout)\n",
                       encoding="utf-8")
    DOC.write_text(DOC.read_text(encoding="utf-8") + row, encoding="utf-8")
    print(f"\nappended to {DOC}")
