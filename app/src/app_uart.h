/* SPDX-License-Identifier: Apache-2.0 */

#ifndef APP_UART_H_
#define APP_UART_H_

#include <stdint.h>

#define APP_UART_PACKET_MAGIC_0 0x5AU
#define APP_UART_PACKET_MAGIC_1 0xA5U
#define APP_UART_RX_TIMEOUT_MS  1000U

int app_uart_init(void);
int app_uart_receive_tensor(int8_t *buffer, uint32_t size);
void app_uart_send_error(int error);
void app_uart_send_result(const int8_t *result, uint32_t size);

#endif /* APP_UART_H_ */
