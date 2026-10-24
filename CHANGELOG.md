# Change history

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
semantic versioning. The version of the data schema is separate from the version of the package
and is reported as `SCHEMA_VERSION`.

## 1.0.0 (2026-10-24)

First public release.

### Added
- **Schema** of 21 fields derived from the structure of the duty in Art. 7(8l) of the Polish Energy
  Law, with two entities (`APPLICATION`, `NODE`), controlled vocabularies of process status and
  resource class, canonical units (kW, ISO dates) and validation (`validate_frame`).
- **Nine adapters in five jurisdictions**: PSE, ENERGA-OPERATOR, TAURON Dystrybucja, Stoen
  Operator, Boryszew (Poland), E-REDES (Portugal), e-distribución (Spain), ESB Networks (Ireland)
  and National Grid (Great Britain); automatic publisher detection and `parse_sources` for several
  documents and editions at once.
- **Quality layer**: eight rules, a column-shift audit and per-publisher reports.
- **Longitudinal module**: comparison of two editions (flows, status transitions, monotone-snapshot
  test), a linkage audit with precision bounds and the sensitivity of the linkage key.
- **Analytical layer**: processing times with censoring (Kaplan-Meier, per-group medians and
  intervals) and node loading, with a voltage filter.
- **Location resolver**: gazetteer-based resolution of place descriptions with declared confidence,
  accuracy and reason, written back to the frame by `geocode_frame`.
- **Charts** for every result (`gridqueue.plots`, extra `pip install "gridqueue[plot]"`).
- **Three access routes**: the Python package with a command-line interface, a Google Colab notebook
  that reproduces the results of the article and stops on any discrepancy, and a browser application
  (Pyodide/WebAssembly) with a simple and a full view, which does not upload the document.
- **Names in the wording of the statute**: `from_legacy_names` and the correspondence table in
  `docs/schema.md` convert tables that use the Polish field names of the Supplementary Material.
- Reproducibility material: source manifest with checksums, download and validation scripts, and
  the expected values of the article.
