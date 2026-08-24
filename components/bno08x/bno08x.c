/* BNO085 (BNO08x) driver for the helmet, I2C transport on a SHARED i2c_master
 * bus (the bottom ToF sensor already owns the bus). Implements the CEVA SH-2
 * HAL over I2C (SHTP: peek the 4-byte header for the length, then read the
 * packet), enables the rotation-vector report, and exposes the latest
 * quaternion. The SHTP-over-I2C read logic mirrors Adafruit's i2chal. */
#include "bno08x.h"
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include <math.h>
#include "esp_timer.h"
#include "sh2.h"
#include "sh2_SensorValue.h"
#include "sh2_err.h"
#include "driver/gpio.h"

static const char *TAG = "bno08x";
#define I2C_TIMEOUT_MS 100

static i2c_master_dev_handle_t s_dev;
static i2c_master_bus_handle_t s_bus = NULL;   /* shared bus, for FSM recovery on error */
static int s_int_gpio = -1;   /* BNO085 INT (active-low = data ready); -1 = poll */
static volatile uint32_t s_calls = 0, s_intlow = 0, s_pkts = 0;
static sh2_Hal_t s_hal;
static bool s_started = false;   /* sh2 handshake done; service() may run */
/* Set ONLY after the handshake, when the fast service task starts and the ToF
 * begins sharing the bus. NULL during init (IMU alone) -> no locking overhead. */
static SemaphoreHandle_t s_mutex = NULL;
static volatile float s_q[4] = {1.0f, 0.0f, 0.0f, 0.0f};  /* w, x, y, z */
static volatile bool  s_have = false;
/* Magnetometer-fusion quality, only meaningful for SH2_ROTATION_VECTOR:
 *   s_status   = calibration accuracy, datasheet 3.1.5: 0=Unreliable 1=Low 2=Med 3=High
 *   s_head_acc = estimated heading accuracy in radians (rotationVector.accuracy) */
static volatile uint8_t s_status = 0;
static volatile float   s_head_acc = 0.0f;

/* ----------------------------------------------------------------- SH-2 HAL */
static int hal_open(sh2_Hal_t *self)
{
    (void)self;
    vTaskDelay(pdMS_TO_TICKS(150));
    /* Force the hub to (re)send its SHTP advertisement + reset-complete packet.
     * The BNO085 only emits that ONCE after a power-on, and an ESP reset does NOT
     * power-cycle the IMU -- so on every boot after the first, sh2_open's handshake
     * finds nothing to read (enable -> -2, evt stays 0). A reset command on the
     * SHTP *executable* channel (channel 1, payload 0x01) makes the hub reboot and
     * re-advertise, so the handshake works on every boot without a manual unplug. */
    uint8_t reset_pkt[5] = { 0x05, 0x00, 0x01, 0x00, 0x01 }; /* len=5, chan=1, seq=0, cmd=RESET */
    i2c_master_transmit(s_dev, reset_pkt, sizeof(reset_pkt), I2C_TIMEOUT_MS);
    vTaskDelay(pdMS_TO_TICKS(200));   /* let the hub reboot + queue the advertisement */
    return 0;
}

static void hal_close(sh2_Hal_t *self) { (void)self; }

static int hal_read(sh2_Hal_t *self, uint8_t *pBuffer, unsigned len, uint32_t *t_us)
{
    (void)self;
    s_calls++;
    if (s_int_gpio >= 0 && gpio_get_level(s_int_gpio) == 0) s_intlow++;
    int ret = 0;
    /* Header peek + cargo read held under ONE lock (when the ToF shares the bus)
     * so a ToF transaction can't split the SHTP read. NULL mutex during init. */
    if (s_mutex) xSemaphoreTake(s_mutex, portMAX_DELAY);
    uint8_t header[4];
    esp_err_t rerr = i2c_master_receive(s_dev, header, 4, I2C_TIMEOUT_MS);
    if (rerr != ESP_OK) {
        if (s_calls <= 10) ESP_LOGW(TAG, "hdr read -> %s", esp_err_to_name(rerr));
    } else {
        uint16_t packet_size = (((uint16_t)header[1] << 8) | header[0]) & 0x7FFF;
        if (packet_size != 0 && packet_size <= len) {
            if (i2c_master_receive(s_dev, pBuffer, packet_size, I2C_TIMEOUT_MS) == ESP_OK) {
                s_pkts++;
                if (t_us) *t_us = (uint32_t)esp_timer_get_time();
                ret = packet_size;
            }
        }
    }
    if (s_mutex) xSemaphoreGive(s_mutex);
    return ret;
}

