# UART protocol version 3

The host and firmware exchange binary, length-delimited frames. Multi-byte
integers and multi-byte tensor elements use little-endian byte order.

Version 3 removes the fixed 256-byte-input/three-byte-output assumption from
the wire contract. At startup, the board identifies the statically linked
model package and declares its tensor byte sizes and data types. The host must
load the same package metadata and reject a mismatch before sending inference.

> Validation status: v3 passes 28 host unit tests, five sanitizer-backed
> Zephyr-native tests, pristine Arm cross-builds, and complete physical-board
> acceptance for both bundled real packages. Current evidence is under
> `docs/evidence/protocol_v3/`.

## Frame layout

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | Magic bytes `5a a5` |
| 2 | 1 | Protocol version (`3`) |
| 3 | 1 | Message type |
| 4 | 2 | Sequence number |
| 6 | 2 | Payload length |
| 8 | variable | Payload |
| `8 + length` | 4 | IEEE CRC-32 |

The CRC covers version, type, sequence, length, and payload; it excludes the
magic and CRC fields. It is reflected IEEE CRC-32 with polynomial
`0xedb88320`, initial state `0xffffffff`, and final XOR `0xffffffff`, compatible
with Python `binascii.crc32`.

## Tensor data-type codes

| Code | Type | Bytes per element |
|---:|---|---:|
| 1 | signed `int8` | 1 |
| 2 | unsigned `uint8` | 1 |
| 3 | signed little-endian `int16` | 2 |
| 4 | little-endian IEEE-754 `float32` | 4 |

Input and output sizes are byte counts, not element counts. Each must fit in
the protocol's unsigned 16-bit length field. The model manifest validates that
`product(shape) * bytes_per_element == size_bytes`.

## Messages

| Type | Name | Direction | Payload |
|---:|---|---|---|
| `0x01` | `INFERENCE_REQUEST` | host to board | exactly the advertised input tensor bytes |
| `0x02` | `CLOCK_REQUEST` | host to board | empty |
| `0x03` | `NPU_STALL_REQUEST` | host to board | empty; diagnostic builds only |
| `0x04` | `WATCHDOG_STALL_REQUEST` | host to board | empty; diagnostic builds only |
| `0x05` | `WATCHDOG_STATUS_REQUEST` | host to board | empty |
| `0x80` | `READY` | board to host | model capabilities described below |
| `0x81` | `ACK` | board to host | empty |
| `0x82` | `RESULT` | board to host | output tensor bytes followed by five `uint32` metrics |
| `0x83` | `CLOCK_STATUS` | board to host | twelve `uint32` clock/status fields |
| `0x84` | `WATCHDOG_STATUS` | board to host | reset cause, timeout ms, and running flag as three `uint32` values |
| `0xff` | `ERROR` | board to host | error code byte followed by signed `int16` detail |

Requests, acknowledgements, results, status, and errors use the same sequence
number. `READY` uses sequence zero; the host chooses each request sequence.

### READY payload

The 12-byte payload is packed as `<IHHBBH`:

| Offset | Type | Meaning |
|---:|---|---|
| 0 | `uint32` | model ID |
| 4 | `uint16` | input tensor size in bytes |
| 6 | `uint16` | output tensor size in bytes |
| 8 | `uint8` | input data-type code |
| 9 | `uint8` | output data-type code |
| 10 | `uint16` | capability flags |

Capability bit 0 means that the selected package requires the TINIElite NPU.
Other bits are reserved and currently zero. The model ID is the first 32 bits
of the selected library's SHA-256 digest, interpreted in network/display order;
for the bundled archive it is `0xc7d11096`. The package validator rejects an
ID that no longer matches the archive, preventing stale host metadata from
silently talking to a different linked model.

The host compares all six fields with its selected `model.json`. A mismatch is
a hard failure: it must not guess shapes, truncate tensors, or decode an output
using the wrong data type.

### RESULT payload

The result begins with exactly the advertised output bytes. Five little-endian
`uint32` fields follow:

1. accelerator wait time in microseconds;
2. generated runtime/CPU portion in microseconds;
3. end-to-end inference time in microseconds;
4. acknowledged NPU DONE interrupt count;
5. spurious NPU interrupt count.

The host decodes the output according to the advertised type and rejects a
payload of any other length. It also rejects zero completion interrupts or a
nonzero spurious count; those checks prevent an image from silently claiming
the verified interrupt path while polling or accepting unrelated entries.

### Status payloads

`CLOCK_STATUS` returns expected MCLK, register-derived MCLK, configured UART
clock, `MCLKCFG`, `HSCLKEN`, `HSCLKCFG`, `SYSPLLCFG0`, `SYSPLLCFG1`, `GENCLKEN`,
`CLKSTATUS`, flash read control, and validation flags. Required validation mask
`0x1f` covers active MCLK source, healthy HSCLK, healthy selected PLL/HFCLK,
expected frequency, and sufficient flash wait states.

## Error codes

| Code | Meaning |
|---:|---|
| 1 | Receive timeout |
| 2 | Unsupported protocol version |
| 3 | Unexpected message type |
| 4 | Invalid payload length |
| 5 | CRC mismatch |
| 6 | Inference failure |
| 7 | Internal error |
| 8 | UART transport error (overrun, parity, framing, break, or noise) |

## Recovery rules

- The receiver scans for the two-byte magic so boot text and damaged bytes do
  not permanently desynchronize the stream.
- Firmware applies one absolute one-second deadline to the complete incoming
  frame and sends a structured error when possible.
- The host rejects mismatched versions, models, types, lengths, sequences, and
  CRCs. It may retry only within its configured retry budget.
- `./scripts/test.sh --fault-test` verifies CRC rejection and recovery before
  normal inference.
- With `CONFIG_APP_NPU_FAULT_INJECTION=y`, `--npu-fault-test` waits without
  starting the accelerator. Firmware reports `-ETIMEDOUT`, drains UART, cold
  resets the opaque model state, and the host requires a new matching `READY`.
- With `CONFIG_APP_WATCHDOG_FAULT_INJECTION=y`, `--watchdog-fault-test` stops
  the only WWDT0 feed path. Recovery is accepted only after a rebooted matching
  `READY`, reset cause `0x0e`, and confirmation that WWDT0 is running.

Fault-injection options are diagnostic only and must be disabled for a
deployment configuration.

## Why the protocol is not a runtime model loader

The READY metadata makes the protocol model-aware, but the `.a` archive is
still linked into the ELF at build time. A static library contains target
object code and relocation/symbol requirements, not a self-describing model
file that firmware can safely load from UART. Changing packages therefore
requires validation, rebuild, flash, and a new READY handshake.
