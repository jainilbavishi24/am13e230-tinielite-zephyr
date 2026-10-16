# Roadmap

## P0 — publishable hardware baseline

- Read and log the effective CPU/MCLK and UART clock configuration.
- Install Device Tree Compiler and remove avoidable build warnings.
- Confirm that the model and golden data may be published by their owner.

## P1 — correctness and reliability

- Replace the additive checksum with a versioned frame containing length,
  sequence number, and CRC-16/CRC-32.
- Add bounded retry/resynchronization behavior and structured device errors.
- Implement actual TINIElite interrupt completion, including IP mask/status/
  clear handling, then compare CPU utilization and latency with polling.
- Add watchdog recovery and repeated/stress inference tests.
- Move UART pin routing to standard Zephyr pinctrl and implement error flags.

## P2 — evidence and automation

- Add a reproducible firmware CI container with the supported Arm toolchain.
- Add static analysis and Zephyr Twister tests for protocol/state logic.
- Validate on an independent labeled dataset and report confusion matrix,
  per-class precision/recall, dataset provenance, and preprocessing.
- Benchmark warm-up, distribution, jitter, CPU-only baseline, NPU utilization,
  power, and binary/RAM footprints under a verified clock configuration.

## P3 — upstream-quality port

- Separate reusable AM13x SoC support from the demo application.
- Replace remaining raw control-register setup with reviewed clock/reset/power
  abstractions.
- Add UART interrupt/async support and broader peripheral tests.
- Prepare board/SoC/driver patches that meet Zephyr contribution requirements.
