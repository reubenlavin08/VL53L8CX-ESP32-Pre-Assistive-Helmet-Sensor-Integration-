/* ToF bench tool — wiring test + SURFACE QUALITY test.
 *
 * Does NOT touch the helmet firmware.
 *
 * WIRING TEST: loops forever, retries every few seconds, tries BOTH SDA/SCL
 * orientations on each bus, so you can rewire live without reflashing.
 *
 * SURFACE TEST: once ranging, accumulates REPORT_FRAMES frames and prints a
 * report per sensor. Point it at a candidate calibration board and compare
 * against a known-good white surface at the SAME distance.
 *
 *   reflectance  -- the sensor's own estimate of how IR-reflective the target
 *                   is. THIS is the number that settles "is my black foam
 *                   board usable". Visible colour does not predict 940 nm
 *                   reflectance; this measures it.
 *   frame-to-frame -- how much a single zone jitters between frames. The
 *                   practical noise you actually have to fit a plane through.
 *   sensor sigma -- the sensor's own per-measurement noise estimate.
 *   valid zones  -- zones returning target_status 5. Dropouts mean not enough
 *                   light is coming back at all.
 *
 * Units are already scaled by the ULD (api.c ~L855): sigma /128 -> mm,
 * reflectance /2 -> percent, signal /2048 -> kcps/SPAD.
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "vl53l8cx_api.h"

static const char *TAG = "TOFTEST";

/* ── EDIT HERE IF THE WIRING MOVES ─────────────────────────────────────── */
#define A_P1     GPIO_NUM_6
#define A_P2     GPIO_NUM_7
#define A_PWREN  GPIO_NUM_4
#define A_PORT   I2C_NUM_0

#define B_P1     GPIO_NUM_15
#define B_P2     GPIO_NUM_16
#define B_PWREN  GPIO_NUM_5
#define B_PORT   I2C_NUM_1

/* 4x4 is the sensor's own averaging mode: it groups 2x2 SPAD blocks into one
 * zone, ~4x lower per-zone noise. For plane fitting it ties with 8x8 (fewer,
 * quieter points vs more, noisier ones) so there's no reason to change. */
#define RESOLUTION   VL53L8CX_RESOLUTION_4X4
#define GRID_SIDE    4
#define RANGING_HZ   10
#define REPORT_FRAMES 50     /* frames per surface report */
/* ─────────────────────────────────────────────────────────────────────── */

#define NZ (GRID_SIDE * GRID_SIDE)

typedef struct { gpio_num_t sda, scl; } pair_t;

/* Welford accumulator per zone, plus frame-wide sums. */
typedef struct {
    int      frames;
    int      n[NZ];            /* valid samples for this zone */
    double   mean[NZ], m2[NZ]; /* running mean / sum-of-squares of distance */
    double   sum_sigma, sum_refl, sum_signal, sum_dist;
    long     valid_total;
} stats_t;

typedef struct {
    const char             *name;
    i2c_port_t              port;
    gpio_num_t              pwren;
    pair_t                  cand[2];
    i2c_master_bus_handle_t bus;
    bool                    ok;
    int                     won;
    stats_t                 st;
} slot_t;

static VL53L8CX_Configuration s_dev[2];   /* MUST be static — ~2.5 KB each */
static VL53L8CX_ResultsData   s_res[2];

static slot_t s_slot[2] = {
    { .name = "A", .port = A_PORT, .pwren = A_PWREN,
      .cand = { { A_P1, A_P2 }, { A_P2, A_P1 } }, .won = -1 },
    { .name = "B", .port = B_PORT, .pwren = B_PWREN,
      .cand = { { B_P1, B_P2 }, { B_P2, B_P1 } }, .won = -1 },
};

static void pwren_pulse(gpio_num_t pin)
{
    gpio_config_t io = {
        .pin_bit_mask = 1ULL << pin,
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&io);
    gpio_set_level(pin, 0);
    vTaskDelay(pdMS_TO_TICKS(100));
    gpio_set_level(pin, 1);
    vTaskDelay(pdMS_TO_TICKS(100));
}

static bool scan_bus(slot_t *s, pair_t p, bool *found_29)
{
    int found = 0;
    *found_29 = false;
    printf("  [%s] SDA=%-2d SCL=%-2d :", s->name, (int)p.sda, (int)p.scl);
    for (uint8_t a = 0x08; a < 0x78; a++) {
        if (i2c_master_probe(s->bus, a, 30) == ESP_OK) {
            printf(" 0x%02X", a);
            if (a == 0x29) *found_29 = true;
            found++;
        }
    }
    if (!found) printf(" -");
    printf("\n");
    return found > 0;
}

