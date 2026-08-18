# Field-test runbook — backpack rig — 2026-08-18

The rig: laptop in backpack running `cv_fusion.py`, helmet ESP32 + USB camera
cabled to it, wired earbuds from the laptop, phone as the pocket display.

## One-time setup (at home)
1. **Windows Mobile Hotspot ON** (Settings → Network → Mobile hotspot).
   Note the hotspot name/password; the laptop's IP on its own hotspot is
   always **192.168.137.1**.
2. Phone: join the laptop's hotspot. Bookmark **http://192.168.137.1:8090/**.
3. Plug in: helmet USB (ESP32), camera USB, earbuds. Screen can be closed *if*
   power settings say "do nothing on lid close" while on battery — check.

## Launch (before it goes in the backpack)
```
cd C:\esp-projects\vl53l8cx_esp32\camera
python cv_fusion.py --source helmet --serial --port COM9
```
`--serial` = ToF+IMU over the USB cable — **no home WiFi needed anywhere**.
The console prints the phone-viewer URL. Open it on the phone: full annotated
view (zones, boxes+ranges, horizon, attitude inset) at ~10 fps.

## Pre-walk checks (2 min)
- [ ] Phone shows the live view and it follows head motion
- [ ] Voice speaks in the earbuds (walk at a wall — "obstacle, ahead")
- [ ] Ticker audible but not drowning speech
- [ ] Physical pause switch kills the motors (flip test)
- [ ] Press `l` on the laptop first if the ball mount needs leveling
      (voice-guided), or run it by feel

## During the walk — what to collect
- Snapshot key moments from the PHONE (screenshot) — misdetections, missed
  obstacles, wrong ranges; each becomes a labelled test case
- Note every false alert and every miss with rough time; the DEVLOG wants
  Problem→Root cause pairs
- Try: doorway, head-height branch/sign, glass door (expect a miss — that's
  the known ToF limit, film it for the demo), thin pole, stairs approach
- Note battery %, any thermal slowdown, any USB dropout ("sensors lost"
  callout = the stream died)

## Known limits going in
- Sunlight cuts ToF range to ~1–1.5 m (indoors/overcast for the first walks)
- Camera↔ToF latency misregisters during fast head turns (de-rotation is on
  the backlog) — scan slowly for now
- imu_mount_cal not run ⇒ horizon/attitude labels may be rotated until it is

## Wishlist discovered by this runbook
- Run on the second laptop instead (lighter backpack) — pull the repo there,
  `pip install ultralytics opencv-python pyserial pyttsx3 pygrabber scipy`,
  same launch line. Spec check pending (machine was unreachable 2026-08-18).
