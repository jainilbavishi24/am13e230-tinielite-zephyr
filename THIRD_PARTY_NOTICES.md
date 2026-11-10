# Third-party notices

This repository contains or depends on third-party material:

- Zephyr Project source and modules are fetched through `west.yml` and retain
  their upstream licenses. They are not copied into this repository.
- `models/waveform_classifier/` and `models/electrical_fault_6class/` contain
  TI tooling outputs, generated headers, regression vectors, and export data.
  They retain the terms in each package's adjacent `LICENSE.txt`; those terms
  are not replaced by the repository's Apache-2.0 license.
- `config/debug/AM13E23019_Zephyr.ccxml` names TI debug-server components and requires
  a separately installed TI UniFlash/CCS distribution.

Before publishing a new model package, the repository owner must confirm that
they have permission to publish its trained model, generated archive, and
golden input data. If ownership cannot be confirmed, do not add those files to
Git history; document how authorized users supply them locally instead.
