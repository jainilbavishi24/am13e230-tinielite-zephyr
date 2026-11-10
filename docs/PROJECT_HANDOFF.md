# Project handoff — AM13E230 TINIElite Edge AI on Zephyr

This is the authoritative operational handoff for a new engineer or coding
agent. It covers the current implementation, evidence, limits, and commands.

**Repository:** https://github.com/jainilbavishi24/am13e230-tinielite-zephyr
**Branch:** main
**Validated environment:** WSL 2 / Ubuntu 22.04, GNU Arm Embedded GCC 10.3.1,
TI UniFlash 9.7, LP-AM13E230 LaunchPad and its XDS110
**Current-state rule:** run `git log -1 --oneline`; do not assume an old handoff
hash is the checked-out revision. The model-package/v3 software and physical
gates were last run on 2026-11-10. At handoff time these changes and evidence
were intentionally still uncommitted; inspect `git status` before proceeding.

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
selected package fixture (waveform or six-channel electrical window)
 -> package-declared preprocessing (affine int8 or identity float32)
 -> USB UART, framed protocol v3 with model identity/sizes/types
 -> Zephyr application on AM13E230 Cortex-M33
 -> generated TVM/TI hybrid graph:
      CPU orchestration + supported TINIElite NPU stages
 -> selected output tensor (three waveform or six electrical-fault scores)
 -> UART result: scores, timings, NPU IRQ diagnostics
~~~

Inference runs on the physical MCU; no cloud participates. The default waveform
model takes int8 shape 1 x 1 x 256 x 1 and produces three int8 scores. Host
preprocessing uses generated bias -70.02075, scale 187.0, shift 6, truncation,
and int8 clipping. The second `electrical_fault_6class` model takes float32
shape 1 x 6 x 128 x 1 (Ia, Ib, Ic, Va, Vb, Vc), uses Simple Window identity
preprocessing, and produces six int8 scores.

AM13E230 is not supported by pinned upstream Zephyr. This repository therefore
implements an out-of-tree board/SoC port plus DTS, pinctrl, UART, clock,
watchdog, NPU, WSL, host tool, test, and CI integration—without modifying
upstream Zephyr.

The application is build-time model-package selectable. `model.json` provides
identity, tensor, artifact, and generated-runtime ABI metadata. CMake validates
that metadata and generates the small C adapter which isolates vendor names;
there is no hand-written per-model C file. It is not a runtime loader for
arbitrary `.a` files. Read
[MODEL_PACKAGES.md](MODEL_PACKAGES.md) before adding or selecting another model.

## 3. Honest claims

### Supported

- Two licensed generated TVM/TI `mod.a` archives are integrated behind the same
  Zephyr and AM13E230 TINIElite NPU path.
- The project supplies the out-of-tree platform port, robust protocol/recovery,
  WSL-native build/flash/test flow, host client, tests, and CI.
- Both current protocol-v3 packages passed physical acceptance on 2026-11-10.
  Each completed 600/600 exact repeated fixtures with zero transport retries.
- Waveform recorded five acknowledged NPU DONE IRQs per inference; electrical
  fault recorded eight. Both had zero spurious entries across 600 runs.
- Hardware tests covered CRC recovery, NPU timeout/cold reset, watchdog
  starvation/reset-cause, UART BREAK recovery, and post-reset inference.
- Clock read-back verified 200 MHz MCLK, 100 MHz UART source, three flash waits.
- Current median timing: waveform 553/118/689 us and electrical fault
  330/525/881 us for accelerator/runtime/total. Conditions: VALIDATION.md.
- The current protocol-v3/model-package source passes 28 host tests, five
  sanitized native tests, static checks, and pristine Arm cross-builds for both
  real packages, in addition to the physical gates above.

### Never claim

- “100% accuracy”: regression fixtures verify deterministic outputs, not
  generalization. The electrical model's held-out result is 706/807 (87.4845%)
  with only 9/99 ABCG recall.
- A complete reproducible waveform training pipeline, or production-quality
  independent validation of the electrical model: the required source data,
  group-wise evaluation, and operating-condition coverage are unavailable.
- Production-ready, certified, or verified for all workloads.
- NPU-vs-CPU speedup, a wholly NPU graph, power saving, or total CPU
  utilization: CPU-equivalent model and measurement instruments are absent.
- Historical 282 us / 340 us latency: it used 200 MHz conversion while the MCU
  was actually 32 MHz, so those timing numbers are invalid.

Resume-safe version:

