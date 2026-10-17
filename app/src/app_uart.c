/* SPDX-License-Identifier: Apache-2.0 */

#include "app_uart.h"

#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <zephyr/device.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/kernel.h>

#define UART_NODE                 DT_CHOSEN(zephyr_console)
#define FRAME_HEADER_SIZE         8U
#define FRAME_CRC_SIZE            4U
#define FRAME_MAX_PAYLOAD_SIZE    APP_NPU_INPUT_SIZE
#define RESULT_PAYLOAD_SIZE       23U
#define CLOCK_STATUS_WORDS        12U
#define CLOCK_STATUS_PAYLOAD_SIZE (CLOCK_STATUS_WORDS * sizeof(uint32_t))

static const struct device *const uart_dev = DEVICE_DT_GET(UART_NODE);

static uint16_t decode_le16(const uint8_t *value)
{
	return (uint16_t)value[0] | ((uint16_t)value[1] << 8);
}

static uint32_t decode_le32(const uint8_t *value)
{
	return (uint32_t)value[0] | ((uint32_t)value[1] << 8) | ((uint32_t)value[2] << 16) |
	       ((uint32_t)value[3] << 24);
}

static void encode_le16(uint8_t *destination, uint16_t value)
{
	destination[0] = (uint8_t)value;
	destination[1] = (uint8_t)(value >> 8);
}

static void encode_le32(uint8_t *destination, uint32_t value)
{
	destination[0] = (uint8_t)value;
	destination[1] = (uint8_t)(value >> 8);
	destination[2] = (uint8_t)(value >> 16);
	destination[3] = (uint8_t)(value >> 24);
}

static uint32_t crc32_update(uint32_t crc, uint8_t value)
{
	crc ^= value;
	for (uint32_t bit = 0U; bit < 8U; ++bit) {
		crc = (crc >> 1) ^ ((crc & 1U) != 0U ? 0xEDB88320U : 0U);
	}
	return crc;
}

static uint32_t frame_crc32(const uint8_t *header, const uint8_t *payload, uint16_t length)
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

static int read_byte_until(uint8_t *value, uint32_t start, uint32_t timeout_ms)
{
	while (uart_poll_in(uart_dev, value) != 0) {
		if ((k_uptime_get_32() - start) >= timeout_ms) {
			return -ETIMEDOUT;
		}
		k_busy_wait(50);
	}
	return 0;
}

static int read_exact(uint8_t *data, uint32_t size, uint32_t start, uint32_t timeout_ms)
{
	for (uint32_t i = 0U; i < size; ++i) {
		int ret = read_byte_until(&data[i], start, timeout_ms);

		if (ret != 0) {
			return ret;
		}
	}
	return 0;
}

static int read_magic(uint32_t start)
{
	bool first_seen = false;
	uint8_t byte;

	for (;;) {
		int ret = read_byte_until(&byte, start, APP_UART_RX_TIMEOUT_MS);

		if (ret != 0) {
			return ret;
		}
		if (first_seen && (byte == APP_UART_FRAME_MAGIC_1)) {
			return 0;
		}
		first_seen = (byte == APP_UART_FRAME_MAGIC_0);
	}
}

static void write_bytes(const uint8_t *data, uint32_t size)
{
	for (uint32_t i = 0U; i < size; ++i) {
		uart_poll_out(uart_dev, data[i]);
	}
}

static int send_frame(enum app_uart_frame_type type, uint16_t sequence, const uint8_t *payload,
		      uint16_t length)
{
	uint8_t header[FRAME_HEADER_SIZE] = {
		APP_UART_FRAME_MAGIC_0,
		APP_UART_FRAME_MAGIC_1,
		APP_UART_PROTOCOL_VERSION,
		(uint8_t)type,
	};
	uint8_t encoded_crc[FRAME_CRC_SIZE];
	uint32_t crc;

	if ((length > FRAME_MAX_PAYLOAD_SIZE) || ((length != 0U) && (payload == NULL))) {
		return -EINVAL;
	}

	encode_le16(&header[4], sequence);
	encode_le16(&header[6], length);
	crc = frame_crc32(header, payload, length);
	encode_le32(encoded_crc, crc);

	write_bytes(header, sizeof(header));
	write_bytes(payload, length);
	write_bytes(encoded_crc, sizeof(encoded_crc));
	return 0;
}

static void send_ready(void)
{
	uint8_t capabilities[4];

	encode_le16(&capabilities[0], APP_NPU_INPUT_SIZE);
	encode_le16(&capabilities[2], APP_NPU_OUTPUT_SIZE);
	(void)send_frame(APP_UART_FRAME_READY, 0U, capabilities, sizeof(capabilities));
}

int app_uart_init(void)
{
	return device_is_ready(uart_dev) ? 0 : -ENODEV;
}

