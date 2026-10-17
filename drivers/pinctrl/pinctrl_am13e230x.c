/* SPDX-License-Identifier: Apache-2.0 */

#define DT_DRV_COMPAT ti_am13e230x_pinctrl

#include <errno.h>
#include <stdint.h>

#include <zephyr/arch/cpu.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/pinctrl.h>
#include <zephyr/sys/sys_io.h>

#define PINCTRL_NODE DT_NODELABEL(pinctrl)
#define PINCM_STRIDE sizeof(uint32_t)

int pinctrl_configure_pins(const pinctrl_soc_pin_t *pins, uint8_t pin_cnt, uintptr_t reg)
{
	const uintptr_t base = DT_REG_ADDR(PINCTRL_NODE);

	ARG_UNUSED(reg);
	if ((pins == NULL) && (pin_cnt != 0U)) {
		return -EINVAL;
	}

	for (uint8_t i = 0U; i < pin_cnt; ++i) {
		sys_write32(pins[i].configuration, base + (pins[i].pin * PINCM_STRIDE));
	}
	return 0;
}
