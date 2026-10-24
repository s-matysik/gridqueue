---
title: Command line
---

# Command line

```bash
gridqueue schema                                   # specification of the 21 fields
gridqueue adapters                                 # publisher declarations
gridqueue parse tauron.pdf --out tauron.parquet --report tauron.json
gridqueue parse --adapter uk_nationalgrid --out uk.parquet   # downloads from the CKAN catalogue
gridqueue validate tauron.parquet --out walidacja.json
gridqueue export tauron.parquet stoen.parquet --out panel.parquet --only-schema
gridqueue compare pse_07.parquet pse_08.parquet --label-a 2026-07-31 --label-b 2026-08-31 \
    --out delta.json --transitions transitions.csv
gridqueue plot energa.parquet --out charts/ --format png,svg
gridqueue plot pse_07.parquet --edition-b pse_08.parquet --out charts/pse/
```

`parse` recognizes the publisher from the file name and, where that is not enough, from the content
of the first page. `--adapter` forces the choice. `--report` writes the extraction report: the row
count, the strategy, the reconstructed ordinal numbers, the fields populated and the anomalies
encountered.

`validate` runs the eight quality rules together with the column-shift audit and writes the
violations along with the rows that cause them; a violation does not abort the run.

`export` merges the results of several adapters into one panel. `--only-schema` omits the extension
columns carrying the `_` prefix.

`compare` sets two editions of one register side by side: the flows of rows, the status transition
matrix, the linkage precision on the fields held out of the key and the key sensitivity.
`--node-key` uses the node key for node-level registers.

`plot` draws every chart the dataset supports (see [Charts](wykresy.md)); with `--edition-b` it adds
the comparison of two editions. Charts that need data the disclosure does not carry are skipped and
listed with the reason. It needs the `plot` extra (matplotlib).

## Provenance of the result

Every row carries a provenance record: the source document, the page, the adapter version and the
version of the gazetteer used when the location was resolved. The statute requires the documents to
be replaced quarterly, so anyone reproducing the work on documents from a later quarter will
download different documents and **should expect different row counts**; this is why the register
edition is recorded in every result rather than assumed.
