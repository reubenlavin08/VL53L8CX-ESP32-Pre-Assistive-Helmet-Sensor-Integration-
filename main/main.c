/**
 * VL53L8CX ESP32-S3 Distance Sensor Interface
 *
 * Streams DATA: + SIGMA: lines per frame over BOTH:
 *   - UART (printf / USB-CDC, ~115200 baud)
 *   - TCP (when a client is connected on TCP_PORT over WiFi)
 *
 * Hardware (SATEL-VL53L8CX breakout â†’ ESP32-S3):
 *   SATEL PWREN     â†’ GPIO_PWREN  (+ 10kÎ© pullup to 3.3V)
 *   SATEL MCLK_SCL  â†’ GPIO_SCL    (+ 2.2kÎ© pullup to 3.3V)
 *   SATEL MOSI_SDA  â†’ GPIO_SDA    (+ 2.2kÎ© pullup to 3.3V)
 *   SATEL NCS       â†’ 3.3V        (tie high = I2C mode)
 *   SATEL SPI_I2C_N â†’ GND         (selects I2C mode)
 *   SATEL VDD       â†’ 5V
 *   SATEL GND       â†’ GND
 */

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdbool.h>
#include <errno.h>
#include <math.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/event_groups.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "driver/ledc.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_ota_ops.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#include "vl53l8cx_api.h"
#include "wifi_credentials.h"

/* â”€â”€ Pin configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#define GPIO_SDA      GPIO_NUM_1
#define GPIO_SCL      GPIO_NUM_2
#define GPIO_PWREN    GPIO_NUM_5
#define BUZZER_GPIO         GPIO_NUM_6   /* active buzzer signal pin */
#define BUZZER_TEST         1            /* set 0 to silence */
#define OBSTACLE_THRESHOLD_MM 600        /* start beeping at this distance (60 cm) */
#define BEEP_MS             50           /* short beep = quieter */
#define BEEP_GAP_MIN_MS     30           /* gap at point-blank (frantic chirping) */
#define BEEP_GAP_MAX_MS     400          /* gap at threshold distance (slow alert) */

/* â”€â”€ Sensor configuration â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#define SENSOR_RESOLUTION   VL53L8CX_RESOLUTION_4X4        /* 16 zones (4× tighter σ, wider angular per zone) */
#define RANGING_FREQ_HZ     30                             /* 1-60 Hz at 4X4, 1-15 Hz at 8X8 */
#define RANGING_MODE        VL53L8CX_RANGING_MODE_CONTINUOUS
#define SHARPENER_PERCENT   5                              /* 0=off, 5=default, 99=max */
#define TARGET_ORDER        VL53L8CX_TARGET_ORDER_CLOSEST  /* CLOSEST for obstacle avoidance */
#define STATUS_FILTER_STRICT 0                             /* 1 = accept status 5 only; 0 = accept {5,6,9} */

/* Sensor is physically mounted rotated N degrees CW from "natural" body
 * orientation (top of FoV = head up, bottom = ground). Stream functions
 * remap zone indices so the transmitted grid is always in body-frame:
 *   output row 0 = top of FoV (looking up)
 *   output row N-1 = bottom of FoV (looking down)
 *   output col 0 = left of body
 *   output col N-1 = right of body
 * If the rendered view is wrong, flip this to 90, 180, 270, or 0. */
#define MOUNT_ROTATION_DEG  270

/* Optical-axis pitch below horizontal when helmet is worn level (degrees).
 * Measured by wall-stare calibration on 2026-05-25 with sensor at 73",
 * wall at 32". Used to convert slant distance per zone to body-frame
 * forward distance for the obstacle-alert logic (so a floor obstacle close
 * to the body triggers the alert even though its slant distance is large).
 * Raw DATA: stream is NOT affected -- that stays as raw slant. */
#define MOUNT_PITCH_DEG     20.0f
#define MAX_GRID_SIDE       8

/* â”€â”€ Display options â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#define PRINT_GRID          0
#define PRINT_CLOSEST_ONLY  0
#define STREAM_DATA         1
#define STREAM_SIGMA        1
#define STREAM_STATUS       1     /* per-zone raw target_status codes */
#define MAX_DISTANCE_MM     4000

/* â”€â”€ WiFi / TCP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#define MAX_WIFI_RETRY      10
#define WIFI_CONNECTED_BIT  BIT0
#define STREAM_BUF_SIZE     512
#define MAX_TCP_CLIENTS     4         /* visualizer + measure.py + headroom */

static const char *TAG = "VL53L8CX";

static EventGroupHandle_t s_wifi_event_group = NULL;
static int s_retry_num = 0;

/* TCP client state â€” fan-out streaming to up to MAX_TCP_CLIENTS clients
 * simultaneously so the visualizer can stay live while measure.py also
 * captures. tcp_write iterates over slots; failed sends self-evict. */
static int g_client_socks[MAX_TCP_CLIENTS];
static SemaphoreHandle_t g_client_mutex = NULL;

/* Nearest valid zone FORWARD distance in mm (i.e. slant distance projected
 * onto the body's horizontal forward axis using the per-row cosine table),
 * updated by ranging_task each frame. 32-bit reads/writes are atomic on
 * ESP32-S3, so no mutex needed. INT16_MAX = no valid zone yet. */
static volatile int16_t g_nearest_mm = INT16_MAX;

/* True if any zone's forward distance is below its row's threshold this
 * frame. Buzzer fires on this flag, not on a single global threshold,
 * because lower rows need larger thresholds — their FoV exits BEFORE the
 * obstacle reaches body proximity, so the alert has to fire while the
 * obstacle is still in view. */
static volatile bool g_alert_active = false;

