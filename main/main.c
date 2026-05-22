/**
 * VL53L8CX ESP32-S3 Distance Sensor Interface
 *
 * Streams DATA: + SIGMA: lines per frame over BOTH:
 *   - UART (printf / USB-CDC, ~115200 baud)
 *   - TCP (when a client is connected on TCP_PORT over WiFi)
 *
 * Hardware (SATEL-VL53L8CX breakout → ESP32-S3):
 *   SATEL PWREN     → GPIO_PWREN  (+ 10kΩ pullup to 3.3V)
 *   SATEL MCLK_SCL  → GPIO_SCL    (+ 2.2kΩ pullup to 3.3V)
 *   SATEL MOSI_SDA  → GPIO_SDA    (+ 2.2kΩ pullup to 3.3V)
 *   SATEL NCS       → 3.3V        (tie high = I2C mode)
 *   SATEL SPI_I2C_N → GND         (selects I2C mode)
 *   SATEL VDD       → 5V
 *   SATEL GND       → GND
 */

#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>

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
#include "esp_ota_ops.h"
#include "esp_http_server.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"
#include "lwip/netdb.h"

#include "vl53l8cx_api.h"
#include "wifi_credentials.h"

/* ── Pin configuration ───────────────────────────────────────────────────── */
#define GPIO_SDA      GPIO_NUM_1
#define GPIO_SCL      GPIO_NUM_2
#define GPIO_PWREN    GPIO_NUM_5
#define BUZZER_GPIO   GPIO_NUM_6     /* passive piezo signal pin */
#define BUZZER_TEST   1              /* set 0 to silence the periodic beep */

/* ── Sensor configuration ────────────────────────────────────────────────── */
#define SENSOR_RESOLUTION   VL53L8CX_RESOLUTION_8X8        /* 64 zones (finer spatial detail) */
#define RANGING_FREQ_HZ     10                             /* 1-60 Hz at 4X4, 1-15 Hz at 8X8 */
#define RANGING_MODE        VL53L8CX_RANGING_MODE_CONTINUOUS

/* ── Display options ─────────────────────────────────────────────────────── */
#define PRINT_GRID          0
#define PRINT_CLOSEST_ONLY  0
#define STREAM_DATA         1
#define STREAM_SIGMA        1
#define MAX_DISTANCE_MM     4000

/* ── WiFi / TCP ──────────────────────────────────────────────────────────── */
#define MAX_WIFI_RETRY      10
#define WIFI_CONNECTED_BIT  BIT0
#define STREAM_BUF_SIZE     512

static const char *TAG = "VL53L8CX";

static EventGroupHandle_t s_wifi_event_group = NULL;
static int s_retry_num = 0;

/* TCP client state — exactly one connected client at a time. */
static int g_client_sock = -1;
static SemaphoreHandle_t g_client_mutex = NULL;

/* ── Write a line to the TCP client if one is connected. ─────────────────────
 *  On any error, close the socket and clear the slot so the server task can
 *  accept a new client.
 */
static void tcp_write(const char *buf, size_t len)
{
    if (g_client_mutex == NULL) return;
    xSemaphoreTake(g_client_mutex, portMAX_DELAY);
    int fd = g_client_sock;
    if (fd >= 0) {
        int sent = send(fd, buf, len, 0);
        if (sent < 0) {
            ESP_LOGW(TAG, "TCP send failed (errno=%d) — dropping client", errno);
            close(fd);
            g_client_sock = -1;
        }
    }
    xSemaphoreGive(g_client_mutex);
}