static bool try_pair(slot_t *s, VL53L8CX_Configuration *dev, pair_t p)
{
    i2c_master_bus_config_t bus_cfg = {
        .clk_source                   = I2C_CLK_SRC_DEFAULT,
        .i2c_port                     = s->port,
        .scl_io_num                   = p.scl,
        .sda_io_num                   = p.sda,
        .glitch_ignore_cnt            = 7,
        .flags.enable_internal_pullup = false,
    };
    if (i2c_new_master_bus(&bus_cfg, &s->bus) != ESP_OK) { s->bus = NULL; return false; }

    bool has29 = false;
    scan_bus(s, p, &has29);
    if (!has29) { i2c_del_master_bus(s->bus); s->bus = NULL; return false; }

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = VL53L8CX_DEFAULT_I2C_ADDRESS >> 1,
        .scl_speed_hz    = VL53L8CX_MAX_CLK_SPEED,
    };
    memset(dev, 0, sizeof(*dev));
    dev->platform.bus_config = bus_cfg;
    dev->platform.reset_gpio = s->pwren;
    if (i2c_master_bus_add_device(s->bus, &dev_cfg, &dev->platform.handle) != ESP_OK)
        goto fail_bus;

    VL53L8CX_Reset_Sensor(&dev->platform);

    uint8_t alive = 0;
    if (vl53l8cx_is_alive(dev, &alive) != VL53L8CX_STATUS_OK || !alive) goto fail_dev;
    ESP_LOGI(TAG, "  [%s] detected — uploading ULD firmware (~1 s)...", s->name);
    if (vl53l8cx_init(dev) != VL53L8CX_STATUS_OK) {
        ESP_LOGW(TAG, "  [%s] ULD upload FAILED — marginal bus", s->name);
        goto fail_dev;
    }
    /* CLOSEST, not the ULD default STRONGEST. With STRONGEST a small object in
     * front of a large bright surface loses -- at 800 mm a 4x4 zone is ~160 mm
     * across, so a pen fills under 1% of it and the board behind wins. CLOSEST
     * reports the nearest target regardless of signal share, which is what makes
     * a small probe usable for measuring the zone geometry.
     *
     * It also changes WHERE a zone flips: CLOSEST flips on first contact with the
     * zone's EDGE, STRONGEST at roughly 50% coverage i.e. the zone CENTRE. Taking
     * both measurements therefore pins down zone centres AND zone widths. */
    if (vl53l8cx_set_target_order(dev, VL53L8CX_TARGET_ORDER_CLOSEST)
            != VL53L8CX_STATUS_OK ||
        vl53l8cx_set_resolution(dev, RESOLUTION) != VL53L8CX_STATUS_OK ||
        vl53l8cx_set_ranging_frequency_hz(dev, RANGING_HZ) != VL53L8CX_STATUS_OK ||
        vl53l8cx_start_ranging(dev) != VL53L8CX_STATUS_OK) {
        ESP_LOGW(TAG, "  [%s] config/start FAILED", s->name);
        goto fail_dev;
    }
    ESP_LOGI(TAG, "  [%s] *** RANGING OK ***  SDA=%d SCL=%d PWREN=%d",
             s->name, (int)p.sda, (int)p.scl, (int)s->pwren);
    return true;

fail_dev:
    i2c_master_bus_rm_device(dev->platform.handle);
fail_bus:
    i2c_del_master_bus(s->bus);
    s->bus = NULL;
    return false;
}

static void stats_reset(stats_t *st) { memset(st, 0, sizeof(*st)); }

static void stats_add(stats_t *st, VL53L8CX_ResultsData *r)
{
    st->frames++;
    for (int z = 0; z < NZ; z++) {
        int i = z * VL53L8CX_NB_TARGET_PER_ZONE;
        if (r->target_status[i] != 5) continue;      /* 5 = valid measurement */

        double d = r->distance_mm[i];
        st->n[z]++;
        double delta = d - st->mean[z];              /* Welford, numerically safe */
        st->mean[z] += delta / st->n[z];
        st->m2[z]   += delta * (d - st->mean[z]);

        st->valid_total++;
        st->sum_dist   += d;
        st->sum_sigma  += r->range_sigma_mm[i];
        st->sum_refl   += r->reflectance[i];
        st->sum_signal += r->signal_per_spad[i];
    }
}

