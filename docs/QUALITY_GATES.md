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
| Inference timeout/reset recovery | PASS | Deliberate NPU stall returns `-ETIMEDOUT`, cold-resets, restores `READY`, then passes 600/600 inferences |
| Independent hardware watchdog | PASS | Deliberate feed starvation causes WWDT0 BOOTRST; reset cause `0x0e`, restarted watchdog, and 600/600 post-reset inferences verified |
| Production UART integration | PARTIAL | Standard Zephyr pinctrl and receive-error reporting are hardware-validated; interrupt/async data transfer remains pending |
| Firmware CI | PASS | GitHub Actions provisions the Arm GNU toolchain and pinned west workspace, cross-builds, verifies key ELF symbols, and publishes firmware artifacts |
| Static and Zephyr-native tests | PASS | Cppcheck, ClangFormat, Ruff, and Python formatting pass; five protocol ztests pass on `native_sim` with ASan and UBSan; 16 host tests pass |
| Independent model evaluation | EXTERNAL INPUT REQUIRED | Original preprocessing contract and an independent labeled dataset are unavailable |
| Comparative benchmarking | PARTIAL / EXTERNAL INPUT REQUIRED | Polling/IRQ main-thread occupancy bounds, NPU timing, and footprint are recorded; an equivalent CPU model artifact and power instrumentation are unavailable |
| Upstream-quality platform port | PENDING | SoC/board/driver split and Zephyr-reviewable patches |

## Known ABI constraint

The generated model archive defines NPU memory-write callbacks with a `void`
return type. The integration checks all callback bounds and logs violations,
but cannot propagate a callback failure through that ABI. Completely removing
this limitation requires regenerating the model/runtime interface with an error
return or adding a compatible out-of-band fault status that the runtime checks.

The repository owner has only the generated `mod.a`, generated header, and six
fixtures—not the original model or generation pipeline. Reconstructing the
licensed archive is neither a valid reproducibility method nor permitted by its
license. This is an explicit artifact-boundary constraint, not unfinished
firmware work.