/* Most-urgent alerting zone this frame, used for beep-rate interpolation:
 *   urgency_ratio = g_urgency_forward / g_urgency_threshold  (0..1)
 *   0   = obstacle at body (fastest beep)
 *   1   = obstacle exactly at its row's threshold (slowest beep)
 * Comparing zones by ratio (not absolute mm) means a lower-row obstacle at
 * 50 cm forward (high urgency, 50/90 = 0.56) beeps faster than an upper-row
 * obstacle at 50 cm forward (lower urgency, 50/60 = 0.83). */
static volatile int16_t g_urgency_forward   = 0;
static volatile int16_t g_urgency_threshold = 1;   /* 1 to avoid div-by-zero */

/* Per-row forward-distance threshold (mm). Output rows are body-frame after
 * the rotation remap: row 0 = top of view (overhead/head), row 7 = bottom
 * (body/waist). Larger thresholds for lower rows give the alert time to
 * fire before the obstacle exits FoV.
 *
 * Logic: row 7 with 20° pitch looks at 32–42° below horizontal, exits the
 * FoV at horizontal ~70 cm forward for belly-button-height obstacles.
 * Setting row 7 threshold to 1200 mm means the alert fires while obstacle
 * is still ~100 cm forward — comfortably in view, comfortably actionable.
 */
/* Per-row alert thresholds. Non-const because we pick 4x4 vs 8x8 set at
 * runtime (preprocessor can't evaluate the ULD's casted resolution macros).
 * Initialised in compute_row_cos_table() once we know `side`. */
static int16_t g_row_threshold_mm[MAX_GRID_SIDE];
static const int16_t g_row_threshold_8x8[MAX_GRID_SIDE] = {
    600, 600, 600, 600, 700, 800, 850, 900,
};
static const int16_t g_row_threshold_4x4[MAX_GRID_SIDE] = {
    600,    /* 4x4 row 0 — top of FoV (head + above) */
    600,    /* 4x4 row 1 — upper middle (head/chest area) */
    800,    /* 4x4 row 2 — lower middle (chest/waist area) */
    950,    /* 4x4 row 3 — bottom (waist/floor area) */
    0, 0, 0, 0,  /* unused at 4x4 */
};

/* Per-row cosine table: forward_distance = slant_distance * g_row_cos[row]
 * Built once at startup from MOUNT_PITCH_DEG + each row's elevation offset
 * from the optical axis. Row index is in body-frame (post-rotation). */
static float g_row_cos[MAX_GRID_SIDE];

/* Latest frame's forward-distance grid (rotation + slant compensation applied),
 * 64 zones max. -1 = invalid. Read by /api/status web handler. */
static volatile int16_t g_latest_forward[MAX_GRID_SIDE * MAX_GRID_SIDE];
/* Latest frame's raw per-zone status code (0-255), in body-frame order.
 * Exposed via /api/status so the viewer can show WHY a zone is invalid
 * (status 7 = rate-consistency fail, 11 = no target detected, etc. per
 * ST UM3109 §5.5). */
static volatile uint8_t g_latest_status[MAX_GRID_SIDE * MAX_GRID_SIDE];
static volatile int     g_latest_grid_side = 0;

static void compute_row_cos_table(int side)
{
    float deg_per_zone = 45.0f / (float)side;
    float pitch_rad    = MOUNT_PITCH_DEG * (float)M_PI / 180.0f;
    for (int r = 0; r < side; r++) {
        /* alpha_row: elevation of this row's center relative to optical axis.
         * Row 0 (top of body view) = looking UP from optical axis = negative.
         * Row N-1 (bottom) = looking DOWN from optical axis = positive. */
        float alpha_rad = ((float)r - (side - 1) / 2.0f)
                          * deg_per_zone * (float)M_PI / 180.0f;
        float elev_rad  = alpha_rad + pitch_rad;
        g_row_cos[r]    = cosf(elev_rad);
    }

    /* Pick the per-row threshold set for this resolution */
    const int16_t *src = (side == 8) ? g_row_threshold_8x8 : g_row_threshold_4x4;
    for (int r = 0; r < MAX_GRID_SIDE; r++) {
        g_row_threshold_mm[r] = src[r];
    }
}

/* â”€â”€ Broadcast a line to every connected TCP client. â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
 *  On any per-client error, close that socket and clear its slot so the
 *  server task can accept replacements.
 */
static void tcp_write(const char *buf, size_t len)
{
    if (g_client_mutex == NULL) return;
    xSemaphoreTake(g_client_mutex, portMAX_DELAY);
    for (int i = 0; i < MAX_TCP_CLIENTS; i++) {
        int fd = g_client_socks[i];
        if (fd < 0) continue;
        int sent = send(fd, buf, len, MSG_DONTWAIT);
        if (sent < 0) {
            ESP_LOGW(TAG, "TCP send failed on client %d (errno=%d) â€” evicting", i, errno);
            close(fd);
            g_client_socks[i] = -1;
        }
    }
    xSemaphoreGive(g_client_mutex);
}

/* ── Mount-rotation helper ───────────────────────────────────────────────────
 * Given an output zone index `out_z` in [0..total), return the sensor's
 * native zone index to read for that output position, based on
 * MOUNT_ROTATION_DEG. Lets the firmware emit zones in body-frame regardless
 * of how the sensor PCB is physically oriented on the helmet.
 */
static inline int rotated_zone(int out_z, int side)
{
    int r_out = out_z / side;
    int c_out = out_z % side;
    int r_src, c_src;
    switch (MOUNT_ROTATION_DEG) {
        case 90:   /* 90 CW: body(r, c) reads sensor(side-1-c, r) */
            r_src = side - 1 - c_out;
            c_src = r_out;
            break;
        case 180:
            r_src = side - 1 - r_out;
            c_src = side - 1 - c_out;
            break;
        case 270:  /* 90 CCW */
            r_src = c_out;
            c_src = side - 1 - r_out;
            break;
        default:   /* 0 -> identity */
            return out_z;
    }
    return r_src * side + c_src;
}

