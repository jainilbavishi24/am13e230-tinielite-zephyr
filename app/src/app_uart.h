/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_UART_H_
#define APP_UART_H_

#include <stdint.h>

#include "app_clock.h"
#include "app_npu.h"

#define APP_UART_FRAME_MAGIC_0    0x5AU
#define APP_UART_FRAME_MAGIC_1    0xA5U
#define APP_UART_PROTOCOL_VERSION 1U
#define APP_UART_RX_TIMEOUT_MS    1000U

enum app_uart_frame_type {
	APP_UART_FRAME_INFER_REQUEST = 0x01,
	APP_UART_FRAME_CLOCK_REQUEST = 0x02,
	APP_UART_FRAME_READY = 0x80,
	APP_UART_FRAME_ACK = 0x81,
	APP_UART_FRAME_RESULT = 0x82,
	APP_UART_FRAME_CLOCK_STATUS = 0x83,
	APP_UART_FRAME_ERROR = 0xFF,
};

struct app_uart_request {
	enum app_uart_frame_type type;
	uint16_t sequence;
};

enum app_uart_error_code {
	APP_UART_ERROR_TIMEOUT = 1,
	APP_UART_ERROR_VERSION = 2,
	APP_UART_ERROR_TYPE = 3,
	APP_UART_ERROR_LENGTH = 4,
	APP_UART_ERROR_CRC = 5,
	APP_UART_ERROR_INFERENCE = 6,
	APP_UART_ERROR_INTERNAL = 7,
};

int app_uart_init(void);
int app_uart_receive_request(int8_t *buffer, uint32_t size, struct app_uart_request *request);
void app_uart_send_error(uint16_t sequence, enum app_uart_error_code code, int error);
int app_uart_send_result(uint16_t sequence, const int8_t *result, uint32_t size,
			 const struct app_npu_metrics *metrics);
int app_uart_send_clock_status(uint16_t sequence, const struct app_clock_status *status);

#endif /* APP_UART_H_ */
