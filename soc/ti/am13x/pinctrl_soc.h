/* SPDX-License-Identifier: Apache-2.0 */

#ifndef ZEPHYR_SOC_TI_AM13X_PINCTRL_SOC_H_
#define ZEPHYR_SOC_TI_AM13X_PINCTRL_SOC_H_

#include <stdint.h>

#include <zephyr/devicetree.h>

#define AM13E230_PINCM_FUNCTION_MASK 0x3FU
#define AM13E230_PINCM_CONNECTED     (1U << 7)
#define AM13E230_PINCM_PULL_DOWN     (1U << 16)
#define AM13E230_PINCM_PULL_UP       (1U << 17)
#define AM13E230_PINCM_INPUT_ENABLE  (1U << 18)

typedef struct pinctrl_soc_pin {
	uint32_t pin;
	uint32_t configuration;
} pinctrl_soc_pin_t;

#define AM13E230_PIN_CONFIGURATION(node_id)                                                        \
	((DT_PROP_BY_IDX(node_id, pinmux, 1) & AM13E230_PINCM_FUNCTION_MASK) |                     \
	 AM13E230_PINCM_CONNECTED |                                                                \
	 (DT_PROP(node_id, bias_pull_down) * AM13E230_PINCM_PULL_DOWN) |                           \
	 (DT_PROP(node_id, bias_pull_up) * AM13E230_PINCM_PULL_UP) |                               \
	 (DT_PROP(node_id, input_enable) * AM13E230_PINCM_INPUT_ENABLE))

#define AM13E230_DT_PIN(node_id)                                                                   \
	{                                                                                          \
		.pin = DT_PROP_BY_IDX(node_id, pinmux, 0),                                         \
		.configuration = AM13E230_PIN_CONFIGURATION(node_id),                              \
	},

#define Z_PINCTRL_STATE_PIN_INIT(node_id, prop, idx)                                               \
	AM13E230_DT_PIN(DT_PROP_BY_IDX(node_id, prop, idx))

#define Z_PINCTRL_STATE_PINS_INIT(node_id, prop)                                                   \
	{                                                                                          \
		DT_FOREACH_PROP_ELEM(node_id, prop, Z_PINCTRL_STATE_PIN_INIT)                      \
	}

#endif /* ZEPHYR_SOC_TI_AM13X_PINCTRL_SOC_H_ */
