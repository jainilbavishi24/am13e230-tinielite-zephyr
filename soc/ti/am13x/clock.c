/* SPDX-License-Identifier: Apache-2.0 */

#include <errno.h>
#include <stdint.h>

#include <zephyr/arch/cpu.h>
#include <zephyr/devicetree.h>
#include <zephyr/init.h>
#include <zephyr/sys/sys_io.h>
#include <zephyr/toolchain.h>

#define SYSCTL_NODE DT_NODELABEL(sysctl)

#define SYSCTL_BASE DT_REG_ADDR_BY_NAME(SYSCTL_NODE, sysctl)
#define FRI_BASE    DT_REG_ADDR_BY_NAME(SYSCTL_NODE, fri)
#define IOMUX_BASE  DT_REG_ADDR_BY_NAME(SYSCTL_NODE, iomux)
#define PLL_PARAMS  DT_REG_ADDR_BY_NAME(SYSCTL_NODE, pll_params)

#define MCLKCFG      (SYSCTL_BASE + 0x1104U)
#define HSCLKEN      (SYSCTL_BASE + 0x1108U)
#define HSCLKCFG     (SYSCTL_BASE + 0x110CU)
#define HFCLKCLKCFG  (SYSCTL_BASE + 0x1110U)
#define SYSPLLCFG0   (SYSCTL_BASE + 0x1120U)
#define SYSPLLCFG1   (SYSCTL_BASE + 0x1124U)
#define SYSPLLPARAM0 (SYSCTL_BASE + 0x1128U)
#define SYSPLLPARAM1 (SYSCTL_BASE + 0x112CU)
#define GENCLKEN     (SYSCTL_BASE + 0x113CU)
#define CLKSTATUS    (SYSCTL_BASE + 0x1204U)
#define XTALCR       (SYSCTL_BASE + 0x1474U)

#define FRI_FRDCNTL    (FRI_BASE + 0x1000U)
#define FRI_INTF_CTRL  (FRI_BASE + 0x1004U)
#define FRI_WS0_MODE   (1U << 0)
#define FRI_RWAIT_MASK (0xFU << 8)
#define FRI_CACHE_MASK ((1U << 1) | (1U << 2))

#define XTAL_PIN_X1_OFFSET (80U * sizeof(uint32_t))
#define XTAL_PIN_X2_OFFSET (81U * sizeof(uint32_t))

#define HSCLKEN_PLL_ENABLE  (1U << 8)
#define HFCLK_MONITOR       (1U << 28)
#define PLL_CLK_OUTPUTS     ((1U << 4) | (1U << 5))
#define PLL_REF_HFCLK       (1U << 0)
#define PLL_PDIV_2          (1U << 0)
#define PLL_QDIV_32         (31U << 8)
#define MCLK_USE_HSCLK      (1U << 16)
#define MCLK_DIV_2_DIV_4    (7U << 24)
#define MCLK_DIV_MASK       (7U << 24)
#define EXT_MCLK_DIV_ENABLE (1U << 11)
#define EXT_MCLK_DIV_MASK   (7U << 8)
#define EXT_MCLK_DIV_4      (1U << 8)

#define STATUS_HFCLK_GOOD (1U << 8)
#define STATUS_PLL_GOOD   (1U << 9)
#define STATUS_PLL_OFF    (1U << 14)
#define STATUS_MCLK_HSCLK (1U << 4)
#define STATUS_HSCLK_GOOD (1U << 21)

#define CLOCK_WAIT_ITERATIONS 4000000U

static int wait_for_status(uint32_t mask, uint32_t expected)
{
	for (uint32_t i = 0U; i < CLOCK_WAIT_ITERATIONS; ++i) {
		if ((sys_read32(CLKSTATUS) & mask) == expected) {
			return 0;
		}
	}
	return -ETIMEDOUT;
}

