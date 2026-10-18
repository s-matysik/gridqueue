# Reproducibility package

What is here and what it proves.

| file | content |
|---|---|
| `manifest.csv` | one row per source document: publisher, jurisdiction, adapter, address, download date, size, SHA-256 |
| `checksums.txt` | the same checksums in `sha256sum -c` format |
| `requirements-lock.txt` | library versions read from the environment in which the published numbers were computed |
| `environment.yml` | an environment for reproducing the work from scratch |
| `run_validation.py` | reproduces the derived numbers from the panel: field coverage, the eight quality rules, core completeness |
| `run_figures.py` | reproduces the three figures that are computed from the panel |

## The source documents are not redistributed here

Two reasons, both substantive. Some of the documents are covered by the rights of their publishers,
and all of them are **replaced at least once per quarter** under art. 7(8l) of the Energy Law; a copy
in the repository would go stale within three months and would start to suggest, falsely, that it
describes the current state.

Instead of a copy there is a manifest. For every document it gives the address, the download date and
the SHA-256, so a person reproducing the work can:

1. download the file from the given address and check the checksum; a match means identical input;
2. find that the checksum does not match, which means that the publisher has issued **a different
   edition of the register**, and that different row counts are then to be expected. This is not a
   failure of reproduction but a property of the quarterly duty.

```bash
cd <directory_with_documents> && sha256sum -c /path/to/checksums.txt
```

## Reproduction

```bash
pip install git+https://github.com/s-matysik/gridqueue@v1.0.0
gridqueue parse <documents...> --out panel.parquet
python reproducibility/run_validation.py panel.parquet
python reproducibility/run_figures.py panel.parquet
python examples/research_use_case.py panel.parquet
```

`run_validation.py` exits with a non-zero code if the sum of violations across publishers does not
close to the panel figure; that assertion caught a real mistake in version 0.3.x, where the table in
the documentation doubled the result.

## What these scripts do not reproduce

**Accuracy against the reference set.** The reference set was produced by a human reading rendered
page extracts visually, independently of the parser output. It is published as a measurement artefact
and cannot be computed by code; if it could, it would not be independent.

**The architecture figure.** It is a hand-drawn diagram and has no input data.