static int hal_write(sh2_Hal_t *self, uint8_t *pBuffer, unsigned len)
{
    (void)self;
    if (len == 0) return 0;
    int ret = 0;
    if (s_mutex) xSemaphoreTake(s_mutex, portMAX_DELAY);
    if (i2c_master_transmit(s_dev, pBuffer, len, I2C_TIMEOUT_MS) == ESP_OK)
        ret = (int)len;
    if (s_mutex) xSemaphoreGive(s_mutex);
    return ret;
}

static uint32_t hal_get_time_us(sh2_Hal_t *self)
{
    (void)self;
    return (uint32_t)esp_timer_get_time();
}

/* --------------------------------------------------------------- callbacks */
static volatile bool s_reset_seen = false;

static void event_cb(void *cookie, sh2_AsyncEvent_t *event)
{
    (void)cookie;
    if (event->eventId == SH2_RESET) {
        s_reset_seen = true;
        ESP_LOGI(TAG, "sensor hub reset");
    }
}

static void enable_reports(void)
{
    sh2_SensorConfig_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.reportInterval_us = 10000;       /* 100 Hz */
    /* AR/VR-Stabilized Game Rotation Vector = 6-axis (accel+gyro, NO magnetometer).
     * Chosen after on-device testing: the haptic motors corrupt the magnetometer at
     * the current ~5 cm spacing (mag accuracy collapsed High->Low, ~60 deg heading
     * JUMPS when motors ran). Mag-free => motor-immune AND no heading jumps; the
     * AR/VR stabilization (datasheet 2.2.3) also suppresses accel-correction jumps.
     * Tradeoff: no absolute-north reference, so yaw drifts slowly -- minimized by
     * gyro zero-rate-offset calibration (converges when held still, datasheet 3.1.3)
     * and the software Recenter. To re-enable mag later (e.g. if the IMU is moved
     * far from the motors) switch back to SH2_ROTATION_VECTOR. */
    int r = sh2_setSensorConfig(SH2_ARVR_STABILIZED_GRV, &cfg);
    ESP_LOGW(TAG, "enable ARVR-stabilized GRV (6-axis, mag-free) -> %d", r);

    /* TAP detector: on-chip event report (fires only on taps -- near-zero
     * bus cost). Double-tap = the hands-free query gesture (PLAN-tap-to-query). */
    memset(&cfg, 0, sizeof(cfg));
    cfg.reportInterval_us = 100000;      /* keep-alive; taps arrive as events */
    cfg.changeSensitivityEnabled = true;
    r = sh2_setSensorConfig(SH2_TAP_DETECTOR, &cfg);
    ESP_LOGW(TAG, "enable TAP detector -> %d", r);

    /* Accelerometer @50 Hz for the drop-alarm state machine (freefall ->
     * impact). Consumed entirely in sensor_cb; nothing new streamed raw
     * (PLAN-drop-alarm). */
    memset(&cfg, 0, sizeof(cfg));
    cfg.reportInterval_us = 20000;       /* 50 Hz */
    r = sh2_setSensorConfig(SH2_ACCELEROMETER, &cfg);
    ESP_LOGW(TAG, "enable accelerometer 50Hz (drop alarm) -> %d", r);
}

static volatile uint32_t s_evt = 0, s_dec_fail = 0, s_rv = 0;

/* -- tap + drop event latches (consume-on-read via accessors below) -- */
static volatile uint8_t  s_tap_flags = 0;
static volatile uint32_t s_tap_seq = 0, s_tap_taken = 0;

