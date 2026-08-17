# HBV-1716WA / "HBV HD CAMERA" — Verified Spec Sheet

**Compiled 2026-07-25.** Every row marked with provenance. Per the hard rule: no inference is
presented as fact. Where no official document exists, ground truth was taken from the device itself.

**USB ID:** `VID_0AC8 PID_0346` — enumerates as **"HBV HD CAMERA"** (+ a UAC microphone).
**Connection on this laptop:** root-hub port HS02, USB 2.0 **High Speed**, no hub, direct.

---

## ⚠️ There is NO official datasheet for this exact model

Verified negative: hbvcamera.com (Shenzhen Huiber Vision) has **no downloads/datasheet section**
and lists **no 140°/"WA" variant** of the 1716. "HBV-1716WA" is a reseller/Amazon SKU, not a
catalogued HBVCAM model. Treat every "WA-specific" number as undocumented until measured.

Substitutes used, in order of authority:
1. **The device's own UVC descriptors** (dumped locally — see mode table below). Authoritative.
2. Official HBVCAM spec tables for **sibling** 1716-family modules (80/94/100/130/180°).
3. OmniVision OV2710 sensor datasheet (already in this folder).

---

## Facts

| Item | Value | Provenance |
|---|---|---|
| Sensor | OmniVision **OV2710**, 1/2.7", 3.0 µm pixel, 1080p30, 69 dB DR | OFFICIAL (OmniVision + HBVCAM) |
| **"140°" is DIAGONAL** | **CONFIRMED** — HBVCAM publishes 1716 FOV as DFOV/HFOV/VFOV triples: 80/70/43, 100/85/58, 130/103/65; the 1716-180 listing says "180° DFOV" | OFFICIAL |
| **Lens EFL / F-number for the WA** | **NOT DOCUMENTED ANYWHERE** | — |
| **HFOV / VFOV for the WA** | **NOT DOCUMENTED.** Our prior ~109°H/67°V is an **EXTRAPOLATION from siblings, not a spec.** Must come from calibration (K matrix) | EXTRAPOLATION — LOW confidence |
| Sibling lens specs (anchor only) | 3.0 mm f/2.4 → 100° DFOV; 3.6 mm f/2.4 → 94°; construction 2G2P; TV distortion <5%; IR-cut 650±10 nm | OFFICIAL, **not transferable to the WA** |
| Focus | "Fixed focus (the lens **is adjustable**)", 30 cm–∞, threaded barrel. **No lock screw documented** → must tape/glue it | OFFICIAL wording |
| Lens mount | M12×0.5 / S-mount, interchangeable | UNVERIFIED (hobbyist teardown only) |
| **PCB silkscreen marking** | **`HBV-1716 2710 S1.0`** — matches the catalogued HBVCAM page `hbvcam-1716-2710-s1.0`. So the **base board is officially documented**; only the "WA" *lens* variant is not | Photo of the board, 2026-07-25. HIGH |
| Board outline | **38 × 38 mm** | **MEASURED with calipers 2026-07-31** — agrees with both the sibling datasheet and the reseller drawing. CONFIRMED |
| Mounting-hole spacing | **32 × 32 mm** (reseller drawing of *our* part) — **conflicts** with the 28 mm figure from the sibling datasheet | Reseller dimensioned drawing. MEDIUM — **measure with calipers before machining a mount** |
| Depth incl. lens | **25 mm** (reseller drawing) — **conflicts** with ~17.5–18 mm from the sibling | Reseller dimensioned drawing. MEDIUM — **measure with calipers** |
| Power | 5 V USB bus, ≤570–1100 mW | OFFICIAL (sibling) |
| USB bridge IC | Likely **Vimicro VC0346** (`VC0346TLNBC`). VID 0x0AC8 = Z-Star/Vimicro. PID↔part mirroring proven in Linux `gspca/vc032x.c` (0321→VC0321, 0323→VC0323) | **STRONG INFERENCE, NOT PROVEN.** To close: photograph the QFN-48 marking |
| VC0346 datasheet | **None public** (NDA). Nearest documented sibling = VC0342 | Verified negative |
| PID 0x0346 in USB-ID databases | **No entry** in usb.ids / devicehunt / gowdy / Treexy | Verified negative |

---

## Modes the device actually advertises (local UVC descriptor dump — GROUND TRUTH)

Dumped with:
```
ffmpeg -f dshow -list_options true -i video="HBV HD CAMERA"
```

