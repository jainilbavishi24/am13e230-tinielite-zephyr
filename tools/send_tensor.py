#!/usr/bin/env python3
"""Run model-package regression and fault tests against AM13E230 firmware."""

from __future__ import annotations

import argparse
import binascii
import glob
import json
import math
import os
import re
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
    from .model_package import (
        SUPPORTED_DTYPES,
        ModelPackage,
        ModelPackageError,
        load_model_package,
    )
else:
    from model_package import (
        SUPPORTED_DTYPES,
        ModelPackage,
        ModelPackageError,
        load_model_package,
    )

BAUD_RATE = 115200
REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "models"
DEFAULT_MODEL_NAME = "waveform_classifier"
MODEL_DIR = MODELS_DIR / DEFAULT_MODEL_NAME
MODEL_PACKAGE = load_model_package(MODEL_DIR)

FRAME_MAGIC = b"\x5a\xa5"
PROTOCOL_VERSION = 3
FRAME_INFER_REQUEST = 0x01
FRAME_CLOCK_REQUEST = 0x02
FRAME_NPU_STALL_REQUEST = 0x03
FRAME_WATCHDOG_STALL_REQUEST = 0x04
FRAME_WATCHDOG_STATUS_REQUEST = 0x05
FRAME_READY = 0x80
FRAME_ACK = 0x81
FRAME_RESULT = 0x82
FRAME_CLOCK_STATUS = 0x83
FRAME_WATCHDOG_STATUS = 0x84
FRAME_ERROR = 0xFF
FRAME_HEADER = struct.Struct("<2sBBHH")
FRAME_CRC = struct.Struct("<I")
RESULT_METRICS = struct.Struct("<IIIII")
ERROR_PAYLOAD = struct.Struct("<Bh")
CAPABILITIES_PAYLOAD = struct.Struct("<IHHBBH")
CLOCK_STATUS_PAYLOAD = struct.Struct("<12I")
WATCHDOG_STATUS_PAYLOAD = struct.Struct("<3I")
MAX_FRAME_PAYLOAD = 0xFFFF
CAPABILITY_REQUIRES_NPU = 0x0001
CLOCK_VALIDATION_REQUIRED = 0x1F
ZEPHYR_ETIMEDOUT = 116
WWDT0_RESET_CAUSE = 0x0E

ERROR_NAMES = {
    1: "timeout",
    2: "unsupported-version",
    3: "unsupported-type",
    4: "invalid-length",
    5: "crc-mismatch",
    6: "inference-failure",
    7: "internal-error",
    8: "UART-transport-error",
}


class ProtocolError(RuntimeError):
    """Raised when a received frame violates the wire protocol."""


def default_port() -> str:
    configured = os.environ.get("TINI_UART_PORT")
    if configured:
        return configured

    # XDS110 exposes two CDC ACM interfaces.  The application/User UART is
    # interface 00; the auxiliary port must not be selected merely because its
    # by-id path happens to sort first.
    by_id = sorted(glob.glob("/dev/serial/by-id/*"))
    application_uart = [path for path in by_id if path.endswith("-if00")]
    if application_uart:
        return application_uart[0]
    if os.path.exists("/dev/ttyACM0"):
        return "/dev/ttyACM0"
    candidates = by_id + sorted(glob.glob("/dev/ttyACM*"))
    return candidates[0] if candidates else "/dev/ttyACM0"


def prepare_serial_port(serial_port: Any) -> None:
    """Put XDS110 in a known state before waiting for a fresh READY frame."""

    serial_port.dtr = False
    serial_port.rts = False
    # XDS110 may retain frames produced by the image that was running before a
    # reflash.  Discard them; firmware emits a new READY frame once per second.
    serial_port.reset_input_buffer()


def resolve_model(name: str) -> ModelPackage:
    if not name or not name.replace("_", "").isalnum():
        raise ModelPackageError("--model must use letters, digits, and underscores")
    return load_model_package(MODELS_DIR / name)


def parse_normalization(model: ModelPackage) -> tuple[float, float, int]:
    source = model.header.read_text(encoding="utf-8")
    preprocessing = model.preprocessing

    def value(name: str, number_pattern: str) -> str:
        match = re.search(rf"{re.escape(name)}\[\][^=]+\=\s*\{{({number_pattern})", source)
        if match is None:
            raise ValueError(f"Could not find {name} in generated model header")
        return match.group(1)

    bias = float(value(str(preprocessing["bias_symbol"]), r"[-+\d.eE]+"))
    scale = float(value(str(preprocessing["scale_symbol"]), r"[-+\d.eE]+"))
    shift = int(value(str(preprocessing["shift_symbol"]), r"[-+\d]+"))
    return bias, scale, shift


