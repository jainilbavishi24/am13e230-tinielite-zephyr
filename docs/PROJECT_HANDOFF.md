# Project handoff — AM13E230 TINIElite Edge AI on Zephyr

This is the authoritative operational handoff for a new engineer or coding
agent. It covers the current implementation, evidence, limits, and commands.

**Repository:** https://github.com/jainilbavishi24/am13e230-tinielite-zephyr
**Branch:** main
**Validated environment:** WSL 2 / Ubuntu 22.04, GNU Arm Embedded GCC 10.3.1,
TI UniFlash 9.7, LP-AM13E230 LaunchPad and its XDS110
**Baseline at creation:** 176ef09 — Add comprehensive project explanation PDFs

## 1. Authority and reading order

Read these before changing firmware behavior:

1. This handoff: task context, safe operations, commands, troubleshooting.
2. [README.md](../README.md): overview and normal setup.
3. [ARCHITECTURE.md](ARCHITECTURE.md): execution and hardware design.
4. [PROTOCOL.md](PROTOCOL.md): byte-level host/firmware contract.
5. [QUALITY_GATES.md](QUALITY_GATES.md), [VALIDATION.md](VALIDATION.md):
   demonstrated results and retained evidence.
6. [AUDIT.md](AUDIT.md), [ROADMAP.md](ROADMAP.md): critical review and future work.

The old project_knowledge_transfer.md one directory *above* this repository is
historical input from the early prototype. It is superseded: it predates the
final protocol, genuine NPU IRQ path, clock repair, watchdog, reorganization,
and corrected timing. Do not use it as implementation authority or alter it
without explicit owner approval.

The PDFs in [explanation/](../explanation/README.md) are human interview/study
material. This Markdown file is the agent-ready source of truth.

## 2. Project in plain terms

~~~text
256 host waveform samples (float)
 -> generated normalization and int8 quantization
 -> USB UART, framed protocol v2
 -> Zephyr application on AM13E230 Cortex-M33
 -> generated TVM/TI hybrid graph:
      CPU orchestration + supported TINIElite NPU stages
 -> three signed scores: sawtooth, sine, square
 -> UART result: scores, timings, NPU IRQ diagnostics
~~~

Inference runs on the physical MCU; no cloud participates. The supplied model
takes int8 shape 1 x 1 x 256 x 1 and produces three int8 scores. Host
preprocessing uses generated bias -70.02075, scale 187.0, shift 6, truncation,
and int8 clipping.

AM13E230 is not supported by pinned upstream Zephyr. This repository therefore
implements an out-of-tree board/SoC port plus DTS, pinctrl, UART, clock,
watchdog, NPU, WSL, host tool, test, and CI integration—without modifying
upstream Zephyr.

## 3. Honest claims

### Supported

- A licensed generated TVM/TI binary archive, mod.a, is integrated with Zephyr
  and the AM13E230 TINIElite NPU.
- The project supplies the out-of-tree platform port, robust protocol/recovery,
  WSL-native build/flash/test flow, host client, tests, and CI.
- Six supplied golden fixtures gave exact physical-board score vectors. A
  recovery test completed 600/600 repeated inferences with zero retries.
- The current image recorded five acknowledged NPU DONE IRQs per inference:
  3,000 completions and zero spurious entries in that run.
- Hardware tests covered CRC recovery, NPU timeout/cold reset, watchdog
  starvation/reset-cause, UART BREAK recovery, and post-reset inference.
- Clock read-back verified 200 MHz MCLK, 100 MHz UART source, three flash waits.
- Recovery-enabled median timing: 554 us NPU wait, 129 us runtime/CPU portion,
  701 us end-to-end. Conditions and evidence: VALIDATION.md.

### Never claim

- “100% accuracy”: six regression fixtures are not an independent evaluation.
- Model training, model generation/regeneration, or independent model testing:
  source model/training/generation inputs are unavailable.
- Production-ready, certified, or verified for all workloads.
- NPU-vs-CPU speedup, a wholly NPU graph, power saving, or total CPU
  utilization: CPU-equivalent model and measurement instruments are absent.
- Historical 282 us / 340 us latency: it used 200 MHz conversion while the MCU
  was actually 32 MHz, so those timing numbers are invalid.

Resume-safe version:

> Built an out-of-tree Zephyr port and WSL-native build/flash/test workflow for
> TI's preview AM13E230 Cortex-M33 MCU; integrated a TVM-generated hybrid
> TINIElite NPU model and verified accelerator symbols and on-board inference
> over a custom UART regression protocol. Six golden vectors and 600 repeated
> recovery-test inferences passed with five acknowledged DONE IRQs per
> inference, zero spurious IRQs, CRC recovery, NPU-timeout reset recovery,
> watchdog reset validation, and 200 MHz clock read-back.

