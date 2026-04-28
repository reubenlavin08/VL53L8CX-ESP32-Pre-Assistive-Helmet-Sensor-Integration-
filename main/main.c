/**
 * VL53L8CX ESP32-S3 Distance Sensor Interface
 *
 * Hardware (SATEL-VL53L8CX breakout → ESP32-S3):
 *   SATEL PWREN    → GPIO_PWREN  (+ 10kΩ pullup to 3.3V)
 *   SATEL MCLK_SCL → GPIO_SCL   (+ 2.2kΩ pullup to 3.3V)
 *   SATEL MOSI_SDA → GPIO_SDA   (+ 2.2kΩ pullup to 3.3V)
 *   SATEL NCS      → 3.3V        (tie high = I2C mode)
 *   SATEL SPI_I2C_N → GND       (selects I2C mode)
 *   SATEL VDD      → 5V
 *   SATEL GND      → GND
 *
 * Change the GPIO defines below to match your wiring.
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "esp_log.h"

#include "vl53l8cx_api.h"

/* ── Pin configuration ───────────────────────────────────────────────────── */
#define GPIO_SDA    GPIO_NUM_1
#define GPIO_SCL    GPIO_NUM_2
#define GPIO_PWREN  GPIO_NUM_5

/* ── Sensor configuration ────────────────────────────────────────────────── */
#define SENSOR_RESOLUTION   VL53L8CX_RESOLUTION_8X8   /* 8×8 = 64 zones */
#define RANGING_FREQ_HZ     10                         /* 1–15 Hz for 8×8 */
#define RANGING_MODE        VL53L8CX_RANGING_MODE_CONTINUOUS

/* ── Display options ─────────────────────────────────────────────────────── */
#define PRINT_GRID          0   /* set 1 to print the 8×8 ASCII grid     */
#define PRINT_CLOSEST_ONLY  0   /* set 1 to only log the nearest zone    */
#define STREAM_DATA         1   /* set 1 to stream a parseable line/frame */
#define MAX_DISTANCE_MM     4000 /* clamp invalid zones to this distance  */

static const char *TAG = "VL53L8CX";

/* ── Helper: stream one parseable line per frame ─────────────────────────
 *  Format:  DATA:<d0>,<d1>,...,<dN>\n
 *  Invalid zones are clamped to MAX_DISTANCE_MM so the host never sees gaps.
 */
#if STREAM_DATA
static void stream_distance_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    printf("DATA:");
    for (int z = 0; z < total; z++) {
        int16_t dist;
        if (results->nb_target_detected[z] > 0 &&
            results->target_status[z * VL53L8CX_NB_TARGET_PER_ZONE] == 5) {
            dist = results->distance_mm[z * VL53L8CX_NB_TARGET_PER_ZONE];
            if (dist > MAX_DISTANCE_MM) dist = MAX_DISTANCE_MM;
        } else {
            dist = MAX_DISTANCE_MM;
        }
        printf("%d%c", dist, (z == total - 1) ? '\n' : ',');
    }
}
#endif

