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
6. The application polls TINIElite CTL5 for each hardware stage, calls the TI
   runtime continuation handler, and enforces a 100 ms per-stage timeout.
7. Three signed class scores and three timing fields return in a CRC-protected
   result frame.
8. The host compares all three scores exactly with the golden fixture.

A separate clock-status request returns the relevant raw SYSCTL/FRI registers,
derived MCLK, configured UART clock, flash wait states, and validation flags.

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
| TINIElite CTL5 | base + `0x1120` |
| Instruction memory | base + `0x2000`, 256 words |
| Parameter memory | base + `0x2800`, 512 words |

## Concurrency model

The current design is intentionally single-request and synchronous. It avoids
queueing tensors while inference is active, keeps the wire protocol ordered,
and makes hardware faults visible. Sequence numbers prevent stale ACK/result
frames from satisfying a newer request. The host applies a bounded retry
budget, while the firmware drains stale bytes before advertising readiness.
Throughput-oriented double buffering remains a future optimization after
interrupt completion is implemented correctly.
