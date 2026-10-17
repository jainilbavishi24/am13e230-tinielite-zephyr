import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("send_tensor", ROOT / "tools" / "send_tensor.py")
assert SPEC is not None and SPEC.loader is not None
SEND_TENSOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEND_TENSOR)


class HostToolTests(unittest.TestCase):
    def test_parses_six_balanced_vectors(self):
        vectors = SEND_TENSOR.parse_vectors(SEND_TENSOR.MODEL_DIR)
        self.assertEqual(6, len(vectors))
        self.assertEqual(["sawtooth", "sawtooth", "sine", "sine", "square", "square"],
                         [item["class"] for item in vectors])
        self.assertTrue(all(len(item["input"]) == 256 for item in vectors))

    def test_normalization_matches_generated_header(self):
        self.assertEqual((-70.02075, 187.0, 6),
                         SEND_TENSOR.parse_normalization(SEND_TENSOR.MODEL_DIR))

    def test_quantization_clamps_and_truncates(self):
        self.assertEqual(-128, SEND_TENSOR.quantize(-1000.0, -70.02075, 187.0, 6))
        self.assertEqual(127, SEND_TENSOR.quantize(1000.0, -70.02075, 187.0, 6))
        self.assertEqual(-3, SEND_TENSOR.quantize(69.0, -70.02075, 187.0, 6))

    def test_versioned_frame_shape_and_crc(self):
        vector = SEND_TENSOR.parse_vectors(SEND_TENSOR.MODEL_DIR)[0]
        payload = SEND_TENSOR.make_payload(
            vector["input"], SEND_TENSOR.parse_normalization(SEND_TENSOR.MODEL_DIR)
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

        expected = SEND_TENSOR.encode_frame(SEND_TENSOR.FRAME_READY, 0, b"\x00\x01\x03\x00")
        reader = SEND_TENSOR.FrameReader(FakeSerial(b"boot log\r\n" + expected))
        frame = reader.read_frame(0.1)
        self.assertEqual(SEND_TENSOR.FRAME_READY, frame["type"])
        self.assertEqual(b"\x00\x01\x03\x00", frame["payload"])

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
        valid = SEND_TENSOR.RESULT_PAYLOAD.pack(1, -1, 0, 500, 100, 650, 4, 0)
        result = SEND_TENSOR.decode_result(valid)
        self.assertEqual([1, -1, 0], result["scores"])
        self.assertEqual(4, result["npu_interrupts"])

        missing_interrupt = SEND_TENSOR.RESULT_PAYLOAD.pack(1, -1, 0, 500, 100, 650, 0, 0)
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "no TINIElite"):
            SEND_TENSOR.decode_result(missing_interrupt)

        spurious_interrupt = SEND_TENSOR.RESULT_PAYLOAD.pack(1, -1, 0, 500, 100, 650, 4, 1)
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "spurious TINIElite"):
            SEND_TENSOR.decode_result(spurious_interrupt)

    def test_result_rejects_malformed_payload(self):
        with self.assertRaisesRegex(SEND_TENSOR.ProtocolError, "malformed"):
            SEND_TENSOR.decode_result(bytes(SEND_TENSOR.RESULT_PAYLOAD.size - 1))

    def test_zephyr_timeout_wire_value_is_explicit(self):
        payload = SEND_TENSOR.ERROR_PAYLOAD.pack(6, -SEND_TENSOR.ZEPHYR_ETIMEDOUT)
        frame = {"payload": payload}
        self.assertEqual(
            "inference-failure (detail -116)", SEND_TENSOR.describe_error(frame)
        )


if __name__ == "__main__":
    unittest.main()
