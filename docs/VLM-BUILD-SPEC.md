# VLM describe/OCR build spec — 2026-08-23

Scoped to industry practice for a production LLM-API integration.
Research base: [[vlm-integration-2026-08-22]] (WorldScribe cascade,
abstention-first prompting, VizWiz failure modes) + live benchmarks.

## Decisions (final)

| Item | Decision | Why |
|---|---|---|
| Model | NIM cloud `meta/llama-3.2-11b-vision-instruct` | 2.3–6.4 s measured; correct abstention; local FAILED on both machines (GTX 1650 4 GB = 20–25 s; field laptop = Iris Xe iGPU, no CUDA) |
| Text/OCR | NIM `nvidia/nemotron-ocr-v2` (free endpoint) — benchmark next | scene-text specialist beats a generalist VLM at reading |
| Interaction | Pull-only keys: `v` = describe ahead, `h` = what's in my hand | silence-default; voice later |
| Connectivity | Requires network (field = phone hotspot, already the rig's design) | no local option exists |

## Industry-standard requirements (the checklist)

1. **Secrets**: API key from `NVIDIA_API_KEY` env var, falling back to a
   git-ignored local file. **Never in code, never committed.**
2. **Timeouts + retry**: connect 5 s, read 20 s; ONE retry on 5xx/timeouts;
   then a spoken, honest failure ("description unavailable — no
   connection"). Silence must never mean "nothing there."
3. **Single-flight**: one query in the air; re-press while busy →
   "still working." No queues that speak stale answers.
4. **Cancellation**: safety tier (directive speech) preempts — result of
   a cancelled query is dropped, never spoken late.
5. **Input hygiene**: sharpest-of-last-10-frames (variance of
   Laplacian); JPEG q70 (~75 KB, under NIM inline limits); hand mode =
   bottom-center crop (egocentric held objects live there).
6. **Grounding**: current YOLO+ToF detections injected as text context
   ("person 1.2 m ahead-left") + instruction not to mention unseen
   objects — the anti-hallucination measure from the research.
7. **Output discipline**: model ignores word caps → client-side
   truncate to the first 2 sentences; strip markdown/asterisks before
   TTS.
8. **Abstention prompt**: "if blurry or not visible, say so — never
   guess" (BLV users cannot detect a wrong answer; verified working in
   our benchmark).
9. **Observability**: every query logged (timestamp, latency, question,
   answer, http status) to `camera/vlm_log.jsonl` — feeds the
   intervention-logging flywheel (IDEA-BANK #16).
10. **Stale-frame guard**: frame older than 1 s → re-grab; answer tagged
    to the frame's timestamp.

## Out of scope (this build)

Voice input · streaming TTS (answers are 1–2 sentences; not worth SSE
complexity at 2–6 s total) · OCR endpoint integration (next build,
after benchmark) · continuous description (never — vOICe lesson).

## Files

- `camera/vlm.py` — client module (key loading, frame selection,
  request, retry, truncation, logging).
- `cv_fusion.py` — frame ring buffer + keys `v`/`h` + busy flag +
  query-tier speech handoff.
