# UART protocol version 1

The host and firmware exchange binary, length-delimited frames. Multi-byte
integers use little-endian byte order.

## Frame layout

| Offset | Size | Field |
|---:|---:|---|
| 0 | 2 | Magic bytes `5a a5` |
| 2 | 1 | Protocol version (`1`) |
| 3 | 1 | Message type |
| 4 | 2 | Sequence number |
| 6 | 2 | Payload length |
| 8 | variable | Payload |
| `8 + length` | 4 | IEEE CRC-32 |

The CRC covers the version, type, sequence, length, and payload; it excludes
the two magic bytes and the CRC field itself. It is the reflected IEEE CRC-32
with polynomial `0xedb88320`, initial state `0xffffffff`, and final XOR
`0xffffffff`, compatible with Python's `binascii.crc32`.

## Messages

| Type | Name | Direction | Payload |
|---:|---|---|---|
| `0x01` | `INFERENCE_REQUEST` | host to board | 256 signed 8-bit model inputs |
| `0x02` | `CLOCK_REQUEST` | host to board | empty |
| `0x80` | `READY` | board to host | input length and output length as two `uint16` values |
| `0x81` | `ACK` | board to host | empty |
| `0x82` | `RESULT` | board to host | three `int8` scores, then accelerator, runtime, and total microseconds as three `uint32` values |
| `0x83` | `CLOCK_STATUS` | board to host | twelve `uint32` clock/status fields described below |
| `0xff` | `ERROR` | board to host | error code byte |

Requests, acknowledgements, results, status, and errors use the same sequence
number. `READY` uses sequence zero; the host chooses each request sequence.

The `CLOCK_STATUS` words are expected MCLK, register-derived MCLK, configured
UART clock, `MCLKCFG`, `HSCLKEN`, `HSCLKCFG`, `SYSPLLCFG0`, `SYSPLLCFG1`,
`GENCLKEN`, `CLKSTATUS`, flash read control, and validation flags. The required
validation mask is `0x1f`: active MCLK source, healthy HSCLK, healthy selected
PLL/HFCLK, expected frequency, and sufficient flash wait states.

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

## Recovery rules

- The receiver scans for the two-byte magic, so boot text and damaged bytes do
  not permanently desynchronize the stream.
- The firmware applies one absolute one-second deadline to the complete incoming
  frame and rejects malformed frames with a structured error when possible.
- The host rejects mismatched versions, message types, lengths, sequences, and
  CRCs. It may retry a request only up to its configured retry budget.
- A CRC fault test is available through `./scripts/test.sh --fault-test`; it
  verifies both rejection and recovery before normal inference begins.