/* â”€â”€ Helper: stream DATA: line to UART + TCP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#if STREAM_DATA
static void stream_distance_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    int side  = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8  : 4;
    char buf[STREAM_BUF_SIZE];
    int off = snprintf(buf, sizeof(buf), "DATA:");
    for (int z = 0; z < total && off < (int)sizeof(buf) - 1; z++) {
        int src = rotated_zone(z, side);
        int16_t dist;
        uint8_t status = results->target_status[src * VL53L8CX_NB_TARGET_PER_ZONE];
        /* Accept status 5 (100% valid), 6 (wrap-around not done, ~50% conf),
         * and 9 (low signal but range valid, ~50% conf). Per ST UM3109 Â§5.5.
         * STRICT mode = status 5 only. */
        bool status_ok = STATUS_FILTER_STRICT
                       ? (status == 5)
                       : (status == 5 || status == 6 || status == 9);
        if (results->nb_target_detected[src] > 0 && status_ok) {
            dist = results->distance_mm[src * VL53L8CX_NB_TARGET_PER_ZONE];
            if (dist > MAX_DISTANCE_MM) dist = MAX_DISTANCE_MM;
        } else {
            dist = MAX_DISTANCE_MM;
        }
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%d%c", dist, (z == total - 1) ? '\n' : ',');
    }
    if (off > (int)sizeof(buf) - 1) off = sizeof(buf) - 1;
    fputs(buf, stdout);
    tcp_write(buf, off);
}
#endif

/* â”€â”€ Helper: stream SIGMA: line to UART + TCP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#if STREAM_SIGMA
static void stream_sigma_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    int side  = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8  : 4;
    char buf[STREAM_BUF_SIZE];
    int off = snprintf(buf, sizeof(buf), "SIGMA:");
    for (int z = 0; z < total && off < (int)sizeof(buf) - 1; z++) {
        int src = rotated_zone(z, side);
        uint16_t sigma = results->range_sigma_mm[src * VL53L8CX_NB_TARGET_PER_ZONE];
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%u%c", (unsigned)sigma, (z == total - 1) ? '\n' : ',');
    }
    if (off > (int)sizeof(buf) - 1) off = sizeof(buf) - 1;
    fputs(buf, stdout);
    tcp_write(buf, off);
}
#endif

/* â”€â”€ Helper: stream STATUS: line to UART + TCP â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
 * Raw per-zone target_status code (0-255) â€” lets the host see WHICH
 * failure mode each filtered zone hit, not just "filtered/passed".
 * Per ST UM3109 Â§5.5:
 *   0 = ranging data not updated
 *   1 = signal rate too low on SPAD
 *   2 = target phase
 *   3 = sigma estimator too high
 *   4 = target consistency failed
 *   5 = range valid (100% confidence)
 *   6 = wrap-around not performed (~50%)
 *   7 = rate consistency failed
 *   8 = signal rate too low
 *   9 = range valid with low signal (~50%)
 *   10 = sigma estimator too high (range valid)
 *   11 = no target detected
 *   12 = blurred target
 *   13 = inconsistent data
 *   255 = no update
 */
#if STREAM_STATUS
static void stream_status_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    int side  = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8  : 4;
    char buf[STREAM_BUF_SIZE];
    int off = snprintf(buf, sizeof(buf), "STATUS:");
    for (int z = 0; z < total && off < (int)sizeof(buf) - 1; z++) {
        int src = rotated_zone(z, side);
        uint8_t status = results->target_status[src * VL53L8CX_NB_TARGET_PER_ZONE];
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%u%c", (unsigned)status, (z == total - 1) ? '\n' : ',');
    }
    if (off > (int)sizeof(buf) - 1) off = sizeof(buf) - 1;
    fputs(buf, stdout);
    tcp_write(buf, off);
}
#endif

