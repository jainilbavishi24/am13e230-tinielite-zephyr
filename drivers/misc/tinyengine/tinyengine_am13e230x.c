/* SPDX-License-Identifier: Apache-2.0 */

#define DT_DRV_COMPAT ti_am13e230x_tinyengine

#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/sys_io.h>

LOG_MODULE_REGISTER(tinyengine_am13e230x, CONFIG_TINYENGINE_LOG_LEVEL);

#define SYSCTL_PWREN_KEY      0x26000000U
#define SYSCTL_RESET_KEY      0xB1000000U
#define TINIE_PERIPHERAL_MASK BIT(0)
#define GSC_TINIE_PRIV_MASK   BIT(0)

#define TINIE_CTL5_OFFSET     0x1120U
#define TINIE_INSTMEM_OFFSET  0x2000U
#define TINIE_PARAMMEM_OFFSET 0x2800U
#define TINIE_INSTMEM_WORDS   256U
#define TINIE_PARAMMEM_WORDS  512U

#define TINIE_BASE         DT_INST_REG_ADDR_BY_NAME(0, npu)
#define TINIE_PWREN        DT_INST_REG_ADDR_BY_NAME(0, pwren)
#define TINIE_RESET_ASSERT DT_INST_REG_ADDR_BY_NAME(0, reset_assert)
#define TINIE_RESET_CLEAR  DT_INST_REG_ADDR_BY_NAME(0, reset_clear)
#define TINIE_GSC_PRIV     DT_INST_REG_ADDR_BY_NAME(0, gsc_priv)

static int tinyengine_am13e230x_init(const struct device *dev)
{
	ARG_UNUSED(dev);

	/* Match the sequence in TI AM13E2x SDK DL_TINIELITE_init(). */
	sys_write32(SYSCTL_RESET_KEY | TINIE_PERIPHERAL_MASK, TINIE_RESET_CLEAR);
	sys_write32(SYSCTL_RESET_KEY | TINIE_PERIPHERAL_MASK, TINIE_RESET_ASSERT);
	sys_write32(sys_read32(TINIE_PWREN) | SYSCTL_PWREN_KEY | TINIE_PERIPHERAL_MASK,
		    TINIE_PWREN);
	k_busy_wait(100U);
	sys_write32(sys_read32(TINIE_GSC_PRIV) | GSC_TINIE_PRIV_MASK, TINIE_GSC_PRIV);

	LOG_INF("TINIElite initialized for polled completion");
	return 0;
}

DEVICE_DT_INST_DEFINE(0, tinyengine_am13e230x_init, NULL, NULL, NULL, POST_KERNEL,
		      CONFIG_KERNEL_INIT_PRIORITY_DEVICE, NULL);

/* ABI expected by TI's generated model archive. */
uint32_t NPU_getCtlReg(void)
{
	return (uint32_t)(TINIE_BASE + TINIE_CTL5_OFFSET);
}

static void copy_words(uintptr_t destination, uint32_t capacity_words, uint32_t byte_offset,
		       uint32_t num_words, const uint32_t *source)
{
	uint32_t first_word;

	if ((source == NULL) || ((byte_offset % sizeof(uint32_t)) != 0U)) {
		LOG_ERR("invalid NPU memory write");
		return;
	}

	first_word = byte_offset / sizeof(uint32_t);
	if ((num_words == 0U) || (first_word > capacity_words) ||
	    (num_words > (capacity_words - first_word))) {
		LOG_ERR("NPU memory write outside hardware bounds");
		return;
	}

	for (uint32_t i = 0U; i < num_words; ++i) {
		sys_write32(source[i], destination + byte_offset + (i * sizeof(uint32_t)));
	}
}

void NPU_setInstrMem(uint32_t byte_offset, uint32_t num_words, const uint32_t *source)
{
	copy_words(TINIE_BASE + TINIE_INSTMEM_OFFSET, TINIE_INSTMEM_WORDS, byte_offset, num_words,
		   source);
}

void NPU_setParamMem(uint32_t byte_offset, uint32_t num_words, const uint32_t *source)
{
	copy_words(TINIE_BASE + TINIE_PARAMMEM_OFFSET, TINIE_PARAMMEM_WORDS, byte_offset, num_words,
		   source);
}
