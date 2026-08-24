"""Soundscape-style audio beacon, ported from Microsoft Soundscape (MIT).

The real thing, not an imitation: plays the original 4-region "Current"
(V2) beacon assets, with the two behaviors that make it feel right
(read from Soundscape's DynamicAudioPlayer/DynamicAudioEngineAsset):

  1. Direction is encoded by TIMBRE -- four angular regions each own a
     loopable WAV phrase; the selector picks by relative bearing.
  2. Region changes land on the next BEAT BOUNDARY (6 beats/phrase), so
     scanning your head sounds musical instead of glitchy.

Deviations from Soundscape, on evidence:
  - A+ ("on target") half-angle default 10 deg, not 15 -- our IMU heading
    beats a phone compass (community fork made this configurable).
  - Constant-power stereo pan on top of the region timbre. Bone
    conduction bypasses the pinna, so ILD panning does the spatial work
    (docs/research-sources/bone-conduction-spatial-2026-08-20.md);
    full HRTF convolution would add little here.
  - Distance stays OUT of the beacon (Soundscape's choice too); arrival
    is the caller's job (2:1 hysteresis geofence), we just play the
    Route_End outro when told.
  - Heading loss -> DIM, never stop (their no-heading behavior).

Assets: camera/assets/soundscape_beacon/*.wav  (MIT, (c) Microsoft).
"""

import pathlib
import threading
import wave

import numpy as np

_HERE = pathlib.Path(__file__).resolve().parent
ASSET_DIR = _HERE / "assets" / "soundscape_beacon"

BEATS_PER_PHRASE = 6          # V2 "Current" beacon: 6 beats / 2.416 s
A_PLUS_HALF_DEG = 10.0        # "on target" half-angle (Soundscape: 15)
MASTER_AMP = 0.22             # sits under speech; ticker is 0.10-0.22
DIM_AMP = 0.08                # heading lost / target lost -> dim, not stop
DUCK = 0.4                    # gain multiplier while speech is playing


