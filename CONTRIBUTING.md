# Contributing

Keep changes scoped, preserve the pinned baseline, and do not commit build
directories or vendor checkouts. Before opening a change, run:

```bash
python -m unittest discover -s tests -v
shellcheck scripts/*.sh
./scripts/build.sh
```

Hardware-facing changes should also run `./scripts/pipeline.sh` and update
`docs/VALIDATION.md` with the board, probe firmware, tool versions, and complete
result summary. Never convert a small golden-vector pass into a general model
accuracy claim.