## 4. Completion state

| Area | State |
|---|---|
| Out-of-tree platform, build, hashes, symbols | Passed baseline |
| Protocol: version/length/sequence/CRC/errors/resync | Passed |
| Six exact fixtures and repeated regression | Passed |
| Explicit clock setup and read-back | Passed |
| NPU timeout/cold reset and WWDT0 recovery | Passed |
| CI, host tests, native ASan/UBSan ztests, static checks | Passed baseline |
| UART pinctrl/error reporting | Passed; transfer remains polling |
| Independent accuracy evaluation | External input required |
| CPU baseline, power, exact utilization | External inputs/instrumentation required |
| Zephyr-upstream-quality split | Pending |

[QUALITY_GATES.md](QUALITY_GATES.md) is the live acceptance matrix.

## 5. Hardware facts

| Item | Value |
|---|---|
| Board / MCU | LP-AM13E230; AM13E23019 Cortex-M33 |
| XDS110 | USB VID:PID 0451:bef3 |
| Flash / primary SRAM | 512 KiB at 0x00000000; 96 KiB at 0x20000000 |
| Separate SRAM | 32 KiB at 0x00c18000, not contiguous linked RAM |
| MCLK | 200 MHz from 25 MHz crystal and PLL /2 * 32 /2 |
| UART | data/control 0x40601000; wrapper 0x40632000; PA0 TX, PA1 RX; 115200; 100 MHz source |
| NPU | base 0x408ff000; CTL5 +0x1120; instr +0x2000 (256 words); param +0x2800 (512 words); IRQ 41 |
| Watchdog | WWDT0 0x400d0000; 32.768 kHz; four seconds |
| Model | models/waveform_classifier/artifacts/mod.a plus header and six fixtures |
| Key exports | tvmgen_default_run, tvmgen_default_finished, TI_NPU_NNC_IRQHandler |

Do not confuse the UART data/control and wrapper address blocks. The model
callbacks for NPU-memory writes return void: bounds problems can be logged but
cannot be returned through the opaque generated runtime. A proper fix needs a
compatible regenerated model/runtime interface, which is not available.

## 6. Source map and design rules

| Path | Responsibility |
|---|---|
| app/src/main.c | single-request server, dispatch |
| app/src/app_npu.c | generated runtime, 100 ms waits, semaphore, NPU metrics |
| app/src/app_uart.c / app_protocol.c | framed polling transport, validation, CRC32 |
| app/src/app_clock.c / app_watchdog.c | clock read-back; WWDT0 control |
| boards/, soc/, dts/ | out-of-tree board/SoC/startup/bindings/pinctrl |
| soc/ti/am13x/clock.c | PRE_KERNEL_1 clock tree, RAM-resident flash configuration |
| drivers/serial/, drivers/misc/tinyengine/ | UNICOMM and NPU callback/ISR/semaphore drivers |
| models/waveform_classifier/ | licensed archive/header/fixtures/SHA: immutable input |
| tools/send_tensor.py | quantization, client, fixtures/faults, JSON evidence |
| tests/ | Python tests and native_sim protocol ztests |
| scripts/ | build, flash, test, quality, WSL USB setup |
| config/AM13E23019_Zephyr.ccxml | XDS110/DSLite configuration |
| docs/evidence/ | machine-readable board evidence |

One request is processed at a time by design. It serializes opaque model state,
READY ordering, recovery, timing, and watchdog feeds. NPU completion remains
real IRQ-driven: ISR acknowledges DONE, atomically increments a count, and gives
a semaphore; continuation runs in thread context. Host rejects zero completions
or nonzero spurious interrupts. A timeout returns an error, drains UART, and
cold-resets because runtime state is opaque. WWDT0 is fed only by main-loop
forward progress.

## 7. Protocol v2

All multi-byte values are little-endian.

~~~text
magic 5a a5 | version 02 | type | uint16 sequence | uint16 length
payload | uint32 IEEE CRC-32
~~~

CRC covers version through payload, excluding magic/CRC; it is reflected IEEE
CRC-32 (0xedb88320, initial/final xor 0xffffffff), matching binascii.crc32.

| Type | Meaning |
|---:|---|
| 0x01 | 256-byte signed-int8 inference request |
| 0x02 / 0x05 | clock status / watchdog status request |
| 0x03 / 0x04 | NPU stall / watchdog stall; diagnostic builds only |
| 0x80 / 0x81 | READY / ACK |
| 0x82 | RESULT: three int8 scores plus accel/runtime/total us, completions, spurious counts |
| 0x83 / 0x84 | clock status / watchdog status |
| 0xff | ERROR: code plus signed int16 detail |

