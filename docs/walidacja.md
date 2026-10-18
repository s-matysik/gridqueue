---
title: Validation
---

# Measured validation

The extraction accuracy is **measured, not declared**. The reference set was produced by visually
reading rendered crops of the pages (230-600 dpi, with the column boundaries drawn in),
**independently of the parser output**.

## Accuracy per publisher

| publisher | reference rows | comparisons | fully correct rows |
|---|---:|---:|---|
| TAURON Dystrybucja | 100 | 1 200 | **98 of 100**, 100 of 100 once the homoglyph pair is excluded |
| Stoen Operator | 100 | 1 200 | **99 of 100**, 100 of 100 after adjudication |
| PSE | 60 | 780 | **60 of 60** |
| ENERGA-OPERATOR | 60 | 780 | **60 of 60** |
| Boryszew Green Energy&Gas | 8 | 64 | **8 of 8** |

The two discrepancies at TAURON are the same homoglyph pair: capital `I` against lower-case `l` in a
sans-serif typeface. A visual settlement is impossible here **in principle**, not merely difficult,
both characters are rendered with glyphs that cannot be told apart at any magnification. The only
available evidence is the text layer of the file. **We report both values and neither replaces the
other.**

The single discrepancy at Stoen settled at 600 dpi **in the parser's favour**; it was an annotator
error. One correction to the ENERGA reference set also fell in the parser's favour.

## Inter-annotator agreement

A subsample of 35 rows was read by **a second annotator working blind**: with no access to the first
annotator's reference set, to the accuracy table, to the validation report or to the parser output.

| measure | value |
|---|---:|
| field-row comparisons | 400 |
| raw agreement | **0,9725** |
| agreement expected by chance | 0,1120 |
| **Cohen's kappa** | **0,9690** |
| agreement of the parser with the adjudicated reference set | **400 of 400** |

All 11 discrepancies are **a convention of notation, not a difference of reading**: seven concern a
cell containing text that is not a date in a date field, four, a hyphen at the end of a line in a
surname. **There was not a single perceptual discrepancy.** The PSE and ENERGA reference sets remain
single-annotator and agreement was not measured for them.

A caveat: the subsample contains no rows with the homoglyph pair, so the 400 of 400 result concerns a
different set of rows and **does not invalidate** the 98 of 100 measurement.

## Geolocation

The coordinate field is not disclosed by any publisher; it arises by derivation from the place name
against a gazetteer with geometry (13 149 names in 25 localities, 292 address points,
OpenStreetMap, ODbL 1.0).

| publisher | rows | with coordinates | coverage |
|---|---:|---:|---:|
| Stoen Operator | 1 236 | 1 217 | **98,463%** |
| Boryszew Green Energy&Gas | 8 | 8 | **100,000%** |
| TAURON Dystrybucja | 10 955 | 0 | 0,000% |
| ENERGA-OPERATOR | 5 382 | 0 | 0,000% |
| PSE | 945 | 0 | 0,000% |
| National Grid | 694 | 0 | 0,000% |
| **panel** | **19 220** | **1 225** | **6,374%** |

The zeros are **confirmed, not repaired by guessing**, and each one has a recorded reason: at TAURON
a substation code with no published dictionary, at PSE and ENERGA a preponderance of rows with no
declared locality, at National Grid the names of grid supply points instead of street addresses.

Verification on a stratified sample of 102 points: agreement of the street name with independent
geocoding **101 of 102 = 99,02%**; the median distance between two independently chosen
representative points of the same street **259,2 m**, with a Spearman correlation with the length of
the axis of **0,714**, the sources indicate the same street and differ in which of its points they
take to be representative.

**A fundamental limitation:** this is verification against a second reading of the same database, not
against a field measurement. The sources are correlated, so the measurement does not rule out an
error common to OpenStreetMap.

**A street name does not determine a point.** 431 of 6 057 Warsaw names (7,12%) have disjoint
components more than 2 km apart. The register gives the street but not the district, so this
ambiguity **cannot be removed from the published data**; it is a finding about the scope of the
disclosure duty, not about the quality of the tool. Every result carries the number of components and
their spread, so that the recipient can filter such rows out.

## Tests versus visual measurement

`python -m pytest -q` reports **120 passed, 2 skipped** out of 122 collected. The two skips are
conditional: the integration tests of the PSE and ENERGA adapters require the source documents.

The two methods catch **different classes of defect** and both mechanisms are present in the package.
Five mapping defects passed through the entire test suite, because none of them raised an exception,
among them one that reversed the agreement status in 88 rows of two publishers. They were detected by
comparing the output with the reference set read from the document. All of them are covered by
regression tests.
