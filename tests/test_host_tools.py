import struct
import unittest
from unittest import mock

from tools import send_tensor as SEND_TENSOR


class HostToolTests(unittest.TestCase):
    def test_default_port_prefers_xds110_application_interface(self):
        paths = [
            "/dev/serial/by-id/usb-Texas_Instruments_XDS110-if03",
            "/dev/serial/by-id/usb-Texas_Instruments_XDS110-if00",
        ]
        with (
            mock.patch.dict(SEND_TENSOR.os.environ, {}, clear=True),
            mock.patch.object(SEND_TENSOR.glob, "glob", side_effect=[paths, []]),
        ):
            self.assertEqual(paths[1], SEND_TENSOR.default_port())

    def test_prepare_serial_port_discards_stale_frames(self):
        class FakeSerial:
            dtr = True
            rts = True

            def __init__(self):
                self.reset_calls = 0

            def reset_input_buffer(self):
                self.reset_calls += 1

        port = FakeSerial()
        SEND_TENSOR.prepare_serial_port(port)
        self.assertFalse(port.dtr)
        self.assertFalse(port.rts)
        self.assertEqual(1, port.reset_calls)

    def test_parses_six_balanced_vectors(self):
        vectors = SEND_TENSOR.parse_vectors(SEND_TENSOR.MODEL_PACKAGE)
        self.assertEqual(6, len(vectors))
        self.assertEqual(
            ["sawtooth", "sawtooth", "sine", "sine", "square", "square"],
            [item["class"] for item in vectors],
        )
        self.assertTrue(all(len(item["input"]) == 256 for item in vectors))

    def test_normalization_matches_generated_header(self):
        self.assertEqual(
            (-70.02075, 187.0, 6),
            SEND_TENSOR.parse_normalization(SEND_TENSOR.MODEL_PACKAGE),
        )

    def test_model_package_describes_default_model(self):
        model = SEND_TENSOR.MODEL_PACKAGE
        self.assertEqual("waveform_classifier", model.name)
        self.assertEqual(0xC7D11096, model.model_id)
        self.assertEqual(256, model.input.size_bytes)
        self.assertEqual(3, model.output.size_bytes)
        self.assertEqual(("Sawtooth", "Sine", "Square"), model.labels)

    def test_quantization_clamps_and_truncates(self):
        self.assertEqual(-128, SEND_TENSOR.quantize(-1000.0, -70.02075, 187.0, 6))
        self.assertEqual(127, SEND_TENSOR.quantize(1000.0, -70.02075, 187.0, 6))
        self.assertEqual(-3, SEND_TENSOR.quantize(69.0, -70.02075, 187.0, 6))

    def test_float32_simple_window_package_and_payload(self):
        model = SEND_TENSOR.resolve_model("electrical_fault_6class")
        vectors = SEND_TENSOR.parse_vectors(model)
        self.assertEqual(12, len(vectors))
        self.assertEqual((1, 6, 128, 1), model.input.shape)
        self.assertEqual("float32", model.input.dtype)
        self.assertEqual(3072, model.input.size_bytes)
        self.assertEqual((1, 6), model.output.shape)
        self.assertEqual("int8", model.output.dtype)
        payload = SEND_TENSOR.make_payload(
            vectors[0]["input"], model, SEND_TENSOR.prepare_preprocessing(model)
        )
        self.assertEqual(3072, len(payload))
        encoded = struct.unpack_from("<3f", payload)
        for expected, actual in zip(vectors[0]["input"][:3], encoded, strict=True):
            self.assertAlmostEqual(expected, actual, places=5)

    def test_versioned_frame_shape_and_crc(self):
        vector = SEND_TENSOR.parse_vectors(SEND_TENSOR.MODEL_PACKAGE)[0]
        payload = SEND_TENSOR.make_payload(
            vector["input"],
            SEND_TENSOR.MODEL_PACKAGE,
            SEND_TENSOR.parse_normalization(SEND_TENSOR.MODEL_PACKAGE),
        )
        packet = SEND_TENSOR.encode_frame(SEND_TENSOR.FRAME_INFER_REQUEST, 42, payload)
        decoded = SEND_TENSOR.decode_frame(packet)
        self.assertEqual(268, len(packet))
        self.assertEqual(SEND_TENSOR.FRAME_MAGIC, packet[:2])
        self.assertEqual(SEND_TENSOR.FRAME_INFER_REQUEST, decoded["type"])
        self.assertEqual(42, decoded["sequence"])
        self.assertEqual(payload, decoded["payload"])

    def test_crc_corruption_is_rejected(self):
        packet = bytearray(SEND_TENSOR.encode_frame(SEND_TENSOR.FRAME_ACK, 7))
        packet[-1] ^= 1
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "CRC mismatch"):
            SEND_TENSOR.decode_frame(bytes(packet))

    def test_frame_reader_resynchronizes_after_boot_text(self):
        class FakeSerial:
            def __init__(self, data):
                self.data = bytearray(data)

            def read(self, size):
                result = self.data[:size]
                del self.data[:size]
                return bytes(result)

        expected_payload = SEND_TENSOR.CAPABILITIES_PAYLOAD.pack(
            SEND_TENSOR.MODEL_PACKAGE.model_id,
            256,
            3,
            1,
            1,
            SEND_TENSOR.CAPABILITY_REQUIRES_NPU,
        )
        expected = SEND_TENSOR.encode_frame(SEND_TENSOR.FRAME_READY, 0, expected_payload)
        reader = SEND_TENSOR.FrameReader(FakeSerial(b"boot log\r\n" + expected))
        frame = reader.read_frame(0.1)
        self.assertEqual(SEND_TENSOR.FRAME_READY, frame["type"])
        self.assertEqual(expected_payload, frame["payload"])

    def test_frame_reader_resynchronizes_after_crc_byte_loss(self):
        class FakeSerial:
            def __init__(self, data):
                self.data = bytearray(data)

            def read(self, size):
                result = self.data[:size]
                del self.data[:size]
                return bytes(result)

        ready_payload = SEND_TENSOR.CAPABILITIES_PAYLOAD.pack(
            SEND_TENSOR.MODEL_PACKAGE.model_id,
            256,
            3,
            1,
            1,
            SEND_TENSOR.CAPABILITY_REQUIRES_NPU,
        )
        ready = SEND_TENSOR.encode_frame(SEND_TENSOR.FRAME_READY, 0, ready_payload)
        # Model a partial frame whose missing CRC byte is replaced by the first
        # magic byte of the following valid frame.
        reader = SEND_TENSOR.FrameReader(FakeSerial(ready[:-1] + ready))
        frame = reader.read_frame(0.1)
        self.assertEqual(SEND_TENSOR.FRAME_READY, frame["type"])
        self.assertEqual(ready_payload, frame["payload"])

    def test_ready_requires_matching_model_package(self):
        payload = SEND_TENSOR.CAPABILITIES_PAYLOAD.pack(
            0xDEADBEEF,
            256,
            3,
            1,
            1,
            SEND_TENSOR.CAPABILITY_REQUIRES_NPU,
        )
        frame = {"payload": payload}
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "do not match"):
            SEND_TENSOR.validate_ready(frame, SEND_TENSOR.MODEL_PACKAGE)

    def test_percentile_is_deterministic(self):
        self.assertEqual(1, SEND_TENSOR.percentile([1], 0.95))
        self.assertEqual(5, SEND_TENSOR.percentile([1, 2, 3, 4, 5], 0.95))

    def test_clock_status_decode_and_validation(self):
        payload = SEND_TENSOR.CLOCK_STATUS_PAYLOAD.pack(
            200_000_000,
            200_000_000,
            32_000_000,
            0x00010000,
            0x00000100,
            0,
            0x31,
            0x1F01,
            0,
            0x00200B10,
            0x00000300,
            SEND_TENSOR.CLOCK_VALIDATION_REQUIRED,
        )
        status = SEND_TENSOR.decode_clock_status(payload)
        self.assertTrue(status["valid"])
        self.assertEqual(3, status["flash_wait_states"])
        self.assertEqual(200_000_000, status["derived_mclk_hz"])

    def test_result_requires_hardware_completion_interrupt(self):
        output = struct.pack("<bbb", 1, -1, 0)
        valid = output + SEND_TENSOR.RESULT_METRICS.pack(500, 100, 650, 4, 0)
        result = SEND_TENSOR.decode_result(valid, SEND_TENSOR.MODEL_PACKAGE)
        self.assertEqual([1, -1, 0], result["scores"])
        self.assertEqual(4, result["npu_interrupts"])

        missing_interrupt = output + SEND_TENSOR.RESULT_METRICS.pack(500, 100, 650, 0, 0)
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "no TINIElite"):
            SEND_TENSOR.decode_result(missing_interrupt, SEND_TENSOR.MODEL_PACKAGE)

        spurious_interrupt = output + SEND_TENSOR.RESULT_METRICS.pack(500, 100, 650, 4, 1)
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "spurious TINIElite"):
            SEND_TENSOR.decode_result(spurious_interrupt, SEND_TENSOR.MODEL_PACKAGE)

    def test_result_rejects_malformed_payload(self):
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "expected"):
            SEND_TENSOR.decode_result(bytes(22), SEND_TENSOR.MODEL_PACKAGE)

    def test_zephyr_timeout_wire_value_is_explicit(self):
        payload = SEND_TENSOR.ERROR_PAYLOAD.pack(6, -SEND_TENSOR.ZEPHYR_ETIMEDOUT)
        frame = {"payload": payload}
        self.assertEqual("inference-failure (detail -116)", SEND_TENSOR.describe_error(frame))

    def test_error_decode_rejects_malformed_payload(self):
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "malformed"):
            SEND_TENSOR.decode_error(bytes(SEND_TENSOR.ERROR_PAYLOAD.size - 1))

    def test_watchdog_status_decode(self):
        payload = SEND_TENSOR.WATCHDOG_STATUS_PAYLOAD.pack(0x0E, 4000, 1)
        status = SEND_TENSOR.decode_watchdog_status(payload)
        self.assertEqual(0x0E, status["reset_cause"])
        self.assertEqual(4000, status["timeout_ms"])
        self.assertTrue(status["running"])

    def test_watchdog_status_rejects_malformed_payload(self):
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "malformed"):
            SEND_TENSOR.decode_watchdog_status(bytes(11))

    def test_watchdog_status_rejects_invalid_running_flag(self):
        payload = SEND_TENSOR.WATCHDOG_STATUS_PAYLOAD.pack(0x0E, 4000, 2)
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "running flag"):
            SEND_TENSOR.decode_watchdog_status(payload)


if __name__ == "__main__":
    unittest.main()