def _load_wav(path):
    with wave.open(str(path), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2, path
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return sr, data.astype(np.float32) / 32768.0


class Beacon:
    """Continuous 4-region beacon. Call update() every frame with the
    target's wearer-relative azimuth (deg, + = right); call stop()
    (optionally arrived=True for the outro melody) to end guidance."""

    def __init__(self):
        self.sr, self.regions = None, {}
        for name in ("A+", "A", "B", "Behind"):
            sr, d = _load_wav(ASSET_DIR / f"Current_{name}.wav")
            self.sr = sr
            self.regions[name] = d
        n = {len(d) for d in self.regions.values()}
        assert len(n) == 1, "region phrases must share frame count"
        self.frames = n.pop()
        self.spb = self.frames // BEATS_PER_PHRASE       # samples per beat
        _, self.outro = _load_wav(ASSET_DIR / "Route_End.wav")

        self.lock = threading.Lock()
        self.active = False
        self.cur = "Behind"        # region now sounding
        self.pending = None        # region to adopt at next beat boundary
        self.pos = 0               # play cursor in the phrase
        self.az = 0.0              # latest relative azimuth, deg
        self.dim = False
        self.duck = False          # True while speech is playing
        self.outro_pos = None      # not None -> playing arrival melody
        self.stream = None

    # -- region selector: Soundscape standardFourRegionSelector, verbatim
    #    thresholds except the configurable A+ half-angle --
    def _region(self, az):
        a = az % 360.0
        h = A_PLUS_HALF_DEG
        if a >= 360 - h or a <= h:
            return "A+"
        if 305 <= a < 360 - h or h < a <= 55:
            return "A"
        if 235 <= a < 305 or 55 < a <= 125:
            return "B"
        return "Behind"

    def _ensure_stream(self):
        if self.stream is not None:
            return
        import sounddevice as sd
        self.stream = sd.OutputStream(samplerate=self.sr, channels=2,
                                      dtype="float32", blocksize=1024,
                                      callback=self._cb)
        self.stream.start()

    def _cb(self, out, nframes, t, status):
        with self.lock:
            if self.outro_pos is not None:            # arrival melody
                seg = self.outro[self.outro_pos:self.outro_pos + nframes]
                buf = np.zeros(nframes, np.float32)
                buf[:len(seg)] = seg * MASTER_AMP
                self.outro_pos += nframes
                if self.outro_pos >= len(self.outro):
                    self.outro_pos = None
                    self.active = False
                out[:] = np.column_stack([buf, buf])
                return
            if not self.active:
                out.fill(0)
                return
            amp = (DIM_AMP if self.dim else MASTER_AMP) * (DUCK if self.duck
                                                           else 1.0)
            # constant-power pan from azimuth (rear mirrored to the sides --
            # the Behind timbre carries "behind"; pan carries the side)
            az = self.az
            if az > 90:   az = 180 - az
            if az < -90:  az = -180 - az
            th = (az + 90.0) / 180.0 * (np.pi / 2)
            gl, gr = np.cos(th) * amp, np.sin(th) * amp

            buf = np.empty(nframes, np.float32)
            done = 0
            while done < nframes:
                # beat-quantized region switching (the Soundscape trick):
                # adopt the pending region only when the cursor crosses a
                # beat boundary
                if self.pending and self.pos % self.spb == 0:
                    self.cur, self.pending = self.pending, None
                nxt_beat = ((self.pos // self.spb) + 1) * self.spb
                take = min(nframes - done, nxt_beat - self.pos,
                           self.frames - self.pos)
                d = self.regions[self.cur]
                buf[done:done + take] = d[self.pos:self.pos + take]
                self.pos = (self.pos + take) % self.frames
                done += take
            out[:] = np.column_stack([buf * gl, buf * gr])

    # -- public API -------------------------------------------------------
    def start(self):
        self._ensure_stream()
        with self.lock:
            self.active = True
            self.outro_pos = None
            self.pos = 0
            self.cur = self._region(self.az)
            self.pending = None

    def update(self, rel_az_deg, dim=False, duck=False):
        with self.lock:
            self.az = float(rel_az_deg)
            self.dim = bool(dim)
            self.duck = bool(duck)
            r = self._region(self.az)
            if r != self.cur:
                self.pending = r
            else:
                self.pending = None

    def stop(self, arrived=False):
        with self.lock:
            if arrived and self.active:
                self.outro_pos = 0        # play outro, then silence
            else:
                self.active = False


class ClickPlayer:
    """Latest-wins stereo one-shot player for the directional ticker
    (PLAN-spatialized-clicks). Constant-power pan with ILD exaggeration
    (x1.5 angle, capped +-90): on bone conduction / laptop speakers the
    level difference does the spatial work (ITD is unreliable there --
    bone-conduction-spatial-2026-08-20). Own OutputStream; Windows mixes
    it with the beacon's."""

    def __init__(self, sr=22050):
        self.sr = sr
        self.lock = threading.Lock()
        self.cur = None          # (stereo ndarray, pos)
        self.stream = None

    def _ensure(self):
        if self.stream is not None:
            return
        import sounddevice as sd
        self.stream = sd.OutputStream(samplerate=self.sr, channels=2,
                                      dtype="float32", blocksize=256,
                                      callback=self._cb)
        self.stream.start()

    def _cb(self, out, nframes, t, status):
        out.fill(0)
        with self.lock:
            if self.cur is None:
                return
            buf, pos = self.cur
            take = min(nframes, len(buf) - pos)
            out[:take] = buf[pos:pos + take]
            self.cur = None if pos + take >= len(buf) else (buf, pos + take)

    def play(self, mono, az_deg):
        self._ensure()
        az = max(-90.0, min(90.0, az_deg * 1.5))
        th = (az + 90.0) / 180.0 * (np.pi / 2)
        st = np.column_stack([mono * np.cos(th),
                              mono * np.sin(th)]).astype(np.float32)
        with self.lock:
            self.cur = (st, 0)
