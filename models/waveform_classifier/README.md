# Waveform classifier artifact

This directory contains the single model used by the demo.

- Input: `1 x 1 x 256 x 1`, signed 8-bit
- Output: three signed 8-bit class scores in the order sawtooth, sine, square
- Accelerator target: TI TINIElite (`TVMGEN_DEFAULT_TI_NPU`)
- Archive SHA-256: `c7d1109684095a9893b8b05e8b172c8f45ed50b2c45015f6e9c82e42e1013e82`

`artifacts/mod.a`, its generated header, and the golden vectors are generated
artifacts and retain the terms in [LICENSE.txt](LICENSE.txt). The six bundled
vectors are regression fixtures, not a statistically meaningful accuracy test.
