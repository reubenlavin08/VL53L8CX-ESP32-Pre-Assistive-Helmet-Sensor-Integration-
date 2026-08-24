# Iris user guide

Everything the system does, and every way to trigger it. Three ways to
control Iris: **voice** (wake word), **phone app** buttons, **keyboard**
on the computer viewer. Plus two gestures on the helmet itself.

## Always on (no trigger needed)

| Feature | What you experience |
|---|---|
| Obstacle callouts | "Stop stop" (<1.2 m directly ahead), "step left/right", named objects when the camera is confident ("maybe chair 2 meters"). Low confidence = just "obstacle" — a wrong name is worse than no name. |
| Haptic motors | Left/center/right temple buzzing, stronger = closer. Works even with audio muted. |
| Proximity ticker | Parking-sensor clicks that speed up as the nearest thing gets closer, panned left/right to where it is. |
| Head-turn gate | While you whip your head around, routine cautions hold their tongue (a fighter-pilot "sterile cockpit"). Urgent warnings still get through. |
| Head clearance | Warns "low clearance, duck" + double haptic pulse for head-height obstacles (branches, door frames) using the IMU to know true vertical. |
| Drop detection | If the helmet falls off, it announces where it is every 10 s and mutes hazard chatter. |
| Flight log | Everything is recorded (speech, sensor data). Last 60 s of video/sensors saved automatically around any incident. |

## Voice commands

Say **"Iris"**, wait for the **high beep**, then the command (5 s window):

- **"describe"** — AI looks through the camera and tells you what's ahead (2-6 s)
- **"what's in my hand"** — same, focused on a held object
- **"what's around"** — one item per direction (front-left / center / right). Say it again within 10 s for distances; a third time for the full AI description
- **"scan doors"** — finds up to 3 doors, tells you clock direction + steps; then **"door one/two/three"** picks one and the audio beacon guides you to it
- **"find door"** (also: window, chair, stairs, table, couch, bed, fridge, sink, elevator, garbage) — finds the *object* with open-vocabulary detection, beacon guides you to it
- **"find exit"** (also: washroom, open, push, pull, sale, ketchup) — finds that *written text* on signs/labels, locks the beacon on it. Text words need actual writing in view — a door with no EXIT sign won't match "exit"; say "find door" for that
- **"read that"** — reads nearby text aloud
- **"guide"** — audio beacon toward what's centered ahead
- **"audio on"** — unmute

**No wake word needed, anytime:** "stop", "quiet" (mute), "wrong" (that callout was wrong — logged for tuning).

## Helmet gestures

- **Double-tap the shell** — same as "describe"
- (Falling helmet announces itself — that's automatic)

## Phone app (and computer viewer buttons)

Top-to-bottom / left-to-right: **What's around · Describe · Mute · Flag ·
Rotate · Help (?) · REC · Power**. Flag = "remember this moment": saves
the last 60 s of video + sensors so problems can be replayed later.
Rotate fills a portrait phone screen with the video (hold the phone
sideways). REC records the annotated video + laptop mic to
`camera/sessions/*_rec/` — for backpack field runs ("Iris… start
recording" works too). Power (tap twice to confirm) shuts Iris down
cleanly and returns the app to the Start screen.

## Keyboard (computer viewer)

| Key | Action |
|---|---|
| `v` / `h` | Describe / what's in my hand |
| `d` then `1-3` | Door scan, pick a door |
| `f` | Find text (type the word) |
| `r` | Read that |
| `g` | Guide beacon on what's ahead |
| `n` | Walkable-tunnel haptics (corridor centering) |
| `l` | Level check (IMU) |
| `u` | Toggle steps/meters |
| `c` | Start/stop session recording (video + mic) |
| `x` | "Wrong" (false-positive vote) |
| `F8` | Mute/unmute |
| `F9` | What's around |
| `F12`/`?` | Print this help in the console |

## The one-line mental model

The helmet handles **"don't walk into things"** automatically (ToF +
haptics + short words). Everything else is **ask-and-answer**: you ask
(voice, tap, button, key), Iris answers once, then goes quiet.
