/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_NPU_H_
#define APP_NPU_H_

#include <stdint.h>

struct app_npu_metrics {
	uint32_t accelerator_us;
	uint32_t runtime_us;
	uint32_t total_us;
	uint32_t npu_interrupts;
	uint32_t npu_spurious_interrupts;
};

int app_npu_init(void);
int app_npu_run_inference(void *input, void *output, struct app_npu_metrics *metrics);
int app_npu_test_stall_timeout(void);

#endif /* APP_NPU_H_ */
