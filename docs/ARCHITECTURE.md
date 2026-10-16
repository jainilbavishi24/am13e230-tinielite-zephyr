# Architecture

## Execution path

1. The host parses one of six float feature vectors and applies the generated
   model's bias, scale, shift, truncation, and int8 clipping.
2. It sends magic `5A A5`, 256 payload bytes, and an 8-bit additive checksum.
3. The Zephyr application validates the packet and acknowledges it.
4. `tvmgen_default_run()` starts the generated hybrid graph.
5. The application polls TINIElite CTL5 for each hardware stage, calls the TI
   runtime continuation handler, and enforces a 100 ms per-stage timeout.
6. Three signed class scores and profiling lines return over UART.
7. The host compares all three scores exactly with the golden fixture.

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
and makes hardware faults visible. Throughput-oriented double buffering is a
future optimization after interrupt completion and protocol sequencing are
implemented correctly.
