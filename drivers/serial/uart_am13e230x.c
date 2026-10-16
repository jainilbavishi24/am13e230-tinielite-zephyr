/* SPDX-License-Identifier: Apache-2.0 */

#define DT_DRV_COMPAT ti_am13e230x_unicomm_uart

#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/sys_io.h>

#define UC_PWREN_OFFSET  0x0800U
#define UC_RSTCTL_OFFSET 0x0804U
#define UC_IPMODE_OFFSET 0x1100U
#define UC_PWREN_ENABLE  0x26000001U
#define UC_RSTCTL_RESET  0xB1000003U
#define UC_IPMODE_UART   0x00000000U

#define UART_CLKDIV_OFFSET 0x0000U
#define UART_CLKSEL_OFFSET 0x0008U
#define UART_CTL0_OFFSET   0x0100U
#define UART_LCRH_OFFSET   0x0104U
#define UART_STAT_OFFSET   0x0108U
#define UART_IBRD_OFFSET   0x0110U
#define UART_FBRD_OFFSET   0x0114U
#define UART_TXDATA_OFFSET 0x0120U
#define UART_RXDATA_OFFSET 0x0124U

#define UART_CLKSEL_BUSCLK 0x00000008U
#define UART_CLKDIV_DIV1   0x00000000U
#define UART_CTL0_ENABLE   BIT(0)
#define UART_CTL0_RXE      BIT(3)
#define UART_CTL0_TXE      BIT(4)
#define UART_CTL0_HSE_MASK 0x00018000U
#define UART_CTL0_HSE_OVS8 0x00008000U
#define UART_CTL0_HSE_OVS3 0x00010000U
#define UART_LCRH_8N1      0x00000030U
#define UART_STAT_RXFE     BIT(2)
#define UART_STAT_TXFF     BIT(6)

struct uart_am13e230x_config {
	uintptr_t uart_base;
	uintptr_t unicomm_base;
	uintptr_t pinmux_base;
	uint32_t clock_freq;
	uint32_t baud_rate;
	uint32_t tx_pincm;
	uint32_t rx_pincm;
};

static void short_delay(void)
{
	for (volatile uint32_t count = 0U; count < 32U; ++count) {
		__asm__ volatile("nop");
	}
}

static void configure_baud(const struct uart_am13e230x_config *config)
{
	uint32_t baud_rate = config->baud_rate;
	uint32_t ctl0 = sys_read32(config->uart_base + UART_CTL0_OFFSET);
	uint32_t divisor;

	ctl0 &= ~UART_CTL0_HSE_MASK;
	if ((baud_rate * 8U) > config->clock_freq) {
		ctl0 |= UART_CTL0_HSE_OVS3;
		divisor = (config->clock_freq * 64U) / (baud_rate * 3U);
	} else if ((baud_rate * 16U) > config->clock_freq) {
		ctl0 |= UART_CTL0_HSE_OVS8;
		baud_rate /= 2U;
		divisor = (((config->clock_freq * 8U) / baud_rate) + 1U) / 2U;
	} else {
		divisor = (((config->clock_freq * 8U) / baud_rate) + 1U) / 2U;
	}

	sys_write32(ctl0, config->uart_base + UART_CTL0_OFFSET);
	sys_write32((divisor >> 6) & 0xFFFFU, config->uart_base + UART_IBRD_OFFSET);
	sys_write32(divisor & 0x3FU, config->uart_base + UART_FBRD_OFFSET);
	/* A write to LCRH latches the new integer/fractional divisors. */
	sys_write32(sys_read32(config->uart_base + UART_LCRH_OFFSET),
		    config->uart_base + UART_LCRH_OFFSET);
}

static int uart_am13e230x_poll_in(const struct device *dev, unsigned char *value)
{
	const struct uart_am13e230x_config *config = dev->config;

	if ((sys_read32(config->uart_base + UART_STAT_OFFSET) & UART_STAT_RXFE) != 0U) {
		return -1;
	}

	*value = (unsigned char)(sys_read32(config->uart_base + UART_RXDATA_OFFSET) & 0xFFU);
	return 0;
}

