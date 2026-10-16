/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_NPU_H_
#define APP_NPU_H_

#include <stdint.h>

#define APP_NPU_INPUT_SIZE  256U
#define APP_NPU_OUTPUT_SIZE 3U

struct app_npu_metrics {
	uint32_t accelerator_us;
	uint32_t runtime_us;
	uint32_t total_us;
};

int app_npu_init(void);
int app_npu_run_inference(int8_t *input, int8_t *output, struct app_npu_metrics *metrics);

#endif /* APP_NPU_H_ */