def prepare_preprocessing(model: ModelPackage) -> tuple[float, float, int] | None:
    """Load any package-specific state needed to encode one input tensor."""

    preprocessing_type = model.preprocessing["type"]
    if preprocessing_type == "ti_affine_shift_header":
        return parse_normalization(model)
    if preprocessing_type == "identity_float32_le":
        return None
    raise ValueError(f"Unsupported preprocessing type {preprocessing_type}")


def parse_vectors(model: ModelPackage) -> list[dict[str, Any]]:
    if model.vector_format == "json_v1":
        vectors = json.loads(model.vector_path.read_text(encoding="utf-8"))
        if not isinstance(vectors, list):
            raise ValueError("JSON golden vectors must be an array")
    elif model.vector_format == "ti_c_arrays_v1":
        source = model.vector_path.read_text(encoding="utf-8")
        source = source.replace("/*", "").replace("*/", "")
        pattern = re.compile(
            rf"//Class:\s*(\w+)[^\n]*Extracted Features\s*\n"
            rf"[^\n]*\b{re.escape(model.input_array)}\[\d+\]\s*=\s*\{{([^}}]+)\}}\s*;\s*\n"
            rf"\s*//Class:\s*[^\n]+?[^\n]*Expected Model Output\s*\n"
            rf"[^\n]*\b{re.escape(model.output_array)}\[\d+\]\s*=\s*\{{([^}}]+)\}}",
            re.DOTALL,
        )
        vectors = []
        for match in pattern.finditer(source):
            inputs = [float(item) for item in match.group(2).split(",") if item.strip()]
            if model.output.dtype == "float32":
                expected: list[int | float] = [
                    float(item) for item in match.group(3).split(",") if item.strip()
                ]
            else:
                expected = [int(item) for item in match.group(3).split(",") if item.strip()]
            vectors.append(
                {
                    "class": match.group(1).strip().split()[0],
                    "input": inputs,
                    "expected": expected,
                }
            )
    else:
        raise ValueError(f"Unsupported vector format {model.vector_format}")

    for vector in vectors:
        if not isinstance(vector, dict):
            raise ValueError("Each golden vector must be an object")
        inputs = vector.get("input")
        expected = vector.get("expected")
        if not isinstance(inputs, list) or len(inputs) != model.input.elements:
            raise ValueError(f"Golden vector input must contain {model.input.elements} values")
        if not isinstance(expected, list) or len(expected) != model.output.elements:
            raise ValueError(f"Golden vector output must contain {model.output.elements} values")
        if not isinstance(vector.get("class"), str):
            raise ValueError("Golden vector class must be a string")

    if not vectors:
        raise ValueError("No golden vectors found")
    return vectors


def quantize(value: float, bias: float, scale: float, shift: int) -> int:
    quantized = int((value + bias) * scale) >> shift
    return max(-128, min(127, quantized))


def make_payload(
    values: list[float],
    model: ModelPackage,
    preprocessing_state: tuple[float, float, int] | None,
) -> bytes:
    if len(values) != model.input.elements:
        raise ValueError(f"Expected {model.input.elements} input values, got {len(values)}")
    preprocessing_type = model.preprocessing["type"]
    if preprocessing_type == "ti_affine_shift_header" and model.input.dtype == "int8":
        if preprocessing_state is None:
            raise ValueError("Affine int8 preprocessing state was not loaded")
        payload = bytes(quantize(item, *preprocessing_state) & 0xFF for item in values)
    elif preprocessing_type == "identity_float32_le" and model.input.dtype == "float32":
        if any(not math.isfinite(item) for item in values):
            raise ValueError("Float32 model input contains a non-finite value")
        payload = struct.pack(f"<{model.input.elements}f", *values)
    else:
        raise ValueError("Selected model preprocessing is not supported by this host client")
    if len(payload) != model.input.size_bytes:
        raise ValueError("Encoded input size does not match model package metadata")
    return payload


def decode_tensor(data: bytes, model: ModelPackage) -> list[int | float]:
    if len(data) != model.output.size_bytes:
        raise ProtocolError(
            f"output tensor has {len(data)} bytes, expected {model.output.size_bytes}"
        )
    format_character = SUPPORTED_DTYPES[model.output.dtype][2]
    values = struct.unpack(f"<{model.output.elements}{format_character}", data)
    return list(values)


