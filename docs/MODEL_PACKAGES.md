# Model-package integration guide

## What “model-agnostic” means here

The application is agnostic to **compatible build-time packages**. It no
longer hardcodes one archive path, tensor length, output length, output type,
generated C struct field, or generated entry-point name in the common server.
Those differences live in a manifest. During CMake configuration, a generator
turns that declarative metadata into the small C adapter required by the
stable application interface.

It does **not** mean any `.a` file can be uploaded and executed at runtime. A
static archive is object code for a particular processor/toolchain plus
symbols and relocation records. It is not a portable, self-describing neural
network. A compatible TI export must be validated, linked into a new ELF, and
flashed.

## Boundary of the reusable implementation

~~~text
models/<name>/model.json
        | tensor contract, files, model identity, generated-runtime ABI names
        v
app/CMakeLists.txt ---- validates/selects package at configure time
        |
        +--> generated app_model_config.h
        +--> generated model_adapter.c
        +--> selected generated static library
                    |
common app_model API| hides generated names and structures
                    v
app_npu.c --> UART protocol v3 --> Python client using the same manifest
~~~

The stable C interface is in `app/src/app_model.h`:

- `app_model_reset()` resets generated completion state;
- `app_model_run(input, output)` calls the generated graph entry point;
- `app_model_is_finished()` reports whether the graph has completed;
- `app_model_continue()` advances the generated asynchronous NPU runtime.

The adapter is intentionally tiny and deterministic. It is generated in the
build directory from validated manifest fields, so adding a compatible model
does not require writing package-specific C. The generated file is the only C
translation unit that mentions a package's input/output structs, field names,
entry point, completion variable, and continuation symbol.

## Package layout

~~~text
models/<name>/
├── model.json
├── artifacts/
│   ├── model.a
│   └── generated_header.h
├── golden_vectors/
│   └── ...
├── docs/                 # optional model-specific evaluation
├── provenance/           # optional original export evidence
├── LICENSE.txt
├── SHA256SUMS
└── README.md
~~~

Do not rename or edit vendor-generated artifacts just to make them resemble the
default model. Preserve their license and describe their generated API in the
manifest.

## Manifest contract

`schema_version` is currently 1. The validator enforces:

- a directory-safe package name using letters, digits, and underscores;
- AM13E2 + TINIElite target identity and `requires_npu: true`;
- existing, package-local archive/header/vector paths;
- a nonzero model ID equal to the first 32 bits of the archive SHA-256;
- positive tensor dimensions and consistent byte sizes;
- input size no larger than 65,535 bytes and output plus its 20-byte result
  metrics no larger than 65,535 bytes;
- supported types: `int8`, `uint8`, `int16`, or `float32`;
- labels either absent or equal in count to output elements;
- power-of-two I/O alignment from 1 through 256;
- supported preprocessing and fixture formats;
- valid C identifiers for generated input/output structs, fields, entry point,
  completion variable, and continuation symbol;
- declarations for the generated structs, entry point, and completion variable
  in the selected generated header.

The runtime section is the declarative replacement for a hand-written adapter:

```json
"runtime": {
  "input_struct": "tvmgen_default_inputs",
  "output_struct": "tvmgen_default_outputs",
  "completion_symbol": "tvmgen_default_finished",
  "continuation_symbol": "TI_NPU_NNC_IRQHandler"
}
```

The tensor sections separately declare their generated `runtime_field` names,
and `artifacts.entry_symbol` declares the graph entry point. These names are
read from the vendor header/archive; they are not guessed. A `.a` file does not
contain tensor meaning, preprocessing, labels, or a stable universal API, so
this small amount of metadata cannot safely be eliminated.

The host currently implements two explicit preprocessing plug-ins:

- `ti_affine_shift_header`: reads generated bias/scale/shift constants and
  emits int8 input for the waveform model;
- `identity_float32_le`: validates finite values and packs raw little-endian
  float32 input for the electrical-fault model.

Outputs may use any supported tensor type. A model with a different transform
needs a new named plug-in in both the validator and host client; do not
mislabel an FFT, scaler, channel reorder, or other transform as identity.

The two concrete examples are
[`waveform_classifier/model.json`](../models/waveform_classifier/model.json)
and
[`electrical_fault_6class/model.json`](../models/electrical_fault_6class/model.json).

## Add a real Edge AI Studio/NNC export

The owner must provide, or confirm permission to publish, all of the following:

1. the AM13E2/TINIElite-generated `.a` archive;
2. its generated C header;
3. the exact input shape, input type, output shape/type, and label order;
4. the preprocessing constants and meaning;
5. at least one legally redistributable input with expected output, preferably
   multiple fixtures covering every class;
