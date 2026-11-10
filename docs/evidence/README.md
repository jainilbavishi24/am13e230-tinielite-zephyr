# Hardware evidence

Evidence is grouped by the wire-protocol/source generation it actually
validated. Do not use retained protocol-v2 measurements as if they described
the current protocol-v3 images.

| Directory | Meaning |
|---|---|
| [`protocol_v2/`](protocol_v2/README.md) | Retained LP-AM13E230 measurements from 2026-10-17 |
| [`protocol_v3/`](protocol_v3/README.md) | Current waveform and electrical-fault acceptance from 2026-11-10 |

Every new record should include the board, probe/tool versions, firmware
revision, exact command, selected model, pass/fail fields, and raw measurements.
Summarize accepted evidence in [VALIDATION.md](../VALIDATION.md); placing a JSON
file here does not by itself make a validation claim.