def encode_frame(frame_type: int, sequence: int, payload: bytes = b"") -> bytes:
    if not 0 <= sequence <= 0xFFFF:
        raise ValueError("Sequence must fit in uint16")
    if len(payload) > MAX_FRAME_PAYLOAD:
        raise ValueError("Frame payload is too large")
    header = FRAME_HEADER.pack(FRAME_MAGIC, PROTOCOL_VERSION, frame_type, sequence, len(payload))
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
        self.buffer = bytearray()

    def _read_more(self, deadline: float) -> bool:
        if time.monotonic() >= deadline:
            return False
        chunk = self.serial_port.read(256)
        if chunk:
            self.buffer.extend(chunk)
            return True
        return False

    def read_frame(self, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last_protocol_error: ProtocolError | None = None

        while time.monotonic() < deadline:
            magic_index = self.buffer.find(FRAME_MAGIC)
            if magic_index < 0:
                if self.buffer[-1:] == FRAME_MAGIC[:1]:
                    del self.buffer[:-1]
                else:
                    self.buffer.clear()
                self._read_more(deadline)
                continue

            if magic_index > 0:
                del self.buffer[:magic_index]
            if len(self.buffer) < FRAME_HEADER.size:
                self._read_more(deadline)
                continue

            _, _, _, _, length = FRAME_HEADER.unpack_from(self.buffer)
            if length > MAX_FRAME_PAYLOAD:
                last_protocol_error = ProtocolError(
                    f"payload length {length} exceeds protocol maximum"
                )
                del self.buffer[0]
                continue

            frame_size = FRAME_HEADER.size + length + FRAME_CRC.size
            if len(self.buffer) < frame_size:
                self._read_more(deadline)
                continue

            candidate = bytes(self.buffer[:frame_size])
            try:
                frame = decode_frame(candidate)
            except ProtocolError as error:
                last_protocol_error = error
                del self.buffer[0]
                continue

            del self.buffer[:frame_size]
            return frame

        if last_protocol_error is not None:
            raise last_protocol_error
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


def decode_error(payload: bytes) -> tuple[int, int]:
    if len(payload) != ERROR_PAYLOAD.size:
        raise ProtocolError("ERROR frame has a malformed payload")
    return ERROR_PAYLOAD.unpack(payload)


def validate_ready(frame: dict[str, Any], model: ModelPackage) -> dict[str, int]:
    if len(frame["payload"]) != CAPABILITIES_PAYLOAD.size:
        raise ProtocolError("READY frame has a malformed capability payload")
    model_id, input_size, output_size, input_dtype, output_dtype, flags = (
        CAPABILITIES_PAYLOAD.unpack(frame["payload"])
    )
    expected = (
        model.model_id,
        model.input.size_bytes,
        model.output.size_bytes,
        model.input.dtype_code,
        model.output.dtype_code,
        model.capability_flags,
    )
    received = (model_id, input_size, output_size, input_dtype, output_dtype, flags)
    if received != expected:
        raise ProtocolError(
            "firmware model capabilities do not match selected package: "
            f"received id=0x{model_id:08x}, input={input_size}B/dtype{input_dtype}, "
            f"output={output_size}B/dtype{output_dtype}, flags=0x{flags:04x}; "
            f"expected id=0x{model.model_id:08x}, input={model.input.size_bytes}B/"
            f"dtype{model.input.dtype_code}, output={model.output.size_bytes}B/"
            f"dtype{model.output.dtype_code}, flags=0x{model.capability_flags:04x}"
        )
    if not flags & CAPABILITY_REQUIRES_NPU:
        raise ProtocolError("firmware model does not report required NPU capability")
    return {
        "model_id": model_id,
        "input_size": input_size,
        "output_size": output_size,
        "input_dtype": input_dtype,
        "output_dtype": output_dtype,
        "flags": flags,
    }


def decode_result(payload: bytes, model: ModelPackage) -> dict[str, Any]:
    expected_size = model.output.size_bytes + RESULT_METRICS.size
    if len(payload) != expected_size:
        raise ProtocolError(f"RESULT payload has {len(payload)} bytes, expected {expected_size}")
    outputs = decode_tensor(payload[: model.output.size_bytes], model)
    (
        accelerator_us,
        runtime_us,
        total_us,
        npu_interrupts,
        npu_spurious_interrupts,
    ) = RESULT_METRICS.unpack_from(payload, model.output.size_bytes)
    if npu_interrupts == 0:
        raise ProtocolError("RESULT reports no TINIElite completion interrupt")
    if npu_spurious_interrupts != 0:
        raise ProtocolError(
            f"RESULT reports {npu_spurious_interrupts} spurious TINIElite interrupt(s)"
        )
    return {
        "outputs": outputs,
        "scores": outputs,
        "accelerator_us": accelerator_us,
        "runtime_us": runtime_us,
        "total_us": total_us,
        "npu_interrupts": npu_interrupts,
        "npu_spurious_interrupts": npu_spurious_interrupts,
    }


def run_vector(
    serial_port: Any,
    reader: FrameReader,
    model: ModelPackage,
    vector: dict[str, Any],
    vector_index: int,
    sequence: int,
    preprocessing_state: tuple[float, float, int] | None,
    ready_timeout: float,
    retries: int,
    quiet: bool,
) -> dict[str, Any]:
    request = encode_frame(
        FRAME_INFER_REQUEST,
        sequence,
        make_payload(vector["input"], model, preprocessing_state),
    )
    last_error = "no response"

    for attempt in range(retries + 1):
        try:
            ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
            validate_ready(ready, model)
            serial_port.write(request)
            serial_port.flush()

            acknowledgement = wait_for_frame(
                reader, {FRAME_ACK, FRAME_ERROR}, 3.0, sequence=sequence
            )
            if acknowledgement["type"] == FRAME_ERROR:
                raise ProtocolError(describe_error(acknowledgement))

            response = wait_for_frame(reader, {FRAME_RESULT, FRAME_ERROR}, 15.0, sequence=sequence)
            if response["type"] == FRAME_ERROR:
                raise ProtocolError(describe_error(response))
            decoded_result = decode_result(response["payload"], model)
            outputs = decoded_result["outputs"]
            expected = vector["expected"]
            passed = outputs == expected
            winner: str | None = None
            if model.labels and outputs:
                winner = model.labels[outputs.index(max(outputs))]
            result = {
                "sequence": sequence,
                "vector_index": vector_index,
                "class": vector["class"],
                "outputs": outputs,
                "scores": outputs,
                "expected": expected,
                "winner": winner,
                "passed": passed,
                "attempts": attempt + 1,
                "accelerator_us": decoded_result["accelerator_us"],
                "runtime_us": decoded_result["runtime_us"],
                "total_us": decoded_result["total_us"],
                "npu_interrupts": decoded_result["npu_interrupts"],
                "npu_spurious_interrupts": decoded_result["npu_spurious_interrupts"],
            }
            if not quiet:
                status = "PASS" if passed else "FAIL"
                print(
                    f"[{sequence:05d}] {vector['class']} outputs={outputs}, "
                    f"expected={expected}, IRQs={result['npu_interrupts']}, "
                    f"total={result['total_us']} us: {status}"
                )
            return result
        except (ProtocolError, TimeoutError) as error:
            last_error = str(error)
            if attempt < retries and not quiet:
                print(f"[{sequence:05d}] transport attempt {attempt + 1} failed: {error}; retrying")

    raise RuntimeError(f"sequence {sequence} failed after {retries + 1} attempts: {last_error}")


def run_crc_fault_test(
    serial_port: Any, reader: FrameReader, model: ModelPackage, ready_timeout: float
) -> None:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready, model)
    sequence = 0xF00D
    damaged = bytearray(encode_frame(FRAME_INFER_REQUEST, sequence, bytes(model.input.size_bytes)))
    damaged[-1] ^= 0x01
    serial_port.write(damaged)
    serial_port.flush()
    response = wait_for_frame(reader, {FRAME_ERROR}, 3.0, sequence=sequence)
    code, _ = decode_error(response["payload"])
    if code != 5:
        raise ProtocolError(
            f"fault injection returned {describe_error(response)}, expected crc-mismatch"
        )
    print("CRC fault injection: PASS (corruption rejected and server recovered)")