| Format | Resolutions | FPS |
|---|---|---|
| **MJPEG** | 1920×1080, 1280×720, 640×480, 352×288, 320×240, 176×144, 160×120 | 5–30 |
| **YUY2** | 640×480, 352×288, 320×240, 176×144, 160×120 | 5–30 |

Note the descriptor lists **1920×1080 MJPEG twice** (duplicate frame index — a known firmware
defect on this bridge; some host stacks select the wrong index).

---

## ❌ 1080p is BROKEN on this unit — measured, not guessed

**Symptom:** MJPEG 1920×1080 returns frames that are entirely zero. Every lower mode works.

**Evidence gathered 2026-07-25:**

| Test | Result |
|---|---|
| OpenCV DSHOW, MJPG 1920×1080, 4 config variants (size-first, fourcc-first, no-FPS, BUFFERSIZE=1) | **0 / 120 non-black frames each** |
| OpenCV DSHOW, **Kurokesu ordering** (FPS → FOURCC ×2 → W → H) + 1.5 s warm-up | mean=0.0, max=0 |
| OpenCV, `CAP_PROP_CONVERT_RGB=0` | buffer 6,220,800 B, all zero, no `ffd8`. **⚠️ This test is INVALID as a "raw payload" check** — see note below |
| **ffmpeg** dshow capture at 1920×1080, `-c:v copy` (bypasses OpenCV *and* every decoder) | **never produces a file; blocks indefinitely waiting for the first frame** (killed at 180 s with `-t 8` set) |
| MJPEG 1280×720 | ✅ sharp, correctly exposed image |
| YUY2 640×480 | ✅ sharp, correctly exposed image |

> **⚠️ Correction — don't repeat this mistake.** `CAP_PROP_CONVERT_RGB=0` does **not** yield raw
> MJPEG on the DSHOW backend. OpenCV's `cap_dshow.cpp` pins the Sample Grabber media type to
> `MEDIASUBTYPE_RGB24` for everything except Y16/NV12, and only consults `CONVERT_RGB` for those.
> So that 6.2 MB zero buffer was simply `1920×1080×3` of **uninitialised RGB24**, not a device
> payload — `retrieveFrame` calls `frame.create()` (which allocates but does not zero-fill;
> fresh OS pages are zero) and a failed read leaves you holding a perfectly black Mat. Use
> **ffmpeg `-c:v copy`** to see real wire bytes on Windows.

**Diagnosis.** The load-bearing evidence is **ffmpeg with `-c:v copy` producing no file at all** at
1080p, while the same command works at 720p. `-c:v copy` writes the device's JPEG bytes straight to
disk with no decoder in the path, so this rules out every decode-side cause (Windows MJPEG
Decompressor limits, missing DHT/Huffman tables, OpenCV property ordering, OpenCV's silent format
fallback). ffmpeg blocking on the first frame means **the stream never starts** — a control-path /
bandwidth-allocation failure, not a pixel problem.

**Root cause (documented, high confidence): the module's firmware declares uncompressed bitrates
inside its MJPEG descriptor block.** For 1080p MJPEG it reports `dwMaxBitRate 995328000` — which is
exactly `1920 × 1080 × 2 bytes × 30 fps × 8`, i.e. the **YUY2 figure copy-pasted into the MJPEG
entry**. The host therefore tries to reserve 3–10× the bandwidth actually needed. Compounding it,
the device is **isochronous-only with no bulk alternate**, and its alt-1 `wMaxPacketSize 0x1400`
(3×1024 B per microframe ≈ 196 Mbit/s) is essentially the entire periodic budget of one USB 2.0
host controller. Allocation fails → the stream starts but delivers nothing.

This is exactly the defect Linux patches with `UVC_QUIRK_FIX_BANDWIDTH` (`modprobe uvcvideo
quirks=128`). **Vimicro's other UVC PIDs (332d, 3410, 3420) all carry that quirk in
`uvc_driver.c`; 0346 does not** — it was simply never added. **Windows has no equivalent lever.**

### Remaining untried options (if 1080p is ever actually needed)
1. Move the camera to a port on a **different USB host controller**, and/or disable the laptop's
   Integrated Camera to free periodic bandwidth on the shared controller. (Cheapest test — if
   1080p starts working, it is allocation contention.)
2. Run capture on **Linux** (e.g. the Raspberry Pi 5 host planned for Phase 3) with
   `modprobe uvcvideo quirks=128` — the documented fix for precisely this firmware bug.
