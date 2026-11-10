# Electrical fault 6-class model package

This package is a build-time-selectable AM13E2/TINIElite classifier generated
by TI Edge AI Studio for Time Series. It classifies one 128-sample window of
six phase-current/phase-voltage channels into six transmission-line states.

## Tensor contract

- Input shape: `1 x 6 x 128 x 1`, little-endian `float32` (3,072 bytes)
- Channel order: `Ia`, `Ib`, `Ic`, `Va`, `Vb`, `Vc`
- Preprocessing: Simple Window; the host supplies the generated raw float
  tensor without an FFT or host quantization
- Output: six signed int8 scores ordered no-fault, BC, ABC, AG, ABG, ABCG
- Winner: index of the maximum output score

The generated `user_input_config.h` is authoritative: although the Studio run
metadata retains an inactive `num_frame_concat: 8` GUI default, the compiled
contract states `FE_NUM_FRAME_CONCAT 1`, and both the generated header and
golden vectors contain 768 float input elements.

## Generation and integrity

- Edge AI Studio Tiny ML Backend: 1.4.0
- TI MCU NNC: 2.1.2
- TI Arm Clang: 5.1.1 LTS
- Model: `CLS_5k_NPU`
- Target: `c, ti-npu type=hard skip_normalize=true output_int=true`
- Archive SHA-256: `7f95a1db4ff427d46a543a7439ce8edda07c87c8b1485adc1a43d8d993052afb`

The package manifest declares the generated input/output struct names, tensor
fields, completion flag, entry point, and continuation symbol. CMake generates
the `app_model.h` adapter from those declarations; no per-model C file is
maintained in this directory.

The vendor compiler report identifies PAD, four GCONV layers, AVGPOOL, and FC
as NPU-offloaded patterns. The model library reports 4,822 bytes of code,
7,965 bytes of read-only data, and 2,256 bytes of read/write data.

GNU `ld.bfd` emits an orphan-section warning for the TI/LLVM-specific
`.symtab_meta` section in `lib2.obj`. Inspection shows that it is 47 bytes,
read-only, and does **not** carry the ELF `ALLOC` flag, so it consumes no target
flash or RAM and is not runtime code. The archive is preserved unchanged.

## Model-quality evidence and limits

The held-out file (`*_2.csv`) evaluation produced 706 correct windows out of
807 (87.4845% window accuracy). No-fault, BC, AG, and ABG were perfect on that
split, while the model substantially confused ABC and ABCG. In particular,
ABCG recall was 9/99. This is an integration baseline, not a production fault
detector and not evidence of independent real-world generalization.

The dataset contains only five sequential chunks per class, uses strongly
overlapping windows, and has unequal class lengths. Those limitations must be
fixed with independent recordings/simulations, balanced sampling, and
operating-condition variation before making model-accuracy claims.

The full confusion matrix, per-class metrics, configuration, and interpretation
are recorded in [docs/EVALUATION.md](docs/EVALUATION.md).

Twelve generated regression vectors are included (two per class). They verify
exact generated outputs, not class correctness; one ABCG fixture is expected
to score ABC slightly higher and is intentionally retained unchanged.

The generated archive, header, vectors, and original export retain the terms
in [LICENSE.txt](LICENSE.txt). The untouched Studio export and its auxiliary
class-name header are kept under `provenance/`; neither is consumed by the
firmware build. Physical acceptance passed on 2026-11-10: 12/12 supplied
fixtures and 600/600 repeated fixtures matched exactly with zero retries,
eight NPU DONE interrupts per inference, zero spurious interrupts, validated
clocks, CRC recovery, NPU-timeout recovery, and WWDT0 recovery. These are
integration-regression results, not independent accuracy evidence.
