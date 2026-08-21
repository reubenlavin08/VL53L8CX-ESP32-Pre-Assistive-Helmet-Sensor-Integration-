# Consumer transit-assistance apps for BLV users — competitive scan — 2026-08-20

Component of the transit/bus-route research (full synthesis agent still
running). All findings from direct fetches of official pages; items marked
unverified could not be confirmed this session.

## The key answer

**No product autonomously says "bus 99 arriving, door 3 m to your right."**
Only Aira delivers that sentence — via a paid human. The gap has three
unclosed pieces:

1. **Headsign OCR at 20–40 m** — all camera apps are near-field,
   single-still.
2. **Door localization with bearing + range** — no product outputs it.
3. **Fusion of GTFS-RT (the transit systems' real-time arrival feed) with
   the camera** — nobody links "the vehicle 25 m away" to "the 99 my feed
   says is due now," even though real-time data collapses the OCR problem
   to verifying 2–3 candidate routes. **That fusion is the unbuilt piece —
   and exactly our architecture (camera + ToF range + live data).**

## 1. Aira (human agents)

- Pricing (aira.io/pricing, updated 2026-03-01, USD): Silver $26/20 min →
  Platinum $1,160/880 min; effective ~$1.30–1.60/min. Free: 3 welcome
  calls + 60 bonus min; Job Seeker 30 min per 24 h; free "Access AI" image
  descriptions.
- Transit sponsors (free minutes in-system): TriMet, Metro Transit
  (Minneapolis), Milwaukee County, Pittsburgh Regional, C-TRAN,
  Jacksonville, Govia Thameslink (UK); 60+ airports incl. YYZ, YVR.
- For transit the agent watches the live phone camera and can literally
  say "your bus is here, door to your right." Limits: costs money outside
  sponsored zones; call setup takes tens of seconds (longer than a bus
  dwell); user must aim the phone.

## 2. Be My Eyes / Be My AI

Free; GPT-4-powered still-photo description + follow-ups, 29 languages.
Capture→upload→describe is multi-second — **not real-time headsign
reading**. Official disclaimer: "does not and should not replace a white
cane, guide dog, or other mobility aid." Ray-Ban Meta integration
unverified (pages 404).

## 3. Microsoft Seeing AI

Free, iOS + Android. Channels: Read, Describe, Products, People, Currency,
Find My Things, World (spatial-audio AR, needs LiDAR, ≈5 m), Colors,
Light. **No distant-sign claim anywhere**; user reviews report digit
errors on LED displays at arm's length — the exact bus-headsign failure
mode.

## 4. Google Lookout + Maps

- Lookout: Text (36 langs), Explore (beta, "less accurate"), Documents,
  Food Labels, Currency (no coins), Images Q&A, Find (fixed class list
  incl. "doors"/"vehicles" with direction, **no range, no route/headsign
  class**).
- Maps: TalkBack + wheelchair-accessible routing. GTFS tells you which bus
  and when — never where the door is.

## 5. Moovit / Transit

Moovit: fully screen-reader-optimized, Live Directions + Get Off Alerts,
3,500 cities. Both apps are GTFS-RT consumers: ±1–2 min predictions, a
stop is a point, no curb/vehicle awareness. (Transit app pages 404 —
unverified.)

## 6. Wearables 2025–26

- **Envision Glasses**: $699–$1,699 + $200/yr; OCR 60+ langs, scenes,
  faces, Ally AI + human call. **No GPS/navigation/transit function.**
- **Glidance Glide**: self-steering wheeled guide; doors/elevators/stairs,
  crosswalk assist; waitlist-only, no price/date. No transit claims.
- **.lumen**: guide-dog-replacement headset; no price/date/specs public.
  No transit claims.
- biped.ai DNS dead (possibly defunct); OrCam MyEye page empty; ARx
  Vision unreachable — all unverified.

## Sources

[Aira pricing](https://aira.io/pricing/) ·
[Aira partners](https://aira.io/partners/) ·
[Aira transportation](https://aira.io/transportation/) ·
[Be My AI](https://www.bemyeyes.com/blog/announcing-be-my-ai) ·
[Seeing AI](https://www.seeingai.com/) ·
[Seeing AI App Store](https://apps.apple.com/us/app/seeing-ai/id999062298) ·
[Lookout help](https://support.google.com/accessibility/android/answer/9031274) ·
[Maps accessibility](https://support.google.com/maps/answer/6396990) ·
[Moovit accessibility](https://moovit.com/accessibility/) ·
[Envision Glasses](https://www.letsenvision.com/glasses) ·
[Glidance](https://glidance.io/) · [.lumen](https://www.dotlumen.com/)