static __ramfunc void configure_flash_wait_states(void)
{
	uint32_t interface_control = sys_read32(FRI_INTF_CTRL);
	uint32_t flash_control;

	sys_write32(interface_control & ~FRI_CACHE_MASK, FRI_INTF_CTRL);
	flash_control = sys_read32(FRI_FRDCNTL) & ~FRI_WS0_MODE;
	sys_write32(flash_control, FRI_FRDCNTL);
	__DSB();
	__ISB();
	flash_control = (flash_control & ~FRI_RWAIT_MASK) | (3U << 8);
	sys_write32(flash_control, FRI_FRDCNTL);
	sys_write32(interface_control | FRI_CACHE_MASK, FRI_INTF_CTRL);
}

static void delay_cycles(uint32_t cycles)
{
	for (volatile uint32_t i = 0U; i < cycles; ++i) {
		__asm__ volatile("nop");
	}
}

static int am13e230_clock_init(void)
{
	uint32_t value;
	int ret;

	configure_flash_wait_states();

	/* The LP-AM13E230 has a 25 MHz crystal on the dedicated X1/X2 pins. */
	sys_write32(0U, IOMUX_BASE + XTAL_PIN_X1_OFFSET);
	sys_write32(0U, IOMUX_BASE + XTAL_PIN_X2_OFFSET);

	/* Start and monitor the crystal before using it as the PLL reference. */
	sys_write32(sys_read32(XTALCR) | 1U, XTALCR);
	sys_write32((sys_read32(HFCLKCLKCFG) & ~0xFFU) | 0xFFU | HFCLK_MONITOR, HFCLKCLKCFG);
	sys_write32(sys_read32(HSCLKEN) & ~(1U << 16), HSCLKEN);
	sys_write32(sys_read32(XTALCR) & ~1U, XTALCR);
	ret = wait_for_status(STATUS_HFCLK_GOOD, STATUS_HFCLK_GOOD);
	if (ret != 0) {
		return ret;
	}

	/* Configure the retained PLL registers to the SDK's 200 MHz profile. */
	sys_write32(sys_read32(HSCLKEN) & ~HSCLKEN_PLL_ENABLE, HSCLKEN);
	ret = wait_for_status(STATUS_PLL_OFF, STATUS_PLL_OFF);
	if (ret != 0) {
		return ret;
	}
	sys_write32(PLL_CLK_OUTPUTS | PLL_REF_HFCLK, SYSPLLCFG0);
	sys_write32(PLL_QDIV_32 | PLL_PDIV_2, SYSPLLCFG1);
	sys_write32(sys_read32(PLL_PARAMS), SYSPLLPARAM0);
	sys_write32(sys_read32(PLL_PARAMS + sizeof(uint32_t)), SYSPLLPARAM1);
	sys_write32(sys_read32(HSCLKEN) | HSCLKEN_PLL_ENABLE, HSCLKEN);
	ret = wait_for_status(STATUS_PLL_GOOD, STATUS_PLL_GOOD);
	if (ret != 0) {
		return ret;
	}

	/* TI's generated sequence enters through /4, then /2, then bypass. */
	value = sys_read32(GENCLKEN) & ~EXT_MCLK_DIV_MASK;
	sys_write32(value | EXT_MCLK_DIV_ENABLE | EXT_MCLK_DIV_4, GENCLKEN);
	sys_write32(0U, HSCLKCFG);
	ret = wait_for_status(STATUS_HSCLK_GOOD, STATUS_HSCLK_GOOD);
	if (ret != 0) {
		return ret;
	}
	sys_write32(sys_read32(MCLKCFG) | MCLK_USE_HSCLK, MCLKCFG);
	delay_cycles(20U);
	ret = wait_for_status(STATUS_MCLK_HSCLK, STATUS_MCLK_HSCLK);
	if (ret != 0) {
		return ret;
	}

	sys_write32((sys_read32(GENCLKEN) & ~EXT_MCLK_DIV_MASK) | EXT_MCLK_DIV_ENABLE, GENCLKEN);
	delay_cycles(20U);
	sys_write32(sys_read32(GENCLKEN) & ~EXT_MCLK_DIV_ENABLE, GENCLKEN);
	delay_cycles(20U);

	value = sys_read32(MCLKCFG) & ~MCLK_DIV_MASK;
	sys_write32(value | MCLK_DIV_2_DIV_4, MCLKCFG);
	return 0;
}

SYS_INIT(am13e230_clock_init, PRE_KERNEL_1, 0);
