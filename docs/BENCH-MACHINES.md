# Machine benchmarks (field-laptop shootout)

Run with `camera/bench_machine.py` — same YOLO-World model + door prompts
as live door mode, 20 timed runs, median/p90.

## Verdict (2026-08-24)

| | Lenovo (gaming) | Reubens-Laptop (Zenbook) |
|---|---|---|
| CPU | i7-9750H (2019, AVX2) | i5-1135G7 (2020, AVX-512) |
| RAM | 32 GB | 7.7 GB |
| GPU | GTX 1650 4GB (CUDA present, **unused** — torch is CPU-only) | Iris Xe (no CUDA) |
| YOLO-World median | 170.5 ms | **104.4 ms** |
| YOLO-World p90 | 381.2 ms | **109.6 ms** |
| JPEG encode | 6.78 ms | 5.29 ms |
| Camera open (HBV) | 1204 ms | not attached at bench time |

The Zenbook wins the CPU-vs-CPU race — Tiger Lake's AVX-512 beats the
older i7, and its timings are far more consistent (p90 within 5% of
median vs 2.2× on the Lenovo, which was also running a full desktop
session). Neither machine has ever run YOLO on GPU: torch is
`2.13.0+cpu` on both. (The GTX 1650 was only exercised in the local-VLM
experiment, which it failed at 20-25 s/answer.)

**Is the Zenbook fast enough?** Yes. The safety loop (ToF → haptics →
"stop stop") does no neural inference — it's geometry at sensor rate,
identical on both machines. YOLO's 104 ms only gates on-demand door/find
scans (~1 s wall including capture), and VLM/OCR are NIM cloud calls,
identical everywhere. The Zenbook's real constraint is 7.7 GB RAM: run
Iris alone, keep browsers closed.

**Optional upgrade:** CUDA torch on the Lenovo should put YOLO-World-S
at ~20-30 ms — worth it only if scan latency ever feels slow in use.

## Lenovo — 2026-08-24 12:02

```json
{
  "host": "Lenovo",
  "os": "Windows-11-10.0.26200-SP0",
  "python": "3.12.10",
  "cpu": "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz",
  "ram_gb": 31.9,
  "gpu": "Intel(R) UHD Graphics 630 | NVIDIA GeForce GTX 1650",
  "torch": "2.13.0+cpu",
  "cuda": "none",
  "yolo_med_ms": 170.5,
  "yolo_p90_ms": 381.2,
  "jpeg_ms": 6.78,
  "cameras": {
    "Integrated Camera": 1478,
    "HBV HD CAMERA": 1204
  }
}
```

## Reubens-Laptop — 2026-08-24 12:04

```json
{
  "host": "Reubens-Laptop",
  "os": "Windows-11-10.0.26200-SP0",
  "python": "3.12.10",
  "cpu": "11th Gen Intel(R) Core(TM) i5-1135G7 @ 2.40GHz",
  "ram_gb": 7.7,
  "gpu": "Intel(R) Iris(R) Xe Graphics",
  "torch": "2.13.0+cpu",
  "cuda": "none",
  "yolo_med_ms": 104.4,
  "yolo_p90_ms": 109.6,
  "jpeg_ms": 5.29,
  "cameras": {
    "USB2.0 HD UVC WebCam": 627,
    "OBS Virtual Camera": "FAIL"
  }
}
```