/* â”€â”€ Helper: full grid + closest (kept for debug) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
static void print_distance_grid(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int side = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8 : 4;
    printf("\n--- Distance grid (mm) ---\n");
    for (int row = 0; row < side; row++) {
        for (int col = 0; col < side; col++) {
            int zone = row * side + col;
            if (results->nb_target_detected[zone] > 0 &&
                results->target_status[zone * VL53L8CX_NB_TARGET_PER_ZONE] == 5) {
                printf("%5d", results->distance_mm[zone * VL53L8CX_NB_TARGET_PER_ZONE]);
            } else {
                printf("    -");
            }
        }
        printf("\n");
    }
    printf("--------------------------\n");
}

#if PRINT_CLOSEST_ONLY
static void print_closest_zone(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total_zones = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    int16_t min_dist = INT16_MAX;
    int     min_zone = -1;
    for (int z = 0; z < total_zones; z++) {
        if (results->nb_target_detected[z] > 0 &&
            results->target_status[z * VL53L8CX_NB_TARGET_PER_ZONE] == 5) {
            int16_t d = results->distance_mm[z * VL53L8CX_NB_TARGET_PER_ZONE];
            if (d < min_dist) { min_dist = d; min_zone = z; }
        }
    }
    int side = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8 : 4;
    if (min_zone >= 0) {
        ESP_LOGI(TAG, "Closest: %d mm  (zone row=%d col=%d)",
                 min_dist, min_zone / side, min_zone % side);
    } else {
        ESP_LOGI(TAG, "Closest: no valid target");
    }
}
#endif

/* â”€â”€ Buzzer test task: 2 kHz PWM tone, 200 ms beep every 5 s â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
#if BUZZER_TEST
#define BUZZER_FREQ_HZ      2000
#define BUZZER_LEDC_CHANNEL LEDC_CHANNEL_0
#define BUZZER_LEDC_TIMER   LEDC_TIMER_0
#define BUZZER_LEDC_MODE    LEDC_LOW_SPEED_MODE
#define BUZZER_LEDC_RES     LEDC_TIMER_10_BIT
#define BUZZER_DUTY_50PCT   512

static void buzzer_task(void *arg)
{
    /* Obstacle alert: beep when nearest zone is closer than the threshold,
     * silent otherwise. Short beep = quieter. */
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << BUZZER_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&cfg);
    gpio_set_drive_capability(BUZZER_GPIO, GPIO_DRIVE_CAP_3);
    gpio_set_level(BUZZER_GPIO, 0);
    ESP_LOGI(TAG, "Obstacle alert on GPIO %d: %d ms beep when any zone < %d mm",
             BUZZER_GPIO, BEEP_MS, OBSTACLE_THRESHOLD_MM);
    /* Beep rate is set by urgency RATIO (forward / row_threshold), not by
     * absolute forward distance. A row-7 obstacle at 50 cm forward (0.55
     * ratio) is more urgent than a row-0 obstacle at 50 cm forward (0.83
     * ratio) — so the row-7 one beeps faster, matching how close the
     * obstacle is to "actionable proximity" for that body region. */
    while (1) {
        bool alert = g_alert_active;
        if (alert) {
            int16_t uf = g_urgency_forward;
            int16_t ut = g_urgency_threshold;
            if (ut < 1) ut = 1;
            int gap = BEEP_GAP_MIN_MS +
                      (int)((int32_t)(BEEP_GAP_MAX_MS - BEEP_GAP_MIN_MS) * uf / ut);
            if (gap < BEEP_GAP_MIN_MS) gap = BEEP_GAP_MIN_MS;
            if (gap > BEEP_GAP_MAX_MS) gap = BEEP_GAP_MAX_MS;
            gpio_set_level(BUZZER_GPIO, 1);
            vTaskDelay(pdMS_TO_TICKS(BEEP_MS));
            gpio_set_level(BUZZER_GPIO, 0);
            vTaskDelay(pdMS_TO_TICKS(gap));
        } else {
            vTaskDelay(pdMS_TO_TICKS(100));   /* idle, poll 10 Hz */
        }
    }
}
#endif

/* OTA rollback confirmation. With CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE, a
 * freshly OTAed image boots in "pending_verify" state. We must call
 * esp_ota_mark_app_valid_cancel_rollback() before the next boot, or the
 * bootloader auto-reverts to the previous slot. Confirm only after WiFi is
 * up AND the sensor has produced at least one frame -- proving both
 * subsystems work. Prevents bricked-partition recovery cycles. */
static void ota_rollback_confirm_task(void *arg)
{
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                        pdFALSE, pdTRUE, portMAX_DELAY);
    int settle_ms = 0;
    while (g_nearest_mm == INT16_MAX && settle_ms < 15000) {
        vTaskDelay(pdMS_TO_TICKS(250));
        settle_ms += 250;
    }
    const esp_partition_t *running = esp_ota_get_running_partition();
    esp_ota_img_states_t state;
    if (running && esp_ota_get_state_partition(running, &state) == ESP_OK) {
        if (state == ESP_OTA_IMG_PENDING_VERIFY) {
            esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
            ESP_LOGI(TAG, "OTA confirm: image healthy, rollback cancelled (%s)",
                     esp_err_to_name(err));
        } else {
            ESP_LOGI(TAG, "OTA confirm: image already marked valid (state=%d)",
                     (int)state);
        }
    }
    vTaskDelete(NULL);
}

