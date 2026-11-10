# Documentation index

Use this page as the entry point for engineering documentation. The root
README is the quick-start; this index separates design, operation, evidence,
and study material.

## Design and implementation

| Document | Purpose |
|---|---|
| [Architecture](ARCHITECTURE.md) | End-to-end execution, platform boundaries, memory map, and concurrency |
| [Protocol](PROTOCOL.md) | UART protocol-v3 frame format, errors, recovery, and message contracts |
| [Model packages](MODEL_PACKAGES.md) | Manifest schema, generated-adapter flow, compatibility limits, and adding a model |

## Operation and project state

| Document | Purpose |
|---|---|
| [Project handoff](PROJECT_HANDOFF.md) | Complete environment, commands, troubleshooting, and continuation context |
| [Quality gates](QUALITY_GATES.md) | Current completion matrix and acceptance criteria |
| [Validation](VALIDATION.md) | Physical and software results with exact commands and limitations |
| [Audit](AUDIT.md) | Critical engineering review and claim boundaries |
| [Roadmap](ROADMAP.md) | Prioritized completed and remaining work |

Machine-readable hardware records are indexed in [evidence/](evidence/README.md).
The interview-study pack remains in [explanation/](../explanation/README.md),
as requested, with generated PDFs separated from their HTML sources.

## Why some directories must remain at the root

The repository is a Zephyr out-of-tree module, so several directories are not
arbitrary clutter:

- `boards/`, `soc/`, and `dts/` are discovery roots declared by
  `zephyr/module.yml`;
- `drivers/`, `include/`, top-level `CMakeLists.txt`, and top-level `Kconfig`
  form the Zephyr module build interface;
- `west.yml` defines the pinned workspace manifest;
- `app/` is the actual Zephyr application passed to `west build`.

Moving these under a cosmetic `src/` or `platform/` directory would require a
different module architecture and would make the project harder—not easier—to
build. Project-owned support material is instead grouped under `config/`,
`docs/`, `models/`, `scripts/`, `tests/`, and `tools/`.
