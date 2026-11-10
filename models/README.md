# Model package contract

This directory contains build-time-selectable model packages. A compatible
package consists of:

- `model.json`: machine-readable identity, tensor metadata, artifact paths,
  generated-runtime ABI names, preprocessing contract, and vector format.
- A target-specific generated static library and header.
- Licensed regression fixtures and `SHA256SUMS`.

CMake validates the manifest and generates the small `app_model.h` adapter in
the build directory. Model packages do not carry hand-written adapter C files.

Select a package at build time:

```bash
APP_MODEL=waveform_classifier ./scripts/build.sh
# equivalent: ./scripts/build.sh -- -DAPP_MODEL=waveform_classifier
```

The default is `waveform_classifier`. Model selection is compile-time:
`.a` archives are statically linked, so changing models requires rebuilding
and reflashing.

## Bundled packages

| Name | Input contract | Output contract | Preprocessing |
|---|---|---|---|
| `waveform_classifier` | `[1, 256]` int8 | `[1, 3]` int8 | TI affine normalization/quantization |
| `electrical_fault_6class` | `[1, 6, 128, 1]` float32 | `[1, 6]` int8 | Identity little-endian float32 |

Both archives pass manifest validation, pristine Arm cross-linking, and the
complete protocol-v3 physical-board acceptance matrix. This does not make an
arbitrary `.a` compatible; every new package still needs the checks below.

## Compatibility boundary

The reusable firmware accepts variable input/output byte sizes and the
following tensor datatypes: int8, uint8, int16, and float32. A package must
target AM13E2/TINIElite and use the generated asynchronous NPU completion ABI
expected by the current TINIElite integration. Manifest runtime fields drive a
generated adapter that isolates input/output structs and fields, completion
state, entry point, and continuation symbol.

Run the package validator before building:

```bash
python -m tools.model_package models/waveform_classifier
python -m tools.model_package models/electrical_fault_6class
```

`model_id` must equal the first 32 bits of the library's SHA-256. This binds
the READY handshake to the actual linked archive and detects stale metadata.

A new package is not hardware-validated merely because it compiles. It still
requires artifact hash/license review, symbol inspection, golden-vector tests,
clock validation, NPU completion/spurious-interrupt checks, timeout recovery,
and physical-board stress testing.

See [docs/MODEL_PACKAGES.md](../docs/MODEL_PACKAGES.md) for the complete schema,
generated-adapter boundary, second-model procedure, and acceptance gates.