/* â”€â”€ WiFi event handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
static void wifi_event_handler(void *arg, esp_event_base_t event_base,
                                int32_t event_id, void *event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "WiFi STA started, connecting to %s...", WIFI_SSID);
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        if (s_retry_num < MAX_WIFI_RETRY) {
            esp_wifi_connect();
            s_retry_num++;
            ESP_LOGW(TAG, "WiFi disconnected, retry %d/%d", s_retry_num, MAX_WIFI_RETRY);
        } else {
            ESP_LOGE(TAG, "WiFi failed after %d retries", MAX_WIFI_RETRY);
        }
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *event = (ip_event_got_ip_t *)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR "  (TCP server on port %d)",
                 IP2STR(&event->ip_info.ip), TCP_PORT);
        s_retry_num = 0;
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

/* â”€â”€ WiFi station init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, NULL));

    wifi_config_t wifi_config = { 0 };
    strncpy((char *)wifi_config.sta.ssid, WIFI_SSID, sizeof(wifi_config.sta.ssid));
    strncpy((char *)wifi_config.sta.password, WIFI_PASSWORD, sizeof(wifi_config.sta.password));
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    wifi_config.sta.pmf_cfg.capable = true;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());
}

/* â”€â”€ OTA: POST /update endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
static esp_err_t ota_post_handler(httpd_req_t *req)
{
    /* Token check via X-OTA-Token header. Token is stored in
     * wifi_credentials.h (gitignored). Anyone on the network can probe the
     * port, so this guards against accidental hijack from other hosts. */
    char token[64] = {0};
    if (httpd_req_get_hdr_value_str(req, "X-OTA-Token", token, sizeof(token)) != ESP_OK
        || strcmp(token, OTA_TOKEN) != 0) {
        httpd_resp_set_status(req, "401 Unauthorized");
        httpd_resp_sendstr(req, "missing or wrong X-OTA-Token header\n");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "OTA: upload starting (Content-Length=%d, free_heap=%lu B, min_free=%lu B)",
             req->content_len,
             (unsigned long)esp_get_free_heap_size(),
             (unsigned long)esp_get_minimum_free_heap_size());

    const esp_partition_t *next = esp_ota_get_next_update_partition(NULL);
    if (!next) {
        ESP_LOGE(TAG, "OTA: esp_ota_get_next_update_partition returned NULL");
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, "no OTA partition available\n");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "OTA: target partition '%s' at offset 0x%lx, size 0x%lx",
             next->label, (unsigned long)next->address, (unsigned long)next->size);

    esp_ota_handle_t handle = 0;
    esp_err_t err = esp_ota_begin(next, OTA_SIZE_UNKNOWN, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_begin failed: %s (free_heap=%lu)", esp_err_to_name(err),
                 (unsigned long)esp_get_free_heap_size());
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, esp_err_to_name(err));
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "OTA: esp_ota_begin OK (handle=%lu, free_heap=%lu)",
             (unsigned long)handle, (unsigned long)esp_get_free_heap_size());

    char buf[1024];
    int total = 0;
    int recv;
    int next_heap_log_at = 0;   /* log heap every 64 KB */
    while ((recv = httpd_req_recv(req, buf, sizeof(buf))) > 0) {
        if (total >= next_heap_log_at) {
            ESP_LOGI(TAG, "OTA: progress %d B  free_heap=%lu  min_free=%lu",
                     total,
                     (unsigned long)esp_get_free_heap_size(),
                     (unsigned long)esp_get_minimum_free_heap_size());
            next_heap_log_at += 64 * 1024;
        }
        err = esp_ota_write(handle, buf, recv);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "esp_ota_write FAILED at %d bytes: %s  free_heap=%lu",
                     total, esp_err_to_name(err),
                     (unsigned long)esp_get_free_heap_size());
            esp_ota_abort(handle);
            httpd_resp_set_status(req, "500 Internal Server Error");
            httpd_resp_sendstr(req, esp_err_to_name(err));
            return ESP_FAIL;
        }
        total += recv;
    }
    if (recv < 0) {
        ESP_LOGE(TAG, "httpd_req_recv FAILED at %d bytes  (errno=%d, free_heap=%lu)",
                 total, errno, (unsigned long)esp_get_free_heap_size());
        esp_ota_abort(handle);
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, "recv failed mid-stream\n");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "OTA: %d bytes received, finalizing (free_heap=%lu)",
             total, (unsigned long)esp_get_free_heap_size());

    err = esp_ota_end(handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_end failed: %s", esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, esp_err_to_name(err));
        return ESP_FAIL;
    }

    err = esp_ota_set_boot_partition(next);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_set_boot_partition failed: %s", esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, esp_err_to_name(err));
        return ESP_FAIL;
    }

    httpd_resp_sendstr(req, "OK â€” rebooting into new image in 1 s\n");
    ESP_LOGI(TAG, "OTA: success, rebooting");
    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();
    return ESP_OK;   /* unreachable */
}

/* ── Minimal phone-friendly HTML viewer served at GET / ─────────────────────
 * Polls /api/status every 200 ms, shows the nearest forward distance as a
 * big colored number. Designed for a phone browser; no laptop required.
 */
static const char VIEWER_HTML[] =
"<!DOCTYPE html><html><head>"
"<meta name='viewport' content='width=device-width,initial-scale=1,user-scalable=no'>"
"<title>Helmet</title>"
"<style>"
"html,body{margin:0;padding:0;height:100%;font-family:-apple-system,monospace;background:#111;color:#eee;}"
".card{height:60vh;display:flex;flex-direction:column;justify-content:center;align-items:center;transition:background .15s;}"
".dist{font-size:28vw;font-weight:700;line-height:1;}"
".unit{font-size:4vw;opacity:.7;margin-top:1vh;}"
".clear{background:#062;}.warn{background:#963;}.alert{background:#a02;}.dead{background:#333;}"
".meta{padding:3vw;font-size:4vw;line-height:1.5;}"
".grid{display:grid;grid-template-columns:repeat(8,1fr);gap:2px;padding:2vw;}"
".cell{aspect-ratio:1;display:flex;align-items:center;justify-content:center;font-size:2.5vw;background:#222;border-radius:4px;color:#888;}"
"</style></head><body>"
"<div id='card' class='card dead'>"
"<div class='dist' id='val'>---</div>"
"<div class='unit'>cm forward to nearest</div></div>"
"<div class='meta'>"
"alert <span id='alt'>?</span> &middot; valid <span id='vc'>?</span>/<span id='vt'>?</span> &middot; row thresholds (cm): <span id='thrs'>?</span>"
"</div>"
"<div class='grid' id='grid'></div>"
"<div class='meta' style='font-size:2.8vw;line-height:1.6'>"
"Status codes (ST UM3109 §5.5): 0=no update, 4=consistency fail, 5=valid, 6=wrap-around, 7=rate inconsistent, 8=signal too low, 9=valid low-signal, 10=sigma too high, 11=no target, 255=no update"
"</div>"
"<script>"
"const grid=document.getElementById('grid');"
"const fmt=mm=>Math.round(mm/10);"
"async function tick(){"
"try{const r=await fetch('/api/status');if(!r.ok)throw 0;const d=await r.json();"
"const v=d.nearest_mm;const el=document.getElementById('val');const c=document.getElementById('card');"
"if(v<0||v>=4000){el.textContent='---';c.className='card dead';}"
"else{el.textContent=fmt(v);c.className='card '+(d.alert?'alert':(v<1500?'warn':'clear'));}"
"document.getElementById('alt').textContent=d.alert?'ON':'off';"
"document.getElementById('thrs').textContent=d.row_thresholds_mm.map(fmt).join(', ');"
"const side=d.side;document.getElementById('vt').textContent=side*side;"
"let nval=0;if(grid.children.length!==side*side){grid.style.gridTemplateColumns='repeat('+side+',1fr)';grid.innerHTML='';for(let i=0;i<side*side;i++){const e=document.createElement('div');e.className='cell';grid.appendChild(e);}}"
"for(let i=0;i<side*side;i++){const z=d.grid[i];const e=grid.children[i];const row=Math.floor(i/side);const thr=d.row_thresholds_mm[row];if(z<0){const s=d.status?d.status[i]:'?';e.textContent='s'+s;e.style.background='#2a1212';e.style.color='#c66';}else{nval++;e.textContent=fmt(z);const f=Math.min(1,z/(1.5*thr));e.style.background='hsl('+(f*120)+',70%,30%)';e.style.color='#fff';}}"
"document.getElementById('vc').textContent=nval;"
"}catch(e){document.getElementById('val').textContent='ERR';document.getElementById('card').className='card dead';}"
"}setInterval(tick,200);tick();"
"</script></body></html>";