#define DROP_FREEFALL_G     0.40f    /* |a| below this = freefall candidate */
#define DROP_FREEFALL_MS    150      /* sustained this long (>=40 cm fall)  */
#define DROP_IMPACT_G       2.5f     /* spike above this within the window  */
#define DROP_IMPACT_WIN_MS  500
static volatile int  s_drop_pending = -1;   /* -1 none, 1 dropped, 0 cleared */
static bool     s_drop_latched = false;
static int64_t  s_ff_start_us = 0;          /* freefall entry time, 0 = none */
static int64_t  s_ff_deadline_us = 0;       /* impact must land before this  */
static int      s_motion_cnt = 0;           /* post-drop pickup detection    */
static int64_t  s_motion_win_us = 0;

static void sensor_cb(void *cookie, sh2_SensorEvent_t *event)
{
    (void)cookie;
    sh2_SensorValue_t v;
    s_evt++;
    if (sh2_decodeSensorEvent(&v, event) != SH2_OK) {
        s_dec_fail++;
        return;
    }
    if (s_evt <= 6) ESP_LOGI(TAG, "evt %lu sensorId=0x%02X", (unsigned long)s_evt, v.sensorId);
    if (v.sensorId == SH2_GAME_ROTATION_VECTOR) {
        s_rv++;
        s_q[0] = v.un.gameRotationVector.real;
        s_q[1] = v.un.gameRotationVector.i;
        s_q[2] = v.un.gameRotationVector.j;
        s_q[3] = v.un.gameRotationVector.k;
        s_have = true;
    } else if (v.sensorId == SH2_ROTATION_VECTOR) {
        s_rv++;
        s_q[0] = v.un.rotationVector.real;
        s_q[1] = v.un.rotationVector.i;
        s_q[2] = v.un.rotationVector.j;
        s_q[3] = v.un.rotationVector.k;
        s_status   = v.status & 0x03;                 /* 0..3 calibration accuracy */
        s_head_acc = v.un.rotationVector.accuracy;    /* heading accuracy, radians */
        s_have = true;
    } else if (v.sensorId == SH2_TAP_DETECTOR) {
        s_tap_flags = v.un.tapDetector.flags;
        s_tap_seq++;
    } else if (v.sensorId == SH2_ACCELEROMETER) {
        /* drop-alarm state machine: freefall window -> impact -> latched;
         * sustained motion afterwards = picked up -> cleared. All in-firmware,
         * nothing streamed raw (PLAN-drop-alarm). */
        float ax = v.un.accelerometer.x, ay = v.un.accelerometer.y,
              az = v.un.accelerometer.z;
        float mag = sqrtf(ax * ax + ay * ay + az * az);   /* m/s^2 */
        int64_t now = esp_timer_get_time();
        if (!s_drop_latched) {
            if (mag < DROP_FREEFALL_G * 9.81f) {
                if (s_ff_start_us == 0) s_ff_start_us = now;
                else if (now - s_ff_start_us > (int64_t)DROP_FREEFALL_MS * 1000)
                    s_ff_deadline_us = now + (int64_t)DROP_IMPACT_WIN_MS * 1000;
            } else {
                s_ff_start_us = 0;
                if (mag > DROP_IMPACT_G * 9.81f && now < s_ff_deadline_us) {
                    s_drop_latched = true;
                    s_drop_pending = 1;
                    s_motion_cnt = 0;
                    s_motion_win_us = now;
                    ESP_LOGW(TAG, "DROP detected (impact %.1f m/s2)", (double)mag);
                }
            }
        } else {
            /* picked up = sustained non-still motion over a 2 s window */
            if (fabsf(mag - 9.81f) > 1.5f) s_motion_cnt++;
            if (now - s_motion_win_us > 2000000) {
                if (s_motion_cnt >= 20) {
                    s_drop_latched = false;
                    s_drop_pending = 0;
                    s_ff_deadline_us = 0;
                    ESP_LOGW(TAG, "DROP cleared (picked up)");
                }
                s_motion_cnt = 0;
                s_motion_win_us = now;
            }
        }
    } else if (v.sensorId == SH2_ARVR_STABILIZED_GRV) {
        s_rv++;
        s_q[0] = v.un.arvrStabilizedGRV.real;
        s_q[1] = v.un.arvrStabilizedGRV.i;
        s_q[2] = v.un.arvrStabilizedGRV.j;
        s_q[3] = v.un.arvrStabilizedGRV.k;
        s_status   = v.status & 0x03;   /* accel/gyro calibration accuracy (no mag) */
        s_head_acc = 0.0f;              /* mag-free: no heading-accuracy estimate */
        s_have = true;
    }
}

