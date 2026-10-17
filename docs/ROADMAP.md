# Roadmap

## P0 — publishable hardware baseline

- [x] Explicitly initialize and read back the 200 MHz MCLK, 100 MHz UART bus
  clock, PLL state, and flash wait states.
- [ ] Install Device Tree Compiler and remove avoidable build warnings.
- [x] Confirm that the model and golden data may be published by their owner.

## P1 — correctness and reliability

- [x] Replace the additive checksum with a versioned frame containing length,
  sequence number, and CRC-16/CRC-32.
- [x] Add bounded retry/resynchronization behavior and structured device errors.
- [x] Hardware-validate TINIElite IRQ 41 completion, including IP mask/status/
  clear handling and completion/spurious counters.
- [ ] Measure CPU utilization and formally compare it with the retained polling
  latency baseline.
- [ ] Add watchdog recovery.
- [x] Add repeated/stress inference tests with machine-readable results.
- [ ] Move UART pin routing to standard Zephyr pinctrl and implement error flags.

## P2 — evidence and automation

- [x] Add and remotely validate the GitHub Actions firmware cross-build, ELF
  symbol checks, and build-artifact publication.
- [ ] Pin a redistributable build-container digest for stronger toolchain
  reproducibility.
- [ ] Add static analysis and Zephyr Twister tests for protocol/state logic.
- [ ] Validate on an independent labeled dataset and report confusion matrix,
  per-class precision/recall, dataset provenance, and preprocessing.
- [ ] Benchmark warm-up, distribution, jitter, CPU-only baseline, NPU utilization,
  power, and binary/RAM footprints under a verified clock configuration.

## P3 — upstream-quality port

- [ ] Separate reusable AM13x SoC support from the demo application.
- [ ] Replace remaining raw control-register setup with reviewed clock/reset/power
  abstractions.
- [ ] Add UART interrupt/async support and broader peripheral tests.
- [ ] Prepare board/SoC/driver patches that meet Zephyr contribution requirements.
