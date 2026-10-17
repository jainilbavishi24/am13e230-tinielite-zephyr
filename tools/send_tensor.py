#!/usr/bin/env python3
"""Run golden-vector and stress inference against the AM13E230 firmware."""

from __future__ import annotations

import argparse
import binascii
from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import re
import struct
import sys
import time
from typing import Any

BAUD_RATE = 115200
CLASS_NAMES = ("Sawtooth", "Sine", "Square")
INPUT_SIZE = 256
OUTPUT_SIZE = 3
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "waveform_classifier"

FRAME_MAGIC = b"\x5a\xa5"
PROTOCOL_VERSION = 2
FRAME_INFER_REQUEST = 0x01
FRAME_CLOCK_REQUEST = 0x02
FRAME_NPU_STALL_REQUEST = 0x03
FRAME_READY = 0x80
FRAME_ACK = 0x81
FRAME_RESULT = 0x82
FRAME_CLOCK_STATUS = 0x83
FRAME_ERROR = 0xFF
FRAME_HEADER = struct.Struct("<2sBBHH")
FRAME_CRC = struct.Struct("<I")
RESULT_PAYLOAD = struct.Struct("<bbbIIIII")
ERROR_PAYLOAD = struct.Struct("<Bh")
CAPABILITIES_PAYLOAD = struct.Struct("<HH")
CLOCK_STATUS_PAYLOAD = struct.Struct("<12I")
MAX_FRAME_PAYLOAD = 1024
CLOCK_VALIDATION_REQUIRED = 0x1F
ZEPHYR_ETIMEDOUT = 116

ERROR_NAMES = {
    1: "timeout",
    2: "unsupported-version",
    3: "unsupported-type",
    4: "invalid-length",
    5: "crc-mismatch",
    6: "inference-failure",
    7: "internal-error",
}


class ProtocolError(RuntimeError):
    """Raised when a received frame violates the wire protocol."""


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


def make_payload(values: list[float], normalization: tuple[float, float, int]) -> bytes:
    if len(values) != INPUT_SIZE:
        raise ValueError(f"Expected {INPUT_SIZE} input values, got {len(values)}")
    return bytes(quantize(item, *normalization) & 0xFF for item in values)