6. artifact license/redistribution terms;
7. ideally the source model/export settings and an independent labelled
   dataset—these are needed for regeneration and accuracy claims, respectively.

Then:

1. Create `models/<name>/` using the layout above.
2. Calculate the archive hash:

   ```bash
   sha256sum models/<name>/artifacts/<archive>.a
   ```

3. Use the first eight hexadecimal hash characters for `model_id`, prefixed
   with `0x`. Record complete hashes in `SHA256SUMS`.
4. Inspect generated declarations and archive symbols:

   ```bash
   arm-none-eabi-nm -g --defined-only models/<name>/artifacts/<archive>.a
   rg 'run|finished|input|output|NPU|IRQHandler' \
     models/<name>/artifacts/<generated_header>.h
   ```

5. Record the generated input/output struct names, tensor field names, entry
   point, completion symbol, and continuation symbol in `model.json`. Do not
   add generated names to `app_npu.c`, `app_uart.c`, or `main.c`.
6. Validate the package and, if desired, preview the generated adapter:

   ```bash
   python -m tools.model_package models/<name>
   python -m tools.generate_model_adapter \
     models/<name> /tmp/<name>_model_adapter.c
   ```

7. Build the selected package:

   ```bash
   APP_MODEL=<name> ./scripts/build.sh
   # equivalent: ./scripts/build.sh -- -DAPP_MODEL=<name>
   ```

8. Inspect `build/generated/model_adapter.c`, the ELF, and the map. Confirm the
   selected entry point, accelerated kernels, TI continuation handler, stable
   adapter functions, and expected archive are linked; confirm the previous
   package is absent.
9. Run host/static/native checks before touching hardware.
10. Only after those pass, flash and run the physical acceptance matrix below.

The client must select the same package:

```bash
APP_MODEL=<name> ./scripts/test.sh
# or: ./scripts/test.sh --model <name>
```

Protocol v3 makes a mismatch fail immediately during READY validation.

## Pre-hardware acceptance matrix

| Check | Command or evidence | Current result |
|---|---|---|
| Manifest/schema/hash | validator plus `sha256sum --check` for both packages | PASS |
| Host behavior | `python -m unittest discover -s tests -v` | PASS, 28 tests |
| Different real tensor contracts | int8 `[1,256]` and float32 `[1,6,128,1]` packages | PASS |
| Alternate metadata contract | synthetic 64-byte input / int16-output package unit test | PASS |
| Python quality | Ruff lint and format | PASS |
| C quality | `./scripts/static_check.sh` | PASS |
| Shell quality | `shellcheck scripts/*.sh` | PASS |
| Protocol safety | native_sim + ASan + UBSan | PASS, 5 tests |
| Default model Arm link | pristine pinned cross-build | PASS; 25,656 B flash, 43,616 B RAM |
| Electrical-fault Arm link | pristine pinned cross-build | PASS; 31,752 B flash, 41,320 B RAM |
| Electrical-fault physical acceptance | complete matrix below | PASS on 2026-11-10: 12/12 fixtures, 600/600 stress, clock/CRC/IRQ/NPU-timeout/WWDT0 checks |

The synthetic package still tests rejection paths and an int16 output contract.
The electrical-fault package is the second real compatible export and proves
the full manifest, preprocessing, generated-adapter, archive, link, flash, and
physical inference path.

## Required hardware acceptance for every new package

A successful link is necessary but not sufficient. On LP-AM13E230, require:

- erase/program/verify succeeds;
- READY exactly matches model ID, sizes, dtypes, and NPU flag;
- all golden fixtures produce their expected complete output tensors;
- clock status confirms 200 MHz MCLK, 100 MHz UART source, and flash waits;
- every inference records one or more acknowledged NPU DONE interrupts and
  zero spurious interrupts;
- CRC corruption is rejected and the next request succeeds;
- NPU timeout/cold-reset recovery succeeds in a diagnostic build;
- independent watchdog reset and restart succeed in a diagnostic build;
- repeated inference completes with zero mismatches and bounded retries;
- JSON evidence, tool versions, commit, board, and memory footprint are saved.

Do not reuse the default model's latency, interrupt count, or expected scores
for a new package. Graph partitioning can change how many NPU stages—and thus
how many DONE interrupts—occur per inference.

## What is still needed from the project owner

No additional artifact or hardware run is needed for the reusable scaffold or
the second package's integration acceptance. A defensible production-quality
model claim still needs independent recordings or simulations, stronger
group-wise dataset separation, balanced classes, operating-condition
variation, and a documented redistributable training pipeline.