/* ── Helper: print full 8×8 distance grid ───────────────────────────────── */
static void print_distance_grid(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int side = (resolution == VL53L8CX_RESOLUTION_8X8) ? 8 : 4;
    printf("\n--- Distance grid (mm) ---\n");
    for (int row = 0; row < side; row++) {
        for (int col = 0; col < side; col++) {
            int zone = row * side + col;
            /* Target status 5 = valid ranging result */
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

/* ── Helper: find and print the nearest valid zone ───────────────────────── */
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
            if (d < min_dist) {
                min_dist = d;
                min_zone = z;
            }
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
#endif /* PRINT_CLOSEST_ONLY */

/* ── Main ranging task ───────────────────────────────────────────────────── */
static void ranging_task(void *arg)
{
    VL53L8CX_Configuration sensor;
    VL53L8CX_ResultsData   results;
    uint8_t                is_alive  = 0;
    uint8_t                is_ready  = 0;
    uint32_t               frame_num = 0;

    /* ── 1. Set up I2C bus ───────────────────────────────────────────────── */
    i2c_master_bus_config_t bus_cfg = {
        .clk_source           = I2C_CLK_SRC_DEFAULT,
        .i2c_port             = I2C_NUM_1,
        .scl_io_num           = GPIO_SCL,
        .sda_io_num           = GPIO_SDA,
        .glitch_ignore_cnt    = 7,
        .flags.enable_internal_pullup = false,  /* using external 2.2kΩ resistors */
    };
    i2c_master_bus_handle_t bus_handle;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus_handle));

    /* ── 2. Register the sensor as a device on the bus ───────────────────── */
    i2c_device_config_t dev_cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = VL53L8CX_DEFAULT_I2C_ADDRESS >> 1, /* 7-bit: 0x29 */
        .scl_speed_hz    = VL53L8CX_MAX_CLK_SPEED,            /* 1 MHz */
    };

    /* ── 3. Fill the platform struct the library uses internally ─────────── */
    memset(&sensor, 0, sizeof(sensor));
    sensor.platform.bus_config  = bus_cfg;
    sensor.platform.reset_gpio  = GPIO_PWREN;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus_handle, &dev_cfg,
                                              &sensor.platform.handle));

    /* ── 4. Hardware reset via PWREN ─────────────────────────────────────── */
    /* The library drives PWREN low then high to give the sensor a clean boot */
    VL53L8CX_Reset_Sensor(&sensor.platform);

    /* ── 5. Check the sensor is alive on the bus ─────────────────────────── */
    uint8_t ret = vl53l8cx_is_alive(&sensor, &is_alive);
    if (ret != VL53L8CX_STATUS_OK || !is_alive) {
        ESP_LOGE(TAG, "Sensor not detected (ret=%u) — check wiring.", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Sensor detected");

    /* ── 6. Upload ULD firmware to the sensor ────────────────────────────── */
    ESP_LOGI(TAG, "Uploading ULD firmware (~1 s)...");
    ret = vl53l8cx_init(&sensor);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "vl53l8cx_init failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "ULD ready — version: %s", VL53L8CX_API_REVISION);

    /* ── 7. Configure ranging ─────────────────────────────────────────────── */
    ret  = vl53l8cx_set_resolution(&sensor, SENSOR_RESOLUTION);
    ret |= vl53l8cx_set_ranging_mode(&sensor, RANGING_MODE);
    ret |= vl53l8cx_set_ranging_frequency_hz(&sensor, RANGING_FREQ_HZ);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "Sensor configuration failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Configured: %s, %d Hz",
             (SENSOR_RESOLUTION == VL53L8CX_RESOLUTION_8X8) ? "8x8" : "4x4",
             RANGING_FREQ_HZ);

    /* ── 8. Start ranging ────────────────────────────────────────────────── */
    ret = vl53l8cx_start_ranging(&sensor);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "start_ranging failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Ranging started");

    /* ── 9. Read loop ────────────────────────────────────────────────────── */
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

#if STREAM_DATA
        stream_distance_line(&results, SENSOR_RESOLUTION);
#endif
#if PRINT_CLOSEST_ONLY
        print_closest_zone(&results, SENSOR_RESOLUTION);
#endif
#if PRINT_GRID
        ESP_LOGI(TAG, "Frame #%lu", (unsigned long)frame_num);
        print_distance_grid(&results, SENSOR_RESOLUTION);
#endif
    }

    /* Unreachable in normal operation */
    vl53l8cx_stop_ranging(&sensor);
    vTaskDelete(NULL);
}

void app_main(void)
{
    ESP_LOGI(TAG, "VL53L8CX interface starting");

    xTaskCreate(
        ranging_task,
        "ranging",
        8192,   /* bytes — ULD needs at least 7168 */
        NULL,
        5,
        NULL
    );
}
