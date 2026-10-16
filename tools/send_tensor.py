#!/usr/bin/env python3
"""Send one or all golden tensors to the AM13E230 inference firmware."""

from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
import re
import sys
import time
from typing import Any

BAUD_RATE = 115200
CLASS_NAMES = ("Sawtooth", "Sine", "Square")
INPUT_SIZE = 256
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "waveform_classifier"


def default_port() -> str:
    configured = os.environ.get("TINI_UART_PORT")
    if configured:
        return configured
    candidates = glob.glob("/dev/serial/by-id/*") + glob.glob("/dev/ttyACM*")
    return candidates[0] if candidates else "/dev/ttyACM0"


def parse_normalization(model_dir: Path) -> tuple[float, float, int]:
    source = (model_dir / "artifacts" / "tvmgen_default.h").read_text(encoding="utf-8")

    def value(name: str, number_pattern: str) -> str:
        match = re.search(rf"{name}\[\][^=]+\=\s*\{{({number_pattern})", source)
        if match is None:
            raise ValueError(f"Could not find {name} in generated model header")
        return match.group(1)

    bias = float(value("tvmgen_default_bias_data", r"[-+\d.eE]+"))
    scale = float(value("tvmgen_default_scale_data", r"[-+\d.eE]+"))
    shift = int(value("tvmgen_default_shift_data", r"[-+\d]+"))
    return bias, scale, shift


def parse_vectors(model_dir: Path) -> list[dict[str, Any]]:
    source = (model_dir / "golden_vectors" / "test_vector.c").read_text(encoding="utf-8")
    # Every fixture uses the same C names; most are enclosed in block comments.
    source = source.replace("/*", "").replace("*/", "")
    pattern = re.compile(
        r"//Class:\s*(\w+)[^\n]*Extracted Features\s*\n"
        r"float model_test_input\[256\]\s*=\s*\{([^}]+)\}\s*;\s*\n"
        r"\s*//Class:\s*\w+[^\n]*Expected Model Output\s*\n"
        r"int8_t golden_output\[3\]\s*=\s*\{([^}]+)\}",
        re.DOTALL,
    )

    vectors: list[dict[str, Any]] = []
    for match in pattern.finditer(source):
        inputs = [float(item) for item in match.group(2).split(",") if item.strip()]
        expected = [int(item) for item in match.group(3).split(",") if item.strip()]
        if len(inputs) != INPUT_SIZE or len(expected) != len(CLASS_NAMES):
            raise ValueError("Malformed golden vector")
        vectors.append({"class": match.group(1), "input": inputs, "expected": expected})

    if not vectors:
        raise ValueError("No golden vectors found")
    return vectors


def quantize(value: float, bias: float, scale: float, shift: int) -> int:
    quantized = int((value + bias) * scale) >> shift
    return max(-128, min(127, quantized))


def make_packet(values: list[float], normalization: tuple[float, float, int]) -> bytes:
    if len(values) != INPUT_SIZE:
        raise ValueError(f"Expected {INPUT_SIZE} input values, got {len(values)}")
    payload = bytes(quantize(item, *normalization) & 0xFF for item in values)
    return bytes((0x5A, 0xA5)) + payload + bytes((sum(payload) & 0xFF,))


def read_line_until(serial_port: Any, deadline: float) -> str | None:
    while time.monotonic() < deadline:
        line = serial_port.readline().decode("utf-8", errors="replace").strip()
        if line:
            return line
    return None


def wait_for(serial_port: Any, marker: str, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = read_line_until(serial_port, deadline)
        if line is None:
            break
        if line == marker:
            return True
        if line.startswith("[PROFILER]") or line.startswith("ERROR:"):
            print(f"  board: {line}")
    return False


def run_vector(serial_port: Any, vector: dict[str, Any], index: int, ready_timeout: float) -> bool:
    print(f"[{index}] {vector['class']}: waiting for READY")
    if not wait_for(serial_port, "READY", ready_timeout):
        raise TimeoutError(
            "Board did not send READY. Press the LaunchPad RESET button, verify the XDS110 "
            "UART is attached to WSL, and retry."
        )

    packet = make_packet(vector["input"], parse_normalization(MODEL_DIR))
    serial_port.write(packet)
    serial_port.flush()
    if not wait_for(serial_port, "ACK", 3.0):
        raise TimeoutError("Board did not acknowledge the tensor")

    deadline = time.monotonic() + 15.0
    scores: list[int] | None = None
    while time.monotonic() < deadline:
        line = read_line_until(serial_port, deadline)
        if line is None:
            break
        if line.startswith("[PROFILER]"):
            print(f"  {line}")
        elif line.startswith("ERROR:"):
            raise RuntimeError(f"Board inference failed: {line}")
        elif line.startswith("RESULT:"):
            scores = [int(item.strip()) for item in line.partition(":")[2].split(",")]
            break

    if scores is None or len(scores) != len(CLASS_NAMES):
        raise TimeoutError("Board did not return a valid RESULT")

    expected = vector["expected"]
    passed = scores == expected
    winner = CLASS_NAMES[scores.index(max(scores))]
    print(f"  scores={scores}, expected={expected}, winner={winner}: {'PASS' if passed else 'FAIL'}")
    return passed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--index", type=int, default=0, help="golden vector index (default: 0)")
    selection.add_argument("--all", action="store_true", help="run every bundled golden vector")
    parser.add_argument("--port", default=default_port(), help="UART path")
    parser.add_argument("--ready-timeout", type=float, default=15.0, help="seconds to wait for READY")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vectors = parse_vectors(MODEL_DIR)
    if args.index < 0 or args.index >= len(vectors):
        print(f"error: index must be between 0 and {len(vectors) - 1}", file=sys.stderr)
        return 2

    try:
        import serial
    except ImportError:
        print("error: install dependencies with: python -m pip install -r requirements.txt", file=sys.stderr)
        return 2

    selected = list(enumerate(vectors)) if args.all else [(args.index, vectors[args.index])]
    failures = 0
    try:
        with serial.Serial(args.port, BAUD_RATE, timeout=0.1, dsrdtr=False, rtscts=False) as port:
            port.dtr = False
            port.rts = False
            for index, vector in selected:
                failures += not run_vector(port, vector, index, args.ready_timeout)
    except (OSError, RuntimeError, TimeoutError, serial.SerialException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"\nRegression summary: {len(selected) - failures}/{len(selected)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
