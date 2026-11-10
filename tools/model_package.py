#!/usr/bin/env python3
"""Load and validate AM13E2 build-time model packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SUPPORTED_DTYPES: dict[str, tuple[int, int, str]] = {
    "int8": (1, 1, "b"),
    "uint8": (2, 1, "B"),
    "int16": (3, 2, "h"),
    "float32": (4, 4, "f"),
}
SUPPORTED_PREPROCESSING = {"identity_float32_le", "ti_affine_shift_header"}
SUPPORTED_VECTOR_FORMATS = {"ti_c_arrays_v1", "json_v1"}
MAX_PROTOCOL_PAYLOAD = 0xFFFF
RESULT_METRICS_SIZE = 20
C_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


@dataclass(frozen=True)
class TensorSpec:
    """Tensor shape and wire representation."""

    shape: tuple[int, ...]
    dtype: str
    runtime_field: str

    @property
    def elements(self) -> int:
        return math.prod(self.shape)

    @property
    def size_bytes(self) -> int:
        return self.elements * SUPPORTED_DTYPES[self.dtype][1]

    @property
    def dtype_code(self) -> int:
        return SUPPORTED_DTYPES[self.dtype][0]

    @property
    def struct_format(self) -> str:
        return SUPPORTED_DTYPES[self.dtype][2]


@dataclass(frozen=True)
class ModelPackage:
    """Validated model-package metadata."""

    directory: Path
    name: str
    display_name: str
    model_id: int
    target_device_family: str
    accelerator: str
    requires_npu: bool
    library: Path
    header: Path
    entry_symbol: str
    input_struct: str
    output_struct: str
    completion_symbol: str
    continuation_symbol: str
    input: TensorSpec
    output: TensorSpec
    labels: tuple[str, ...]
    preprocessing: dict[str, Any]
    vector_format: str
    vector_path: Path
    input_array: str
    output_array: str
    io_alignment: int

    @property
    def capability_flags(self) -> int:
        return 1 if self.requires_npu else 0


class ModelPackageError(ValueError):
    """Raised when model-package metadata violates the contract."""


def _required(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise ModelPackageError(f"{context} is missing required field {key!r}")
    return mapping[key]


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelPackageError(f"{context} must be an object")
    return value


def _safe_path(directory: Path, relative: Any, field: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ModelPackageError(f"{field} must be a non-empty relative path")
    path = (directory / relative).resolve()
    try:
        path.relative_to(directory.resolve())
    except ValueError as error:
        raise ModelPackageError(f"{field} escapes the model package") from error
    if not path.is_file():
        raise ModelPackageError(f"{field} does not exist: {path}")
    return path


def _tensor(mapping: dict[str, Any], context: str) -> TensorSpec:
    shape_value = _required(mapping, "shape", context)
    if (
        not isinstance(shape_value, list)
        or not shape_value
        or any(
            not isinstance(item, int) or isinstance(item, bool) or item <= 0 for item in shape_value
        )
    ):
        raise ModelPackageError(f"{context}.shape must contain positive integers")
    dtype = _required(mapping, "dtype", context)
    if dtype not in SUPPORTED_DTYPES:
        raise ModelPackageError(
            f"{context}.dtype must be one of {', '.join(sorted(SUPPORTED_DTYPES))}"
        )
    runtime_field = _required(mapping, "runtime_field", context)
    if not isinstance(runtime_field, str) or C_IDENTIFIER.fullmatch(runtime_field) is None:
        raise ModelPackageError(f"{context}.runtime_field must be a C identifier")
    tensor = TensorSpec(tuple(shape_value), dtype, runtime_field)
    declared_size = _required(mapping, "size_bytes", context)
    if declared_size != tensor.size_bytes:
        raise ModelPackageError(
            f"{context}.size_bytes is {declared_size}, calculated {tensor.size_bytes}"
        )
    if tensor.size_bytes > 0xFFFF:
        raise ModelPackageError(f"{context} is too large for the uint16 protocol length")
    return tensor


def load_model_package(directory: Path) -> ModelPackage:
    """Read and validate one model package."""

    directory = directory.resolve()
    manifest_path = directory / "model.json"
    if not manifest_path.is_file():
        raise ModelPackageError(f"model manifest not found: {manifest_path}")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelPackageError(f"could not read {manifest_path}: {error}") from error
    data = _mapping(data, "manifest")

    if _required(data, "schema_version", "manifest") != 1:
        raise ModelPackageError("only model-package schema_version 1 is supported")

    name = _required(data, "name", "manifest")
    display_name = _required(data, "display_name", "manifest")
    if not isinstance(name, str) or C_IDENTIFIER.fullmatch(name) is None:
        raise ModelPackageError(
            "manifest.name must be a C-style identifier using ASCII letters, digits, and underscores"
        )
    if not isinstance(display_name, str) or not display_name:
        raise ModelPackageError("manifest.display_name must be a non-empty string")

    model_id_value = _required(data, "model_id", "manifest")
    try:
        model_id = (
            int(model_id_value, 0) if isinstance(model_id_value, str) else int(model_id_value)
        )
    except (TypeError, ValueError) as error:
        raise ModelPackageError(
            "manifest.model_id must be an integer or base-prefixed string"
        ) from error
    if not 0 < model_id <= 0xFFFFFFFF:
        raise ModelPackageError("manifest.model_id must fit a nonzero uint32")

    target = _mapping(_required(data, "target", "manifest"), "target")
    device_family = _required(target, "device_family", "target")
    accelerator = _required(target, "accelerator", "target")
    requires_npu = _required(target, "requires_npu", "target")
    if device_family != "AM13E2" or accelerator != "TINIElite" or requires_npu is not True:
        raise ModelPackageError(
            "current firmware requires target AM13E2, accelerator TINIElite, requires_npu=true"
        )

    artifacts = _mapping(_required(data, "artifacts", "manifest"), "artifacts")
    library = _safe_path(
        directory, _required(artifacts, "library", "artifacts"), "artifacts.library"
    )
    archive_digest = hashlib.sha256(library.read_bytes()).digest()
    expected_model_id = int.from_bytes(archive_digest[:4], "big")
    if model_id != expected_model_id:
        raise ModelPackageError(
            f"manifest.model_id is 0x{model_id:08x}, but the first 32 bits of the "
            f"library SHA-256 are 0x{expected_model_id:08x}"
        )
    header = _safe_path(directory, _required(artifacts, "header", "artifacts"), "artifacts.header")
    entry_symbol = _required(artifacts, "entry_symbol", "artifacts")
    if not isinstance(entry_symbol, str) or C_IDENTIFIER.fullmatch(entry_symbol) is None:
        raise ModelPackageError("artifacts.entry_symbol must be a C identifier")

    runtime = _mapping(_required(data, "runtime", "manifest"), "runtime")
    runtime_identifiers: dict[str, str] = {}
    for key in ("input_struct", "output_struct", "completion_symbol", "continuation_symbol"):
        value = _required(runtime, key, "runtime")
        if not isinstance(value, str) or C_IDENTIFIER.fullmatch(value) is None:
            raise ModelPackageError(f"runtime.{key} must be a C identifier")
        runtime_identifiers[key] = value

    try:
        header_source = header.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ModelPackageError(f"could not read generated header {header}: {error}") from error
    for declaration in (
        f"struct {runtime_identifiers['input_struct']}",
        f"struct {runtime_identifiers['output_struct']}",
        entry_symbol,
        runtime_identifiers["completion_symbol"],
    ):
        if declaration not in header_source:
            raise ModelPackageError(
                f"generated header does not declare runtime token {declaration!r}"
            )

    input_spec = _tensor(_mapping(_required(data, "input", "manifest"), "input"), "input")
    output_mapping = _mapping(_required(data, "output", "manifest"), "output")
    output_spec = _tensor(output_mapping, "output")
    if output_spec.size_bytes + RESULT_METRICS_SIZE > MAX_PROTOCOL_PAYLOAD:
        raise ModelPackageError(
            "output tensor plus 20-byte metrics exceeds the uint16 protocol length"
        )
    labels_value = output_mapping.get("labels", [])
    if not isinstance(labels_value, list) or any(
        not isinstance(label, str) or not label for label in labels_value
    ):
        raise ModelPackageError("output.labels must be an array of non-empty strings")
    if labels_value and len(labels_value) != output_spec.elements:
        raise ModelPackageError("output.labels length must equal output element count")

    preprocessing = _mapping(_required(data, "preprocessing", "manifest"), "preprocessing")
    preprocessing_type = _required(preprocessing, "type", "preprocessing")
    if preprocessing_type not in SUPPORTED_PREPROCESSING:
        raise ModelPackageError(f"unsupported preprocessing type {preprocessing_type!r}")
    if preprocessing_type == "ti_affine_shift_header":
        if input_spec.dtype != "int8":
            raise ModelPackageError("ti_affine_shift_header requires int8 input")
        for key in ("bias_symbol", "scale_symbol", "shift_symbol"):
            value = _required(preprocessing, key, "preprocessing")
            if not isinstance(value, str) or C_IDENTIFIER.fullmatch(value) is None:
                raise ModelPackageError(f"preprocessing.{key} must be a C identifier")
    elif preprocessing_type == "identity_float32_le" and input_spec.dtype != "float32":
        raise ModelPackageError("identity_float32_le requires float32 input")

    vectors = _mapping(_required(data, "golden_vectors", "manifest"), "golden_vectors")
    vector_format = _required(vectors, "format", "golden_vectors")
    if vector_format not in SUPPORTED_VECTOR_FORMATS:
        raise ModelPackageError(f"unsupported golden-vector format {vector_format!r}")
    vector_path = _safe_path(
        directory, _required(vectors, "path", "golden_vectors"), "golden_vectors.path"
    )
    input_array = str(vectors.get("input_array", ""))
    output_array = str(vectors.get("output_array", ""))
    if vector_format == "ti_c_arrays_v1" and (not input_array or not output_array):
        raise ModelPackageError(
            "ti_c_arrays_v1 requires golden_vectors.input_array and output_array"
        )

    io_alignment = _required(data, "io_alignment", "manifest")
    if (
        not isinstance(io_alignment, int)
        or isinstance(io_alignment, bool)
        or io_alignment > 256
        or io_alignment & (io_alignment - 1)
    ):
        raise ModelPackageError("io_alignment must be a power of two from 1 to 256")

    return ModelPackage(
        directory=directory,
        name=name,
        display_name=display_name,
        model_id=model_id,
        target_device_family=device_family,
        accelerator=accelerator,
        requires_npu=requires_npu,
        library=library,
        header=header,
        entry_symbol=entry_symbol,
        input_struct=runtime_identifiers["input_struct"],
        output_struct=runtime_identifiers["output_struct"],
        completion_symbol=runtime_identifiers["completion_symbol"],
        continuation_symbol=runtime_identifiers["continuation_symbol"],
        input=input_spec,
        output=output_spec,
        labels=tuple(labels_value),
        preprocessing=preprocessing,
        vector_format=vector_format,
        vector_path=vector_path,
        input_array=input_array,
        output_array=output_array,
        io_alignment=io_alignment,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_directory", type=Path)
    args = parser.parse_args()
    try:
        model = load_model_package(args.model_directory)
    except ModelPackageError as error:
        parser.error(str(error))
    print(
        f"{model.name}: id=0x{model.model_id:08x}, "
        f"input={model.input.shape}/{model.input.dtype}/{model.input.size_bytes}B, "
        f"output={model.output.shape}/{model.output.dtype}/{model.output.size_bytes}B, "
        f"target={model.target_device_family}/{model.accelerator}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