static esp_err_t root_get_handler(httpd_req_t *req)
{
    httpd_resp_set_type(req, "text/html");
    httpd_resp_send(req, VIEWER_HTML, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

static esp_err_t status_get_handler(httpd_req_t *req)
{
    int side = g_latest_grid_side;
    if (side <= 0) side = 8;
    int total = side * side;
    int16_t nearest = g_nearest_mm;
    bool alert = g_alert_active;

    /* JSON includes per-row thresholds so the viewer can colour each row
     * against its own threshold. urgency_pct = forward / row_threshold × 100
     * for the most-urgent alerting zone (0 = at body, 100 = at threshold). */
    int urgency_pct = 0;
    if (g_urgency_threshold > 0 && alert) {
        urgency_pct = (int)((int32_t)g_urgency_forward * 100 / g_urgency_threshold);
        if (urgency_pct < 0)   urgency_pct = 0;
        if (urgency_pct > 100) urgency_pct = 100;
    } else {
        urgency_pct = -1;   /* sentinel: no alert */
    }
    char buf[2560];
    int off = snprintf(buf, sizeof(buf),
        "{\"nearest_mm\":%d,\"alert\":%s,\"urgency_pct\":%d,\"side\":%d,\"row_thresholds_mm\":[",
        (int)nearest, alert ? "true" : "false", urgency_pct, side);
    for (int r = 0; r < side && off < (int)sizeof(buf) - 8; r++) {
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%s%d", r ? "," : "", (int)g_row_threshold_mm[r]);
    }
    off += snprintf(buf + off, sizeof(buf) - off, "],\"grid\":[");
    for (int i = 0; i < total && off < (int)sizeof(buf) - 8; i++) {
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%s%d", i ? "," : "", (int)g_latest_forward[i]);
    }
    off += snprintf(buf + off, sizeof(buf) - off, "],\"status\":[");
    for (int i = 0; i < total && off < (int)sizeof(buf) - 8; i++) {
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%s%u", i ? "," : "", (unsigned)g_latest_status[i]);
    }
    off += snprintf(buf + off, sizeof(buf) - off, "]}");

    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    httpd_resp_send(req, buf, off);
    return ESP_OK;
}

static esp_err_t health_get_handler(httpd_req_t *req)
{
    char buf[256];
    int off = snprintf(buf, sizeof(buf),
        "{\"free_heap\":%lu,\"min_free_heap\":%lu,\"uptime_ms\":%lu,\"frames\":%lu}",
        (unsigned long)esp_get_free_heap_size(),
        (unsigned long)esp_get_minimum_free_heap_size(),
        (unsigned long)(esp_timer_get_time() / 1000),
        (unsigned long)g_latest_grid_side);   /* placeholder — frame count if added later */
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    httpd_resp_send(req, buf, off);
    return ESP_OK;
}

static void start_ota_server(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port       = OTA_HTTP_PORT;
    cfg.recv_wait_timeout = 60;          /* longer wait so slow flash writes don't drop OTA */
    cfg.send_wait_timeout = 60;
    cfg.stack_size        = 12288;       /* extra headroom for OTA write paths */
    cfg.max_uri_handlers  = 8;

    httpd_handle_t server = NULL;
    if (httpd_start(&server, &cfg) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server");
        return;
    }
    httpd_uri_t ota_uri    = { .uri = "/update",      .method = HTTP_POST, .handler = ota_post_handler,    .user_ctx = NULL };
    httpd_uri_t root_uri   = { .uri = "/",            .method = HTTP_GET,  .handler = root_get_handler,    .user_ctx = NULL };
    httpd_uri_t status_uri = { .uri = "/api/status",  .method = HTTP_GET,  .handler = status_get_handler,  .user_ctx = NULL };
    httpd_uri_t health_uri = { .uri = "/api/health",  .method = HTTP_GET,  .handler = health_get_handler,  .user_ctx = NULL };
    httpd_register_uri_handler(server, &ota_uri);
    httpd_register_uri_handler(server, &root_uri);
    httpd_register_uri_handler(server, &status_uri);
    httpd_register_uri_handler(server, &health_uri);
    ESP_LOGI(TAG, "HTTP server on port %d: GET / (viewer), GET /api/status, GET /api/health, POST /update",
             OTA_HTTP_PORT);
}

/* â”€â”€ TCP server task â€” single-client, blocks on accept() between clients â”€â”€â”€â”€ */
static void tcp_server_task(void *arg)
{
    /* Wait for WiFi connection before opening any sockets */
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT,
                        pdFALSE, pdTRUE, portMAX_DELAY);

    /* Start the OTA HTTP server alongside the TCP data server. */
    start_ota_server();

    int listener = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    if (listener < 0) {
        ESP_LOGE(TAG, "TCP socket failed: errno=%d", errno);
        vTaskDelete(NULL);
    }

    int opt = 1;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port   = htons(TCP_PORT),
        .sin_addr   = { .s_addr = htonl(INADDR_ANY) },
    };
    if (bind(listener, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        ESP_LOGE(TAG, "TCP bind failed: errno=%d", errno);
        close(listener);
        vTaskDelete(NULL);
    }
    if (listen(listener, 1) < 0) {
        ESP_LOGE(TAG, "TCP listen failed: errno=%d", errno);
        close(listener);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "TCP server listening on port %d", TCP_PORT);

    while (1) {
        struct sockaddr_in cli_addr;
        socklen_t cli_len = sizeof(cli_addr);
        int client = accept(listener, (struct sockaddr *)&cli_addr, &cli_len);
        if (client < 0) {
            ESP_LOGE(TAG, "TCP accept failed: errno=%d", errno);
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        char ip[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &cli_addr.sin_addr, ip, sizeof(ip));

        /* TCP_NODELAY: avoid Nagle so frames go out immediately */
        int nodelay = 1;
        setsockopt(client, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));

        /* Stash in first empty slot; if all slots full, evict the oldest
         * (slot 0) to make room. Disconnect detection happens lazily inside
         * tcp_write() when a send() fails â€” no per-client task needed. */
        xSemaphoreTake(g_client_mutex, portMAX_DELAY);
        int slot = -1;
        for (int i = 0; i < MAX_TCP_CLIENTS; i++) {
            if (g_client_socks[i] < 0) { slot = i; break; }
        }
        if (slot < 0) {
            ESP_LOGW(TAG, "All %d client slots full, evicting slot 0", MAX_TCP_CLIENTS);
            close(g_client_socks[0]);
            /* shift remaining down so the oldest is always slot 0 */
            for (int i = 0; i < MAX_TCP_CLIENTS - 1; i++) {
                g_client_socks[i] = g_client_socks[i + 1];
            }
            slot = MAX_TCP_CLIENTS - 1;
        }
        g_client_socks[slot] = client;
        xSemaphoreGive(g_client_mutex);

        ESP_LOGI(TAG, "TCP client connected from %s (slot %d)", ip, slot);
    }
}

/* â”€â”€ Main ranging task â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */
static void ranging_task(void *arg)
{
    VL53L8CX_Configuration sensor;
    VL53L8CX_ResultsData   results;
    uint8_t                is_alive  = 0;
    uint8_t                is_ready  = 0;
    uint32_t               frame_num = 0;

    i2c_master_bus_config_t bus_cfg = {
        .clk_source           = I2C_CLK_SRC_DEFAULT,
        .i2c_port             = I2C_NUM_1,
        .scl_io_num           = GPIO_SCL,
        .sda_io_num           = GPIO_SDA,
        .glitch_ignore_cnt    = 7,
        .flags.enable_internal_pullup = false,
    };
    i2c_master_bus_handle_t bus_handle;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus_handle));

    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = VL53L8CX_DEFAULT_I2C_ADDRESS >> 1,
        .scl_speed_hz    = VL53L8CX_MAX_CLK_SPEED,
    };

    memset(&sensor, 0, sizeof(sensor));
    sensor.platform.bus_config  = bus_cfg;
    sensor.platform.reset_gpio  = GPIO_PWREN;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus_handle, &dev_cfg,
                                              &sensor.platform.handle));

    VL53L8CX_Reset_Sensor(&sensor.platform);

    uint8_t ret = vl53l8cx_is_alive(&sensor, &is_alive);
    if (ret != VL53L8CX_STATUS_OK || !is_alive) {
        ESP_LOGE(TAG, "Sensor not detected (ret=%u) â€” check wiring.", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Sensor detected");

    ESP_LOGI(TAG, "Uploading ULD firmware (~1 s)...");
    ret = vl53l8cx_init(&sensor);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "vl53l8cx_init failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "ULD ready â€” version: %s", VL53L8CX_API_REVISION);

    ret  = vl53l8cx_set_resolution(&sensor, SENSOR_RESOLUTION);
    ret |= vl53l8cx_set_ranging_mode(&sensor, RANGING_MODE);
    ret |= vl53l8cx_set_ranging_frequency_hz(&sensor, RANGING_FREQ_HZ);
    ret |= vl53l8cx_set_sharpener_percent(&sensor, SHARPENER_PERCENT);
    ret |= vl53l8cx_set_target_order(&sensor, TARGET_ORDER);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "Sensor configuration failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Configured: %s, %d Hz, sharpener=%d%%, order=%s, filter=%s",
             (SENSOR_RESOLUTION == VL53L8CX_RESOLUTION_8X8) ? "8x8" : "4x4",
             RANGING_FREQ_HZ, SHARPENER_PERCENT,
             (TARGET_ORDER == VL53L8CX_TARGET_ORDER_CLOSEST) ? "CLOSEST" : "STRONGEST",
             STATUS_FILTER_STRICT ? "{5} strict" : "{5,6,9}");

    /* Build the per-row slant->forward cosine table for the buzzer logic */
    int side_init = (SENSOR_RESOLUTION == VL53L8CX_RESOLUTION_8X8) ? 8 : 4;
    compute_row_cos_table(side_init);
    ESP_LOGI(TAG, "Mount pitch %.1f deg DOWN -- slant->forward cosines:",
             (double)MOUNT_PITCH_DEG);
    for (int r = 0; r < side_init; r++) {
        ESP_LOGI(TAG, "  row %d: cos = %.4f  (forward = slant * %.4f)",
                 r, (double)g_row_cos[r], (double)g_row_cos[r]);
    }

    ret = vl53l8cx_start_ranging(&sensor);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "start_ranging failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Ranging started");

    while (1) {
        ret = vl53l8cx_check_data_ready(&sensor, &is_ready);
        if (ret != VL53L8CX_STATUS_OK) {
            ESP_LOGE(TAG, "check_data_ready error (ret=%u)", ret);
            VL53L8CX_WaitMs(&sensor.platform, 5);
            continue;
        }
        if (!is_ready) {
            VL53L8CX_WaitMs(&sensor.platform, 5);
            continue;
        }
        ret = vl53l8cx_get_ranging_data(&sensor, &results);
        if (ret != VL53L8CX_STATUS_OK) {
            ESP_LOGE(TAG, "get_ranging_data error (ret=%u)", ret);
            continue;
        }
        ++frame_num;

        /* Update nearest-valid-zone FORWARD distance for the buzzer task.
         * Iterate in body-frame (output) order so each zone's row index r_out
         * matches the per-row cosine table built in compute_row_cos_table().
         * Forward distance = slant * cos(row_elevation + mount_pitch). */
        int side        = (SENSOR_RESOLUTION == VL53L8CX_RESOLUTION_8X8) ? 8 : 4;
        int total_zones = side * side;
        int16_t nearest_forward    = INT16_MAX;
        bool    any_alert          = false;
        int16_t urgency_forward    = 0;       /* most-urgent zone, for beep rate */
        int16_t urgency_threshold  = 1;
        bool    have_urgency       = false;
        for (int z_out = 0; z_out < total_zones; z_out++) {
            int z_src = rotated_zone(z_out, side);
            int r_out = z_out / side;
            uint8_t status = results.target_status[z_src * VL53L8CX_NB_TARGET_PER_ZONE];
            bool status_ok = STATUS_FILTER_STRICT
                           ? (status == 5)
                           : (status == 5 || status == 6 || status == 9);
            int16_t forward_for_grid = -1;
            g_latest_status[z_out] = status;
            if (results.nb_target_detected[z_src] > 0 && status_ok) {
                int16_t slant = results.distance_mm[z_src * VL53L8CX_NB_TARGET_PER_ZONE];
                if (slant > 0) {
                    int16_t forward = (int16_t)((float)slant * g_row_cos[r_out]);
                    forward_for_grid = forward;
                    if (forward < nearest_forward) nearest_forward = forward;
                    int16_t row_thresh = g_row_threshold_mm[r_out];
                    if (forward < row_thresh) {
                        any_alert = true;
                        /* Compare urgency ratios as cross-products to avoid floats:
                         *   forward/row_thresh < urgency_forward/urgency_threshold
                         *   ⇔  forward * urgency_threshold < urgency_forward * row_thresh
                         */
                        if (!have_urgency ||
                            (int32_t)forward * urgency_threshold
                                < (int32_t)urgency_forward * row_thresh) {
                            urgency_forward   = forward;
                            urgency_threshold = row_thresh;
                            have_urgency      = true;
                        }
                    }
                }
            }
            g_latest_forward[z_out] = forward_for_grid;
        }
        g_nearest_mm        = nearest_forward;
        g_alert_active      = any_alert;
        g_urgency_forward   = urgency_forward;
        g_urgency_threshold = urgency_threshold;
        g_latest_grid_side  = side;

#if STREAM_DATA
        stream_distance_line(&results, SENSOR_RESOLUTION);
#endif
#if STREAM_SIGMA
        stream_sigma_line(&results, SENSOR_RESOLUTION);
#endif
#if STREAM_STATUS
        stream_status_line(&results, SENSOR_RESOLUTION);
#endif
#if PRINT_CLOSEST_ONLY
        print_closest_zone(&results, SENSOR_RESOLUTION);
#endif
#if PRINT_GRID
        ESP_LOGI(TAG, "Frame #%lu", (unsigned long)frame_num);
        print_distance_grid(&results, SENSOR_RESOLUTION);
#endif
    }

    vl53l8cx_stop_ranging(&sensor);
    vTaskDelete(NULL);
}

