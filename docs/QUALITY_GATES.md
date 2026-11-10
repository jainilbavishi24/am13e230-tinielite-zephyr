# Engineering quality gates

This matrix separates demonstrated behavior from planned work. A gate is marked
passed only when reproducible evidence exists.

| Gate | Status | Evidence or acceptance condition |
|---|---|---|
| Reproducible firmware build | PASS (software) | Clean pinned Zephyr protocol-v3 builds: waveform 25,656 B flash / 43,616 B RAM; electrical fault 31,752 B flash / 41,320 B RAM |
| Model artifact integrity | PASS | SHA-256 manifests plus model IDs derived from each archive SHA-256 |
| Build-time model-package abstraction | PASS (software) | Stable generated-adapter API and two real packages with different shapes, input dtypes, preprocessing, labels, generated fields, and archives; compatible packages require metadata rather than hand-written C |
| Second real model package | PASS | Licensed electrical-fault export validates, cross-links, flashes, and passes all physical acceptance checks |
| Protocol v3 software gate | PASS | 28 host tests; five native_sim tests with ASan/UBSan; exact READY model/size/dtype validation |
| Protocol v3 physical-board gate | PASS | Both packages passed erase/program/verify, exact fixtures, CRC, clock, IRQ, NPU-timeout, watchdog, and 600-inference acceptance on 2026-11-10 |
| Generated NPU kernels linked | PASS (software) | ELF inspection finds each selected entry point, continuation/IRQ symbol, and package-specific accelerated runtime symbols |
| Basic hardware correctness | PASS | Both v3 images passed erase/program/verify and exact package fixtures |
| Robust framed transport | PASS | v3 validates version, length, sequence, model identity, CRC, and stream resynchronization; live runs used zero retries |
| Transport fault recovery | PASS | Deliberately corrupted CRC was rejected and the next transaction succeeded for both packages |
| Repeated inference | PASS | Waveform 600/600 and electrical fault 600/600 exact, with zero retries; raw JSON retained |
| Explicit clock configuration/read-back | PASS | Both v3 images reported 200 MHz MCLK, 100 MHz UART source, three flash wait states, and validation flags `0x1f` |
| True NPU interrupt completion | PASS | Waveform: five DONE IRQs/inference; electrical fault: eight; 600 runs each and zero spurious IRQs |
| Inference timeout/reset recovery | PASS | Both packages returned `-ETIMEDOUT`, cold-reset opaque runtime state, restored READY, then passed stress inference |
| Independent hardware watchdog | PASS | Both packages produced WWDT0 reset cause `0x0e`, restarted the four-second watchdog, and passed stress inference |
| Production UART integration | PARTIAL | Standard Zephyr pinctrl and receive-error reporting are hardware-validated; interrupt/async data transfer remains pending |
| Firmware CI | LOCAL PASS / REMOTE NOT YET RUN | Workflow validates, hashes, cross-builds, symbol-checks, and publishes both packages; the current working tree remains intentionally uncommitted |
| Static and Zephyr-native tests | PASS | Cppcheck, ClangFormat, Ruff, Python formatting, and ShellCheck pass; five protocol ztests pass on `native_sim` with ASan/UBSan; 28 host tests pass |
| Electrical-fault held-out evaluation | PARTIAL | Edge AI Studio reports 706/807 (87.4845%), but ABCG recall is 9/99 and overlapping windows/few source files limit independence |
| Independent real-world model evaluation | EXTERNAL INPUT REQUIRED | Requires new recordings or simulations, group-wise separation, balance, provenance, and operating-condition coverage |
| Comparative benchmarking | PARTIAL / EXTERNAL INPUT REQUIRED | Polling/IRQ main-thread occupancy bounds, NPU timing, and footprint are recorded; an equivalent CPU model artifact and power instrumentation are unavailable |
| Upstream-quality platform port | PENDING | SoC/board/driver split and Zephyr-reviewable patches |

## Known ABI constraint

The generated model archive defines NPU memory-write callbacks with a `void`
return type. The integration checks all callback bounds and logs violations,
but cannot propagate a callback failure through that ABI. Completely removing
this limitation requires regenerating the model/runtime interface with an error
return or adding a compatible out-of-band fault status that the runtime checks.

For the default waveform package, the repository owner has only the generated
`mod.a`, generated header, and six fixtures—not the original model or training
pipeline. The electrical-fault run supplies richer generated training/export
evidence, but not a documented redistributable end-to-end dataset pipeline.
Reconstructing either licensed archive is not a valid reproducibility method.
These are explicit artifact-boundary constraints, not unfinished firmware work.

## Meaning of the v2/v3 split

Protocol-v2 evidence is retained as development history. Protocol v3 changes
common buffer sizing and adds exact model/tensor metadata; it has now received
its own complete physical acceptance rather than inheriting v2 status. Use the
2026-11-10 files under `docs/evidence/protocol_v3/` for current claims.
