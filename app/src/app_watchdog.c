/* SPDX-License-Identifier: Apache-2.0 */

#include "app_watchdog.h"

#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_io.h>

#define WWDT_NODE   DT_NODELABEL(wwdt0)
#define SYSCTL_NODE DT_NODELABEL(sysctl)

#define WWDT_BASE   DT_REG_ADDR(WWDT_NODE)
#define SYSCTL_BASE DT_REG_ADDR_BY_NAME(SYSCTL_NODE, sysctl)

#define WWDT_PWREN_OFFSET  0x0800U
#define WWDT_RSTCTL_OFFSET 0x0804U
#define WWDT_STAT_OFFSET   0x0814U
#define WWDT_CTL0_OFFSET   0x1100U
#define WWDT_CTL1_OFFSET   0x1104U
#define WWDT_CNTRST_OFFSET 0x1108U
#define WWDT_STATUS_OFFSET 0x110CU
#define SYSCTL_SYSTEMCFG   0x1180U
#define SYSCTL_RSTCAUSE    0x1220U

#define WWDT_PWREN_KEY       0x26000000U
#define WWDT_RESET_KEY       0xB1000000U
#define WWDT_CTL0_KEY        0xC9000000U
#define WWDT_CTL1_KEY        0xBE000000U
#define SYSCTL_SYSTEMCFG_KEY 0x1B000000U

#define WWDT_POWER_ENABLE       BIT(0)
#define WWDT_RESET_ASSERT       BIT(0)
#define WWDT_RESET_STICKY_CLEAR BIT(1)
#define WWDT_RESET_STICKY       BIT(16)
#define WWDT_RUNNING            BIT(0)
#define SYSCTL_WWDT0_NMI        BIT(0)
#define SYSCTL_RESET_CAUSE_MASK 0x1FU
#define WWDT_RESTART_KEY        0xA7U

/* LFCLK / 4 * 2^15 = 4 seconds. Window 0 is open for the full period. */
#define WWDT_CLOCK_DIVIDE_BY_4 3U
#define WWDT_PERIOD_2_POW_15   0x30U
#define WWDT_CONTROL           (WWDT_CTL0_KEY | WWDT_CLOCK_DIVIDE_BY_4 | WWDT_PERIOD_2_POW_15)
#define WWDT_TIMEOUT_MS        4000U
#define WWDT_POWER_WAIT_US     1000U

static uint32_t boot_reset_cause;
static bool initialized;

static bool wait_for_mask(uintptr_t address, uint32_t mask, bool set)
{
	for (uint32_t elapsed = 0U; elapsed < WWDT_POWER_WAIT_US; ++elapsed) {
		if (((sys_read32(address) & mask) != 0U) == set) {
			return true;
		}
		k_busy_wait(1U);
	}
	return false;
}

int app_watchdog_init(void)
{
	uint32_t system_config;

	boot_reset_cause = sys_read32(SYSCTL_BASE + SYSCTL_RSTCAUSE) & SYSCTL_RESET_CAUSE_MASK;

	/* A WWDT0 violation must cause a BOOTRST, not merely an NMI. */
	system_config = sys_read32(SYSCTL_BASE + SYSCTL_SYSTEMCFG);
	system_config &= ~(0xFF000000U | SYSCTL_WWDT0_NMI);
	sys_write32(system_config | SYSCTL_SYSTEMCFG_KEY, SYSCTL_BASE + SYSCTL_SYSTEMCFG);

	/* Match TI driverlib: reset, power, wait for power, then configure once. */
	sys_write32(WWDT_RESET_KEY | WWDT_RESET_STICKY_CLEAR | WWDT_RESET_ASSERT,
		    WWDT_BASE + WWDT_RSTCTL_OFFSET);
	sys_write32(WWDT_PWREN_KEY | WWDT_POWER_ENABLE, WWDT_BASE + WWDT_PWREN_OFFSET);
	if (!wait_for_mask(WWDT_BASE + WWDT_PWREN_OFFSET, WWDT_POWER_ENABLE, true) ||
	    !wait_for_mask(WWDT_BASE + WWDT_STAT_OFFSET, WWDT_RESET_STICKY, true)) {
		return -EIO;
	}

	sys_write32(WWDT_CONTROL, WWDT_BASE + WWDT_CTL0_OFFSET);
	sys_write32(WWDT_CTL1_KEY, WWDT_BASE + WWDT_CTL1_OFFSET);
	if (!wait_for_mask(WWDT_BASE + WWDT_STATUS_OFFSET, WWDT_RUNNING, true)) {
		return -EIO;
	}

	initialized = true;
	return 0;
}

int app_watchdog_feed(void)
{
	if (!initialized) {
		return -EFAULT;
	}

	sys_write32(WWDT_RESTART_KEY, WWDT_BASE + WWDT_CNTRST_OFFSET);
	return 0;
}

void app_watchdog_read_status(struct app_watchdog_status *status)
{
	if (status == NULL) {
		return;
	}

	status->reset_cause = boot_reset_cause;
	status->timeout_ms = WWDT_TIMEOUT_MS;
	status->running = sys_read32(WWDT_BASE + WWDT_STATUS_OFFSET) & WWDT_RUNNING;
}

void app_watchdog_test_stall(void)
{
	/* Deliberately withhold the only feed source. WWDT0 must reset the board. */
	for (;;) {
		k_cpu_idle();
	}
}
