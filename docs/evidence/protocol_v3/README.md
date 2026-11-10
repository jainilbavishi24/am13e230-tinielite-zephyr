# Protocol-v3 physical evidence

These machine-readable reports were captured from LP-AM13E230 through XDS110
from WSL on 2026-11-10. Both firmware images were freshly built, erased,
programmed, verified, and exercised through protocol v3.

| File | Evidence |
|---|---|
| `waveform_clock_2026-11-10.json` | 200 MHz MCLK, 100 MHz UART source, three flash waits, validation flags `0x1f` |
| `waveform_full_acceptance_2026-11-10.json` | CRC/NPU-timeout/WWDT0 recovery; 600/600 exact, zero retries, five IRQs/run, zero spurious |
| `electrical_fault_clock_2026-11-10.json` | 200 MHz MCLK, 100 MHz UART source, three flash waits, validation flags `0x1f` |
| `electrical_fault_fixtures_2026-11-10.json` | All 12 supplied package fixtures exactly reproduced |
| `electrical_fault_full_acceptance_2026-11-10.json` | CRC/NPU-timeout/WWDT0 recovery; 600/600 exact, zero retries, eight IRQs/run, zero spurious |

Fixture equality is deterministic integration evidence. It is not an
independent estimate of model accuracy or real-world generalization. See
[VALIDATION.md](../../VALIDATION.md) for commands, interpretation, historical
protocol-v2 results, and explicit limitations.
