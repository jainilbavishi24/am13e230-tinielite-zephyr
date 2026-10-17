/* SPDX-License-Identifier: Apache-2.0 */

#include <stdint.h>

#include <zephyr/ztest.h>

#include "app_protocol.h"

#define INPUT_SIZE 256U

ZTEST(app_protocol, test_crc32_empty_ack)
{
	const uint8_t header[] = {
		APP_UART_FRAME_MAGIC_0,
		APP_UART_FRAME_MAGIC_1,
		APP_UART_PROTOCOL_VERSION,
		APP_UART_FRAME_ACK,
		0x07,
		0x00,
		0x00,
		0x00,
	};

	zassert_equal(app_protocol_frame_crc32(header, NULL, 0U), 0xED5BA133U);
}

ZTEST(app_protocol, test_crc32_inference_payload)
{
	const uint8_t header[] = {
		APP_UART_FRAME_MAGIC_0,
		APP_UART_FRAME_MAGIC_1,
		APP_UART_PROTOCOL_VERSION,
		APP_UART_FRAME_INFER_REQUEST,
		0x2A,
		0x00,
		0x00,
		0x01,
	};
	uint8_t payload[INPUT_SIZE];

	for (uint32_t i = 0U; i < INPUT_SIZE; ++i) {
		payload[i] = (uint8_t)i;
	}
	zassert_equal(app_protocol_frame_crc32(header, payload, sizeof(payload)), 0xC9D6FF2EU);
}

ZTEST(app_protocol, test_valid_requests)
{
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_INFER_REQUEST, INPUT_SIZE,
						    INPUT_SIZE, false, false),
		      APP_UART_ERROR_NONE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_CLOCK_REQUEST, 0U, INPUT_SIZE,
						    false, false),
		      APP_UART_ERROR_NONE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_WATCHDOG_STATUS_REQUEST, 0U,
						    INPUT_SIZE, false, false),
		      APP_UART_ERROR_NONE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_NPU_STALL_REQUEST, 0U,
						    INPUT_SIZE, true, false),
		      APP_UART_ERROR_NONE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_WATCHDOG_STALL_REQUEST, 0U,
						    INPUT_SIZE, false, true),
		      APP_UART_ERROR_NONE);
}

ZTEST(app_protocol, test_rejects_invalid_version_type_and_length)
{
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION + 1U,
						    APP_UART_FRAME_INFER_REQUEST, INPUT_SIZE,
						    INPUT_SIZE, true, true),
		      APP_UART_ERROR_VERSION);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION, 0x7FU, 0U,
						    INPUT_SIZE, true, true),
		      APP_UART_ERROR_TYPE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_INFER_REQUEST, INPUT_SIZE - 1U,
						    INPUT_SIZE, true, true),
		      APP_UART_ERROR_LENGTH);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_CLOCK_REQUEST, 1U, INPUT_SIZE,
						    true, true),
		      APP_UART_ERROR_LENGTH);
}

ZTEST(app_protocol, test_fault_injection_is_explicitly_gated)
{
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_NPU_STALL_REQUEST, 0U,
						    INPUT_SIZE, false, true),
		      APP_UART_ERROR_TYPE);
	zassert_equal(app_protocol_validate_request(APP_UART_PROTOCOL_VERSION,
						    APP_UART_FRAME_WATCHDOG_STALL_REQUEST, 0U,
						    INPUT_SIZE, true, false),
		      APP_UART_ERROR_TYPE);
}

ZTEST_SUITE(app_protocol, NULL, NULL, NULL, NULL, NULL);
