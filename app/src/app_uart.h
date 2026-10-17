/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_UART_H_
#define APP_UART_H_

#include <stdint.h>

#include "app_clock.h"
#include "app_npu.h"
#include "app_protocol.h"
#include "app_watchdog.h"

#define APP_UART_RX_TIMEOUT_MS 1000U

struct app_uart_request {
	enum app_uart_frame_type type;
	uint16_t sequence;
};

int app_uart_init(void);
int app_uart_receive_request(int8_t *buffer, uint32_t size, struct app_uart_request *request);
void app_uart_send_error(uint16_t sequence, enum app_uart_error_code code, int error);
int app_uart_send_result(uint16_t sequence, const int8_t *result, uint32_t size,
			 const struct app_npu_metrics *metrics);
int app_uart_send_clock_status(uint16_t sequence, const struct app_clock_status *status);
int app_uart_send_watchdog_status(uint16_t sequence, const struct app_watchdog_status *status);

#endif /* APP_UART_H_ */
