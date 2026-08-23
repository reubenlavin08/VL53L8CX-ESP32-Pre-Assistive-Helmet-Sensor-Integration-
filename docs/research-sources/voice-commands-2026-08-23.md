# Voice command interface — research + corrected design — 2026-08-23

You asked for industry-standard verification before building. Verdict:
**the original plan was half right** — Vosk small + grammar is the right
free engine, but *ungated always-on* is not what anyone ships and has a
confirmed failure mode.

## The correction (evidence)

- **Vosk grammar mode force-matches**: acoustically similar
  out-of-vocabulary speech gets matched to grammar entries "even with
  confidence scores of 1.0" (vosk-api issue #1339); the official
  `[unk]` rejection token "hardly ever" fires on some models (#1017).
  Always-on on a street = spurious commands from bystander speech and
  our own TTS.
- **Every shipping worn device gates commands**: "Hey Envision," "Hey
  Meta," "Hey OrCam" + buttons. None run an open always-on grammar.
  Wake-word engines are the components that publish false-accepts/hour
  (openWakeWord claims <0.5/hr, unverified) — that's where the industry
  puts the always-on gate.
- Whisper-family engines rejected for this job: no streaming grammar,
  heavy CPU always-on, and hallucinate text on silence/noise.
- Picovoice Rhino has true out-of-context rejection — technically
  superior, but needs an account key and free-tier terms are
  unverified. v2 candidate.

## The shipped design (v1)

1. **Engine**: Vosk small-en-us (installed) + KaldiRecognizer JSON
   grammar, 16 kHz mono via sounddevice.
2. **Two-state gate**: IDLE grammar = ["helmet", "stop", "quiet",
   "[unk]"] — only the wake word arms; **"stop" and "quiet" work
   without waking** (false-accept cost is benign: things go quiet).
   Wake → earcon → ARMED for 5 s with the full command grammar →
   single command → back to IDLE. Timeout → low tone.
3. **Commands**: describe · what's/what is in my hand · scan doors ·
   door one/two/three · guide · stop · quiet · audio on · what's/what
   is around. Multi-word phrases on purpose (harder to false-match).
4. **Rejection**: any result containing [unk] or not an exact phrase
   is discarded and logged.
5. **Half-duplex**: mic frames dropped while our TTS speaks + 250 ms
   tail — the standard software-only self-hearing fix (AEC on Windows
   Python is not viable; skip).
6. **Confirmation UX** (BLV evidence: terse beats verbose): earcon on
   wake; just-do-it for queries; one-word echo for mode changes.
7. **Logging**: every accepted AND rejected utterance →
   `camera/voice_log.jsonl` (tuning data + flywheel).
8. Keyboard stays as fallback (BLV users report social discomfort
   speaking aloud in public — always have a silent path).

## Deferred to v2

AEC/barge-in · custom-trained wake word · Rhino migration (check free
tier) · boom-mic hardware (the ordered headsets have mics) · adaptive
thresholds from the logged false accepts.