/* ── Helper: stream DATA: line to UART + TCP ─────────────────────────────── */
#if STREAM_DATA
static void stream_distance_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    char buf[STREAM_BUF_SIZE];
    int off = snprintf(buf, sizeof(buf), "DATA:");
    for (int z = 0; z < total && off < (int)sizeof(buf) - 1; z++) {
        int16_t dist;
        uint8_t status = results->target_status[z * VL53L8CX_NB_TARGET_PER_ZONE];
        /* Accept status 5 (100% valid), 6 (wrap-around not done, ~50% conf),
         * and 9 (low signal but range valid, ~50% conf). Per ST UM3109 §5.5. */
        if (results->nb_target_detected[z] > 0 &&
            (status == 5 || status == 6 || status == 9)) {
            dist = results->distance_mm[z * VL53L8CX_NB_TARGET_PER_ZONE];
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

/* ── Helper: stream SIGMA: line to UART + TCP ────────────────────────────── */
#if STREAM_SIGMA
static void stream_sigma_line(VL53L8CX_ResultsData *results, uint8_t resolution)
{
    int total = (resolution == VL53L8CX_RESOLUTION_8X8) ? 64 : 16;
    char buf[STREAM_BUF_SIZE];
    int off = snprintf(buf, sizeof(buf), "SIGMA:");
    for (int z = 0; z < total && off < (int)sizeof(buf) - 1; z++) {
        uint16_t sigma = results->range_sigma_mm[z * VL53L8CX_NB_TARGET_PER_ZONE];
        off += snprintf(buf + off, sizeof(buf) - off,
                        "%u%c", (unsigned)sigma, (z == total - 1) ? '\n' : ',');
    }
    if (off > (int)sizeof(buf) - 1) off = sizeof(buf) - 1;
    fputs(buf, stdout);
    tcp_write(buf, off);
}
#endif

/* ── Helper: full grid + closest (kept for debug) ────────────────────────── */
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

/* ── Buzzer test task: 2 kHz PWM tone, 200 ms beep every 5 s ────────────── */
#if BUZZER_TEST
#define BUZZER_FREQ_HZ      2000
#define BUZZER_LEDC_CHANNEL LEDC_CHANNEL_0
#define BUZZER_LEDC_TIMER   LEDC_TIMER_0
#define BUZZER_LEDC_MODE    LEDC_LOW_SPEED_MODE
#define BUZZER_LEDC_RES     LEDC_TIMER_10_BIT
#define BUZZER_DUTY_50PCT   512

static void buzzer_task(void *arg)
{
    /* Simple: drive BUZZER_GPIO HIGH with max drive strength. */
    gpio_config_t cfg = {
        .pin_bit_mask = 1ULL << BUZZER_GPIO,
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&cfg);
    gpio_set_drive_capability(BUZZER_GPIO, GPIO_DRIVE_CAP_3);
    gpio_set_level(BUZZER_GPIO, 1);
    ESP_LOGI(TAG, "GPIO %d HIGH (max drive)", BUZZER_GPIO);
    vTaskDelay(portMAX_DELAY);
}
#endif

/* ── WiFi event handler ──────────────────────────────────────────────────── */
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

/* ── WiFi station init ───────────────────────────────────────────────────── */
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

/* ── OTA: POST /update endpoint ──────────────────────────────────────────── */
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

    ESP_LOGI(TAG, "OTA: upload starting (Content-Length=%d)", req->content_len);

    const esp_partition_t *next = esp_ota_get_next_update_partition(NULL);
    if (!next) {
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, "no OTA partition available\n");
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "OTA: writing to partition '%s' at offset 0x%lx",
             next->label, (unsigned long)next->address);

    esp_ota_handle_t handle = 0;
    esp_err_t err = esp_ota_begin(next, OTA_SIZE_UNKNOWN, &handle);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_ota_begin failed: %s", esp_err_to_name(err));
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, esp_err_to_name(err));
        return ESP_FAIL;
    }

    char buf[1024];
    int total = 0;
    int recv;
    while ((recv = httpd_req_recv(req, buf, sizeof(buf))) > 0) {
        err = esp_ota_write(handle, buf, recv);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "esp_ota_write failed at %d bytes: %s", total, esp_err_to_name(err));
            esp_ota_abort(handle);
            httpd_resp_set_status(req, "500 Internal Server Error");
            httpd_resp_sendstr(req, esp_err_to_name(err));
            return ESP_FAIL;
        }
        total += recv;
    }
    if (recv < 0) {
        ESP_LOGE(TAG, "httpd_req_recv failed at %d bytes", total);
        esp_ota_abort(handle);
        httpd_resp_set_status(req, "500 Internal Server Error");
        httpd_resp_sendstr(req, "recv failed mid-stream\n");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "OTA: %d bytes received, finalizing", total);

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

    httpd_resp_sendstr(req, "OK — rebooting into new image in 1 s\n");
    ESP_LOGI(TAG, "OTA: success, rebooting");
    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();
    return ESP_OK;   /* unreachable */
}