static void uart_am13e230x_poll_out(const struct device *dev, unsigned char value)
{
	const struct uart_am13e230x_config *config = dev->config;

	while ((sys_read32(config->uart_base + UART_STAT_OFFSET) & UART_STAT_TXFF) != 0U) {
	}

	sys_write32((uint32_t)value, config->uart_base + UART_TXDATA_OFFSET);
}

static int uart_am13e230x_err_check(const struct device *dev)
{
	ARG_UNUSED(dev);
	return 0;
}

static int uart_am13e230x_init(const struct device *dev)
{
	const struct uart_am13e230x_config *config = dev->config;
	uint32_t ctl0;

	/* PA0/PA1 values are board data supplied by devicetree. */
	sys_write32(config->tx_pincm, config->pinmux_base);
	sys_write32(config->rx_pincm, config->pinmux_base + sizeof(uint32_t));

	sys_write32(UC_RSTCTL_RESET, config->unicomm_base + UC_RSTCTL_OFFSET);
	short_delay();
	if ((sys_read32(config->unicomm_base + UC_PWREN_OFFSET) & BIT(0)) == 0U) {
		sys_write32(UC_PWREN_ENABLE, config->unicomm_base + UC_PWREN_OFFSET);
	}
	short_delay();
	sys_write32(UC_IPMODE_UART, config->unicomm_base + UC_IPMODE_OFFSET);
	short_delay();

	ctl0 = sys_read32(config->uart_base + UART_CTL0_OFFSET) & ~UART_CTL0_ENABLE;
	sys_write32(ctl0, config->uart_base + UART_CTL0_OFFSET);
	sys_write32(UART_CTL0_RXE | UART_CTL0_TXE, config->uart_base + UART_CTL0_OFFSET);
	sys_write32(UART_LCRH_8N1, config->uart_base + UART_LCRH_OFFSET);
	sys_write32(UART_CLKSEL_BUSCLK, config->uart_base + UART_CLKSEL_OFFSET);
	sys_write32(UART_CLKDIV_DIV1, config->uart_base + UART_CLKDIV_OFFSET);
	configure_baud(config);

	ctl0 = sys_read32(config->uart_base + UART_CTL0_OFFSET) | UART_CTL0_ENABLE;
	sys_write32(ctl0, config->uart_base + UART_CTL0_OFFSET);
	short_delay();
	return 0;
}

static DEVICE_API(uart, uart_am13e230x_driver_api) = {
	.poll_in = uart_am13e230x_poll_in,
	.poll_out = uart_am13e230x_poll_out,
	.err_check = uart_am13e230x_err_check,
};

#define UART_AM13E230X_INIT(inst)                                                                  \
	static const struct uart_am13e230x_config uart_am13e230x_config_##inst = {                 \
		.uart_base = DT_INST_REG_ADDR_BY_NAME(inst, uart),                                 \
		.unicomm_base = DT_INST_REG_ADDR_BY_NAME(inst, unicomm),                           \
		.pinmux_base = DT_INST_REG_ADDR_BY_NAME(inst, pinmux),                             \
		.clock_freq = DT_PROP(DT_PHANDLE(DT_DRV_INST(inst), clocks), clock_frequency),     \
		.baud_rate = DT_INST_PROP(inst, current_speed),                                    \
		.tx_pincm = DT_INST_PROP(inst, ti_tx_pincm),                                       \
		.rx_pincm = DT_INST_PROP(inst, ti_rx_pincm),                                       \
	};                                                                                         \
	DEVICE_DT_INST_DEFINE(inst, uart_am13e230x_init, NULL, NULL,                               \
			      &uart_am13e230x_config_##inst, PRE_KERNEL_1,                         \
			      CONFIG_SERIAL_INIT_PRIORITY, &uart_am13e230x_driver_api);

DT_INST_FOREACH_STATUS_OKAY(UART_AM13E230X_INIT)
