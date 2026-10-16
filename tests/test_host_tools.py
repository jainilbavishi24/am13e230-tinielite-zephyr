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

    def test_packet_shape_and_checksum(self):
        vector = SEND_TENSOR.parse_vectors(SEND_TENSOR.MODEL_DIR)[0]
        packet = SEND_TENSOR.make_packet(
            vector["input"], SEND_TENSOR.parse_normalization(SEND_TENSOR.MODEL_DIR)
        )
        self.assertEqual(259, len(packet))
        self.assertEqual(bytes((0x5A, 0xA5)), packet[:2])
        self.assertEqual(sum(packet[2:-1]) & 0xFF, packet[-1])


if __name__ == "__main__":
    unittest.main()
