# Engineering quality gates

This matrix separates demonstrated behavior from planned work. A gate is marked
passed only when reproducible evidence exists.

| Gate | Status | Evidence or acceptance condition |
|---|---|---|
| Reproducible firmware build | PASS | Clean pinned Zephyr build; flash/RAM sizes recorded in `VALIDATION.md` |
| Model artifact integrity | PASS | Published SHA-256 manifest verification |
| Generated NPU kernels linked | PASS | ELF symbol inspection identifies four TINIElite kernels |
| Basic hardware correctness | PASS | Six exact golden-vector results after erase/program/verify |
| Robust framed transport | PASS | Version, length, sequence, CRC-32, errors, deadlines, retry budget, resynchronization |
| Transport fault recovery | PASS | Deliberate CRC corruption rejected; following transaction succeeds |
| Repeated inference | PASS | 600/600 exact results, zero retries; raw JSON retained |
| Explicit clock configuration/read-back | PASS | Staged 200 MHz PLL initialization, 100 MHz UART divisor, three flash wait states, raw register evidence |
| True NPU interrupt completion | PASS | 600 runs, five acknowledged DONE IRQs per inference, zero spurious IRQs; protocol-v2 JSON retained |
| Watchdog/fault recovery | PENDING | Demonstrate recovery from a deliberately stalled inference and transport fault |
| Production UART integration | PENDING | Zephyr pinctrl plus status/error handling and interrupt or async operation |
| Firmware CI | PASS | GitHub Actions provisions the Arm GNU toolchain and pinned west workspace, cross-builds, verifies key ELF symbols, and publishes firmware artifacts |
| Static and Zephyr-native tests | PENDING | Static analysis and Twister coverage for protocol/state logic |
| Independent model evaluation | PENDING | Labeled dataset, provenance, preprocessing, confusion matrix, precision/recall |
| Comparative benchmarking | PENDING | Verified clocks, CPU baseline, NPU speedup, utilization, and power |
| Upstream-quality platform port | PENDING | SoC/board/driver split and Zephyr-reviewable patches |

## Known ABI constraint

The generated model archive defines NPU memory-write callbacks with a `void`
return type. The integration checks all callback bounds and logs violations,
but cannot propagate a callback failure through that ABI. Completely removing
this limitation requires regenerating the model/runtime interface with an error
return or adding a compatible out-of-band fault status that the runtime checks.
