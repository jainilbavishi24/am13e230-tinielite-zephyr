/* SPDX-License-Identifier: Apache-2.0 */

#include "app_uart.h"

#include <errno.h>
#include <stdbool.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#define UART_NODE DT_CHOSEN(zephyr_console)

static const struct device *const uart_dev = DEVICE_DT_GET(UART_NODE);

static int read_byte(uint8_t *value, uint32_t timeout_ms)
{
	uint32_t start = k_uptime_get_32();

	while (uart_poll_in(uart_dev, value) != 0) {
		if ((k_uptime_get_32() - start) >= timeout_ms) {
			return -ETIMEDOUT;
		}
		k_busy_wait(50);
	}

	return 0;
}

int app_uart_init(void)
{
	return device_is_ready(uart_dev) ? 0 : -ENODEV;
}

int app_uart_receive_tensor(int8_t *buffer, uint32_t size)
{
	uint8_t byte;
	uint8_t checksum = 0U;
	int ret;

	if ((buffer == NULL) || (size == 0U)) {
		return -EINVAL;
	}

	/*
	 * The host transmits only after this marker, so stale bytes are safe to
	 * discard.
	 */
	while (uart_poll_in(uart_dev, &byte) == 0) {
	}

	printk("READY\n");

	ret = read_byte(&byte, APP_UART_RX_TIMEOUT_MS);
	if ((ret != 0) || (byte != APP_UART_PACKET_MAGIC_0)) {
		return (ret != 0) ? ret : -EBADMSG;
	}

	ret = read_byte(&byte, APP_UART_RX_TIMEOUT_MS);
	if ((ret != 0) || (byte != APP_UART_PACKET_MAGIC_1)) {
		printk("NACK_HEADER\n");
		return (ret != 0) ? ret : -EBADMSG;
	}

	for (uint32_t i = 0U; i < size; ++i) {
		ret = read_byte(&byte, APP_UART_RX_TIMEOUT_MS);
		if (ret != 0) {
			printk("NACK_TIMEOUT\n");
			return ret;
		}
		buffer[i] = (int8_t)byte;
		checksum = (uint8_t)(checksum + byte);
	}

	ret = read_byte(&byte, APP_UART_RX_TIMEOUT_MS);
	if (ret != 0) {
		printk("NACK_TIMEOUT\n");
		return ret;
	}

	if (byte != checksum) {
		printk("NACK_CHECKSUM\n");
		return -EBADMSG;
	}

	printk("ACK\n");
	return 0;
}

void app_uart_send_error(int error)
{
	printk("ERROR: %d\n", error);
}

void app_uart_send_result(const int8_t *result, uint32_t size)
{
	if ((result == NULL) || (size != 3U)) {
		app_uart_send_error(-EINVAL);
		return;
	}

	printk("RESULT: %d, %d, %d\n", result[0], result[1], result[2]);
}