static void start_ota_server(void)
{
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
    cfg.server_port = OTA_HTTP_PORT;
    cfg.recv_wait_timeout = 30;
    cfg.send_wait_timeout = 30;
    cfg.stack_size = 8192;

    httpd_handle_t server = NULL;
    if (httpd_start(&server, &cfg) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start OTA HTTP server");
        return;
    }
    httpd_uri_t ota_uri = {
        .uri = "/update",
        .method = HTTP_POST,
        .handler = ota_post_handler,
        .user_ctx = NULL,
    };
    httpd_register_uri_handler(server, &ota_uri);
    ESP_LOGI(TAG, "OTA HTTP server listening on port %d (POST /update)", OTA_HTTP_PORT);
}

/* ── TCP server task — single-client, blocks on accept() between clients ──── */
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
        ESP_LOGI(TAG, "TCP client connected from %s", ip);

        /* TCP_NODELAY: avoid Nagle so frames go out immediately */
        int nodelay = 1;
        setsockopt(client, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));

        /* Publish the fd; close any prior one (defensive) */
        xSemaphoreTake(g_client_mutex, portMAX_DELAY);
        if (g_client_sock >= 0) close(g_client_sock);
        g_client_sock = client;
        xSemaphoreGive(g_client_mutex);

        /* Block here until the client disconnects (we don't expect any data
         * from the host — recv just gives us a disconnect signal). */
        char drain[16];
        while (1) {
            ssize_t r = recv(client, drain, sizeof(drain), 0);
            if (r <= 0) break;     /* 0 = closed by peer, -1 = error */
        }
        ESP_LOGI(TAG, "TCP client disconnected");

        xSemaphoreTake(g_client_mutex, portMAX_DELAY);
        if (g_client_sock == client) {
            close(client);
            g_client_sock = -1;
        }
        xSemaphoreGive(g_client_mutex);
    }
}

/* ── Main ranging task ───────────────────────────────────────────────────── */
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
        ESP_LOGE(TAG, "Sensor not detected (ret=%u) — check wiring.", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "Sensor detected");

    ESP_LOGI(TAG, "Uploading ULD firmware (~1 s)...");
    ret = vl53l8cx_init(&sensor);
    if (ret != VL53L8CX_STATUS_OK) {
        ESP_LOGE(TAG, "vl53l8cx_init failed (ret=%u)", ret);
        vTaskDelete(NULL);
    }
    ESP_LOGI(TAG, "ULD ready — version: %s", VL53L8CX_API_REVISION);

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

#if STREAM_DATA
        stream_distance_line(&results, SENSOR_RESOLUTION);
#endif
#if STREAM_SIGMA
        stream_sigma_line(&results, SENSOR_RESOLUTION);
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

    /* Start WiFi (async — connection completes in the background). */
    wifi_init_sta();

    /* TCP server task waits for WiFi internally, then listens. */
    xTaskCreate(tcp_server_task, "tcp_server", 4096, NULL, 4, NULL);

#if BUZZER_TEST
    /* Buzzer / GPIO control task. 4096 byte stack — 2048 was overflowing. */
    xTaskCreate(buzzer_task, "buzzer", 4096, NULL, 2, NULL);
#endif
}
