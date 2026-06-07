#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "driver/i2c_master.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Start the BNO085 on an EXISTING i2c_master bus (shared with the ToF sensor).
 * Adds the device at addr_7bit and spawns a task that runs the SH-2 service
 * loop and keeps the latest rotation-vector quaternion. Returns false if the
 * device can't be added to the bus. */
bool bno08x_start(i2c_master_bus_handle_t bus, uint8_t addr_7bit);

/* Copy the latest orientation quaternion as {w, x, y, z}.
 * Returns false if no rotation-vector report has arrived yet. */
bool bno08x_get_quat(float out_wxyz[4]);

#ifdef __cplusplus
}
#endif
