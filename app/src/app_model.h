/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_MODEL_H_
#define APP_MODEL_H_

#include <stdbool.h>
#include <stdint.h>

#include "app_model_config.h"

enum app_model_dtype {
	APP_MODEL_DTYPE_INT8 = 1,
	APP_MODEL_DTYPE_UINT8 = 2,
	APP_MODEL_DTYPE_INT16 = 3,
	APP_MODEL_DTYPE_FLOAT32 = 4,
};

#define APP_MODEL_CAPABILITY_REQUIRES_NPU 0x0001U

void app_model_reset(void);
int32_t app_model_run(void *input, void *output);
bool app_model_is_finished(void);
void app_model_continue(void);

#endif /* APP_MODEL_H_ */
