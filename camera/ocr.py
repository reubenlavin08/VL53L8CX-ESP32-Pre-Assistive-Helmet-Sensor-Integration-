"""Scene OCR via NVIDIA NIM nemotron-ocr-v2 (cloud).

Design: docs/plans/PLAN-find-by-text.md. NOTE: dedicated CV-infer endpoint,
NOT chat completions. Response schema pinned from the live 2026-08-23
benchmark: data[0].text_detections[] of {text_prediction:{text,confidence},
bounding_box:{points:[{x,y}x4]}} with points normalized 0-1.

Same client discipline as vlm.py: shared NIM key loading, single-flight,
(5,20) timeouts + one retry, every call logged to ocr_log.jsonl.
"""

import base64
import json
import pathlib
import threading
import time

import cv2

from vlm import _api_key, sharpest  # same key + blur-aware frame pick

NIM_URL = "https://ai.api.nvidia.com/v1/cv/nvidia/nemotron-ocr-v2"
_HERE = pathlib.Path(__file__).resolve().parent
LOG = _HERE / "ocr_log.jsonl"

busy = threading.Event()


def read(frame, min_conf=0.0):
    """One OCR pass on a BGR frame. Returns a list of
    {"text","conf","cx","cy","w","h"} (normalized 0-1 centers/extents),
    [] for no text, or None on failure (caller speaks the honest error).
    Single-flight: returns None immediately if a call is in the air."""
    import requests
    if busy.is_set():
        return None
    busy.set()
    t0 = time.time()
    entry = {"t": time.strftime("%H:%M:%S")}
    try:
        key = _api_key()
        if not key:
            entry["err"] = "no key"
            return None
        ok, jb = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            entry["err"] = "encode"
            return None
        b64 = base64.b64encode(jb.tobytes()).decode()
        body = {"input": [{"type": "image_url",
                           "url": f"data:image/jpeg;base64,{b64}"}]}
        r = None
        for attempt in (1, 2):
            try:
                r = requests.post(NIM_URL, json=body, timeout=(5, 20),
                                  headers={"Authorization": f"Bearer {key}"})
                if r.status_code < 500:
                    break
            except requests.RequestException as e:
                entry["err"] = f"attempt{attempt}:{e.__class__.__name__}"
                r = None
        if r is None or r.status_code != 200:
            entry["status"] = getattr(r, "status_code", None)
            return None
        words = []
        for det in r.json()["data"][0].get("text_detections", []):
            conf = det["text_prediction"]["confidence"]
            if conf < min_conf:
                continue
            pts = det["bounding_box"]["points"]
            xs = [pt["x"] for pt in pts]
            ys = [pt["y"] for pt in pts]
            words.append({"text": det["text_prediction"]["text"],
                          "conf": conf,
                          "cx": sum(xs) / len(xs), "cy": sum(ys) / len(ys),
                          "w": max(xs) - min(xs), "h": max(ys) - min(ys)})
        entry.update(status=200, n=len(words), s=round(time.time() - t0, 2))
        return words
    finally:
        entry.setdefault("s", round(time.time() - t0, 2))
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        busy.clear()
