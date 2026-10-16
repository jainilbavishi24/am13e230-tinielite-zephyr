/* SPDX-License-Identifier: Apache-2.0 */

#include "app_npu.h"
#include "model_runtime_abi.h"

#include <errno.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <tvmgen_default.h>

#define TINYENGINE_NODE      DT_COMPAT_GET_ANY_STATUS_OKAY(ti_am13e230x_tinyengine)
#define NPU_STAGE_TIMEOUT_MS 100U

static const struct device *const npu_dev = DEVICE_DT_GET(TINYENGINE_NODE);

int app_npu_init(void)
{
	return device_is_ready(npu_dev) ? 0 : -ENODEV;
}

int app_npu_run_inference(int8_t *input, int8_t *output, struct app_npu_metrics *metrics)
{
	struct tvmgen_default_inputs inputs = {
		.onnx__Add_0 = input,
	};
	struct tvmgen_default_outputs outputs = {
		.output = output,
	};
	uint32_t total_start;
	uint32_t total_us;
	uint32_t accelerator_us = 0U;
	uint32_t runtime_us = 0U;
	uint32_t runtime_start;
	int32_t run_status;

	if ((input == NULL) || (output == NULL) || (metrics == NULL)) {
		return -EINVAL;
	}

	tvmgen_default_finished = 0;
	total_start = k_cycle_get_32();

	runtime_start = k_cycle_get_32();
	run_status = tvmgen_default_run(&inputs, &outputs);
	runtime_us += k_cyc_to_us_floor32(k_cycle_get_32() - runtime_start);
	if (run_status != 0) {
		return -EIO;
	}

	while (tvmgen_default_finished == 0) {
		uint32_t deadline = k_uptime_get_32();
		uint32_t accelerator_start = k_cycle_get_32();

		while (*(volatile uint32_t *)(uintptr_t)NPU_getCtlReg() != 0U) {
			if ((k_uptime_get_32() - deadline) >= NPU_STAGE_TIMEOUT_MS) {
				return -ETIMEDOUT;
			}
		}
		accelerator_us += k_cyc_to_us_floor32(k_cycle_get_32() - accelerator_start);

		/* Continue the generated runtime after one hardware stage completes. */
		runtime_start = k_cycle_get_32();
		TI_NPU_NNC_IRQHandler();
		runtime_us += k_cyc_to_us_floor32(k_cycle_get_32() - runtime_start);
	}
	total_us = k_cyc_to_us_floor32(k_cycle_get_32() - total_start);

	metrics->accelerator_us = accelerator_us;
	metrics->runtime_us = runtime_us;
	metrics->total_us = total_us;

	return 0;
}
