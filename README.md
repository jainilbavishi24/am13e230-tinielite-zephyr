# AM13E230 TINIElite inference on Zephyr

An out-of-tree Zephyr board, SoC, UART driver, TINIElite adapter, and hardware
inference demo for the Texas Instruments LP-AM13E230 LaunchPad. A generated
TVM/TI model classifies 256-element feature tensors as sawtooth, sine, or
square waveforms.

> Project status: hardware-validated engineering prototype under systematic
> hardening. It is suitable for a portfolio or resume when described with the
> limitations below; it is not yet a production inference platform.

## What is demonstrated

- Custom Zephyr support for the preview AM13E23019 Cortex-M33 device and board.
- Explicit TI-aligned 200 MHz PLL startup, flash wait-state setup, and
  register read-back validation.
- A polling-mode UNICOMM UART driver and versioned, CRC32-protected protocol.
- TI TINIElite power/reset/privilege setup aligned with TI's AM13E2x SDK.
- A linked accelerator model containing four TINIElite hardware kernels.
- Native WSL build, native Linux UniFlash/DSLite programming, and UART testing.
- Host regression tooling that checks exact outputs for all six supplied
  golden vectors and returns a nonzero status on failure.
- Structured device errors, sequence validation, bounded transport retries,
  protocol fault injection, stress runs, and JSON evidence output.

The reorganized implementation has been erased, programmed, verified, and run
on the LaunchPad. All six supplied vectors produced their exact golden scores,
and a subsequent 600-inference stress run completed with no failures or
transport retries. Under the read-back-validated 200 MHz configuration, median
end-to-end inference time was 668 us. See
[docs/VALIDATION.md](docs/VALIDATION.md) for the recorded evidence and caveats.

## Architecture

```text
Python host ──versioned CRC32 frame──> Zephyr application
                                             │
                              generated TVM/TI runtime
                                  │                 │
                             TINIElite NPU       CPU stages
                                  └────────┬────────┘
                                           │
Python host <──framed scores + timing──── UART
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for memory maps and execution
details. The byte-level wire contract is in
[docs/PROTOCOL.md](docs/PROTOCOL.md).

## Repository layout

```text
app/                 Zephyr inference server application
boards/              LP-AM13E230 board definition
soc/                  AM13E23019 SoC definition
dts/                  SoC nodes and custom bindings
drivers/              TINIElite adapter and UNICOMM UART driver
models/               One active generated model and six regression fixtures
tools/                Python hardware regression client
scripts/              Build, flash, WSL USB setup, and pipeline commands
config/               TI debug-probe target configuration
tests/                Host-side unit tests
docs/                 Audit, design, validation evidence, and roadmap
```

## Fresh workspace setup

The manifest pins Zephyr to commit
`9574b65fbaa01aa0c8f418bd7a6b97beb15fcc54` and fetches only the required CMSIS
modules.

```bash
mkdir am13e230-workspace && cd am13e230-workspace
git clone <YOUR_REPOSITORY_URL> am13e230-tinielite-zephyr
python3 -m venv .venv
. .venv/bin/activate
pip install west
west init -l am13e230-tinielite-zephyr
west update
pip install -r zephyr/scripts/requirements.txt
pip install -r am13e230-tinielite-zephyr/requirements.txt
```

Use a fresh west workspace. A downstream Zephyr tree that already defines an
`lp_am13e230` board will conflict with this repository's out-of-tree board of
the same name.

Install CMake, Ninja, Device Tree Compiler, and an Arm GNU Embedded toolchain.
The validated local build used GCC 10.3.1. If `west` is not on `PATH`, set
`WEST_BIN=/absolute/path/to/west`.

## WSL hardware access

In an elevated Windows PowerShell, bind and attach the XDS110 device using its
actual BUSID (do not type angle brackets):

```powershell
& "C:\Program Files\usbipd-win\usbipd.exe" list
& "C:\Program Files\usbipd-win\usbipd.exe" bind --force --busid 4-3
& "C:\Program Files\usbipd-win\usbipd.exe" attach --wsl --busid 4-3
```

Then in WSL:

```bash
./scripts/setup_xds110_wsl.sh
```

The Linux release of TI UniFlash is required for native WSL flashing. By
default the scripts expect it at `~/ti/uniflash_9.7.0`; override this with
`TI_UNIFLASH_ROOT`.

## Build, flash, and validate

```bash
./scripts/build.sh
./scripts/flash.sh
./scripts/test.sh
```

Or run all three:

```bash
./scripts/pipeline.sh
```

If the test reports that `READY` was not received, press the LaunchPad RESET
button once. The host now times out with this instruction instead of waiting
forever. `scripts/test.sh` keeps one serial connection open and runs all six
vectors sequentially.

Run protocol fault injection and a 600-inference stress test with:

```bash
./scripts/test.sh --fault-test --repeat 100 --quiet \
  --json-output docs/evidence/hardware_stress.json
```

Read back and validate the active clock tree independently of inference with:

```bash
./scripts/test.sh --clock-status \
  --json-output docs/evidence/hardware_clock.json
```

## Honest project claims

Good resume wording:

> Built out-of-tree Zephyr support and a WSL-native build/flash/test workflow
> for TI's preview AM13E230 Cortex-M33 MCU; integrated a TVM-generated hybrid
> TINIElite NPU model and verified accelerator symbols and on-board inference
> over a custom UART regression protocol.

Avoid claiming “100% model accuracy,” “interrupt-driven NPU,” “production
ready,” or “CI-tested firmware.” The present evidence includes six golden
regression vectors repeated successfully over 600 inferences, CRC fault
recovery, explicit/read-back-validated 200 MHz clock setup, polled accelerator
completion, host-only CI, and prototype hardware validation. See
[docs/QUALITY_GATES.md](docs/QUALITY_GATES.md) for the live
completion matrix and [docs/AUDIT.md](docs/AUDIT.md) for the assessment.

## Licensing

Project-authored source is Apache-2.0. Generated model artifacts and fixtures
retain their separate terms in
[models/waveform_classifier/LICENSE.txt](models/waveform_classifier/LICENSE.txt).
Review [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) before publishing a fork.
