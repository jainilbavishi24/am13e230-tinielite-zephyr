/* SPDX-License-Identifier: Apache-2.0 */

#include "app_clock.h"

#include <stddef.h>
#include <stdint.h>

#include <zephyr/arch/cpu.h>
#include <zephyr/devicetree.h>
#include <zephyr/sys/sys_io.h>

#define SYSCTL_NODE DT_NODELABEL(sysctl)
#define UART_NODE   DT_CHOSEN(zephyr_console)

#define SYSCTL_BASE      DT_REG_ADDR_BY_NAME(SYSCTL_NODE, sysctl)
#define FRI_BASE         DT_REG_ADDR_BY_NAME(SYSCTL_NODE, fri)
#define EXPECTED_MCLK_HZ DT_PROP(DT_NODELABEL(cpu0), clock_frequency)
#define UART_CLOCK_HZ    DT_PROP(DT_PHANDLE(UART_NODE, clocks), clock_frequency)
#define HFCLK_HZ         DT_PROP(SYSCTL_NODE, ti_hfclk_frequency)
#define SYSOSC_HZ        DT_PROP(SYSCTL_NODE, ti_sysosc_frequency)

#define MCLKCFG_OFFSET       0x1104U
#define HSCLKEN_OFFSET       0x1108U
#define HSCLKCFG_OFFSET      0x110CU
#define PLLCFG0_OFFSET       0x1120U
#define PLLCFG1_OFFSET       0x1124U
#define GENCLKEN_OFFSET      0x113CU
#define CLKSTATUS_OFFSET     0x1204U
#define FLASH_CONTROL_OFFSET 0x1000U

#define MCLKCFG_USE_HSCLK         (1U << 16)
#define HSCLKEN_PLL_ENABLE        (1U << 8)
#define HSCLKCFG_USE_HFCLK        (1U << 0)
#define PLLCFG0_REF_HFCLK         (1U << 0)
#define PLLCFG0_CLK0_ENABLE       (1U << 4)
#define GENCLKEN_DIV_ENABLE       (1U << 11)
#define CLKSTATUS_HF_GOOD         (1U << 8)
#define CLKSTATUS_PLL_GOOD        (1U << 9)
#define CLKSTATUS_MCLK_HS         (1U << 4)
#define CLKSTATUS_HS_SOURCE_HFCLK (1U << 16)
#define CLKSTATUS_HS_DEAD         (1U << 20)
#define CLKSTATUS_HS_GOOD         (1U << 21)

#define FLASH_WS0_MODE           (1U << 0)
#define FLASH_RWAIT_SHIFT        8U
#define FLASH_RWAIT_MASK         0xFU
#define FLASH_200MHZ_WAIT_STATES 3U

static uint32_t pll_output_hz(uint32_t pllcfg0, uint32_t pllcfg1)
{
	uint32_t reference_hz = (pllcfg0 & PLLCFG0_REF_HFCLK) != 0U ? HFCLK_HZ : SYSOSC_HZ;
	uint32_t pdiv = 1U << (pllcfg1 & 0x3U);
	uint32_t qdiv = ((pllcfg1 >> 8) & 0x7FU) + 1U;
	uint32_t rdiv = ((((pllcfg0 >> 8) & 0xFU) + 1U) * 2U);

	return (reference_hz / pdiv) * qdiv / rdiv;
}

static uint32_t active_mclk_hz(const struct app_clock_status *status)
{
	uint32_t frequency;

	if ((status->clkstatus & CLKSTATUS_MCLK_HS) == 0U) {
		return (status->clkstatus & 0x3U) == 1U ? 4000000U : SYSOSC_HZ;
	}

	if ((status->clkstatus & CLKSTATUS_HS_SOURCE_HFCLK) != 0U) {
		return HFCLK_HZ;
	}

	frequency = pll_output_hz(status->pllcfg0, status->pllcfg1);
	if ((status->genclken & GENCLKEN_DIV_ENABLE) != 0U) {
		frequency /= ((((status->genclken >> 8) & 0x7U) + 1U) * 2U);
	}
	return frequency;
}

void app_clock_read_status(struct app_clock_status *status)
{
	uint32_t flash_wait_states;

	if (status == NULL) {
		return;
	}

	status->expected_mclk_hz = EXPECTED_MCLK_HZ;
	status->uart_clock_hz = UART_CLOCK_HZ;
	status->mclkcfg = sys_read32(SYSCTL_BASE + MCLKCFG_OFFSET);
	status->hsclken = sys_read32(SYSCTL_BASE + HSCLKEN_OFFSET);
	status->hsclkcfg = sys_read32(SYSCTL_BASE + HSCLKCFG_OFFSET);
	status->pllcfg0 = sys_read32(SYSCTL_BASE + PLLCFG0_OFFSET);
	status->pllcfg1 = sys_read32(SYSCTL_BASE + PLLCFG1_OFFSET);
	status->genclken = sys_read32(SYSCTL_BASE + GENCLKEN_OFFSET);
	status->clkstatus = sys_read32(SYSCTL_BASE + CLKSTATUS_OFFSET);
	status->flash_control = sys_read32(FRI_BASE + FLASH_CONTROL_OFFSET);
	status->derived_mclk_hz = active_mclk_hz(status);
	status->validation_flags = 0U;

	if (((status->mclkcfg & MCLKCFG_USE_HSCLK) != 0U) &&
	    ((status->clkstatus & CLKSTATUS_MCLK_HS) != 0U)) {
		status->validation_flags |= APP_CLOCK_VALID_MCLK_SOURCE;
	}
	if (((status->clkstatus & CLKSTATUS_HS_GOOD) != 0U) &&
	    ((status->clkstatus & CLKSTATUS_HS_DEAD) == 0U)) {
		status->validation_flags |= APP_CLOCK_VALID_HSCLK;
	}
	if ((status->hsclkcfg & HSCLKCFG_USE_HFCLK) != 0U) {
		if ((status->clkstatus & CLKSTATUS_HF_GOOD) != 0U) {
			status->validation_flags |= APP_CLOCK_VALID_PLL;
		}
	} else if (((status->hsclken & HSCLKEN_PLL_ENABLE) != 0U) &&
		   ((status->pllcfg0 & PLLCFG0_CLK0_ENABLE) != 0U) &&
		   ((status->clkstatus & CLKSTATUS_PLL_GOOD) != 0U)) {
		status->validation_flags |= APP_CLOCK_VALID_PLL;
	}
	if (status->derived_mclk_hz == status->expected_mclk_hz) {
		status->validation_flags |= APP_CLOCK_VALID_FREQUENCY;
	}

	flash_wait_states =
		(status->flash_control & FLASH_WS0_MODE) != 0U
			? 0U
			: (status->flash_control >> FLASH_RWAIT_SHIFT) & FLASH_RWAIT_MASK;
	if ((status->expected_mclk_hz <= 50000000U) ||
	    (flash_wait_states >= FLASH_200MHZ_WAIT_STATES)) {
		status->validation_flags |= APP_CLOCK_VALID_FLASH_WAIT_STATES;
	}
}

bool app_clock_status_is_valid(const struct app_clock_status *status)
{
	return (status != NULL) && ((status->validation_flags & APP_CLOCK_VALIDATION_REQUIRED) ==
				    APP_CLOCK_VALIDATION_REQUIRED);
}
