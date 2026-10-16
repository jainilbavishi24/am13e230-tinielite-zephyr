# Critical engineering audit

Audit date: 2026-10-17

## Verdict

This is a legitimate, resume-worthy hardware/firmware bring-up project. The
ELF links generated `tvmgen_default_ti_npu_convolveNHWC_*` and
`tvmgen_default_ti_npu_avgPoolNHWC_3` kernels, the firmware has run on the
LaunchPad, and native WSL flashing and UART inference have been demonstrated.
It is not merely printing expected answers or silently running a CPU-only
model.

It remains an engineering prototype. The original repository overstated its
maturity in several places: six supplied vectors do not establish model
accuracy, NPU completion was polled rather than interrupt-driven, local scripts
were described as CI/CD, and production-quality fault handling was absent.

## Scope reviewed

Every project-owned or modified area was reviewed: board and SoC definitions,
devicetree and bindings, UART and NPU drivers, firmware application, generated
model headers/archive/symbols, all six golden vectors, WSL scripts, host Python
tools, flash configuration, build output/map/symbols, backups, dumps, and the
knowledge-transfer document. Upstream Zephyr's millions of vendored lines were
not re-audited; its exact revision was identified and pinned.

## Confirmed correct

| Area | Evidence | Assessment |
|---|---|---|
| NPU identity | ELF contains four `tvmgen_default_ti_npu_*` kernels and TI runtime symbols | Real accelerator integration |
| Hardware map | `0x408ff000`, CTL5 `+0x1120`, instruction `+0x2000`, parameter `+0x2800` | Matches TI SDK/register definitions |
| NPU memory limits | 256 instruction words, 512 parameter words | Matches TI SDK driverlib |
| NPU IRQ number | IRQ 41 | Matches TI device header |
| Memory | 512 KiB flash; 96 KiB primary SRAM plus a separate 32 KiB bank/alias | Physical total is 128 KiB; linker currently uses 96 KiB |
| Model shape | 256 signed 8-bit inputs, three signed 8-bit scores | Header and protocol agree |
| WSL workflow | Linux build, Linux UniFlash/DSLite program/verify, `/dev/ttyACM0` exchange | Previously demonstrated on hardware |

## Serious findings in the original layout

1. NPU completion was not interrupt driven. IRQ 41 was connected and enabled,
   but the IP-level interrupt was not enabled, the observed IRQ count was zero,
   and the application polled CTL5 then called `TI_NPU_NNC_IRQHandler()`.
2. Inference and CTL5 loops had no timeout. A runtime or hardware fault could
   hang forever, and `tvmgen_default_run()` status was discarded.
3. The host parsed but discarded golden scores, accepted negative indices, and
   returned success after missing results. Therefore it was not an automated
   regression test.
4. “100% accuracy” referred at most to six balanced fixtures—two per class—not
   an independent dataset, confusion matrix, or statistical evaluation.
5. A receive thread could announce the next `READY` while the main thread was
   still inferring. The observed indefinite wait was separately explained by a
   missed manual board reset, but the early-ready ordering was still ambiguous.
6. Driver register addresses and board PA0/PA1 pinmux values were embedded in C
   instead of devicetree data.
7. CPU clock metadata disagreed (`32 MHz` versus the `200 MHz` Zephyr cycle
   configuration), making timing claims easy to misinterpret.
8. The working changes lived inside a 2.4 GB Zephyr checkout with duplicate
   models, backups, disassemblies, PDF dumps, virtual environments, and build
   output. That is unsuitable as a public project repository.
9. The claimed OpenOCD runner was not the proven flashing path. TI DSLite with
   the XDS110 configuration is the working path.
10. There was no project-owned manifest, dependency lock, host unit test, or
    GitHub Actions workflow.

## Corrections in this repository

- Converted the project to an out-of-tree Zephyr module/application and pinned
  the exact Zephyr and module revisions in `west.yml`.
- Kept one active model and recorded artifact hashes and licensing.
- Derived NPU, SYSCTL, GSC, UART, UNICOMM, and pinmux data from devicetree.
- Matched TI's documented reset, power, and privilege sequence.
- Removed the misleading NPU IRQ counter/claim; execution is explicitly polled.
- Added runtime-status handling and a timeout for every NPU hardware stage.
- Removed the background UART thread so readiness and inference are serialized.
- Replaced cycle-count UART timeouts with millisecond uptime timeouts.
- Added exact golden-score comparisons, index validation, monotonic deadlines,
  `--all`, actionable reset guidance, and reliable nonzero failure codes.
- Replaced the additive checksum with a versioned, length-delimited CRC-32
  protocol carrying sequence numbers, structured errors, and timing metadata.
- Added bounded host retries, stream resynchronization, deliberate CRC fault
  injection, repeat mode, latency statistics, and machine-readable evidence.
- Added unit tests, artifact hash verification, host CI, shell checks, and
  reproducible build/flash scripts.

## Remaining limitations

- The framed transport passed deliberate CRC corruption/recovery and 600
  consecutive hardware inferences with 600 exact results and zero retries.
  Multi-hour soak, repeated reset, brownout, and broader fault-injection tests
  are still pending.
- The CPU and peripheral clock tree is assumed to have been established by the
  device startup/debug environment. Read-back or explicit clock initialization
  is needed before publishing clock-normalized benchmark claims.
- The UART driver implements polling only; error-status reporting, standard
  Zephyr pinctrl, interrupts, and async APIs are not implemented.
- The NPU memory callback ABI returns `void`, so archive memory-write errors can
  only be logged rather than propagated into the generated runtime.
- CI validates host code and artifact integrity, not the cross-compiled
  firmware. A container/toolchain job should be added when the compiler setup
  is made redistributable and stable.
- Six golden fixtures are regression coverage, not an accuracy evaluation.
- AM13E230 collateral is preview-era and current TI pages contain changing
  frequency information. Pin the document/SDK revision used for every claim.

The live completion matrix and acceptance criteria are maintained in
[`QUALITY_GATES.md`](QUALITY_GATES.md).

## Resume assessment

Strong project themes are low-level MCU bring-up, Zephyr porting, devicetree,
MMIO driver development, NPU/runtime integration, embedded protocol design,
WSL USB/debug-probe operation, and measurement. Present it as a validated
prototype and explain the remaining limitations; that honesty improves the
project rather than weakening it.