> Built an out-of-tree Zephyr port and WSL-native build/flash/test workflow for
> TI's preview AM13E230 Cortex-M33 MCU; implemented manifest-driven build-time
> integration for two TVM/TI TINIElite NPU models with different tensor types,
> then verified both on hardware through a CRC-protected UART protocol. Each
> completed 600/600 exact fixture regressions with zero retries/spurious IRQs,
> plus NPU-timeout recovery, watchdog reset validation, and 200 MHz clock
> read-back.

## 4. Completion state

| Area | State |
|---|---|
| Out-of-tree platform, build, hashes, symbols | Current v3 software and hardware gates passed |
| Build-time model-package abstraction | Passed with two real cross-links and physical runs |
| Protocol v3: identity/version/length/sequence/CRC/errors/resync | Software and physical gates passed |
| Supplied fixtures and repeated regression | Waveform 600/600; electrical fault 600/600 on v3 hardware |
| Explicit clock setup and read-back | Passed for both v3 images |
| NPU timeout/cold reset and WWDT0 recovery | Passed for both v3 images |
| CI, host tests, native ASan/UBSan ztests, static checks | Current local software gate passed |
| UART pinctrl/error reporting | Passed; transfer remains polling |
| Electrical held-out evaluation | Recorded, but weak ABCG recall and dataset-independence limits |
| Independent real-world accuracy evaluation | External input required |
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
| Models | Waveform: 256 int8 in / 3 int8 out / 6 fixtures; electrical: 768 float32 in / 6 int8 out / 12 fixtures |
| Key exports | tvmgen_default_run, tvmgen_default_finished, TI_NPU_NNC_IRQHandler |

Do not confuse the UART data/control and wrapper address blocks. The model
callbacks for NPU-memory writes return void: bounds problems can be logged but
cannot be returned through the opaque generated runtime. A proper fix needs a
compatible regenerated model/runtime interface, which is not available.

## 6. Source map and design rules

| Path | Responsibility |
|---|---|
| app/src/main.c | single-request server, dispatch |
| app/src/app_model.h | stable selected-model interface and generated config |
| app/src/app_npu.c | model-independent runtime control, 100 ms waits, semaphore, metrics |
| app/src/app_uart.c / app_protocol.c | framed polling transport, validation, CRC32 |
| app/src/app_clock.c / app_watchdog.c | clock read-back; WWDT0 control |
| boards/, soc/, dts/ | out-of-tree board/SoC/startup/bindings/pinctrl |
| soc/ti/am13x/clock.c | PRE_KERNEL_1 clock tree, RAM-resident flash configuration |
| drivers/serial/, drivers/misc/tinyengine/ | UNICOMM and NPU callback/ISR/semaphore drivers |
| models/ | selectable manifests/artifacts/licenses/fixtures |
| tools/model_package.py | package schema, path, tensor, runtime-ABI, and archive-ID validation |
| tools/generate_model_adapter.py | deterministic configure-time C adapter generation from the selected manifest |
| tools/send_tensor.py | selected preprocessing, client, fixtures/faults, JSON evidence |
| tests/ | Python tests and native_sim protocol ztests |
| scripts/ | build, flash, test, quality, WSL USB setup |
| config/debug/AM13E23019_Zephyr.ccxml | XDS110/DSLite configuration |
| config/udev/ | restricted XDS110 USB permission rule |
| docs/evidence/protocol_v2/ | retained machine-readable v2 board evidence |
| docs/evidence/protocol_v3/ | current 2026-11-10 waveform/electrical board evidence |

One request is processed at a time by design. It serializes opaque model state,
READY ordering, recovery, timing, and watchdog feeds. NPU completion remains
real IRQ-driven: ISR acknowledges DONE, atomically increments a count, and gives
a semaphore; continuation runs in thread context. Host rejects zero completions
or nonzero spurious interrupts. A timeout returns an error, drains UART, and
cold-resets because runtime state is opaque. WWDT0 is fed only by main-loop
forward progress.

## 7. Protocol v3

All multi-byte values are little-endian.

~~~text
magic 5a a5 | version 03 | type | uint16 sequence | uint16 length
payload | uint32 IEEE CRC-32
~~~

CRC covers version through payload, excluding magic/CRC; it is reflected IEEE
CRC-32 (0xedb88320, initial/final xor 0xffffffff), matching binascii.crc32.