Errors: 1 timeout, 2 version, 3 type, 4 length, 5 CRC, 6 inference, 7 internal,
8 UART transport. A frame has one absolute one-second receive deadline. Both
host and firmware resynchronize after damaged frames. Read PROTOCOL.md before
changing any wire behavior.

## 8. Fresh WSL setup and software checks

Use a **clean** west workspace. An old surrounding Zephyr tree had a duplicate
board and unrelated edits; do not use it.

~~~bash
sudo apt-get update
sudo apt-get install --no-install-recommends -y \
  clang-format cmake cppcheck device-tree-compiler gcc-arm-none-eabi \
  gcc-multilib gperf ninja-build python3-venv shellcheck

mkdir -p ~/am13e230-workspace
cd ~/am13e230-workspace
git clone https://github.com/jainilbavishi24/am13e230-tinielite-zephyr.git
python3 -m venv .venv
. .venv/bin/activate
python -m pip install west
west init -l am13e230-tinielite-zephyr
west update
python -m pip install -r zephyr/scripts/requirements.txt
python -m pip install -r am13e230-tinielite-zephyr/requirements.txt
python -m pip install -r am13e230-tinielite-zephyr/requirements-dev.txt
cd am13e230-tinielite-zephyr
~~~

TI UniFlash Linux 9.7 is only needed to flash hardware. Default location:
~/ti/uniflash_9.7.0; otherwise set TI_UNIFLASH_ROOT or DSLITE_LINUX_PATH.

