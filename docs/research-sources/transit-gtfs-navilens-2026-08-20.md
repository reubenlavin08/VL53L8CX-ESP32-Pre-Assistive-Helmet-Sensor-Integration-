# GTFS-Realtime + NaviLens + beacon infrastructure — 2026-08-20

Component of the transit research pack. Directly answers: what live data
can the helmet fuse with the camera at a bus stop?

## 1. GTFS + GTFS-Realtime (the transit agencies' open data)

**Static** ([GTFS Schedule Reference](https://gtfs.org/documentation/schedule/reference/)):
`stops.txt` gives `stop_id`, `stop_code` (the pole-sign number),
lat/lon, `location_type` (0 stop / 2 entrance / 4 boarding area),
`platform_code`. `routes.txt` `route_short_name` ("32", "100X") and
`trips.txt` `trip_headsign` are **exactly the strings on a bus headsign —
our OCR targets.**

**Realtime** ([reference](https://gtfs.org/documentation/realtime/reference/)):
`VehiclePosition` = lat/lon required, optional bearing/speed, own
timestamp, `current_status` ∈ {INCOMING_AT, STOPPED_AT, IN_TRANSIT_TO} +
`stop_id` — **`STOPPED_AT` at your stop is the strongest single signal.**
`TripUpdate` delay: positive = late. `uncertainty` usually omitted =
unknown; no GPS-accuracy field exists in the spec.

**Cadence** ([Best Practices](https://gtfs.org/documentation/realtime/best-practices/)):
refresh ≥ every 30 s; data "should not be older than 90 seconds." At
30 km/h a bus moves ~750 m in that sanctioned worst case — **GTFS-RT
proposes candidates; it can never confirm "this bus, now." Camera must
confirm.**

**TransLink Vancouver — confirmed endpoints** (free registered API key):
- TripUpdates `https://gtfsapi.translink.ca/v3/gtfsrealtime?apikey=[ApiKey]`
- VehiclePositions `https://gtfsapi.translink.ca/v3/gtfsposition?apikey=[ApiKey]`
- Alerts `https://gtfsapi.translink.ca/v3/gtfsalerts?apikey=[ApiKey]`
- Static `https://gtfs-static.translink.ca/gtfs/google_transit.zip` (no
  key, posted weekly). Mandatory attribution; data "as is."

## 2. NaviLens (ddtags)

Vendor claims ([navilens.com](https://www.navilens.com/en/)): read at
+30 m, 12× farther than QR, 160° angle, 1/30 s detection, works while
moving, no focusing. **All vendor-stated, unreplicated — no independent
evaluation found.** Deployments ([Wikipedia](https://en.wikipedia.org/wiki/NaviLens)):
Barcelona TMB, Belgium SNCB, Melbourne trams, NYC subway pilot, San
Antonio VIA, Singapore SMRT. Personal use free; venues pay.

## 3. Wayfindr / beacons

- wayfindr.net TLS-dead, GitHub org empty — circumstantially dormant.
  Its standard lives on as **ITU-T F.921** (approved 2018, in force).
- **iBeacon ranging** ([Apple CLBeacon.accuracy](https://developer.apple.com/documentation/corelocation/clbeacon/accuracy)):
  "Do not use it to identify a precise location for the beacon." Beacons
  answer "which stop," never "how far."

## 4. Other systems

- **GoodMaps**: camera visual positioning, claims ~0.3 m accuracy
  (vendor); transit partners Network Rail, Sound Transit, Arriva.
- **Soundscape**: Microsoft confirms concluded; MIT partial open-source.
  **Soundscape Community revival is real and shipping**
  ([soundscape.services](https://soundscape.services/)) — Vision Ireland
  consortium incl. original co-founders, live on the App Store.
- RightHear (2,500+ facilities), Evelity (offline, 10 langs) — tech
  undisclosed.

## 5. Fusion value for the helmet (the design insight)

GPS + `stops.txt` → nearest stop → the **complete legal set of route
strings at that pole** (typically a handful). TripUpdates narrow to
routes due now; a `STOPPED_AT` VehiclePosition often leaves ONE candidate.
This turns open-set OCR of a moving LED headsign into **closed-set
classification over K known strings** — score OCR hypotheses by edit
distance to the candidate set (kills "R4"→"84" confusions), and get the
destination text free from `trip_headsign` without reading it.

Constraints: 90 s staleness ⇒ GTFS-RT sets the prior, camera provides
the likelihood; feeds are legally best-effort ⇒ hedge prior-only
announcements. A ddtag, where present, is the one deterministic
non-vision channel — treat as opportunistic override.

Unverified this session: MTA pilot details, NaviLens simultaneous-tag
count, Wayfindr LU trials, GPS accuracy figures.
