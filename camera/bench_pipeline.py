"""Backpack-readiness benchmark -- times every compute-heavy stage of
cv_fusion on THIS machine, no hardware needed.

    python camera/bench_pipeline.py

Stages timed on synthetic 720p frames: YOLO26n-seg inference (the dominant
cost), cylindrical remap, JPEG encode for the phone viewer, fisheye zone
projection. Prints a live-fps verdict for the field rig.
"""
import pathlib
import time

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent


def t(fn, n=15, warmup=3):
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t0) / n * 1000


def main():
    img = (np.random.rand(720, 1280, 3) * 255).astype(np.uint8)
    print("=" * 54)
    print(" BACKPACK BENCHMARK")
    print("=" * 54)

    cal = np.load(ROOT / "camera" / "calibration_720p.npz")
    K, D = cal["K"], cal["D"].reshape(4, 1)

    import sys
    sys.path.insert(0, str(ROOT / "camera"))
    import cv_fusion as cvf
    mx, my, _ = cvf.build_cyl(K, D)
    ms_remap = t(lambda: cv2.remap(img, mx, my, cv2.INTER_LINEAR))
    print(f"cylindrical remap        {ms_remap:7.1f} ms")

    ms_jpeg = t(lambda: cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70]))
    print(f"phone-viewer JPEG        {ms_jpeg:7.1f} ms")

    ring = cvf.zone_boundary_tans() if hasattr(cvf, "zone_boundary_tans") else None
    import fusion_overlay as fo
    ring = fo.zone_boundary_tans()
    P = ring.shape[2]
    pts = (ring.reshape(-1, 2) * 800.0)
    allp = np.column_stack([pts, np.full(len(pts), 800.0)])

    def proj():
        cv2.fisheye.projectPoints(allp.reshape(1, -1, 3).astype(np.float64),
                                  np.zeros(3), np.zeros(3), K, D)
    ms_proj = t(proj, n=50)
    print(f"zone projection (x2)     {ms_proj*2:7.1f} ms")

    from ultralytics import YOLO
    m = YOLO(str(ROOT / "yolo26n-seg.pt"))
    ms_seg = t(lambda: m.predict(img, imgsz=416, verbose=False), n=10)
    print(f"YOLO26n-seg @416         {ms_seg:7.1f} ms   <- dominant")

    m2 = YOLO(str(ROOT / "yolo26n.pt"))
    ms_det = t(lambda: m2.predict(img, imgsz=416, verbose=False), n=10)
    print(f"YOLO26n detect-only @416 {ms_det:7.1f} ms   (fallback mode)")

    print("-" * 54)
    # detector runs in its own thread; the render loop carries remap-encode-proj
    render_ms = ms_remap + ms_jpeg + ms_proj * 2 + 8
    print(f"render loop  ~{1000/render_ms:5.1f} fps   "
          f"detector(seg) ~{1000/ms_seg:4.1f} fps   detect-only ~{1000/ms_det:4.1f} fps")
    seg_ok = ms_seg < 200
    print(f"VERDICT: {'FIELD-READY with seg' if seg_ok else 'use detect-only in the field (seg too slow)'}"
          f"{' -- try OpenVINO export for a free speedup' if ms_seg > 120 else ''}")


if __name__ == "__main__":
    main()
