#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "driver/i2c_master.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Single-owner model (no internal task, no mutex): the CALLER's task owns the
 * bus. Add the BNO085 at addr_7bit, force a fresh SHTP advertisement, run the
 * SH-2 handshake + enable the game-rotation-vector, and BLOCK until the IMU is
 * reporting or timeout_ms elapses. Call this BEFORE the shared ToF is added, so
 * the handshake runs on an uncontended bus. Returns true if it's reporting.
 * int_gpio: BNO085 INT pin (-1 = poll; this clone's INT pad is unreliable). */
bool bno08x_init(i2c_master_bus_handle_t bus, uint8_t addr_7bit, int int_gpio, uint32_t timeout_ms);

/* Pump the SH-2 service once (read any ready report, update the quaternion). */
void bno08x_service(void);

/* Spawn a dedicated ~500 Hz service task (the BNO085 self-starves if serviced
 * slower than its report rate, and the main ranging loop is too slow). Call
 * AFTER bno08x_init() and AFTER the shared ToF is up. `mutex` serialises every
 * IMU transaction against the ToF reads on the shared bus -- the SAME handle the
 * ToF read path must take. */
void bno08x_run_task(SemaphoreHandle_t mutex);

/* Copy the latest orientation quaternion as {w, x, y, z}.
 * Returns false if no rotation-vector report has arrived yet. */
bool bno08x_get_quat(float out_wxyz[4]);

/* Magnetometer-fusion quality of the current ROTATION_VECTOR report.
 * Returns calibration accuracy 0..3 (0=Unreliable 1=Low 2=Med 3=High, datasheet
 * 3.1.5). If head_acc_rad != NULL, also writes the estimated heading accuracy in
 * radians. Use this to judge whether the magnetic environment is clean enough. */
uint8_t bno08x_get_status(float *head_acc_rad);

#ifdef __cplusplus
}
#endif
