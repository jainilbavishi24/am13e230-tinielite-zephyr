/* SPDX-License-Identifier: Apache-2.0 */

#ifndef ZEPHYR_INCLUDE_DRIVERS_TINYENGINE_H_
#define ZEPHYR_INCLUDE_DRIVERS_TINYENGINE_H_

#include <stdint.h>

#include <zephyr/kernel.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Clear stale completion state before starting an inference. */
int tinyengine_prepare_inference(void);

/** Wait for a hardware DONE interrupt. */
int tinyengine_wait_for_completion(k_timeout_t timeout);

/** Return the number of acknowledged hardware DONE interrupts since boot. */
uint32_t tinyengine_completion_count(void);

/** Return the number of unexpected TINIElite interrupt entries since boot. */
uint32_t tinyengine_spurious_count(void);

#ifdef __cplusplus
}
#endif

#endif /* ZEPHYR_INCLUDE_DRIVERS_TINYENGINE_H_ */