static void stats_report(const char *name, stats_t *st)
{
    if (!st->valid_total) {
        printf("\n==== SURFACE [%s] ==== %d frames: NO VALID ZONES AT ALL\n"
               "     Nothing is coming back. Too far, too absorbing, or nothing in view.\n",
               name, st->frames);
        return;
    }

    /* pooled within-zone stddev = the frame-to-frame jitter of one zone */
    double ssq = 0; int dof = 0;
    for (int z = 0; z < NZ; z++)
        if (st->n[z] > 1) { ssq += st->m2[z]; dof += st->n[z] - 1; }
    double jitter = dof ? sqrt(ssq / dof) : 0.0;

    double per_frame_valid = (double)st->valid_total / st->frames;
    double refl = st->sum_refl / st->valid_total;

    printf("\n==== SURFACE [%s] ====  %d frames, %dx%d\n", name, st->frames, GRID_SIDE, GRID_SIDE);
    printf("  valid zones     %5.1f / %d   (%.0f%%)\n",
           per_frame_valid, NZ, 100.0 * per_frame_valid / NZ);
    printf("  mean distance   %7.1f mm\n", st->sum_dist / st->valid_total);
    printf("  frame-to-frame  %7.2f mm   <- real jitter you must fit through\n", jitter);
    printf("  sensor sigma    %7.2f mm   <- sensor's own noise estimate\n",
           st->sum_sigma / st->valid_total);
    printf("  reflectance     %7.1f %%    <- KEY: IR reflectance of the target\n", refl);
    printf("  signal          %7.1f kcps/SPAD\n", st->sum_signal / st->valid_total);

    /* Interpretation. Thresholds are rules of thumb for calibration use, not
     * datasheet limits — the honest test is always black vs white side by side
     * at the SAME distance. */
    printf("  --> ");
    if (per_frame_valid < NZ * 0.9)
        printf("DROPOUTS (%.0f%% valid). Not enough light back. Use a lighter surface.\n",
               100.0 * per_frame_valid / NZ);
    else if (refl < 10.0)
        printf("VERY DARK at 940nm (%.0f%%). Works, but noisy — prefer white.\n", refl);
    else if (jitter > 10.0)
        printf("NOISY (%.1f mm jitter). Usable if you average hard; white would be better.\n", jitter);
    else
        printf("GOOD. All zones returning, low jitter. Fine for calibration.\n");
    printf("     Compare against white at the SAME distance — that's the real test.\n");
}

void app_main(void)
{
    printf("\n=== ToF bench tool: wiring + surface quality ===\n");
    printf("A: pins %d/%d PWREN=%d    B: pins %d/%d PWREN=%d\n",
           A_P1, A_P2, A_PWREN, B_P1, B_P2, B_PWREN);
    printf("Hold a surface ~50 cm away, filling the field. Report every %d frames.\n\n",
           REPORT_FRAMES);

    int round = 0;
    while (1) {
        bool any_down = false;
        for (int i = 0; i < 2; i++) if (!s_slot[i].ok) any_down = true;

        if (any_down) {
            printf("--- scan round %d ---\n", ++round);
            for (int i = 0; i < 2; i++) {
                slot_t *s = &s_slot[i];
                if (s->ok) continue;
                pwren_pulse(s->pwren);
                for (int c = 0; c < 2; c++) {
                    if (try_pair(s, &s_dev[i], s->cand[c])) {
                        s->ok = true; s->won = c;
                        stats_reset(&s->st);
                        break;
                    }
                }
            }
            for (int i = 0; i < 2; i++) {
                slot_t *s = &s_slot[i];
                if (s->ok) printf("  [%s] UP   (SDA=%d SCL=%d)\n", s->name,
                                  (int)s->cand[s->won].sda, (int)s->cand[s->won].scl);
                else       printf("  [%s] down — nothing on either orientation\n", s->name);
            }
            printf("\n");
        }

        for (int i = 0; i < 2; i++) {
            slot_t *s = &s_slot[i];
            if (!s->ok) continue;
            uint8_t rdy = 0;
            if (vl53l8cx_check_data_ready(&s_dev[i], &rdy) == VL53L8CX_STATUS_OK && rdy &&
                vl53l8cx_get_ranging_data(&s_dev[i], &s_res[i]) == VL53L8CX_STATUS_OK) {
                /* Machine-readable grid for tof_id_viewer.py. -1 = invalid zone.
                 * Raw sensor zone order, NO de-rotation -- this is a wiring/ID
                 * tool, so it must show what the hardware actually reports. */
                printf("GRID:%s", s->name);
                for (int z = 0; z < NZ; z++) {
                    int k = z * VL53L8CX_NB_TARGET_PER_ZONE;
                    printf(",%d", (s_res[i].target_status[k] == 5)
                                  ? (int)s_res[i].distance_mm[k] : -1);
                }
                printf("\n");

                stats_add(&s->st, &s_res[i]);
                if (s->st.frames >= REPORT_FRAMES) {
                    stats_report(s->name, &s->st);
                    stats_reset(&s->st);
                }
            }
        }

        vTaskDelay(pdMS_TO_TICKS(any_down ? 3000 : 20));
    }
}
