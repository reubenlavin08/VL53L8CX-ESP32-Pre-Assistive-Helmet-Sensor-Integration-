/* BNO085 (BNO08x) driver for the helmet, I2C transport on a SHARED i2c_master
 * bus (the bottom ToF sensor already owns the bus). Implements the CEVA SH-2
 * HAL over I2C (SHTP: peek the 4-byte header for the length, then read the
 * packet), enables the rotation-vector report, and exposes the latest
 * quaternion. The SHTP-over-I2C read logic mirrors Adafruit's i2chal. */
#include "bno08x.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sh2.h"
#include "sh2_SensorValue.h"
#include "sh2_err.h"

static const char *TAG = "bno08x";
#define I2C_TIMEOUT_MS 100

static i2c_master_dev_handle_t s_dev;
static sh2_Hal_t s_hal;
static volatile float s_q[4] = {1.0f, 0.0f, 0.0f, 0.0f};  /* w, x, y, z */
static volatile bool  s_have = false;

/* ----------------------------------------------------------------- SH-2 HAL */
static int hal_open(sh2_Hal_t *self)
{
    /* RST is tied high in hardware -> rely on the power-on reset. Give the hub
     * time to boot; sh2_open() then resyncs over SHTP. */
    (void)self;
    vTaskDelay(pdMS_TO_TICKS(200));
    return 0;
}

static void hal_close(sh2_Hal_t *self) { (void)self; }

static int hal_read(sh2_Hal_t *self, uint8_t *pBuffer, unsigned len, uint32_t *t_us)
{
    (void)self;
    uint8_t header[4];
    /* Peek the SHTP header to learn the packet length. */
    if (i2c_master_receive(s_dev, header, 4, I2C_TIMEOUT_MS) != ESP_OK)
        return 0;
    uint16_t packet_size = (((uint16_t)header[1] << 8) | header[0]) & 0x7FFF;  /* clear continuation bit */
    if (packet_size == 0)
        return 0;                         /* nothing waiting */
    if (packet_size > len) {
        ESP_LOGW(TAG, "SHTP packet %u > buf %u, dropping", packet_size, (unsigned)len);
        return 0;
    }
    /* Read the whole packet (header + cargo). */
    if (i2c_master_receive(s_dev, pBuffer, packet_size, I2C_TIMEOUT_MS) != ESP_OK)
        return 0;
    if (t_us) *t_us = (uint32_t)esp_timer_get_time();
    return packet_size;
}

static int hal_write(sh2_Hal_t *self, uint8_t *pBuffer, unsigned len)
{
    (void)self;
    if (len == 0) return 0;
    if (i2c_master_transmit(s_dev, pBuffer, len, I2C_TIMEOUT_MS) != ESP_OK)
        return 0;
    return (int)len;
}

static uint32_t hal_get_time_us(sh2_Hal_t *self)
{
    (void)self;
    return (uint32_t)esp_timer_get_time();
}

/* --------------------------------------------------------------- callbacks */
static void event_cb(void *cookie, sh2_AsyncEvent_t *event)
{
    (void)cookie;
    if (event->eventId == SH2_RESET)
        ESP_LOGI(TAG, "sensor hub reset");
}

static void sensor_cb(void *cookie, sh2_SensorEvent_t *event)
{
    (void)cookie;
    sh2_SensorValue_t v;
    if (sh2_decodeSensorEvent(&v, event) != SH2_OK)
        return;
    if (v.sensorId == SH2_ROTATION_VECTOR) {
        s_q[0] = v.un.rotationVector.real;
        s_q[1] = v.un.rotationVector.i;
        s_q[2] = v.un.rotationVector.j;
        s_q[3] = v.un.rotationVector.k;
        s_have = true;
    }
}

static void imu_task(void *arg)
{
    (void)arg;
    s_hal.open      = hal_open;
    s_hal.close     = hal_close;
    s_hal.read      = hal_read;
    s_hal.write     = hal_write;
    s_hal.getTimeUs = hal_get_time_us;

    int r = sh2_open(&s_hal, event_cb, NULL);
    if (r != SH2_OK) {
        ESP_LOGE(TAG, "sh2_open failed (%d) - check wiring/PS pins", r);
        vTaskDelete(NULL);
        return;
    }

    sh2_ProductIds_t ids;
    memset(&ids, 0, sizeof(ids));
    if (sh2_getProdIds(&ids) == SH2_OK)
        ESP_LOGI(TAG, "BNO085 online (%u product-id entries)", ids.numEntries);

    sh2_setSensorCallback(sensor_cb, NULL);

    sh2_SensorConfig_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.reportInterval_us = 10000;       /* 100 Hz rotation vector */
    if (sh2_setSensorConfig(SH2_ROTATION_VECTOR, &cfg) != SH2_OK)
        ESP_LOGE(TAG, "enable rotation-vector failed");
    else
        ESP_LOGI(TAG, "rotation vector enabled @100Hz");

    while (1) {
        sh2_service();
        vTaskDelay(pdMS_TO_TICKS(2));
    }
}

/* -------------------------------------------------------------------- API */
bool bno08x_start(i2c_master_bus_handle_t bus, uint8_t addr_7bit)
{
    i2c_device_config_t dc = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = addr_7bit,
        .scl_speed_hz    = 400000,       /* BNO085 max; ToF on same bus keeps its own 1MHz */
    };
    if (i2c_master_bus_add_device(bus, &dc, &s_dev) != ESP_OK) {
        ESP_LOGE(TAG, "i2c add_device 0x%02X failed", addr_7bit);
        return false;
    }
    xTaskCreate(imu_task, "imu", 5120, NULL, 5, NULL);
    return true;
}

bool bno08x_get_quat(float out[4])
{
    if (!s_have) return false;
    out[0] = s_q[0]; out[1] = s_q[1]; out[2] = s_q[2]; out[3] = s_q[3];
    return true;
}
