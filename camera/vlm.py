"""On-demand VLM scene description via NVIDIA NIM (cloud).

Design: docs/VLM-BUILD-SPEC.md. Local inference is not an option on
either machine (GTX 1650 4 GB: 20-25 s/answer; field laptop: Iris Xe,
no CUDA), so this is a thin, disciplined cloud client:

  - key from NVIDIA_API_KEY env, else a git-ignored local file
  - sharpest-of-N frame selection (VizWiz: blur is the #1 killer)
  - sensor-context grounding + forced abstention in the prompt
  - 5 s connect / 20 s read, one retry, honest spoken failure
  - single-flight, cancellable, first-2-sentences truncation
  - every query appended to vlm_log.jsonl (flywheel food)
"""

import base64
import json
import os
import pathlib
import re
import threading
import time

import cv2
import numpy as np

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL = "meta/llama-3.2-11b-vision-instruct"
_HERE = pathlib.Path(__file__).resolve().parent
LOG = _HERE / "vlm_log.jsonl"
_KEY_FALLBACKS = [
    _HERE / "nim_key.txt",                       # git-ignored, ours
    pathlib.Path("C:/Users/User/openclaw/.env"),  # existing key location
]

SYS = ("You are a sighted assistant describing a live camera view to a "
       "blind user. Answer in ONE sentence, under 20 words. Concrete "
       "nouns, colors, and egocentric directions (left/right/ahead, "
       "near/far) only. No opinions or filler. If the image is too "
       "blurry or the thing asked about is not visible, say exactly "
       "that - never guess.")

busy = threading.Event()      # single-flight guard, readable by the UI


def _api_key():
    k = os.environ.get("NVIDIA_API_KEY")
    if k:
        return k.strip()
    for p in _KEY_FALLBACKS:
        try:
            for line in p.read_text().splitlines():
                line = line.strip()
                if line.startswith("NVIDIA_API_KEY="):
                    return line.split("=", 1)[1].strip()
                if line.startswith("nvapi-"):
                    return line
        except OSError:
            continue
    return None


def sharpest(frames):
    """Pick the least blurry of the recent frames (variance of Laplacian)."""
    best, bv = None, -1.0
    for f in frames:
        v = cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY),
                          cv2.CV_64F).var()
        if v > bv:
            bv, best = v, f
    return best


def _encode(img, hand_mode):
    if hand_mode:                     # held objects live bottom-center in an
        h, w = img.shape[:2]          # egocentric rig; generous margin
        img = img[int(h * 0.30):, int(w * 0.15):int(w * 0.85)]
    ok, jb = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return base64.b64encode(jb.tobytes()).decode() if ok else None


def _log(entry):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _truncate(text):
    """First 2 sentences, markdown stripped -- the model ignores word caps."""
    text = re.sub(r"[*_#`]", "", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:2]).strip()


def describe(frames, question, sensor_ctx="", hand_mode=False,
             cancel=None, speak=None):
    """Run one query. frames: list of recent BGR frames. speak(text) is
    called with the final utterance (or an honest failure). Returns the
    text, or None if cancelled/superseded."""
    import requests
    if busy.is_set():
        if speak:
            speak("still working")
        return None
    busy.set()
    t0 = time.time()
    entry = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "q": question,
             "hand": hand_mode}
    try:
        key = _api_key()
        if not key:
            if speak:
                speak("description unavailable, no API key")
            entry["err"] = "no key"
            return None
        img = sharpest(frames)
        if img is None:
            if speak:
                speak("no camera frame")
            entry["err"] = "no frame"
            return None
        b64 = _encode(img, hand_mode)
        prompt = question
        if sensor_ctx:
            prompt = (f"Sensor context (may be stale, use only to ground "
                      f"what you SEE): {sensor_ctx}.\n{question}")
        body = {"model": MODEL,
                "messages": [
                    {"role": "system", "content": SYS},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url":
                            {"url": f"data:image/jpeg;base64,{b64}"}}]}],
                "max_tokens": 80, "temperature": 0.2}
        r = None
        for attempt in (1, 2):
            try:
                r = requests.post(NIM_URL, json=body, timeout=(5, 20),
                                  headers={"Authorization": f"Bearer {key}"})
                if r.status_code < 500:
                    break
            except requests.RequestException as e:
                entry["err"] = f"attempt{attempt}: {e.__class__.__name__}"
                r = None
        if r is None or r.status_code != 200:
            entry["status"] = getattr(r, "status_code", None)
            if speak:
                speak("description unavailable, no connection")
            return None
        text = _truncate(r.json()["choices"][0]["message"]["content"])
        entry.update(status=200, ans=text, s=round(time.time() - t0, 2))
        if cancel is not None and cancel.is_set():
            entry["cancelled"] = True          # dropped, never spoken late
            return None
        if speak:
            speak(text)
        return text
    finally:
        entry.setdefault("s", round(time.time() - t0, 2))
        _log(entry)
        busy.clear()
