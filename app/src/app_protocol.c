/* SPDX-License-Identifier: Apache-2.0 */

#include "app_protocol.h"

#include <limits.h>
#include <stddef.h>

#define FRAME_HEADER_SIZE 8U

static uint32_t crc32_update(uint32_t crc, uint8_t value)
{
	crc ^= value;
	for (uint32_t bit = 0U; bit < 8U; ++bit) {
		crc = (crc >> 1) ^ ((crc & 1U) != 0U ? 0xEDB88320U : 0U);
	}
	return crc;
}

uint32_t app_protocol_frame_crc32(const uint8_t *header, const uint8_t *payload, uint16_t length)
{
	uint32_t crc = UINT32_MAX;

	for (uint32_t i = 2U; i < FRAME_HEADER_SIZE; ++i) {
		crc = crc32_update(crc, header[i]);
	}
	for (uint32_t i = 0U; i < length; ++i) {
		crc = crc32_update(crc, payload[i]);
	}
	return ~crc;
}

enum app_uart_error_code app_protocol_validate_request(uint8_t version, uint8_t type,
						       uint16_t length, uint16_t input_size,
						       bool allow_npu_fault,
						       bool allow_watchdog_fault)
{
	if (version != APP_UART_PROTOCOL_VERSION) {
		return APP_UART_ERROR_VERSION;
	}

	switch (type) {
	case APP_UART_FRAME_INFER_REQUEST:
		return length == input_size ? APP_UART_ERROR_NONE : APP_UART_ERROR_LENGTH;
	case APP_UART_FRAME_CLOCK_REQUEST:
	case APP_UART_FRAME_WATCHDOG_STATUS_REQUEST:
		return length == 0U ? APP_UART_ERROR_NONE : APP_UART_ERROR_LENGTH;
	case APP_UART_FRAME_NPU_STALL_REQUEST:
		if (!allow_npu_fault) {
			return APP_UART_ERROR_TYPE;
		}
		return length == 0U ? APP_UART_ERROR_NONE : APP_UART_ERROR_LENGTH;
	case APP_UART_FRAME_WATCHDOG_STALL_REQUEST:
		if (!allow_watchdog_fault) {
			return APP_UART_ERROR_TYPE;
		}
		return length == 0U ? APP_UART_ERROR_NONE : APP_UART_ERROR_LENGTH;
	default:
		return APP_UART_ERROR_TYPE;
	}
}