| Type | Meaning |
|---:|---|
| 0x01 | input tensor bytes; exact advertised byte length |
| 0x02 / 0x05 | clock status / watchdog status request |
| 0x03 / 0x04 | NPU stall / watchdog stall; diagnostic builds only |
| 0x80 / 0x81 | READY(model ID, sizes, dtypes, flags) / ACK |
| 0x82 | RESULT: selected output bytes plus accel/runtime/total us, completions, spurious counts |
| 0x83 / 0x84 | clock status / watchdog status |
| 0xff | ERROR: code plus signed int16 detail |

Errors: 1 timeout, 2 version, 3 type, 4 length, 5 CRC, 6 inference, 7 internal,
8 UART transport. A frame has one absolute one-second receive deadline. Both
host and firmware resynchronize after damaged frames. Read PROTOCOL.md before
changing any wire behavior.

READY is 12 bytes packed `<IHHBBH`: archive-derived uint32 model ID, uint16
input bytes, uint16 output bytes, uint8 input/output dtype codes, and uint16
flags. The host must match all fields with its selected package before sending
input. See PROTOCOL.md for dtype codes and complete semantics. Both current v3
model packages passed this handshake and the full physical acceptance matrix.

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
python -m tools.model_package models/waveform_classifier
python -m tools.model_package models/electrical_fault_6class
(cd models/waveform_classifier && sha256sum --check SHA256SUMS)
(cd models/electrical_fault_6class && sha256sum --check SHA256SUMS)
ruff check tools tests
ruff format --check tools tests
python -m unittest discover -s tests -v
./scripts/static_check.sh
shellcheck scripts/*.sh
./scripts/build.sh
~~~

Select a model consistently for build and host:

~~~bash
APP_MODEL=waveform_classifier ./scripts/build.sh
APP_MODEL=waveform_classifier ./scripts/test.sh

APP_MODEL=electrical_fault_6class PRISTINE=always ./scripts/build.sh
APP_MODEL=electrical_fault_6class ./scripts/test.sh
~~~

The electrical package's software contract is model ID `0x7f95a1db`, 3,072
input bytes (`[1,6,128,1]` float32), six output bytes (`[1,6]` int8), and 16-byte
buffer alignment. Its generated run metadata contains an inactive GUI value
`num_frame_concat: 8`; do not use it. The compiled generated header and vectors
authoritatively show one frame, six variables, 128 samples, and 768 floats.

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

XDS110 exposes two CDC ports. The application/User UART is interface `if00`
(observed as `/dev/ttyACM0`); `if03`/`ttyACM1` is not the application stream.
The client uses `TINI_UART_PORT` when set, otherwise prefers a by-id `-if00`
path, then `/dev/ttyACM0`. It clears buffered pre-flash frames before waiting
for the firmware's next READY. Do not commit private serial paths.

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
reviewed JSON in the matching `docs/evidence/protocol_v*/` directory and a
VALIDATION.md update.

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
| Clock/reset/watchdog | Build plus physical clock/recovery test; update the versioned evidence directory and VALIDATION.md. |
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
| docs/evidence/protocol_v2/hardware_clock_2026-10-17.json | 200 MHz MCLK, 100 MHz UART, flash waits |
| docs/evidence/protocol_v2/hardware_irq_stress_2026-10-17.json | 600 runs, five IRQs/run, zero spurious |
| docs/evidence/protocol_v2/hardware_recovery_2026-10-17.json | CRC recovery, NPU timeout/cold reset, 600 post-reset |
| docs/evidence/protocol_v2/hardware_uart_pinctrl_2026-10-17.json | UART BREAK/reopen/recovery |
| docs/evidence/protocol_v2/hardware_stress_2026-10-17.json | Clock-valid historical polling comparison |
| docs/evidence/protocol_v3/waveform_full_acceptance_2026-11-10.json | Current waveform CRC/reset/stress/IRQ result |
| docs/evidence/protocol_v3/electrical_fault_fixtures_2026-11-10.json | Current electrical 12-fixture exact regression |
| docs/evidence/protocol_v3/electrical_fault_full_acceptance_2026-11-10.json | Current electrical CRC/reset/stress/IRQ result |
| docs/evidence/protocol_v3/*_clock_2026-11-10.json | Current per-image clock/register read-back |

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

Use accurate scope: both protocol-v3 packages passed physical acceptance on
2026-11-10, including 600/600 exact fixture regressions, IRQ/clock/CRC/NPU-
timeout/watchdog gates. Exact fixtures are integration regression, not model
accuracy. The electrical model's held-out result is recorded but it is not
production-certified or independently validated. Do not quote invalid 282/340
us historical timing.
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
