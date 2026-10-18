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
```

`parse` recognizes the publisher from the file name and, where that is not enough, from the content
of the first page. `--adapter` forces the choice. `--report` writes the extraction report: the row
count, the strategy, the reconstructed ordinal numbers, the fields populated and the anomalies
encountered.

`validate` runs the eight quality rules together with the column-shift audit and writes the
violations along with the rows that cause them; a violation does not abort the run.

`export` merges the results of several adapters into one panel. `--only-schema` omits the extension
columns carrying the `_` prefix.

## Provenance of the result

Every row carries a provenance record: the source document, the page, the adapter version and the
version of the gazetteer used when the location was resolved. The statute requires the documents to
be replaced quarterly, so anyone reproducing the work on documents from a later quarter will
download different documents and **should expect different row counts**; this is why the register
edition is recorded in every result rather than assumed.