void app_main(void)
{
    ESP_LOGI(TAG, "VL53L8CX + WiFi interface starting");

    g_client_mutex = xSemaphoreCreateMutex();
    for (int i = 0; i < MAX_TCP_CLIENTS; i++) {
        g_client_socks[i] = -1;
    }

    /* Start the ranging task FIRST so the sensor can complete its I2C init
     * (about ~1 s of ULD firmware upload) BEFORE WiFi spins up. Otherwise
     * the WiFi current spike can brown the sensor's 5V rail and the I2C
     * is-alive check fails. */
    xTaskCreate(ranging_task, "ranging", 8192, NULL, 5, NULL);

    /* Give the sensor a head start before bringing up WiFi. */
    vTaskDelay(pdMS_TO_TICKS(2500));

    /* NVS is required by the WiFi driver to store its config. */
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    /* Start WiFi (async â€” connection completes in the background). */
    wifi_init_sta();

    /* TCP server task waits for WiFi internally, then listens. */
    xTaskCreate(tcp_server_task, "tcp_server", 4096, NULL, 4, NULL);

#if BUZZER_TEST
    /* Buzzer / GPIO control task. 4096 byte stack â€” 2048 was overflowing. */
    xTaskCreate(buzzer_task, "buzzer", 4096, NULL, 2, NULL);
#endif

    /* OTA rollback safety: confirm this image works (WiFi + sensor both up)
     * within ~30 s of boot, else bootloader auto-reverts to previous slot. */
    xTaskCreate(ota_rollback_confirm_task, "ota_confirm", 4096, NULL, 3, NULL);
}