def encode_frame(frame_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if not 0 <= sequence <= 0xFFFF:
        raise ValueError("Sequence must fit in uint16")
    if len(payload) > MAX_FRAME_PAYLOAD:
        raise ValueError("Frame payload is too large")
    header = FRAME_HEADER.pack(
        FRAME_MAGIC, PROTOCOL_VERSION, frame_type, sequence, len(payload)
    )
    crc = binascii.crc32(header[2:] + payload) & 0xFFFFFFFF
    return header + payload + FRAME_CRC.pack(crc)


def decode_frame(data: bytes) -> dict[str, Any]:
    minimum_size = FRAME_HEADER.size + FRAME_CRC.size
    if len(data) < minimum_size:
        raise ProtocolError("truncated frame")
    magic, version, frame_type, sequence, length = FRAME_HEADER.unpack_from(data)
    expected_size = FRAME_HEADER.size + length + FRAME_CRC.size
    if magic != FRAME_MAGIC:
        raise ProtocolError("invalid frame magic")
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    if length > MAX_FRAME_PAYLOAD:
        raise ProtocolError(f"payload length {length} exceeds protocol maximum")
    if len(data) != expected_size:
        raise ProtocolError(f"frame length is {len(data)}, expected {expected_size}")
    payload = data[FRAME_HEADER.size : FRAME_HEADER.size + length]
    received_crc = FRAME_CRC.unpack_from(data, FRAME_HEADER.size + length)[0]
    expected_crc = binascii.crc32(data[2 : FRAME_HEADER.size] + payload) & 0xFFFFFFFF
    if received_crc != expected_crc:
        raise ProtocolError(
            f"CRC mismatch: received 0x{received_crc:08x}, expected 0x{expected_crc:08x}"
        )
    return {"type": frame_type, "sequence": sequence, "payload": payload}


class FrameReader:
    """Read CRC-checked frames while discarding boot text and line noise."""

    def __init__(self, serial_port: Any):
        self.serial_port = serial_port

    def _read_exact(self, size: int, deadline: float) -> bytes:
        data = bytearray()
        while len(data) < size and time.monotonic() < deadline:
            chunk = self.serial_port.read(size - len(data))
            if chunk:
                data.extend(chunk)
        if len(data) != size:
            raise TimeoutError(f"received {len(data)} of {size} expected bytes")
        return bytes(data)

    def read_frame(self, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        first_magic_seen = False
        while time.monotonic() < deadline:
            byte = self._read_exact(1, deadline)[0]
            if first_magic_seen and byte == FRAME_MAGIC[1]:
                header_tail = self._read_exact(FRAME_HEADER.size - 2, deadline)
                header = FRAME_MAGIC + header_tail
                _, _, _, _, length = FRAME_HEADER.unpack(header)
                if length > MAX_FRAME_PAYLOAD:
                    raise ProtocolError(f"payload length {length} exceeds protocol maximum")
                body = self._read_exact(length + FRAME_CRC.size, deadline)
                return decode_frame(header + body)
            first_magic_seen = byte == FRAME_MAGIC[0]
        raise TimeoutError("timed out waiting for a framed response")


def wait_for_frame(
    reader: FrameReader,
    accepted_types: set[int],
    timeout: float,
    sequence: int | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = reader.read_frame(max(0.001, deadline - time.monotonic()))
        if frame["type"] not in accepted_types:
            continue
        if sequence is not None and frame["sequence"] != sequence:
            continue
        return frame
    raise TimeoutError("timed out waiting for the expected response frame")


def describe_error(frame: dict[str, Any]) -> str:
    payload = frame["payload"]
    if len(payload) != ERROR_PAYLOAD.size:
        return f"malformed error payload ({len(payload)} bytes)"
    code, detail = ERROR_PAYLOAD.unpack(payload)
    return f"{ERROR_NAMES.get(code, f'unknown-{code}')} (detail {detail})"


def validate_ready(frame: dict[str, Any]) -> None:
    if len(frame["payload"]) != CAPABILITIES_PAYLOAD.size:
        raise ProtocolError("READY frame has a malformed capability payload")
    input_size, output_size = CAPABILITIES_PAYLOAD.unpack(frame["payload"])
    if (input_size, output_size) != (INPUT_SIZE, OUTPUT_SIZE):
        raise ProtocolError(
            f"firmware model shape is {input_size}x{output_size}, expected "
            f"{INPUT_SIZE}x{OUTPUT_SIZE}"
        )


def decode_result(payload: bytes) -> dict[str, Any]:
    if len(payload) != RESULT_PAYLOAD.size:
        raise ProtocolError("RESULT frame has a malformed payload")
    (
        score_0,
        score_1,
        score_2,
        accelerator_us,
        runtime_us,
        total_us,
        npu_interrupts,
        npu_spurious_interrupts,
    ) = RESULT_PAYLOAD.unpack(payload)
    if npu_interrupts == 0:
        raise ProtocolError("RESULT reports no TINIElite completion interrupt")
    if npu_spurious_interrupts != 0:
        raise ProtocolError(
            f"RESULT reports {npu_spurious_interrupts} spurious TINIElite interrupt(s)"
        )
    return {
        "scores": [score_0, score_1, score_2],
        "accelerator_us": accelerator_us,
        "runtime_us": runtime_us,
        "total_us": total_us,
        "npu_interrupts": npu_interrupts,
        "npu_spurious_interrupts": npu_spurious_interrupts,
    }


def run_vector(
    serial_port: Any,
    reader: FrameReader,
    vector: dict[str, Any],
    vector_index: int,
    sequence: int,
    normalization: tuple[float, float, int],
    ready_timeout: float,
    retries: int,
    quiet: bool,
) -> dict[str, Any]:
    request = encode_frame(FRAME_INFER_REQUEST, sequence, make_payload(vector["input"], normalization))
    last_error = "no response"

    for attempt in range(retries + 1):
        try:
            ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
            validate_ready(ready)
            serial_port.write(request)
            serial_port.flush()

            acknowledgement = wait_for_frame(
                reader, {FRAME_ACK, FRAME_ERROR}, 3.0, sequence=sequence
            )
            if acknowledgement["type"] == FRAME_ERROR:
                raise ProtocolError(describe_error(acknowledgement))

            response = wait_for_frame(
                reader, {FRAME_RESULT, FRAME_ERROR}, 15.0, sequence=sequence
            )
            if response["type"] == FRAME_ERROR:
                raise ProtocolError(describe_error(response))
            decoded_result = decode_result(response["payload"])
            scores = decoded_result["scores"]
            accelerator_us = decoded_result["accelerator_us"]
            runtime_us = decoded_result["runtime_us"]
            total_us = decoded_result["total_us"]
            npu_interrupts = decoded_result["npu_interrupts"]
            npu_spurious_interrupts = decoded_result["npu_spurious_interrupts"]
            expected = vector["expected"]
            passed = scores == expected
            result = {
                "sequence": sequence,
                "vector_index": vector_index,
                "class": vector["class"],
                "scores": scores,
                "expected": expected,
                "winner": CLASS_NAMES[scores.index(max(scores))],
                "passed": passed,
                "attempts": attempt + 1,
                "accelerator_us": accelerator_us,
                "runtime_us": runtime_us,
                "total_us": total_us,
                "npu_interrupts": npu_interrupts,
                "npu_spurious_interrupts": npu_spurious_interrupts,
            }
            if not quiet:
                status = "PASS" if passed else "FAIL"
                print(
                    f"[{sequence:05d}] {vector['class']} scores={scores}, "
                    f"expected={expected}, IRQs={npu_interrupts}, total={total_us} us: {status}"
                )
            return result
        except (ProtocolError, TimeoutError) as error:
            last_error = str(error)
            if attempt < retries and not quiet:
                print(f"[{sequence:05d}] transport attempt {attempt + 1} failed: {error}; retrying")

    raise RuntimeError(f"sequence {sequence} failed after {retries + 1} attempts: {last_error}")


def run_crc_fault_test(serial_port: Any, reader: FrameReader, ready_timeout: float) -> None:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready)
    sequence = 0xF00D
    damaged = bytearray(encode_frame(FRAME_INFER_REQUEST, sequence, bytes(INPUT_SIZE)))
    damaged[-1] ^= 0x01
    serial_port.write(damaged)
    serial_port.flush()
    response = wait_for_frame(reader, {FRAME_ERROR}, 3.0, sequence=sequence)
    code, _ = ERROR_PAYLOAD.unpack(response["payload"])
    if code != 5:
        raise ProtocolError(f"fault injection returned {describe_error(response)}, expected crc-mismatch")
    print("CRC fault injection: PASS (corruption rejected and server recovered)")


def run_npu_stall_test(serial_port: Any, reader: FrameReader, ready_timeout: float) -> None:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready)
    sequence = 0xF17E
    serial_port.write(encode_frame(FRAME_NPU_STALL_REQUEST, sequence))
    serial_port.flush()
    acknowledgement = wait_for_frame(
        reader, {FRAME_ACK, FRAME_ERROR}, 3.0, sequence=sequence
    )
    if acknowledgement["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(acknowledgement))
    response = wait_for_frame(reader, {FRAME_ERROR}, 3.0, sequence=sequence)
    if len(response["payload"]) != ERROR_PAYLOAD.size:
        raise ProtocolError("NPU stall test returned a malformed error payload")
    code, detail = ERROR_PAYLOAD.unpack(response["payload"])
    if code != 6 or detail != -ZEPHYR_ETIMEDOUT:
        raise ProtocolError(
            f"NPU stall test returned {describe_error(response)}, expected inference timeout"
        )

    recovered = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(recovered)
    print("NPU stall recovery: PASS (timeout reported, system reset, READY restored)")


def decode_clock_status(payload: bytes) -> dict[str, Any]:
    if len(payload) != CLOCK_STATUS_PAYLOAD.size:
        raise ProtocolError("CLOCK_STATUS frame has a malformed payload")
    values = CLOCK_STATUS_PAYLOAD.unpack(payload)
    names = (
        "expected_mclk_hz",
        "derived_mclk_hz",
        "uart_clock_hz",
        "mclkcfg",
        "hsclken",
        "hsclkcfg",
        "pllcfg0",
        "pllcfg1",
        "genclken",
        "clkstatus",
        "flash_control",
        "validation_flags",
    )
    status = dict(zip(names, values, strict=True))
    status["valid"] = (
        status["validation_flags"] & CLOCK_VALIDATION_REQUIRED
    ) == CLOCK_VALIDATION_REQUIRED
    status["flash_wait_states"] = (
        0
        if status["flash_control"] & 1
        else (status["flash_control"] >> 8) & 0xF
    )
    return status


def request_clock_status(
    serial_port: Any, reader: FrameReader, ready_timeout: float
) -> dict[str, Any]:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready)
    sequence = 1
    serial_port.write(encode_frame(FRAME_CLOCK_REQUEST, sequence))
    serial_port.flush()
    response = wait_for_frame(
        reader, {FRAME_CLOCK_STATUS, FRAME_ERROR}, 3.0, sequence=sequence
    )
    if response["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(response))
    return decode_clock_status(response["payload"])


def print_clock_status(status: dict[str, Any]) -> None:
    verdict = "PASS" if status["valid"] else "FAIL"
    print(f"Clock validation: {verdict}")
    print(
        f"MCLK: derived={status['derived_mclk_hz']} Hz, "
        f"expected={status['expected_mclk_hz']} Hz"
    )
    print(f"UART configured clock: {status['uart_clock_hz']} Hz")
    print(f"Flash wait states: {status['flash_wait_states']}")
    for name in (
        "mclkcfg",
        "hsclken",
        "hsclkcfg",
        "pllcfg0",
        "pllcfg1",
        "genclken",
        "clkstatus",
        "flash_control",
        "validation_flags",
    ):
        print(f"{name}: 0x{status[name]:08x}")


def percentile(values: list[int], percentage: float) -> int:
    if not values:
        raise ValueError("Cannot calculate a percentile of an empty collection")
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentage + 0.5)))
    return ordered[index]


