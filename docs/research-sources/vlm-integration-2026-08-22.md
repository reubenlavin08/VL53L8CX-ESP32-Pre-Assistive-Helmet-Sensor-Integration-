# VLM "describe" tier — model choice + integration design — 2026-08-22

You asked how a VLM fits with everything else. Answer: build-ready.
Condensed-verbatim from the research agent.

## The pick

**Local default: Qwen3-VL-8B** (Ollama `qwen3-vl:8b`, Q4 = 6.1 GB VRAM,
Apache 2.0) — explicitly trained for spatial perception (positions,
viewpoints, occlusions). **API fallback: Claude Sonnet** on
timeout/offline (~$0.005/query; even 100 queries/day ≈ $15/mo).
Estimated latency ~1.5–2.5 s per query on our GPU (benchmark to
confirm). 8 GB VRAM machines: use `qwen3-vl:4b`.

## The key precedent: WorldScribe (UIST 2024)

- **Three-tier cascade by richness/latency**: YOLO-class labels
  (0.1 s) → small VLM (~3 s) → big VLM (~9 s). **Our architecture
  already mirrors tier 1 — the VLM adds tiers 2–3.**
- **Length adapts**: <5 words while the scene changes; detail only on
  dwell. On-demand version: one short sentence; detail on follow-up
  press.
- User study (6 BVI): hallucinations eroded trust; verbose output
  "overwhelming"; users want "minimum viable information, like a human
  describer."

## The safety-critical finding

**BLV users rate wrong answers as plausible — they cannot detect
hallucination** (arXiv 2408.06303). VizWiz shows blind-taken photos
are routinely blurry/badly framed. Therefore: **abstention is a
first-class feature** — the prompt must force "I can't see that
clearly" over a guess, because the user can't check.

## The system prompt (use as-is)

```
You are a sighted assistant describing a live camera view to a blind user.
Answer in ONE sentence, under 20 words. Concrete nouns, colors, and egocentric
directions (left/right/ahead, near/far) only. No opinions or filler.
If the image is too blurry or the thing asked about is not visible, say
exactly that — never guess.
Example: "A red mug on the counter, handle toward you."
```

## Integration design (fits the tier engine)

1. **Query tier ONLY** — safety speech/ticker always preempts the VLM
   mid-sentence, never the reverse (cancel flag).
2. **Sensor-fusion prompting**: inject live YOLO+ToF state as text
   ("person 1.2 m ahead-left; chair 0.8 m right") + "don't mention
   objects you can't see in the image" — grounds the model, directly
   attacks hallucination.
3. **Frame selection**: sharpest of the last ~10 frames
   (variance-of-Laplacian) — kills the VizWiz blur failure.
4. **"What's in my hand"**: v1 = fixed bottom-center crop (held objects
   live there in an egocentric rig — no hand detector needed); MediaPipe
   Hands only if that fails (it degrades on egocentric fisheye).
5. **Pre-warm**: Ollama `keep_alive: -1` + one dummy inference at boot;
   VRAM check vs YOLO (fine on 12–16 GB).
6. **Streaming TTS**: split on sentence punctuation → first audio ~1 s.

A ~30-line integration sketch (keypress → sharpest frame → crop →
Ollama stream → sentence-by-sentence TTS with cancel) is in the agent
report; implementation is an afternoon once Ollama is installed.

## Unverified flags

Local latency (estimate — benchmark); MediaPipe egocentric numbers;
crop-vs-full benefit (A/B ourselves); Moondream 3 VRAM/serving.

Sources: WorldScribe arXiv:2408.06627 · arXiv:2408.06303 · VizWiz ·
Be My AI · Qwen3-VL HF/Ollama pages.

## Benchmark results (2026-08-22, the desktop, GTX 1650 4 GB)

| Option | Warm latency | Quality | Verdict |
|---|---|---|---|
| Local qwen3-vl:2b (Ollama) | **20-25 s** for a complete answer (early "3.8 s" was truncated thinking, empty answer) | Good - correctly described the room | **FAIL** on this GPU |
| NIM cloud llama-3.2-11b-vision (free endpoint, user's key in openclaw/.env) | **2.3-6.4 s** (variable, free-tier queue) | Good; **abstained correctly** on unanswerable ("too blurry - can't identify"); ignores word cap -> truncate to first sentence client-side | **USABLE - the pick for this machine** |

Decisions: NIM = the VLM path on the desktop (needs connectivity);
re-benchmark locally on the field laptop (stronger GPU) before assuming
cloud-only in the field. 8B local model impossible here (6.1 GB model,
4 GB VRAM). NIM catalog also has nemotron-ocr-v2 (free endpoint) - a
candidate for the signage/find-by-text OCR engine instead of local
PARSeq; and nemotron-nano-12b-v2-vl untested.