/* Consume-on-read tap event. Returns true once per new tap; flags bit 64
 * (TAPDET_DOUBLE) = double tap. */
bool bno08x_get_tap(uint8_t *flags)
{
    if (s_tap_seq == s_tap_taken) return false;
    s_tap_taken = s_tap_seq;
    if (flags) *flags = s_tap_flags;
    return true;
}

/* Consume-on-read drop event: -1 no change, 1 drop latched, 0 cleared. */
int bno08x_get_drop(void)
{
    int e = s_drop_pending;
    s_drop_pending = -1;
    return e;
}

/* -------------------------------------------------------------------- API */
/* Single-owner model: NO internal task, NO mutex. The CALLER's task owns the bus
 * -- it must call bno08x_service() periodically (from the same loop that reads the
 * other device). bno08x_init() runs the whole SH-2 handshake on the (still
 * uncontended) bus and blocks until the IMU is reporting or timeout_ms elapses. */
bool bno08x_init(i2c_master_bus_handle_t bus, uint8_t addr_7bit, int int_gpio, uint32_t timeout_ms)
{
    s_bus = bus;
    if (int_gpio >= 0) {
        gpio_config_t ic = {
            .pin_bit_mask = 1ULL << int_gpio,
            .mode = GPIO_MODE_INPUT,
            .pull_up_en = GPIO_PULLUP_ENABLE,
            .pull_down_en = GPIO_PULLDOWN_DISABLE,
            .intr_type = GPIO_INTR_DISABLE,
        };
        gpio_config(&ic);
        s_int_gpio = int_gpio;
    }
    i2c_device_config_t dc = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7,
        .device_address  = addr_7bit,
        .scl_speed_hz    = 400000,       /* BNO085 max */
        /* The BNO085 holds SCL low (clock-stretch) when polled with no report
         * ready; with the default (short) tolerance such a poll TIMES OUT as a
         * failed read, which is why most steady-state reads came back empty
         * (pkts<<calls). Give it ~12 ms (just over one 100 Hz report period) so a
         * poll waits for the imminent report instead of failing. Safe now that the
         * SHTP soft-reset (hal_open) fixes the handshake -- the earlier "scl_wait_us
         * broke the handshake" was really the missing-advertisement bug. Single
         * owner, so a brief stretch-wait blocks only this loop, never a second task. */
        .scl_wait_us     = 12000,
    };
    if (i2c_master_bus_add_device(bus, &dc, &s_dev) != ESP_OK) {
        ESP_LOGE(TAG, "i2c add_device 0x%02X failed", addr_7bit);
        return false;
    }

    s_hal.open      = hal_open;       /* soft-resets the hub -> fresh advertisement */
    s_hal.close     = hal_close;
    s_hal.read      = hal_read;
    s_hal.write     = hal_write;
    s_hal.getTimeUs = hal_get_time_us;

    int r = sh2_open(&s_hal, event_cb, NULL);
    if (r != SH2_OK) {
        ESP_LOGE(TAG, "sh2_open failed (%d) - check wiring/PS pins", r);
        return false;
    }
    sh2_setSensorCallback(sensor_cb, NULL);

    sh2_ProductIds_t ids;
    memset(&ids, 0, sizeof(ids));
    if (sh2_getProdIds(&ids) == SH2_OK)
        ESP_LOGI(TAG, "BNO085 online (%u product-id entries)", ids.numEntries);

    /* --- Calibration config for mag-free head tracking ---
     * ACCEL + GYRO dynamic calibration ON, MAG OFF:
     *  - GYRO: continuously removes the gyroscope zero-rate offset (ZRO) -> cuts
     *    yaw drift, which is the dominant error source without the magnetometer
     *    (datasheet 3.1.3; a head has the tremor the ZRO algorithm needs).
     *  - ACCEL: keeps pitch/roll anchored to gravity (datasheet 3.1.6 VR guidance).
     *  - MAG: left OFF -- we don't fuse the magnetometer (the haptic motors corrupt
     *    it), so calibrating it would waste effort. (Default has accel+mag on.)
     * Note: cal settings do NOT persist across hub resets (datasheet 3.1.1), so this
     * runs every boot, after the hal_open soft-reset + sh2_open. */
    int cr = sh2_setCalConfig(SH2_CAL_ACCEL | SH2_CAL_GYRO);
    ESP_LOGW(TAG, "setCalConfig accel+gyro (mag off) -> %d", cr);
    /* Persist Dynamic Calibration Data periodically so the converged ZRO/accel cal
     * is saved to flash and reloaded on reboot -- start each session already
     * calibrated instead of re-converging from scratch (datasheet 3.4). */
    int dr = sh2_setDcdAutoSave(true);
    ESP_LOGW(TAG, "setDcdAutoSave(true) -> %d", dr);

    enable_reports();
    s_started = true;

    /* Built-in "IMU up" barrier: pump the service loop on the uncontended bus
     * until the first report arrives (or we give up). */
    int64_t t0 = esp_timer_get_time();
    while (!s_have && (esp_timer_get_time() - t0) < (int64_t)timeout_ms * 1000) {
        bno08x_service();
        vTaskDelay(pdMS_TO_TICKS(5));
    }
    if (s_have)
        ESP_LOGI(TAG, "IMU up after %lld ms (handshake OK)",
                 (long long)((esp_timer_get_time() - t0) / 1000));
    else
        ESP_LOGW(TAG, "IMU not reporting after %lu ms", (unsigned long)timeout_ms);
    return s_have;
}

