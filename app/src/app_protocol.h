/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_PROTOCOL_H_
#define APP_PROTOCOL_H_

#include <stdbool.h>
#include <stdint.h>

#define APP_UART_FRAME_MAGIC_0    0x5AU
#define APP_UART_FRAME_MAGIC_1    0xA5U
#define APP_UART_PROTOCOL_VERSION 2U

enum app_uart_frame_type {
	APP_UART_FRAME_INFER_REQUEST = 0x01,
	APP_UART_FRAME_CLOCK_REQUEST = 0x02,
	APP_UART_FRAME_NPU_STALL_REQUEST = 0x03,
	APP_UART_FRAME_WATCHDOG_STALL_REQUEST = 0x04,
	APP_UART_FRAME_WATCHDOG_STATUS_REQUEST = 0x05,
	APP_UART_FRAME_READY = 0x80,
	APP_UART_FRAME_ACK = 0x81,
	APP_UART_FRAME_RESULT = 0x82,
	APP_UART_FRAME_CLOCK_STATUS = 0x83,
	APP_UART_FRAME_WATCHDOG_STATUS = 0x84,
	APP_UART_FRAME_ERROR = 0xFF,
};

enum app_uart_error_code {
	APP_UART_ERROR_NONE = 0,
	APP_UART_ERROR_TIMEOUT = 1,
	APP_UART_ERROR_VERSION = 2,
	APP_UART_ERROR_TYPE = 3,
	APP_UART_ERROR_LENGTH = 4,
	APP_UART_ERROR_CRC = 5,
	APP_UART_ERROR_INFERENCE = 6,
	APP_UART_ERROR_INTERNAL = 7,
	APP_UART_ERROR_TRANSPORT = 8,
};

uint32_t app_protocol_frame_crc32(const uint8_t *header, const uint8_t *payload, uint16_t length);

enum app_uart_error_code app_protocol_validate_request(uint8_t version, uint8_t type,
						       uint16_t length, uint16_t input_size,
						       bool allow_npu_fault,
						       bool allow_watchdog_fault);

#endif /* APP_PROTOCOL_H_ */