~~~bash
git status --short --branch
git log -1 --oneline
(cd models/waveform_classifier && sha256sum --check SHA256SUMS)
ruff check tools tests
ruff format --check tools tests
python -m unittest discover -s tests -v
./scripts/static_check.sh
shellcheck scripts/*.sh
./scripts/build.sh
~~~

Run Zephyr-native tests from the **west workspace root**:

~~~bash
ZEPHYR_TOOLCHAIN_VARIANT=host west twister \
  -T am13e230-tinielite-zephyr/tests/protocol \
  -p native_sim --inline-logs --enable-asan --enable-ubsan
~~~

## 9. XDS110 attachment, build, and test

In **elevated Windows PowerShell**, identify USB 0451:bef3. Replace 4-3 with the
actual BUSID; do not type placeholder brackets.

~~~powershell
& "C:\Program Files\usbipd-win\usbipd.exe" list
& "C:\Program Files\usbipd-win\usbipd.exe" bind --force --busid 4-3
& "C:\Program Files\usbipd-win\usbipd.exe" attach --wsl --busid 4-3
~~~

bind normally persists; attach is commonly required after a replug/restart. If
already attached, verify in WSL rather than attaching repeatedly.

Once per WSL machine:

~~~bash
./scripts/setup_xds110_wsl.sh
# Open a new WSL shell, then:
lsusb
ls -l /dev/ttyACM* /dev/serial/by-id/
~~~

The client uses TINI_UART_PORT if set, then a lexical by-id port, then
/dev/ttyACM0. Do not commit private serial paths.

Build, flash, and run fixtures:

~~~bash
cd ~/am13e230-workspace
. .venv/bin/activate
cd am13e230-tinielite-zephyr
./scripts/build.sh
./scripts/flash.sh
./scripts/test.sh
# or: ./scripts/pipeline.sh
~~~

Output is build/zephyr/zephyr.hex. After flash, a client may miss the first
READY; press the board RESET once and rerun. This explained a previous apparent
indefinite wait; it is not automatically a deadlock.

Hardware acceptance commands intentionally reset/stall the board:

~~~bash
./scripts/test.sh --clock-status --json-output /tmp/am13e230-clock.json
./scripts/test.sh --fault-test --repeat 100 --quiet \
  --json-output /tmp/am13e230-stress.json
./scripts/test.sh --fault-test --npu-fault-test --watchdog-fault-test \
  --repeat 100 --quiet --json-output /tmp/am13e230-recovery.json
~~~

The last command needs diagnostic-only app/prj.conf options
CONFIG_APP_NPU_FAULT_INJECTION=y and CONFIG_APP_WATCHDOG_FAULT_INJECTION=y.
Disable them in deployment configurations. Changed hardware behavior requires
reviewed JSON in docs/evidence/ and a VALIDATION.md update.

## 10. Troubleshooting and acceptance rules

| Symptom | Safe next action |
|---|---|
| usbipd not found | New elevated PowerShell or full executable path. |
| PowerShell BUSID parse error | Do not type angle brackets; replace 4-3 with actual BUSID. |
| Already attached | Check usbipd list and WSL lsusb; do not repeatedly attach. |
| No XDS110 in WSL | Re-list, bind/attach actual 0451:bef3 after replug. |
| tty permission denied | Run setup_xds110_wsl.sh, new WSL shell, reconnect USB. |
| No READY after flash | Press RESET once, rerun client. |
| DSLite missing | Install UniFlash 9.7 or set TI_UNIFLASH_ROOT / DSLITE_LINUX_PATH. |
| Missing CMSIS | From west topdir: west update cmsis cmsis_6 |
| Duplicate board / odd DTS | Clean workspace; never copy board into upstream Zephyr. |
| Zero/spurious NPU IRQs | Stop claims; pristine build and inspect NPU IRQ enable/clear/ISR, app_npu, symbols. |

| Change | Required checks |
|---|---|
| Docs only | git diff --check and link/command review; no unproven claim updates. |
| Python/parser | Ruff, format, Python tests; native ztests for framing. |
| Protocol | Above plus native ztests and physical CRC/recovery where possible; update PROTOCOL.md. |
| App/driver/DTS | Static checks, clean build/symbols; physical pipeline and relevant fault/clock gate. |
| Clock/reset/watchdog | Build plus physical clock/recovery test; update evidence/VALIDATION.md. |
| Model artifacts | Do not edit without explicit owner authority, licence, and new hashes. |
| CI | Equivalent local checks, then wait for remote success before claiming it. |

Normal pre-push:

~~~bash
ruff check tools tests
ruff format --check tools tests
python -m unittest discover -s tests -v
./scripts/static_check.sh
shellcheck scripts/*.sh
./scripts/build.sh
git diff --check
~~~

## 11. Evidence, remaining work, and agent rules

Key files:

| File | Meaning |
|---|---|
| docs/evidence/hardware_clock_2026-10-17.json | 200 MHz MCLK, 100 MHz UART, flash waits |
| docs/evidence/hardware_irq_stress_2026-10-17.json | 600 runs, five IRQs/run, zero spurious |
| docs/evidence/hardware_recovery_2026-10-17.json | CRC recovery, NPU timeout/cold reset, 600 post-reset |
| docs/evidence/hardware_uart_pinctrl_2026-10-17.json | UART BREAK/reopen/recovery |
| docs/evidence/hardware_stress_2026-10-17.json | Clock-valid historical polling comparison |

Prioritized future work: independent labelled model evaluation; CPU/power/trace
benchmarking; long-soak/reset/brownout/UART fault testing; async UART with full
regression coverage; reusable AM13x split/upstream work; digest-pinned CI image.
Write measurable acceptance criteria first; do not guess around external-input
limitations.

Rules:

1. Start with git status --short --branch. Preserve user changes; never reset a
   dirty tree.
2. Never patch upstream Zephyr or copy this board into it to make a build pass.
3. Do not modify mod.a, generated headers, fixtures, hashes, or licences without
   explicit authority; never reverse engineer/recreate model artifacts.
4. Keep waits/retries bounded and test protocol changes across host, ztest,
   firmware, and docs.
5. Never claim hardware/CI/timing/accuracy success without exact evidence.
6. Do not commit build output, virtualenvs, logs, private serial paths, or
   unreviewed evidence.

## 12. Copy-ready prompt for another chat

~~~text
You are continuing the AM13E230 TINIElite Zephyr repository. Read
docs/PROJECT_HANDOFF.md fully, then README.md, docs/ARCHITECTURE.md,
docs/PROTOCOL.md, docs/QUALITY_GATES.md, docs/VALIDATION.md, docs/AUDIT.md,
and docs/ROADMAP.md. This handoff is operational authority; the old transfer
file outside the repository is historical and superseded.

Before editing, run git status --short --branch and preserve user changes. This
is an out-of-tree Zephyr project: never patch upstream Zephyr. The licensed
binary model archive is immutable unless authority and new licence/hash details
are provided.

Use accurate scope: this is hardware-validated on-board NPU integration and
regression testing, not model training, production certification, or an
independent accuracy study. Do not quote invalid 282/340 us historical timing.
Run relevant local checks in PROJECT_HANDOFF.md; for hardware changes use its
WSL/XDS110 attach, flash, and evidence procedure. Ask before destructive Git
actions, model changes, external publication, or scope expansion. Report
changed paths, tests actually run, and what remains unverified.

My next task is: [replace with task].
~~~

When handing over a future task, state changed paths, why, exact checks and
outcomes, whether hardware was connected, evidence paths/tool versions/commit,
unverified portions, and any required user action such as XDS110 reattach or
one RESET press after flashing.
