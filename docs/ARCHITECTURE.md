# Architecture

## Execution path

1. A pre-kernel SoC initializer configures three flash wait states, starts the
   25 MHz board crystal, configures and locks the PLL, and switches MCLK through
   `/4`, `/2`, and bypass stages to 200 MHz before the Zephyr system timer starts.
2. CMake validates and selects one `models/<name>/model.json`, generates common
   tensor configuration plus a package-specific C adapter in the build tree,
   compiles the generated adapter, and links the selected static archive. The
   default package is the waveform classifier.
3. At boot, protocol v3 advertises the selected archive-derived model ID,
   tensor byte sizes, tensor types, and NPU capability flag. The host compares
   them with the same manifest before inference.
4. The host parses a package fixture and applies that package's declared
   preprocessing. The waveform plug-in reads generated affine bias/scale/shift
   constants and emits int8 input; the electrical-fault plug-in validates and
   packs raw little-endian float32 samples.
5. It sends a versioned inference frame with a sequence number, the advertised
   input byte length, and an IEEE CRC32.
6. The Zephyr application resynchronizes on the magic bytes, validates the
   complete frame under a single deadline, and returns a sequence-matched ACK
   or structured error.
7. `app_model_run()` crosses the stable generated-adapter boundary and calls
   the selected package's generated graph entry point.
8. The TINIElite IP asserts DONE on IRQ 41. The driver ISR reads masked status,
   acknowledges DONE, increments an atomic completion counter, and signals a
   semaphore. The application waits up to 100 ms per hardware stage and calls
   the manifest-selected continuation function through the generated adapter
   in thread context.
9. The advertised output tensor bytes, three timing fields, and two NPU
   interrupt counters return in a CRC-protected result frame.
10. The host decodes the selected output type and compares the complete tensor
    with the package's golden fixture.

A separate clock-status request returns the relevant raw SYSCTL/FRI registers,
derived MCLK, configured UART clock, flash wait states, and validation flags.

If an NPU stage does not signal completion within 100 ms, the firmware sends a
structured timeout error, allows the polling UART transmitter to drain, and
requests a cold Cortex-M system reset. A test-only request deliberately enters
this wait without starting the accelerator; the host requires a fresh `READY`
after reset and then reruns normal inference. The full reset is intentional
because the binary-only model archive may retain opaque continuation state that
a peripheral-only reset cannot safely repair.

WWDT0 independently supervises the whole synchronous server. It uses the
32.768 kHz low-frequency clock with a four-second period and no closed feed
window. Only forward progress in the main request loop feeds it; there is no
background feeder that could hide a deadlocked application. A test-only
request withholds feeding, and after reboot the host reads the latched SYSCTL
reset cause and requires `BOOTWWDT0` (`0x0e`).

See [PROTOCOL.md](PROTOCOL.md) for the byte-level contract and recovery rules.

## Model-package boundary

The common firmware knows only the stable functions in `app_model.h` and the
generated constants in `app_model_config.h`. Package-specific generated
struct names, input/output field names, entry symbols, completion variables,
and continuation calls are declared in `model.json` and emitted into
`build/generated/model_adapter.c`. This keeps model variation separate from
clock, transport, fault recovery, and NPU-driver code without requiring a
hand-written C file for each compatible package.

Selection is compile-time because a `.a` archive contains target object code
that must be resolved by the linker. Protocol v3 is model-aware but is not a
dynamic linker or arbitrary archive loader. Full requirements and acceptance
steps are in [MODEL_PACKAGES.md](MODEL_PACKAGES.md).

## Hardware map used

| Resource | Address/size |
|---|---:|
| Flash | `0x00000000`, 512 KiB |
| Primary linked SRAM | `0x20000000`, 96 KiB |
| Separate SRAM bank/code alias | `0x00c18000`, 32 KiB |
| UNICOMM UART | `0x40601000` |
| UNICOMM wrapper | `0x40632000` |
| TINIElite | `0x408ff000` |
| WWDT0 | `0x400d0000` |
| TINIElite CTL5 | base + `0x1120` |
| Instruction memory | base + `0x2000`, 256 words |
| Parameter memory | base + `0x2800`, 512 words |

## Concurrency model

The current design is intentionally single-request and synchronous. It avoids
queueing tensors while inference is active, keeps the wire protocol ordered,
and makes hardware faults visible. Sequence numbers prevent stale ACK/result
frames from satisfying a newer request. The host applies a bounded retry
budget, while the firmware drains stale bytes before advertising readiness.
Throughput-oriented double buffering remains a future optimization; the
single-request path is retained because it keeps timing, recovery, and opaque
model-runtime state transitions deterministic.

## Current validation boundary

The package validator, 28 host tests, sanitizer-backed native protocol tests,
and pristine Arm cross-builds pass for both bundled models on protocol v3.
Both v3 images also passed complete physical acceptance on LP-AM13E230 on
2026-11-10: exact fixtures, clock read-back, CRC recovery, NPU-timeout recovery,
WWDT0 recovery, repeated inference, nonzero DONE IRQs, and zero spurious IRQs.
The earlier protocol-v2 results remain available only as development history.