3. Dump the descriptors with **USB Device Tree Viewer** (`UsbTreeView.exe /R=report.txt`,
   https://www.uwe-sieber.de/usbtreeview_e.html) and check whether a **high-bandwidth alternate
   setting exists** ("3 transactions per microframe"). Without one, the top alt caps at
   1×1024 B/µframe = 8.2 MB/s ≈ 269 KB/frame at 30 fps — too small for 1080p MJPEG.
4. Capture the actual negotiation with **USBPcap + Wireshark** (filter `usb_video`; Wireshark
   decodes `VS_PROBE_CONTROL`/`VS_COMMIT_CONTROL` incl. `dwMaxPayloadTransferSize`). Plug the
   camera in *after* starting the capture or the descriptors are never seen.

### Relevant primary-spec facts (for whoever picks this up)
- **UVC 1.5 §4.3.1.1** on `dwMaxPayloadTransferSize`: *"This field is set by the device and read
  only from the host. **Some host implementations restrict the maximum value permitted for this
  field.**"* — the spec conceding hosts cap this; a real 1080p failure vector.
- **UVC 1.5 §4.3.1.1.1:** *"The USB bandwidth reserved shall be calculated by the host as the
  advertised `dwMaxBitRate` from the selected Frame Descriptor."* — this is exactly why the
  copy-pasted uncompressed `dwMaxBitRate` breaks us.
- `dwMaxVideoFrameBufferSize` in the frame descriptor is **deprecated** (UVC 1.1 RR0064); the
  Probe/Commit `dwMaxVideoFrameSize` is authoritative.
- **USB 2.0 HS ceiling for one isoc endpoint:** 3072 B/µframe × 8000 = 24.6 MB/s ≈ 196 Mbit/s
  (≈814 KB per frame at 30 fps). 1080p30 MJPEG at ~10:1 ≈ 12.4 MB/s **fits with room to spare** —
  so raw throughput is NOT the limit. 1080p30 YUY2 = 124 MB/s is physically impossible on HS,
  which is why YUY2 1080p is officially capped at 5 fps.
- **Windows allocates periodic bandwidth first-come-first-served**, and per Microsoft: *"The system
  can't configure the device and fails to enumerate it. Since it's not apparent why the enumeration
  failed, the user has bad experience."*
- **UVC MJPEG payload spec §3.3:** `DHT` (Huffman table) is **optional**; when absent the decoder
  must substitute the ISO 10918-1 Annex K.3.3 default tables. Legal UVC, invalid standalone JPEG.
  Worth knowing generally — **not** our cause (720p decodes fine through the same decoder).
- Truncated JPEGs decode to **uniform gray (~128)**, not black — another reason our all-zero
  buffers pointed at "no data" rather than "bad decode".

**Spec documents:** "USB Device Class Definition for Video Devices, Rev 1.5" and "…Motion-JPEG
Payload, Rev 1.1" — https://www.usb.org/document-library/video-class-v15-document-set

---

## ✅ DECISION: capture at MJPEG 1280×720 @30

Rationale:
- 720p is verified working, sharp, and 30 fps.
- Object detectors resize to ~640×640 regardless — 1080p pixels are discarded downstream.
- ToF is a 4×4 zone grid; extra camera resolution adds nothing to depth alignment.
- ~2.2× less data per frame → faster fusion loop, matters on the Pi 5 later.
- Cost: only fine detail on small distant objects. Not our use case (obstacles < 4 m).

**All calibration must be performed at 1280×720**, because K (fx, fy, cx, cy) is
resolution-dependent. Recalibrate (or rescale K) if the capture resolution ever changes.

---

## Reference URLs
- OV2710 datasheet — https://datasheet4u.com/pdf-down/O/V/2/OV2710_OmniVision.pdf
- OV2710 product brief — https://static6.arrow.com/aropdfconversion/20a4701909ea0c3602c8573c489a64272f1c28d6/ov2710pbv1.1web.pdf
- Real `0ac8:0346` lsusb -v dump — https://github.com/regalleuchte/autodarts/blob/master/calibration/hbv_ov2710_000/_lsusb.txt
- HBVCAM 1716 family (mode table) — https://www.hbvcamera.com/2-mega-pixel-usb-cameras/2mp-ov2710-1080p-hd-camera-module-with-ir-cut-with-850nm-ir-board.html
- HBVCAM 1716 family (lens table) — https://www.hbvcamera.com/2-mega-pixel-usb-cameras/hd-cmos-camera-module.html
- Vimicro VC0342 (nearest documented bridge sibling) — https://www.radioradar.net/en/files.html?fid=776339