def run_npu_stall_test(
    serial_port: Any, reader: FrameReader, model: ModelPackage, ready_timeout: float
) -> None:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready, model)
    sequence = 0xF17E
    serial_port.write(encode_frame(FRAME_NPU_STALL_REQUEST, sequence))
    serial_port.flush()
    acknowledgement = wait_for_frame(reader, {FRAME_ACK, FRAME_ERROR}, 3.0, sequence=sequence)
    if acknowledgement["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(acknowledgement))
    response = wait_for_frame(reader, {FRAME_ERROR}, 3.0, sequence=sequence)
    code, detail = decode_error(response["payload"])
    if code != 6 or detail != -ZEPHYR_ETIMEDOUT:
        raise ProtocolError(
            f"NPU stall test returned {describe_error(response)}, expected inference timeout"
        )

    recovered = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(recovered, model)
    print("NPU stall recovery: PASS (timeout reported, system reset, READY restored)")


def decode_watchdog_status(payload: bytes) -> dict[str, int | bool]:
    if len(payload) != WATCHDOG_STATUS_PAYLOAD.size:
        raise ProtocolError("WATCHDOG_STATUS frame has a malformed payload")
    reset_cause, timeout_ms, running = WATCHDOG_STATUS_PAYLOAD.unpack(payload)
    if running not in (0, 1):
        raise ProtocolError(f"WATCHDOG_STATUS has invalid running flag {running}")
    return {
        "reset_cause": reset_cause,
        "timeout_ms": timeout_ms,
        "running": running == 1,
    }


def request_watchdog_status(
    serial_port: Any, reader: FrameReader, sequence: int
) -> dict[str, int | bool]:
    serial_port.write(encode_frame(FRAME_WATCHDOG_STATUS_REQUEST, sequence))
    serial_port.flush()
    response = wait_for_frame(reader, {FRAME_WATCHDOG_STATUS, FRAME_ERROR}, 3.0, sequence=sequence)
    if response["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(response))
    return decode_watchdog_status(response["payload"])


def run_watchdog_stall_test(
    serial_port: Any,
    reader: FrameReader,
    model: ModelPackage,
    ready_timeout: float,
) -> dict[str, int | bool]:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready, model)
    sequence = 0xD06D
    serial_port.write(encode_frame(FRAME_WATCHDOG_STALL_REQUEST, sequence))
    serial_port.flush()
    acknowledgement = wait_for_frame(reader, {FRAME_ACK, FRAME_ERROR}, 3.0, sequence=sequence)
    if acknowledgement["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(acknowledgement))

    recovered = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(recovered, model)
    status = request_watchdog_status(serial_port, reader, sequence + 1)
    if status["reset_cause"] != WWDT0_RESET_CAUSE:
        raise ProtocolError(f"reset cause is 0x{status['reset_cause']:02x}, expected WWDT0 (0x0e)")
    if not status["running"]:
        raise ProtocolError("WWDT0 did not restart after watchdog recovery")
    print(
        "Hardware watchdog recovery: PASS "
        f"(WWDT0 reset cause 0x0e, timeout {status['timeout_ms']} ms, watchdog running)"
    )
    return status


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
        0 if status["flash_control"] & 1 else (status["flash_control"] >> 8) & 0xF
    )
    return status


def request_clock_status(
    serial_port: Any,
    reader: FrameReader,
    model: ModelPackage,
    ready_timeout: float,
) -> dict[str, Any]:
    ready = wait_for_frame(reader, {FRAME_READY}, ready_timeout)
    validate_ready(ready, model)
    sequence = 1
    serial_port.write(encode_frame(FRAME_CLOCK_REQUEST, sequence))
    serial_port.flush()
    response = wait_for_frame(reader, {FRAME_CLOCK_STATUS, FRAME_ERROR}, 3.0, sequence=sequence)
    if response["type"] == FRAME_ERROR:
        raise ProtocolError(describe_error(response))
    return decode_clock_status(response["payload"])


def print_clock_status(status: dict[str, Any]) -> None:
    verdict = "PASS" if status["valid"] else "FAIL"
    print(f"Clock validation: {verdict}")
    print(f"MCLK: derived={status['derived_mclk_hz']} Hz, expected={status['expected_mclk_hz']} Hz")
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


def model_report(model: ModelPackage) -> dict[str, Any]:
    return {
        "name": model.name,
        "display_name": model.display_name,
        "id": f"0x{model.model_id:08x}",
        "target_device_family": model.target_device_family,
        "accelerator": model.accelerator,
        "input_shape": model.input.shape,
        "input_dtype": model.input.dtype,
        "input_size_bytes": model.input.size_bytes,
        "output_shape": model.output.shape,
        "output_dtype": model.output.dtype,
        "output_size_bytes": model.output.size_bytes,
        "labels": model.labels,
        "preprocessing": model.preprocessing["type"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--index", type=int, default=0, help="golden vector index")
    selection.add_argument("--all", action="store_true", help="run every golden vector")
    selection.add_argument(
        "--clock-status", action="store_true", help="read and validate clock registers"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("APP_MODEL", DEFAULT_MODEL_NAME),
        help="model package name under models/ (default: waveform_classifier)",
    )
    parser.add_argument("--repeat", type=int, default=1, help="repeat selected vectors N times")
    parser.add_argument("--retries", type=int, default=2, help="transport retries per inference")
    parser.add_argument(
        "--fault-test", action="store_true", help="verify CRC rejection before inference"
    )
    parser.add_argument(
        "--npu-fault-test",
        action="store_true",
        help="trigger an NPU wait timeout and verify reset recovery",
    )
    parser.add_argument(
        "--watchdog-fault-test",
        action="store_true",
        help="stop servicing WWDT0 and verify its reset cause after recovery",
    )
    parser.add_argument("--quiet", action="store_true", help="print only summary and failures")
    parser.add_argument("--json-output", type=Path, help="write machine-readable results")
    parser.add_argument("--port", default=default_port(), help="UART path")
    parser.add_argument(
        "--ready-timeout", type=float, default=15.0, help="seconds to wait for READY"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        model = resolve_model(args.model)
        vectors = parse_vectors(model)
        preprocessing_state = prepare_preprocessing(model)
    except (ModelPackageError, OSError, ValueError) as error:
        print(f"error: invalid model package: {error}", file=sys.stderr)
        return 2

    if args.index < 0 or args.index >= len(vectors):
        print(f"error: index must be between 0 and {len(vectors) - 1}", file=sys.stderr)
        return 2
    if args.repeat < 1 or args.retries < 0 or args.ready_timeout <= 0:
        print(
            "error: repeat must be positive, retries nonnegative, and timeout positive",
            file=sys.stderr,
        )
        return 2

    try:
        import serial
    except ImportError:
        print(
            "error: install dependencies with: python -m pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 2

    selected = list(enumerate(vectors)) if args.all else [(args.index, vectors[args.index])]
    work = selected * args.repeat
    results: list[dict[str, Any]] = []
    watchdog_status: dict[str, int | bool] | None = None

    print(
        f"Model: {model.display_name} (id 0x{model.model_id:08x}, "
        f"input {model.input.size_bytes} B, output {model.output.size_bytes} B)"
    )
    try:
        with serial.Serial(args.port, BAUD_RATE, timeout=0.05, dsrdtr=False, rtscts=False) as port:
            prepare_serial_port(port)
            reader = FrameReader(port)
            if args.clock_status:
                status = request_clock_status(port, reader, model, args.ready_timeout)
                print_clock_status(status)
                if args.json_output:
                    report = {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "protocol_version": PROTOCOL_VERSION,
                        "model": model_report(model),
                        "clock_status": status,
                    }
                    args.json_output.write_text(
                        json.dumps(report, indent=2) + "\n", encoding="utf-8"
                    )
                    print(f"Wrote {args.json_output}")
                return 0 if status["valid"] else 1
            if args.fault_test:
                run_crc_fault_test(port, reader, model, args.ready_timeout)
            if args.npu_fault_test:
                run_npu_stall_test(port, reader, model, args.ready_timeout)
            if args.watchdog_fault_test:
                watchdog_status = run_watchdog_stall_test(port, reader, model, args.ready_timeout)
            for position, (vector_index, vector) in enumerate(work, start=1):
                sequence = position & 0xFFFF or 1
                results.append(
                    run_vector(
                        port,
                        reader,
                        model,
                        vector,
                        vector_index,
                        sequence,
                        preprocessing_state,
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
        "model": model_report(model),
        "total": len(results),
        "passed": len(results) - failures,
        "failed": failures,
        "transport_retries": retries_used,
        "crc_fault_test_passed": args.fault_test,
        "npu_stall_recovery_test_passed": args.npu_fault_test,
        "watchdog_recovery_test_passed": args.watchdog_fault_test,
        "watchdog_status": watchdog_status,
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
    print(f"npu_spurious_interrupts: total={spurious_total}, max={spurious_metric['max']}")

    if args.json_output:
        report = {"summary": summary, "results": results}
        args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.json_output}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