/* Pump SH-2 once: reads any ready report, updates the quaternion, re-enables
 * after a hub reset. Call from the owner task's loop (rate-limit to ~100 Hz). */
void bno08x_service(void)
{
    if (!s_started) return;
    sh2_service();
    if (s_reset_seen) {
        s_reset_seen = false;
        ESP_LOGW(TAG, "reset detected -> re-enabling reports");
        enable_reports();
    }
    static uint32_t hb = 0;
    if (++hb % 1000 == 0)
        ESP_LOGW(TAG, "hb: calls=%lu pkts=%lu evt=%lu rv=%lu",
                 (unsigned long)s_calls, (unsigned long)s_pkts,
                 (unsigned long)s_evt, (unsigned long)s_rv);
}

/* Spawn the dedicated fast service task. Call AFTER bno08x_init() and AFTER the
 * shared ToF is up. The BNO085 must be serviced far faster than its 100 Hz report
 * rate or it self-starves -- the main ranging loop (streaming-bound, ~33 Hz) is
 * too slow, so the IMU gets its own ~500 Hz task. `mutex` serialises every IMU
 * transaction against the ToF reads on the shared bus. */
static void imu_task(void *arg)
{
    (void)arg;
    while (1) {
        bno08x_service();
        vTaskDelay(pdMS_TO_TICKS(2));   /* ~500 Hz: well above the 100 Hz report rate */
    }
}

void bno08x_run_task(SemaphoreHandle_t mutex)
{
    s_mutex = mutex;   /* from now on every IMU transaction takes the lock */
    xTaskCreate(imu_task, "imu", 4096, NULL, 6, NULL);
}

bool bno08x_get_quat(float out[4])
{
    if (!s_have) return false;
    out[0] = s_q[0]; out[1] = s_q[1]; out[2] = s_q[2]; out[3] = s_q[3];
    return true;
}

/* Mag-fusion quality for the current ROTATION_VECTOR report.
 * status: 0=Unreliable 1=Low 2=Med 3=High (datasheet 3.1.5); *head_acc_rad optional. */
uint8_t bno08x_get_status(float *head_acc_rad)
{
    if (head_acc_rad) *head_acc_rad = s_head_acc;
    return s_status;
}
