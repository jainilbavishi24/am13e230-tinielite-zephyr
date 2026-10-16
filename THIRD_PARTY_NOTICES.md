# Third-party notices

This repository contains or depends on third-party material:

- Zephyr Project source and modules are fetched through `west.yml` and retain
  their upstream licenses. They are not copied into this repository.
- `models/waveform_classifier/artifacts/`, its generated header, and the golden
  vectors are TI tooling outputs and retain the terms in the adjacent
  `LICENSE.txt`. Those terms are not replaced by the repository's Apache-2.0
  license.
- `config/AM13E23019_Zephyr.ccxml` names TI debug-server components and requires
  a separately installed TI UniFlash/CCS distribution.

Before making the repository public, the repository owner must confirm that
they have permission to publish the trained model, generated archive, and
golden input data. If that ownership cannot be confirmed, remove the model and
fixtures from Git history and document how authorized users supply them
locally.
