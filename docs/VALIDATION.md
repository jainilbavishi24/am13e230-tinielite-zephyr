# Validation record

## Clean repository checks

Performed on 2026-10-17 in WSL Ubuntu 22.04:

- Clean Zephyr source at `9574b65fbaa01aa0c8f418bd7a6b97beb15fcc54`
- GNU Arm Embedded GCC 10.3.1
- Zephyr configure, compile, and link: pass
- Output: 24,604 bytes flash; 43,608 bytes RAM (including a conservative
  32 KiB main stack)
- Python unit tests: 11/11 pass
- ShellCheck and Bash syntax: pass
- Model SHA-256 verification: pass
- ELF inspection: four TINIElite kernels, TI handler, model entry point, and NPU
  memory callbacks present

The environment reports non-fatal warnings for an absent standalone DTC and an
old ccache. Install `device-tree-compiler`; update ccache or disable it to make
the local build log clean.

GitHub Actions run
[`39005309316`](https://github.com/jainilbavishi24/am13e230-tinielite-zephyr/actions/runs/39005309316)
also passed the host suite, clean workspace initialization, Arm firmware
cross-build, linked NPU/IRQ symbol checks, and firmware artifact upload for
commit `ee9293c`.

## Earlier hardware evidence

The original implementation was built, programmed, verified, and exercised on
LP-AM13E230 through XDS110 from WSL. Representative results were:

- sawtooth score `[1, -1, 0]`
- sine score `[0, 1, 0]`
- square score `[0, 0, 1]`
- accelerator wait around 282 us
- CPU/runtime portion around 50 us
- hybrid inference around 340 us

These figures are retained as historical evidence only and must not be quoted
as valid latency. Hardware read-back later proved the CPU was actually running
at 32 MHz while Zephyr converted cycles as if it were 200 MHz. Functional
outputs remain valid; these timing values were understated by approximately
6.25 times.

## Reorganized firmware hardware gate

Status: **passed on 2026-10-16** through XDS110 from WSL.

Acceptance command used:

```bash
ZEPHYR_BASE=/tmp/am13e230-zephyr-clean ./scripts/pipeline.sh
```

The explicit `ZEPHYR_BASE` selected an isolated copy of the pinned upstream
revision because the surrounding legacy workspace also contained an older
in-tree board named `lp_am13e230`.

Results:

- DSLite erase/program/verify: pass.
- One serial session completed all six vectors: pass.
- Exact score comparisons: 6/6 pass (two sawtooth, two sine, two square).
- NPU stage timeouts or board errors: none.
- Accelerator wait: 283-284 us as originally reported.
- Runtime/CPU portion: 45 us as originally reported.
- End-to-end inference: 343 us as originally reported.

During validation, the end-to-end timestamp was moved ahead of profiler UART
prints after the first run showed that those prints had inflated the total to
1,064 us. The corrected image was rebuilt, reprogrammed, verified, and all six
vectors were rerun successfully. The later register audit proved that moving
the timestamp removed UART-print overhead but did not correct the erroneous
32 MHz versus 200 MHz cycle conversion; these timing values are superseded.

## Clock initialization and read-back gate

Status: **passed on 2026-10-17** through XDS110 from WSL.

The first read-only telemetry image reproduced the defect: MCLK was 32 MHz,
the PLL was disabled, and flash used zero wait states while devicetree and
Zephyr timing metadata declared 200 MHz. The implementation was then changed
to match TI SDK 26.01.00.03's generated sequence:

- Set three flash read wait states from a RAM-resident routine.
- Configure the LP-AM13E230 X1/X2 pins and start its 25 MHz crystal.
- Configure PLL `/2` predivide, `x32` feedback, and `/2` CLK0 output.
- Switch MCLK through `/4`, `/2`, and bypass stages to 200 MHz.
- Configure the UART for its resulting 100 MHz bus clock.

Command:

```bash
./scripts/pipeline.sh --clock-status \
  --json-output docs/evidence/hardware_clock_2026-10-17.json
```

Read-back result: pass. Derived MCLK was 200,000,000 Hz, UART configuration was
100,000,000 Hz, flash wait states were three, `SYSPLLCFG0=0x00000031`,
`SYSPLLCFG1=0x00001f01`, and all required validation flags (`0x1f`) were set.
Raw evidence is retained in
[`evidence/hardware_clock_2026-10-17.json`](evidence/hardware_clock_2026-10-17.json).

## Polling protocol and stress baseline

Status: **passed on 2026-10-17** through XDS110 from WSL.

The current framed protocol was rebuilt, erased, programmed, verified, and
tested with:

```bash
ZEPHYR_BASE=/tmp/am13e230-zephyr-clean \
  ./scripts/pipeline.sh --fault-test --json-output /tmp/protocol.json
./scripts/test.sh --repeat 100 --quiet --fault-test \
  --json-output docs/evidence/hardware_stress_2026-10-17.json
```

Results:

- Deliberately corrupted CRC: rejected with the expected structured error.
- Recovery after the corrupt request: pass, without resetting the board.
- Acceptance regression: 6/6 exact vectors, zero transport retries.
- Stress regression: 600/600 exact vectors, zero transport retries.
- Accelerator latency: 509 us minimum, 510 us median and p95, 510 us maximum.
- Runtime/CPU latency: 128 us median and p95, 140 us maximum.
- End-to-end latency: 666 us minimum, 668 us median and p95, 679 us maximum.

Every stress result and its score/timing data is retained in
[`evidence/hardware_stress_2026-10-17.json`](evidence/hardware_stress_2026-10-17.json).
These were the clock-validated polling baseline. The interrupt-driven result
below supersedes it for the current firmware.

## Interrupt-driven completion and stress gate

Status: **passed on 2026-10-17** through XDS110 from WSL.

Protocol v2 replaced CTL5 polling with a driver-owned IRQ 41 handler. The ISR
checks masked DONE status, clears the IP interrupt, increments an atomic
completion counter, and signals a semaphore. The application performs the TI
runtime continuation in thread context and enforces a 100 ms wait deadline.

The flashed image was verified with:

```bash
./scripts/test.sh --fault-test --repeat 100 --quiet \
  --json-output docs/evidence/hardware_irq_stress_2026-10-17.json
./scripts/test.sh --clock-status \
  --json-output docs/evidence/hardware_irq_clock_2026-10-17.json
```

Results:

- DSLite erase/program/verify: pass.
- Deliberately corrupted CRC and following recovery transaction: pass.
- Stress regression: 600/600 exact vectors, zero transport retries.
- Hardware DONE interrupts: exactly five per inference, 3,000 total.
- Spurious TINIElite interrupts: zero.
- Accelerator wait: 554 us minimum, median, p95, and maximum.
- Runtime/CPU portion: 117 us minimum, median, p95, and maximum.
- End-to-end latency: 689 us minimum, median, p95, and maximum.
- Same-image clock read-back: 200 MHz MCLK, 100 MHz UART clock, three flash
  wait states, required validation flags `0x1f`.

Raw per-inference and clock-register evidence is retained in
[`evidence/hardware_irq_stress_2026-10-17.json`](evidence/hardware_irq_stress_2026-10-17.json)
and
[`evidence/hardware_irq_clock_2026-10-17.json`](evidence/hardware_irq_clock_2026-10-17.json).

## NPU timeout and reset recovery gate

Status: **passed on 2026-10-17** through XDS110 from WSL.

The test-only `NPU_STALL_REQUEST` entered the same semaphore wait used by a
normal hardware stage without starting TINIElite. The board returned structured
inference error `-ETIMEDOUT` (`-116` in Zephyr's errno ABI), drained UART,
performed a cold system reset, rebooted, and emitted a fresh valid `READY`.
CRC corruption/recovery was exercised in the same session. The host then ran
600 normal inferences to prove that accelerator and opaque model-runtime state
were clean after reset.

Results:

- NPU stall detection, error response, cold reset, and restored readiness: pass.
- CRC rejection and recovery before the stall: pass.
- Post-reset regression: 600/600 exact results, zero transport retries.
- Hardware interrupts: 3,000 completions, zero spurious entries.
- Current-image latency: 554 us accelerator wait, 129 us runtime/CPU, 701 us
  end-to-end (minimum, median, p95, and maximum were identical in this run).

Machine-readable evidence, including explicit pass fields for both injected
faults, is retained in
[`evidence/hardware_recovery_2026-10-17.json`](evidence/hardware_recovery_2026-10-17.json).
