# Project explanation pack

This folder is the interview-study companion for the AM13E230 TINIElite Zephyr
project. It starts with the build and Zephyr foundations needed to understand
the project, then follows the real implementation down to registers, protocol
bytes, fault recovery, and test evidence. The PDFs are intended to be read in
order before an interview.

## Recommended reading order

1. [00 — Foundations: build system, Kconfig, object code, and out-of-tree work](00_foundations_for_understanding.pdf)
2. [01 — Project from first principles](01_project_from_first_principles.pdf)
3. [02 — Firmware and platform deep dive](02_firmware_and_platform_deep_dive.pdf)
4. [03 — Development history, validation, and limitations](03_history_validation_and_limitations.pdf)
5. [04 — Interview preparation and question bank](04_interview_preparation.pdf)

The PDFs are generated from the HTML files in [`source/`](source/). Regenerate
them with:

```bash
./explanation/generate_pdfs.sh
```

## Accuracy policy

The pack is based on the current repository, retained machine-readable
hardware evidence, Git history, and the original project handoff. Historical
claims that were later disproved or superseded are labelled as such.

In particular, the six supplied fixtures prove deterministic regression
behavior, not general model accuracy. The original model, training pipeline,
independent dataset, and model-generation scripts are not available.

