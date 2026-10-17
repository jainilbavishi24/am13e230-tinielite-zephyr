/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_WATCHDOG_H_
#define APP_WATCHDOG_H_

#include <stdint.h>

#define APP_WATCHDOG_RESET_CAUSE_WWDT0 0x0EU

struct app_watchdog_status {
	uint32_t reset_cause;
	uint32_t timeout_ms;
	uint32_t running;
};

int app_watchdog_init(void);
int app_watchdog_feed(void);
void app_watchdog_read_status(struct app_watchdog_status *status);
void app_watchdog_test_stall(void);

#endif /* APP_WATCHDOG_H_ */
