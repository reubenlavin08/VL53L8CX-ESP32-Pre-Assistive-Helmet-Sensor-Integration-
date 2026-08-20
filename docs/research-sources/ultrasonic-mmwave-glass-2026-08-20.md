# Ultrasonic / mmWave / glass-sensing research — 2026-08-20 (sub-agent, condensed verbatim)

## The glass physics (derived, solid)
- 40 kHz ultrasound vs glass: acoustic impedance mismatch 34,000:1 →
  **99.99% of energy reflects** (glass = a wall acoustically).
- 940 nm ToF vs glass: Fresnel → **4.1% reflects, ~92% transmits** (sensor
  ranges whatever is BEHIND the pane).
- Ultrasound is also blind to optical color (matte black is acoustically
  ordinary) and immune to sunlight — it fails on none of ToF's three failure
  modes, and vice versa (specular walls off-angle, soft/absorbing fabrics).
- LIMIT: at 40 kHz almost every surface is acoustically SPECULAR (Rayleigh:
  roughness <1.1 mm) — a glass door >~10-15° oblique returns nothing. Solves
  the head-on case (the dangerous one); never promise full glass coverage.

## ⚡ FREE WINS (do before buying anything)
1. **VL53L8CX has a hardware sync pin (B1)** — `vl53l8cx_set_external_sync_pin_enable`
   in our ULD driver (L8CX-only; absent in L5CX). Drive B1 from the ESP32 to
   interleave the two sensors' integration windows → kills mutual
   interference without XSHUT time-multiplexing. One GPIO + one API call.
   (Verify intended use vs UM3109; distinct from xtalk calibration.)
2. **TOPGN-style glass signature in firmware**: glass = plausible range with
   anomalously low return signal, or valid ToF range contradicting the
   camera. Our sensor already reports per-zone signal/ambient rates.
   (TOPGN arXiv:2408.05608: transparent-obstacle detection from intensity,
   +12.7% F-score, 50 Hz on mobile CPU.)

## Hardware adds, ranked
1. **TDK CH201 ultrasonic** (3.5×3.5 mm, 5 m, I²C, coded pulses; vendor
   page literally claims "any color and optical transparency", "any
   lighting") — primary pick, CHECK STOCK/PRICE (unverified). Fallback:
   MaxBotix MB1202, $34.95 verified, I²C, 40 Hz, but 0-65°C + bigger.
2. **Radar: defer to Phase 3.** Cheap modules (Acconeer A121) are RANGE-ONLY
   (zero azimuth); 12-channel TI parts (~9.5° azimuth) cost/burn too much;
   radar sees THROUGH walls (false-positive source on a helmet); only truly
   rain-immune option though (60 GHz: ~0.25 dB over 10 m in heavy rain).
   Precedent exists: V-band conformal wearable antenna for BLV (Vadher 2024).
3. Rain reality: ToF's rain problem is WATER ON THE COVER (xtalk cal is for
   a dry cover) — hydrophobic coating + a brim beats adding radar.

## Direct architectural precedent
**arXiv:2510.06518 (2025): ToF + ultrasonic fusion + tiny CNN detecting
glass and reprojecting depth, real-time on a sub-300 g drone** — exactly the
proposed architecture at our size/weight budget.

Legacy note: ultrasonic BLV devices — Miniguide (alive, no glass claim),
UltraCane (domain now a sports-streaming site — dead).

Physics footnotes: 40 kHz update ceiling 57 Hz at 3 m; sound speed drifts
0.177%/°C (needs temp compensation); ultrasonic crosstalk needs TDMA/coded
pulses.

Unverified this session (search cap): CH201 price/stock, ITU-R P.2040 60 GHz
glass numbers, UM3109 sync-pin intent, Toposens status.
