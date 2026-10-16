/* SPDX-License-Identifier: Apache-2.0 */

#include <errno.h>
#include <stdint.h>

#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

#include "app_clock.h"
#include "app_npu.h"
#include "app_uart.h"

static int8_t model_input[APP_NPU_INPUT_SIZE] __aligned(16);
static int8_t model_output[APP_NPU_OUTPUT_SIZE] __aligned(16);

int main(void)
{
	struct app_npu_metrics metrics;
	struct app_uart_request request;
	struct app_clock_status clock_status;
	int ret;

	printk("\n*** AM13E230 Zephyr TINIElite demo ***\n");
	printk("Execution mode: polled NPU completion, framed protocol v1\n");

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
		ret = app_uart_receive_request(model_input, sizeof(model_input), &request);
		if (ret != 0) {
			continue;
		}
		if (request.type == APP_UART_FRAME_CLOCK_REQUEST) {
			app_clock_read_status(&clock_status);
			ret = app_uart_send_clock_status(request.sequence, &clock_status);
			if (ret != 0) {
				app_uart_send_error(request.sequence, APP_UART_ERROR_INTERNAL, ret);
			}
			continue;
		}

		ret = app_npu_run_inference(model_input, model_output, &metrics);
		if (ret != 0) {
			app_uart_send_error(request.sequence, APP_UART_ERROR_INFERENCE, ret);
			continue;
		}

		ret = app_uart_send_result(request.sequence, model_output, sizeof(model_output),
					   &metrics);
		if (ret != 0) {
			app_uart_send_error(request.sequence, APP_UART_ERROR_INTERNAL, ret);
		}
	}

	return 0;
}
