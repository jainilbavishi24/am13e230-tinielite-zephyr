# Electrical-fault model evaluation record

This file records the evidence supplied by the TI Edge AI Studio run
`20261106-190446`. It separates model-quality evidence from firmware-integration
evidence. Nothing here is a physical-board result.

## Training and export configuration

| Setting | Value |
|---|---|
| Device / model | AM13E2 / `CLS_5k_NPU` |
| Preprocessing | Simple Window, no FFT or feature extraction |
| Compiled input | one frame × six channels × 128 samples |
| Window stride | 0.01 of the frame length |
| Split | 60% train / 30% validation / 10% test, amongst files |
| Epochs / batch | 50 / 32 |
| Learning rate | 0.04 |
| Quantization | QAT, 8-bit weights and activations |
| Compile target | Cortex-M33, hard-float, TINIElite hard acceleration |

The run metadata retains `num_frame_concat: 8`, but that GUI field is disabled
under Simple Window mode. It is not the compiled tensor contract. The generated
`user_input_config.h`, TVM header, and vectors consistently specify one frame,
six variables, 128 samples, and 768 float32 elements.

## Held-out file result

The Studio test split used one held-out source file per class and created 807
overlapping windows. Rows are true classes and columns are predicted classes.

| True \ predicted | No fault | BC | ABC | AG | ABG | ABCG | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| No fault | 346 | 0 | 0 | 0 | 0 | 0 | 346 |
| BC | 0 | 73 | 0 | 0 | 0 | 0 | 73 |
| ABC | 0 | 0 | 81 | 0 | 0 | 11 | 92 |
| AG | 0 | 0 | 0 | 98 | 0 | 0 | 98 |
| ABG | 0 | 0 | 0 | 0 | 99 | 0 | 99 |
| ABCG | 0 | 0 | 90 | 0 | 0 | 9 | 99 |

Overall accuracy is 706/807 = **87.4845%**. The aggregate number hides the
weakest class:

| Class | Precision | Recall | F1 |
|---|---:|---:|---:|
| No fault | 1.0000 | 1.0000 | 1.0000 |
| BC | 1.0000 | 1.0000 | 1.0000 |
| ABC | 0.4737 | 0.8804 | 0.6160 |
| AG | 1.0000 | 1.0000 | 1.0000 |
| ABG | 1.0000 | 1.0000 | 1.0000 |
| ABCG | 0.4500 | 0.0909 | 0.1513 |
| Macro average | 0.8206 | 0.8286 | 0.7945 |

The dominant error is ABCG being predicted as ABC. The model therefore must
not be described as a reliable six-class protection or diagnostic system.

## Why this is not independent real-world validation

- Each class has only a small number of sequential source files.
- A 0.01 stride produces strongly overlapping windows; adjacent examples are
  highly correlated and must not be treated like independent recordings.
- Class window counts are unequal, so overall accuracy is dominated by the
  larger no-fault class.
- The test split is separate by file, but all files may still share the same
  simulator, acquisition setup, operating conditions, or generation process.
- No evidence yet covers sensor noise, component tolerances, unseen fault
  impedance/location, load variation, frequency drift, or real field data.

The correct claim is: the export provides a useful software-integration
baseline and a documented held-out-file result. A production claim requires
new independently generated or recorded groups, balanced classes, operating-
condition coverage, and physical-board validation.

## Golden vectors versus model accuracy

The package contains 12 golden vectors, two selected from each nominal class.
They are regression fixtures: the firmware must reproduce the generated output
bytes exactly. They are not extra test samples and do not measure accuracy. One
ABCG fixture is expected to choose ABC by a one-score margin; retaining it is
important because it tests exact runtime equivalence without rewriting an
unfavorable expected result.
