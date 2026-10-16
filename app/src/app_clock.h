/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_CLOCK_H_
#define APP_CLOCK_H_

#include <stdbool.h>
#include <stdint.h>

struct app_clock_status {
	uint32_t expected_mclk_hz;
	uint32_t derived_mclk_hz;
	uint32_t uart_clock_hz;
	uint32_t mclkcfg;
	uint32_t hsclken;
	uint32_t hsclkcfg;
	uint32_t pllcfg0;
	uint32_t pllcfg1;
	uint32_t genclken;
	uint32_t clkstatus;
	uint32_t flash_control;
	uint32_t validation_flags;
};

enum app_clock_validation_flag {
	APP_CLOCK_VALID_MCLK_SOURCE = (1U << 0),
	APP_CLOCK_VALID_HSCLK = (1U << 1),
	APP_CLOCK_VALID_PLL = (1U << 2),
	APP_CLOCK_VALID_FREQUENCY = (1U << 3),
	APP_CLOCK_VALID_FLASH_WAIT_STATES = (1U << 4),
};

#define APP_CLOCK_VALIDATION_REQUIRED                                                              \
	(APP_CLOCK_VALID_MCLK_SOURCE | APP_CLOCK_VALID_HSCLK | APP_CLOCK_VALID_PLL |               \
	 APP_CLOCK_VALID_FREQUENCY | APP_CLOCK_VALID_FLASH_WAIT_STATES)

void app_clock_read_status(struct app_clock_status *status);
bool app_clock_status_is_valid(const struct app_clock_status *status);

#endif /* APP_CLOCK_H_ */
