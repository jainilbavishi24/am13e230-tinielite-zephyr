# Contributing

Contributions should preserve the out-of-tree layout and the pinned west
baseline. Do not copy project files into the upstream Zephyr checkout, commit
build output, or modify generated model artifacts without updating their
license and SHA-256 manifest.

## Development setup

Follow the clean-workspace instructions in [README.md](README.md), activate the
workspace virtual environment, and install both dependency sets:

```bash
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Required checks

Run these checks before opening a pull request:

```bash
ruff check tools tests
ruff format --check tools tests
python -m unittest discover -s tests -v
./scripts/static_check.sh
shellcheck scripts/*.sh
./scripts/build.sh
```

Protocol changes must also pass the sanitized Zephyr-native suite from the west
workspace root:

```bash
ZEPHYR_TOOLCHAIN_VARIANT=host west twister \
  -T am13e230-tinielite-zephyr/tests/protocol \
  -p native_sim --inline-logs --enable-asan --enable-ubsan
```

## Hardware-facing changes

Changes to the SoC, clock, devicetree, pinctrl, UART, TINIElite driver,
watchdog, generated-runtime integration, or wire protocol require physical
board validation:

```bash
./scripts/pipeline.sh
./scripts/test.sh --fault-test --repeat 100 --quiet
./scripts/test.sh --clock-status
```

Update [docs/VALIDATION.md](docs/VALIDATION.md) and add machine-readable
evidence under `docs/evidence/` when a change alters hardware behavior,
latency, memory footprint, or recovery semantics. Record the board, probe
firmware, tool versions, commit, commands, and complete result summary.

## Review expectations

- Keep register constants traceable to a TI SDK or reference-manual revision.
- Put hardware description in devicetree instead of application code when the
  data is board- or SoC-specific.
- Bound waits and retries; do not introduce unbounded failure paths.
- Preserve structured errors and sequence validation across protocol changes.
- Treat the six bundled vectors as regression fixtures, not an accuracy study.
- Keep commits focused and update documentation in the same change as behavior.
