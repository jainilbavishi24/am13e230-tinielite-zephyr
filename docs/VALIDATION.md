# Validation record

## Clean repository checks

Performed on 2026-10-17 in WSL Ubuntu 22.04:

- Clean Zephyr source at `9574b65fbaa01aa0c8f418bd7a6b97beb15fcc54`
- GNU Arm Embedded GCC 10.3.1
- Zephyr configure, compile, and link: pass
- Output: 22,520 bytes flash; 43,520 bytes RAM (including a conservative
  32 KiB main stack)
- Python unit tests: 7/7 pass
- ShellCheck and Bash syntax: pass
- Model SHA-256 verification: pass
- ELF inspection: four TINIElite kernels, TI handler, model entry point, and NPU
  memory callbacks present

The environment reports non-fatal warnings for an absent standalone DTC and an
old ccache. Install `device-tree-compiler`; update ccache or disable it to make
the local build log clean.

## Earlier hardware evidence

The original implementation was built, programmed, verified, and exercised on
LP-AM13E230 through XDS110 from WSL. Representative results were:

- sawtooth score `[1, -1, 0]`
- sine score `[0, 1, 0]`
- square score `[0, 0, 1]`
- accelerator wait around 282 us
- CPU/runtime portion around 50 us
- hybrid inference around 340 us

These figures are retained as historical evidence only. The measurement uses
Zephyr cycle conversion configured for 200 MHz and must be repeated after
clock read-back/initialization is verified.

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
- Accelerator wait: 283-284 us.
- Runtime/CPU portion: 45 us.
- End-to-end inference: 343 us.

During validation, the end-to-end timestamp was moved ahead of profiler UART
prints after the first run showed that those prints had inflated the total to
1,064 us. The corrected image was rebuilt, reprogrammed, verified, and all six
vectors were rerun successfully. Timing remains subject to the clock-tree
verification caveat described above.

## Protocol and stress gate

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
- Accelerator latency: 284 us minimum, 286 us median and p95, 286 us maximum.
- Runtime/CPU latency: 46 us median, 51 us maximum.
- End-to-end latency: 343 us minimum, 345 us median and p95, 349 us maximum.

Every stress result and its score/timing data is retained in
[`evidence/hardware_stress_2026-10-17.json`](evidence/hardware_stress_2026-10-17.json).
Latency remains provisional until the clock configuration is explicitly read
back and verified.
