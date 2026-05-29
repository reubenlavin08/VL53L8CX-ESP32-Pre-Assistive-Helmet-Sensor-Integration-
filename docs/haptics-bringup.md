# Haptic motor bring-up log

Goal: directional haptic feedback ring on the inner rim of the helmet. Small motors buzz against the scalp to indicate obstacle direction (left column of FoV alerting → left motor buzzes, etc.). Eventually mapped to ToF columns. See `photos/test_rig/future_test_ideas.md` "Directional haptic feedback ring".

## Parts on hand (2026-05-26)

### Vibration motors
- **Type: ERM coin / pancake** (eccentric rotating mass). Brushed DC motor with off-center weight.
  - NOT piezo. Piezo = ceramic, reads open-circuit, high-V low-current, no kickback. This reads 70 Ω → coil → real motor → has inductive kickback → needs flyback diode.
- **Coil resistance (measured): 70 Ω**
- **Assumed rating:** 3 V nominal (standard for coin ERMs). Do NOT exceed ~3.3 V.
- **Estimated current:** stall ≈ 3 V / 70 Ω ≈ 43 mA; running less (back-EMF). Brief startup inrush ≈ stall.
- Form factor: ~10 mm coin, red/blue pigtail wires.

### Transistors
- **2N3904** (NPN BJT). "-338" suffix = batch code, ignore.
  - Ic max = 200 mA continuous → fine for ONE 43 mA motor with margin.
  - **One transistor per motor.** A 4-motor rim needs 4× 2N3904.
  - TO-92 package.