int app_uart_receive_request(int8_t *buffer, uint32_t size, struct app_uart_request *request)
{
	uint8_t header[FRAME_HEADER_SIZE] = {
		APP_UART_FRAME_MAGIC_0,
		APP_UART_FRAME_MAGIC_1,
	};
	uint8_t received_crc[FRAME_CRC_SIZE];
	uint8_t stale_byte;
	uint16_t payload_length;
	uint16_t frame_sequence = 0U;
	uint32_t start;
	int ret;

	if ((buffer == NULL) || (request == NULL) || (size == 0U) ||
	    (size > FRAME_MAX_PAYLOAD_SIZE)) {
		return -EINVAL;
	}

	while (uart_poll_in(uart_dev, &stale_byte) == 0) {
	}
	send_ready();
	start = k_uptime_get_32();

	ret = read_magic(start);
	if (ret != 0) {
		return ret;
	}
	ret = read_exact(&header[2], FRAME_HEADER_SIZE - 2U, start, APP_UART_RX_TIMEOUT_MS);
	if (ret != 0) {
		app_uart_send_error(0U, APP_UART_ERROR_TIMEOUT, ret);
		return ret;
	}

	frame_sequence = decode_le16(&header[4]);
	request->sequence = frame_sequence;
	payload_length = decode_le16(&header[6]);
	if (header[2] != APP_UART_PROTOCOL_VERSION) {
		app_uart_send_error(frame_sequence, APP_UART_ERROR_VERSION, -EPROTO);
		return -EPROTO;
	}
	if ((header[3] != APP_UART_FRAME_INFER_REQUEST) &&
	    (header[3] != APP_UART_FRAME_CLOCK_REQUEST) &&
	    (!IS_ENABLED(CONFIG_APP_NPU_FAULT_INJECTION) ||
	     (header[3] != APP_UART_FRAME_NPU_STALL_REQUEST))) {
		app_uart_send_error(frame_sequence, APP_UART_ERROR_TYPE, -EPROTO);
		return -EPROTO;
	}
	request->type = (enum app_uart_frame_type)header[3];
	if (((request->type == APP_UART_FRAME_INFER_REQUEST) && (payload_length != size)) ||
	    (((request->type == APP_UART_FRAME_CLOCK_REQUEST) ||
	      (request->type == APP_UART_FRAME_NPU_STALL_REQUEST)) &&
	     (payload_length != 0U))) {
		app_uart_send_error(frame_sequence, APP_UART_ERROR_LENGTH, -EMSGSIZE);
		return -EMSGSIZE;
	}

	ret = read_exact((uint8_t *)buffer, payload_length, start, APP_UART_RX_TIMEOUT_MS);
	if (ret == 0) {
		ret = read_exact(received_crc, sizeof(received_crc), start, APP_UART_RX_TIMEOUT_MS);
	}
	if (ret != 0) {
		app_uart_send_error(frame_sequence, APP_UART_ERROR_TIMEOUT, ret);
		return ret;
	}

	if (decode_le32(received_crc) !=
	    frame_crc32(header, (const uint8_t *)buffer, payload_length)) {
		app_uart_send_error(frame_sequence, APP_UART_ERROR_CRC, -EBADMSG);
		return -EBADMSG;
	}

	if ((request->type == APP_UART_FRAME_INFER_REQUEST) ||
	    (request->type == APP_UART_FRAME_NPU_STALL_REQUEST)) {
		return send_frame(APP_UART_FRAME_ACK, frame_sequence, NULL, 0U);
	}
	return 0;
}

void app_uart_send_error(uint16_t sequence, enum app_uart_error_code code, int error)
{
	uint8_t payload[3];
	int16_t detail;

	if (error < INT16_MIN) {
		detail = INT16_MIN;
	} else if (error > INT16_MAX) {
		detail = INT16_MAX;
	} else {
		detail = (int16_t)error;
	}

	payload[0] = (uint8_t)code;
	encode_le16(&payload[1], (uint16_t)detail);
	(void)send_frame(APP_UART_FRAME_ERROR, sequence, payload, sizeof(payload));
}

int app_uart_send_result(uint16_t sequence, const int8_t *result, uint32_t size,
			 const struct app_npu_metrics *metrics)
{
	uint8_t payload[RESULT_PAYLOAD_SIZE];

	if ((result == NULL) || (metrics == NULL) || (size != APP_NPU_OUTPUT_SIZE)) {
		return -EINVAL;
	}

	payload[0] = (uint8_t)result[0];
	payload[1] = (uint8_t)result[1];
	payload[2] = (uint8_t)result[2];
	encode_le32(&payload[3], metrics->accelerator_us);
	encode_le32(&payload[7], metrics->runtime_us);
	encode_le32(&payload[11], metrics->total_us);
	encode_le32(&payload[15], metrics->npu_interrupts);
	encode_le32(&payload[19], metrics->npu_spurious_interrupts);
	return send_frame(APP_UART_FRAME_RESULT, sequence, payload, sizeof(payload));
}

int app_uart_send_clock_status(uint16_t sequence, const struct app_clock_status *status)
{
	uint8_t payload[CLOCK_STATUS_PAYLOAD_SIZE];
	const uint32_t values[CLOCK_STATUS_WORDS] = {
		status != NULL ? status->expected_mclk_hz : 0U,
		status != NULL ? status->derived_mclk_hz : 0U,
		status != NULL ? status->uart_clock_hz : 0U,
		status != NULL ? status->mclkcfg : 0U,
		status != NULL ? status->hsclken : 0U,
		status != NULL ? status->hsclkcfg : 0U,
		status != NULL ? status->pllcfg0 : 0U,
		status != NULL ? status->pllcfg1 : 0U,
		status != NULL ? status->genclken : 0U,
		status != NULL ? status->clkstatus : 0U,
		status != NULL ? status->flash_control : 0U,
		status != NULL ? status->validation_flags : 0U,
	};

	if (status == NULL) {
		return -EINVAL;
	}
	for (uint32_t i = 0U; i < CLOCK_STATUS_WORDS; ++i) {
		encode_le32(&payload[i * sizeof(uint32_t)], values[i]);
	}
	return send_frame(APP_UART_FRAME_CLOCK_STATUS, sequence, payload, sizeof(payload));
}
