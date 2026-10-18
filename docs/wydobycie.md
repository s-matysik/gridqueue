---
title: Extraction method
---

# Extraction method

Instead of regular expressions over flattened text, extraction from the **position of the words on
the page**.

* **`ruled`**, column boundaries taken from the vertical **vector edges** recorded in the file
  (TAURON, Stoen, ENERGA). An empty cell is fenced off by a line, so it cannot merge with the
  neighbouring one. In the ENERGA document the grid is not made of line objects but of 176 thin
  rectangles; the strategy works correctly on those.
* **`banded`**, boundaries from the vertical corridors of whitespace (Boryszew; a document with no
  grid).
* **spreadsheet**, PSE read directly from the cells, **together with character formatting**.
  Without that, the superscripts marking footnotes merge into the content, and in numeric fields
  they destroy the value. The truncation happens on the basis of the formatting, not on the basis of
  guessing where the string ends; guessing would mutilate genuine substation names that end with a
  letter.
* Multi-line rows merged column by column following the ordinal number.
* Wrapped headers in narrow columns read by geometric assignment of the header words to the
  columns.

## Why `pdfplumber`

It gives direct access to the coordinates of the words and to the vector edges. `camelot` in lattice
mode reconstructs the column boundaries from a raster image and requires Ghostscript, `tabula`
requires a JVM; in both, the column boundary is the **result of detection on an image** rather than
a number from the file.

## What this changed, measured

The audit counts the rows in which a non-empty value sits in a field it cannot belong to.
In the TAURON document: **767 of 10 559 = 7,264%** with regex extraction, **0 of 10 955 = 0,000%**
with extraction from the column layout. The old parser **also lost rows**: in the new extraction the
ordinal numbers run 1…10 955 with no gaps and no duplicates, which means it recovered 396 rows
fewer.

The 0,000% result should be read as what it measures: the audit is a **detector of internal type
inconsistency**, not a comparison against a reference set. Freedom from error is measured by the
reference set, see [validation](walidacja.md).

```python
from gridqueue import audit_column_shift
a = audit_column_shift(df)
a.udzial, a.n_wierszy, a.szczegoly[:3]
```