### Diodes
- **NONE on hand initially.** Ordering a 200-pc / 14-value assorted diode kit (C$6.39) that includes 1N4148, 1N4001/4007, and Schottky 1N5817/1N5819/1N5822.
- **For the helmet build use a Schottky 1N5819 across each motor** — lower forward voltage (~0.3 V vs 0.7 V silicon) clamps the kickback spike lower and switches faster. Ideal flyback for a 3 V motor.
- "Flyback diode" is a *role*, not a special part — any ordinary diode with low Vf, fast recovery, and reverse rating above the supply works. 1N5819 (Schottky) is the best pick from the kit; 1N4148 is a fine fallback.
- **Diode necessity verdict:** for a 70 Ω coin ERM, brief bench testing WITHOUT a diode is fine (tiny kickback energy, 2N3904 survives 40 V). Add the 1N5819 for the continuous/worn build — PWM switches ~1000×/sec and small spikes accumulate stress over weeks.
- **LEDs are NOT a substitute** — low reverse breakdown (~5 V, close to the 3.3 V reverse bias they'd sit under), high forward voltage (clamps late), poor pulse handling.

### Test equipment
- Multimeter: yes
- Bench power supply: no
- ESP32-S3 dev board + breadboard: yes

## GPIO budget (from main.c)
Used: GPIO1 (SDA), GPIO2 (SCL), GPIO5 (PWREN), GPIO6 (buzzer).
**Free for haptics test: GPIO7** (not a strapping pin on S3). Strapping pins to avoid: GPIO0, 3, 45, 46.

## 2N3904 pinout (CRITICAL — easy to get wrong)
TO-92 package, **flat face toward you, legs pointing down**:
```
   ___________
  /           \      flat face facing you
 |   2N3904    |
 |             |
  \___________/
    |   |   |
    E   B   C
   (1) (2) (3)
```
- Pin 1 (left)   = **Emitter**  → GND
- Pin 2 (middle) = **Base**     → through resistor to GPIO
- Pin 3 (right)  = **Collector** → to motor

(Double-check with multimeter diode mode if unsure: B→E and B→C both read ~0.7 V one direction, open the other. The common pin is Base.)

## Driver circuit (low-side switch, one motor)
```
                   +3V3
                    │
                    ├──────────────┐
                  [motor]       [1N4148 diode]   <- diode optional for brief
                    │           (band/cathode    test, REQUIRED for build
                    │            toward +3V3)
                    ├──────────────┘
                    │
              Collector (pin 3)
                    │
   GPIO7 ──[1kΩ]── Base (pin 2)
                    │
              Emitter (pin 1)
                    │
                   GND  (shared with ESP32 GND)
```
- **1 kΩ base resistor**: GPIO outputs 3.3 V, base-emitter drops ~0.7 V, so ~2.6 mA flows into the base → saturates the transistor well for a 43 mA load. 470 Ω–1 kΩ all fine.
- **Flyback diode** across the motor: banded end (cathode) toward +3V3. It catches the kickback spike when the motor switches off.
- **Common ground:** ESP32 GND and motor-supply GND must be the same.

## Test sequence
1. **Motor sanity** — motor leads directly to 3V3 + GND (no transistor). Should buzz. Confirms motor is alive.
2. **Static on/off** — build driver, set GPIO7 HIGH → buzz, LOW → stop.
3. **PWM intensity** — drive GPIO7 with LEDC PWM, ramp duty 0→100%. Should go from still → gentle → strong buzz. This is the knob for "stronger buzz = closer obstacle."
4. **Scale to rim** — one transistor + motor per direction, map to ToF columns.

## How to run the test — Option B (chosen): integrated behind a flag, OTA-flashable

The motor test lives **inside the main firmware** behind `#define HAPTIC_TEST` in `main.c`.
When set to 1, `app_main` skips sensor ranging and runs `haptic_test_task` (motor ramp on
GPIO7, LEDC channel 1 / timer 1 — buzzer owns channel 0/timer 0). **WiFi + the OTA server
still come up**, so you can always OTA back to normal firmware. This preserves the OTA
workflow — no USB, no losing the sensor firmware.

OTA-rollback note: with ranging skipped, `g_nearest_mm` never updates, so
`ota_rollback_confirm_task` falls through its 15 s sensor-wait timeout and then marks the
image valid (it only strictly requires WiFi). So the test image won't auto-revert.

Steps:
1. In `main.c`, set `#define HAPTIC_TEST 1`
2. Build + OTA-flash the same way you normally do
3. Serial monitor (or just feel the motor): loops PHASE 1 full-on 2 s -> PHASE 2 off 1 s ->
   PHASE 3 ramp up -> PHASE 4 ramp down
4. When done: set `#define HAPTIC_TEST 0`, build + OTA again to return to normal

Wiring is unchanged from the circuit above (GPIO7 -> 1k -> 2N3904 base, etc.).

### Superseded: standalone project at `C:\esp-projects\haptic_test\`
Created before we picked Option B. It's a bare USB-flash-only project (no WiFi/OTA), so it
would overwrite the sensor firmware and can't be reverted over the air. **Not used** — left
on disk as a minimal reference. Safe to delete.

## ESP-IDF LEDC PWM test code (one motor on GPIO7)
Reference copy of the core code (the live version is in the standalone project above).
```c
#include "driver/ledc.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#define HAPTIC_GPIO        7
#define HAPTIC_LEDC_CH     LEDC_CHANNEL_0
#define HAPTIC_LEDC_TIMER  LEDC_TIMER_0
#define HAPTIC_FREQ_HZ     1000          /* 1 kHz: smooth motor drive, low whine */
#define HAPTIC_RES         LEDC_TIMER_8_BIT  /* duty 0..255 */

static void haptic_init(void) {
    ledc_timer_config_t t = {
        .speed_mode      = LEDC_LOW_SPEED_MODE,
        .timer_num       = HAPTIC_LEDC_TIMER,
        .duty_resolution = HAPTIC_RES,
        .freq_hz         = HAPTIC_FREQ_HZ,
        .clk_cfg         = LEDC_AUTO_CLK,
    };
    ledc_timer_config(&t);
    ledc_channel_config_t c = {
        .gpio_num   = HAPTIC_GPIO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel    = HAPTIC_LEDC_CH,
        .timer_sel  = HAPTIC_LEDC_TIMER,
        .duty       = 0,
        .hpoint     = 0,
    };
    ledc_channel_config(&c);
}

static void haptic_set(uint8_t duty) {   /* 0 = off, 255 = full */
    ledc_set_duty(LEDC_LOW_SPEED_MODE, HAPTIC_LEDC_CH, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, HAPTIC_LEDC_CH);
}

void app_main(void) {
    haptic_init();
    while (1) {
        for (int d = 0; d <= 255; d += 5) { haptic_set(d); vTaskDelay(pdMS_TO_TICKS(30)); }
        for (int d = 255; d >= 0; d -= 5) { haptic_set(d); vTaskDelay(pdMS_TO_TICKS(30)); }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
```
Expected: motor smoothly ramps from still → gentle → strong → back down, repeating. If it only does on/off and not intensity, check the transistor is saturating (lower the base resistor) and that PWM is on the base, not direct to the motor.

## Results log
- **2026-05-26 — one motor working.** Driver: GPIO7 → 1 kΩ → 2N3904 base, 3V3 → motor → collector, emitter → GND. No flyback diode (brief bench test). 1 kΩ base resistor saturated fine — did NOT need to drop to 470 Ω. PWM intensity ramp (LEDC ch1/timer1, 1 kHz, 8-bit) felt smooth across the full duty range. Flashed via OTA (HAPTIC_TEST=1, 786 KB, 5.6 s @ 141 KB/s). WiFi+OTA stayed alive in test mode as designed — able to OTA back afterward.
- **2026-05-28 — all 3 motors working.** Extended `haptic_test_task` to drive GPIO7/15/16 on LEDC channels 1/2/3 (shared timer1, 1 kHz). Per-motor phases (A alone → B alone → C alone) + all-3-together phase. All 3 motors fire on their correct phases. **PHASE 4 (all 3 simultaneous at full duty) ran without brownout on 3V3 rail with NO bulk cap and NO diodes** — the dev board's onboard regulator + USB supply handled the combined load fine. Cap + diodes still recommended for the final worn build but proved unnecessary for bench.
- **2026-05-28 — physical-to-pin mapping VERIFIED** via single-pin OTA pulse test (`HAPTIC_ID_MODE`). Each motor was pulsed in isolation (250 ms every 3 s) while user reported physical location:
  - **GPIO 7  = CENTER (forehead)**
  - **GPIO 15 = RIGHT temple**
  - **GPIO 16 = LEFT temple**
  - Aliases `HAPTIC_GPIO_CENTER` / `_RIGHT` / `_LEFT` added to `main.c` so column-mapping code reads geographically rather than by wiring order.
- **2026-05-28 — directional column→motor drive IMPLEMENTED + live-tested.** `ranging_task` now drives all 3 motors every frame (approach #1 + dominance weighting + squared curve, all as designed). Re-verified right motor in isolation via `HAPTIC_ID_MODE` first, then flashed the directional build. Confirmed working on the bench: obstacle in a column fires the matching motor.
  - **Bug found + fixed in same session — ERM dead-zone.** First directional build used a pure squared curve `duty = 255 × (1−ratio)²`. Symptom (user-reported): buzzer fired at the threshold distance but the **motor stayed silent until the obstacle was within ~20 cm, then jumped to full power**. Cause: ERM coin motors don't spin below ~50 % duty, and the squared curve sits near 0 across most of the alert band. **Fix:** added `HAPTIC_DUTY_MIN` (130 ≈ 51 %) as a floor — an alerting motor now jumps straight to just-felt the instant the buzzer fires, and the squared curve ramps it 130→255 as the obstacle closes. Maps the alert band onto `[MIN..MAX]` instead of `[0..MAX]`. Tunable per motor.
  - **Dominance weighting preserves the floor** — a secondary (non-dominant) motor scales only its *above-floor* portion by 0.7, so it stays ≥ `HAPTIC_DUTY_MIN` (always felt) but clearly weaker than the dominant direction.
  - **HTTP-server wedge observed once** (first directional build): with the desk filling the bottom row at ~11 cm, motors ran sustained at high duty and the ESP's HTTP server stopped responding (still pinged) ~30–60 s later — consistent with sustained brush-motor noise / rail sag on the un-decoupled bench rig. Did not recur in normal use. Watch during walk tests; mitigations on deck = motor-terminal 100 nF + rail 100 µF (mailed), optional duty cap, optional HTTP watchdog.

## Implementation — directional haptic response (column → motor) — DONE 2026-05-28

**Status:** IMPLEMENTED + bench-tested 2026-05-28. Decisions below were locked in (research-backed) and are now in firmware. Remaining = walk-test tuning of `HAPTIC_DUTY_MIN` + the open HTTP-wedge watch item.

**Design choices (sourced in `docs/research-sources/directional-haptics-mapping.md`):**
1. **Approach #1 — hard regional mapping + concurrent firing** (precedent: GuideTouch arXiv 2601.13813)
   - col 0 → LEFT motor (GPIO 16)
   - cols 1–2 → CENTER motor (GPIO 7)
   - col 3 → RIGHT motor (GPIO 15)
   - At 8×8 (future): cols 0–1 → LEFT, cols 2–5 → CENTER, cols 6–7 → RIGHT (general rule: cols < side/4 → LEFT, ≥ 3·side/4 → RIGHT, else CENTER)
2. **Squared PWM curve** `duty = max × (1 − ratio)²` matching the existing buzzer curve (Stevens-law-supported for alerting per Verrillo 1969 DOI 10.3758/BF03212793)
3. **Dominance weighting** when ≥2 motors fire — most-urgent at full duty, others ×0.7 (mitigates "wall of vibration" failure mode per Zegarra Flores arXiv 2201.04453 — single-motor 98.6%, multi-motor 70%)
4. **Buzzer keeps firing alongside motors** — buzzer = global urgency on audio channel, motors = direction on haptic channel (no overlap in encoded meaning)
5. **No per-motor acuity gain for v1** — Oliveira 2016 (DOI 10.1109/HAPTICS.2016.7463147) shows forehead acuity 3.25 mm vs temples 7.26 mm, so side motors *might* need higher peak duty to feel equally salient, but the exact gain is a guess without measurement. Defer to walk-test refinement.

**Implementation plan:**
1. Refactor `main.c`: pull HAPTIC_GPIOS / HAPTIC_CHS / HAPTIC_FREQ_HZ / HAPTIC_N / `haptic_set` / `haptic_all` *outside* the `#if HAPTIC_TEST` block so they're always compiled.
2. Add `haptic_motors_init()` (LEDC timer + 3 channel configs) called unconditionally from `app_main` right after the safety GPIO-LOW config.
3. Add column→motor index constants (`HAPTIC_IDX_CENTER = 0`, `HAPTIC_IDX_RIGHT = 1`, `HAPTIC_IDX_LEFT = 2` — matches existing HAPTIC_GPIOS array order).
4. In `ranging_task`'s per-zone loop, alongside existing global urgency tracking, track per-motor "worst urgency forward / threshold" (3 trackers, one per motor, indexed by which column-region the zone falls in).
5. After the loop: for each motor compute `ratio_pct = forward × 100 / thresh`, clamp to 0–100, `curve_pct = ratio_pct² / 100`, then `duty = HAPTIC_DUTY_MAX × (100 − curve_pct) / 100`.
6. Apply dominance: if ≥2 motors have duty > 0, scale all-but-max by ×0.7 (×7/10 integer math, no float).
7. Write LEDC duty for each motor.
8. OTA flash, walk-test, refine per-motor scaling or weight curve based on feel.

**Open question for walk test:** does the CENTER motor on forehead feel notably stronger than side motors at matched duty (Oliveira-predicted)? If yes, add per-motor gain (LEFT/RIGHT ×1.2–1.4).

**Bonus future enhancements (don't block first walk test):**
- Expose per-motor duty in `/api/status` JSON so the phone viewer can show 3-bar level meters
- Make dominance weight (currently 0.7) a runtime knob via `/api/config` POST endpoint
- Add a HAPTIC_DEBOUNCE_MS to suppress flicker on borderline zones

**Don't break the existing `HAPTIC_TEST` / `HAPTIC_ID_MODE` paths** — they remain useful for hardware bring-up + re-identification after any rewiring.
