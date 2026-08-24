"""Wake-word-gated voice commands via Vosk (offline, CPU).

Design + evidence: docs/research-sources/voice-commands-2026-08-23.md.
Two-state machine (industry pattern -- every shipping wearable gates
behind a wake word; Vosk grammar mode force-matches bystander speech,
vosk-api #1339):

  IDLE   grammar ["iris", "stop", "quiet", "[unk]"]
         - "iris" -> earcon -> ARMED (5 s window)
         - "stop"/"quiet" work UNGATED (false-accept cost is benign)
  ARMED  full command grammar; one accepted command -> IDLE;
         timeout -> low tone -> IDLE

Half-duplex: mic frames are dropped while our own TTS speaks (+250 ms
tail). Every final utterance -- accepted or rejected -- is logged to
voice_log.jsonl for threshold tuning later.
"""

import json
import pathlib
import queue
import threading
import time

_HERE = pathlib.Path(__file__).resolve().parent
MODEL_DIR = _HERE / "models" / "vosk-model-small-en-us-0.15"
LOG = _HERE / "voice_log.jsonl"
ARM_S = 5.0
TAIL_S = 0.25          # keep dropping mic briefly after TTS ends

# spoken phrase -> command token (multi-word on purpose: harder to
# false-match than single words)
PHRASES = {
    "describe": "describe",
    "what's in my hand": "hand",
    "what is in my hand": "hand",
    "scan doors": "doors",
    "scan for doors": "doors",
    "door one": "sel1",
    "door two": "sel2",
    "door three": "sel3",
    "guide": "guide",
    "stop": "stop",
    "quiet": "quiet",
    "audio on": "audio_on",
    "what's around": "around",
    "what is around": "around",
    "wrong": "wrong",
    "flag that": "flag",
    "read that": "read",
}

# curated findable words (closed grammar cannot do open vocabulary --
# arbitrary words are dev-keyboard-only via key f; PLAN-find-by-text)
FIND_WORDS = ["exit", "washroom", "open", "push", "pull", "sale", "ketchup"]
for _w in FIND_WORDS:
    PHRASES[f"find {_w}"] = f"find:{_w}"
WAKE = "iris"             # the iris of the eye, and the Greek goddess of sight
IDLE_OK = {"stop": "stop", "quiet": "quiet", "wrong": "wrong"}  # ungated

commands = queue.Queue()
available = False


def _log(entry):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def _beep(freq, ms):
    try:
        import winsound
        winsound.Beep(freq, ms)
    except Exception:
        pass


def _worker(is_speaking):
    global available
    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer, SetLogLevel
    except ImportError as e:
        print(f"voice: unavailable ({e})")
        return
    if not MODEL_DIR.exists():
        print(f"voice: model missing at {MODEL_DIR}")
        return
    SetLogLevel(-1)
    model = Model(str(MODEL_DIR))
    idle_gram = json.dumps([WAKE] + list(IDLE_OK) + ["[unk]"])
    full_gram = json.dumps(list(PHRASES) + [WAKE, "[unk]"])
    rec = KaldiRecognizer(model, 16000, idle_gram)
    audio_q = queue.Queue(maxsize=50)

    def cb(indata, frames, t, status):
        try:
            audio_q.put_nowait(bytes(indata))
        except queue.Full:
            pass

    state = {"armed_until": 0.0}
    tts_tail = [0.0]

    def set_grammar(g):
        nonlocal rec
        rec = KaldiRecognizer(model, 16000, g)

    try:
        stream = sd.RawInputStream(samplerate=16000, blocksize=4000,
                                   dtype="int16", channels=1, callback=cb)
        stream.start()
    except Exception as e:
        print(f"voice: no microphone ({e})")
        return
    available = True
    print("voice: ready (say 'iris' to wake; 'stop'/'quiet' always work)")

    while True:
        data = audio_q.get()
        now = time.monotonic()
        # half-duplex: never listen while (or just after) we speak
        if is_speaking():
            tts_tail[0] = now
            rec.Reset()
            continue
        if now - tts_tail[0] < TAIL_S:
            continue
        armed = now < state["armed_until"]
        if not armed and state["armed_until"] > 0:
            state["armed_until"] = 0.0        # window expired
            _beep(500, 120)
            set_grammar(idle_gram)
        if not rec.AcceptWaveform(data):
            continue
        txt = json.loads(rec.Result()).get("text", "").strip()
        if not txt:
            continue
        entry = {"t": time.strftime("%H:%M:%S"), "heard": txt,
                 "armed": armed}
        if "[unk]" in txt:
            entry["verdict"] = "rejected-unk"
            _log(entry)
            continue
        if not armed:
            if txt == WAKE:
                state["armed_until"] = now + ARM_S
                set_grammar(full_gram)
                _beep(1400, 120)
                entry["verdict"] = "wake"
            elif txt in IDLE_OK:
                commands.put(IDLE_OK[txt])
                entry["verdict"] = f"cmd:{IDLE_OK[txt]} (ungated)"
            else:
                entry["verdict"] = "rejected-idle"
        else:
            if txt in PHRASES:
                commands.put(PHRASES[txt])
                entry["verdict"] = f"cmd:{PHRASES[txt]}"
                state["armed_until"] = 0.0    # one command per wake
                set_grammar(idle_gram)
            elif txt == WAKE:
                state["armed_until"] = now + ARM_S   # re-arm
                entry["verdict"] = "re-wake"
            else:
                entry["verdict"] = "rejected-nomatch"
        _log(entry)


def start(is_speaking):
    """Launch the voice worker. is_speaking: callable -> bool (half-duplex)."""
    threading.Thread(target=_worker, args=(is_speaking,),
                     daemon=True).start()
