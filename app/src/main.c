/* SPDX-License-Identifier: Apache-2.0 */

#include <errno.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "app_npu.h"
#include "app_uart.h"

static int8_t model_input[APP_NPU_INPUT_SIZE] __aligned(16);
static int8_t model_output[APP_NPU_OUTPUT_SIZE] __aligned(16);

int main(void)
{
	int ret;

	printk("\n*** AM13E230 Zephyr TINIElite demo ***\n");
	printk("Execution mode: polled NPU completion\n");

	ret = app_uart_init();
	if (ret != 0) {
		printk("FATAL: UART initialization failed (%d)\n", ret);
		return ret;
	}

	ret = app_npu_init();
	if (ret != 0) {
		printk("FATAL: NPU initialization failed (%d)\n", ret);
		return ret;
	}

	for (;;) {
		ret = app_uart_receive_tensor(model_input, sizeof(model_input));
		if (ret != 0) {
			continue;
		}

		ret = app_npu_run_inference(model_input, model_output);
		if (ret != 0) {
			app_uart_send_error(ret);
			continue;
		}

		app_uart_send_result(model_output, sizeof(model_output));
	}

	return 0;
}
