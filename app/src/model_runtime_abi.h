/* SPDX-License-Identifier: Apache-2.0 */

#ifndef MODEL_RUNTIME_ABI_H_
#define MODEL_RUNTIME_ABI_H_

#include <stdint.h>

/* Private ABI exported by TI's generated model and the TINIElite shim. */
void TI_NPU_NNC_IRQHandler(void);
uint32_t NPU_getCtlReg(void);

#endif /* MODEL_RUNTIME_ABI_H_ */
