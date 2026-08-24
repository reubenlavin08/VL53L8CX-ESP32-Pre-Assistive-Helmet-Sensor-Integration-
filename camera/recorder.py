"""Session recorder: annotated dashboard video + microphone audio.

For field runs with the laptop closed in a backpack: toggle from the
phone (REC button) or key `c`. Writes to sessions/<stamp>_rec/:
  rec.mp4  -- the annotated view (overlays, callout text) at ~10 fps
  rec.wav  -- laptop microphone, 16 kHz mono (wearer's voice + room;
              TTS callouts are in the flight log with timestamps and can
              be composited in later with ffmpeg)

Video is written at a fixed nominal fps with wall-clock throttling, so
long runs drift a little against the audio -- fine for review/demo
footage, not for lip-sync.
"""

import pathlib
import time
import wave

import cv2

_HERE = pathlib.Path(__file__).resolve().parent
FPS = 10.0


class Recorder:
    def __init__(self):
        self.vw = None
        self.wav = None
        self.stream = None
        self.path = None
        self._last = 0.0

    @property
    def on(self):
        return self.vw is not None

    def start(self, frame):
        if self.on:
            return
        d = _HERE / "sessions" / (time.strftime("%Y-%m-%d_%H%M%S") + "_rec")
        d.mkdir(parents=True, exist_ok=True)
        h, w = frame.shape[:2]
        self.vw = cv2.VideoWriter(str(d / "rec.mp4"),
                                  cv2.VideoWriter_fourcc(*"mp4v"),
                                  FPS, (w, h))
        self.path = d
        self._last = 0.0
        try:
            import sounddevice as sd
            self.wav = wave.open(str(d / "rec.wav"), "wb")
            self.wav.setnchannels(1)
            self.wav.setsampwidth(2)
            self.wav.setframerate(16000)

            def cb(indata, frames, t, status):
                if self.wav is not None:
                    try:
                        self.wav.writeframes(bytes(indata))
                    except ValueError:
                        pass
            # WASAPI shared mode: coexists with the voice thread's stream
            self.stream = sd.RawInputStream(samplerate=16000, blocksize=2000,
                                            dtype="int16", channels=1,
                                            callback=cb)
            self.stream.start()
        except Exception as e:
            print(f"recorder: no mic audio ({e})")
            self.stream = None

    def add(self, frame, now):
        if self.vw is not None and now - self._last >= 1.0 / FPS:
            self._last = now
            self.vw.write(frame)

    def stop(self):
        if not self.on:
            return None
        self.vw.release()
        self.vw = None
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        if self.wav is not None:
            w, self.wav = self.wav, None
            w.close()
        return self.path