def summarize_metric(results: list[dict[str, Any]], name: str) -> dict[str, float | int]:
    values = [int(item[name]) for item in results]
    return {
        "min": min(values),
        "mean": round(sum(values) / len(values), 3),
        "median": percentile(values, 0.5),
        "p95": percentile(values, 0.95),
        "max": max(values),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--index", type=int, default=0, help="golden vector index (default: 0)")
    selection.add_argument("--all", action="store_true", help="run every bundled golden vector")
    selection.add_argument(
        "--clock-status", action="store_true", help="read and validate clock registers"
    )
    parser.add_argument("--repeat", type=int, default=1, help="repeat the selected set N times")
    parser.add_argument("--retries", type=int, default=2, help="transport retries per inference")
    parser.add_argument("--fault-test", action="store_true", help="verify CRC rejection before inference")
    parser.add_argument(
        "--npu-fault-test",
        action="store_true",
        help="trigger an NPU wait timeout and verify reset recovery",
    )
    parser.add_argument("--quiet", action="store_true", help="print only summary and failures")
    parser.add_argument("--json-output", type=Path, help="write machine-readable results")
    parser.add_argument("--port", default=default_port(), help="UART path")
    parser.add_argument("--ready-timeout", type=float, default=15.0, help="seconds to wait for READY")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vectors = parse_vectors(MODEL_DIR)
    if args.index < 0 or args.index >= len(vectors):
        print(f"error: index must be between 0 and {len(vectors) - 1}", file=sys.stderr)
        return 2
    if args.repeat < 1 or args.retries < 0 or args.ready_timeout <= 0:
        print("error: repeat must be positive, retries nonnegative, and timeout positive", file=sys.stderr)
        return 2

    try:
        import serial
    except ImportError:
        print("error: install dependencies with: python -m pip install -r requirements.txt", file=sys.stderr)
        return 2

    selected = list(enumerate(vectors)) if args.all else [(args.index, vectors[args.index])]
    work = selected * args.repeat
    normalization = parse_normalization(MODEL_DIR)
    results: list[dict[str, Any]] = []

    try:
        with serial.Serial(args.port, BAUD_RATE, timeout=0.05, dsrdtr=False, rtscts=False) as port:
            port.dtr = False
            port.rts = False
            reader = FrameReader(port)
            if args.clock_status:
                status = request_clock_status(port, reader, args.ready_timeout)
                print_clock_status(status)
                if args.json_output:
                    report = {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "protocol_version": PROTOCOL_VERSION,
                        "clock_status": status,
                    }
                    args.json_output.write_text(
                        json.dumps(report, indent=2) + "\n", encoding="utf-8"
                    )
                    print(f"Wrote {args.json_output}")
                return 0 if status["valid"] else 1
            if args.fault_test:
                run_crc_fault_test(port, reader, args.ready_timeout)
            if args.npu_fault_test:
                run_npu_stall_test(port, reader, args.ready_timeout)
            for position, (vector_index, vector) in enumerate(work, start=1):
                sequence = position & 0xFFFF or 1
                results.append(
                    run_vector(
                        port,
                        reader,
                        vector,
                        vector_index,
                        sequence,
                        normalization,
                        args.ready_timeout,
                        args.retries,
                        args.quiet,
                    )
                )
    except (OSError, ProtocolError, RuntimeError, TimeoutError, serial.SerialException) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    failures = sum(not item["passed"] for item in results)
    retries_used = sum(item["attempts"] - 1 for item in results)
    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_version": PROTOCOL_VERSION,
        "total": len(results),
        "passed": len(results) - failures,
        "failed": failures,
        "transport_retries": retries_used,
        "crc_fault_test_passed": args.fault_test,
        "npu_stall_recovery_test_passed": args.npu_fault_test,
        "accelerator_us": summarize_metric(results, "accelerator_us"),
        "runtime_us": summarize_metric(results, "runtime_us"),
        "total_us": summarize_metric(results, "total_us"),
        "npu_interrupts": summarize_metric(results, "npu_interrupts"),
        "npu_spurious_interrupts": summarize_metric(results, "npu_spurious_interrupts"),
    }
    print(f"\nRegression summary: {summary['passed']}/{summary['total']} passed")
    print(f"Transport retries: {retries_used}")
    for name in ("accelerator_us", "runtime_us", "total_us"):
        metric = summary[name]
        print(
            f"{name}: min={metric['min']}, median={metric['median']}, "
            f"p95={metric['p95']}, max={metric['max']} us"
        )
    interrupt_metric = summary["npu_interrupts"]
    print(
        "npu_interrupts: "
        f"min={interrupt_metric['min']}, median={interrupt_metric['median']}, "
        f"p95={interrupt_metric['p95']}, max={interrupt_metric['max']}"
    )
    spurious_metric = summary["npu_spurious_interrupts"]
    spurious_total = sum(item["npu_spurious_interrupts"] for item in results)
    print(
        f"npu_spurious_interrupts: total={spurious_total}, "
        f"max={spurious_metric['max']}"
    )

    if args.json_output:
        report = {"summary": summary, "results": results}
        args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.json_output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
