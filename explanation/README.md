# Project explanation pack

This folder is the interview-study companion for the AM13E230 TINIElite Zephyr
project. It explains the project from first principles, then follows the real
implementation down to registers, protocol bytes, fault recovery, and test
evidence. The four searchable A4 PDFs contain 47 pages in total.

## Recommended reading order

1. [01 — Project from first principles](01_project_from_first_principles.pdf)
2. [02 — Firmware and platform deep dive](02_firmware_and_platform_deep_dive.pdf)
3. [03 — Development history, validation, and limitations](03_history_validation_and_limitations.pdf)
4. [04 — Interview preparation and question bank](04_interview_preparation.pdf)

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

