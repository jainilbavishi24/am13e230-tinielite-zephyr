# Architecture

## Execution path

1. A pre-kernel SoC initializer configures three flash wait states, starts the
   25 MHz board crystal, configures and locks the PLL, and switches MCLK through
   `/4`, `/2`, and bypass stages to 200 MHz before the Zephyr system timer starts.
2. The host parses one of six float feature vectors and applies the generated
   model's bias, scale, shift, truncation, and int8 clipping.
3. It sends a versioned inference frame with a sequence number, explicit
   payload length, 256 payload bytes, and an IEEE CRC32.
4. The Zephyr application resynchronizes on the magic bytes, validates the
   complete frame under a single deadline, and returns a sequence-matched ACK
   or structured error.
5. `tvmgen_default_run()` starts the generated hybrid graph.
6. The TINIElite IP asserts DONE on IRQ 41. The driver ISR reads masked status,
   acknowledges DONE, increments an atomic completion counter, and signals a
   semaphore. The application waits up to 100 ms per hardware stage and calls
   the TI runtime continuation handler in thread context.
7. Three signed class scores, three timing fields, and the acknowledged NPU
   interrupt count return in a CRC-protected result frame.
8. The host compares all three scores exactly with the golden fixture.

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
