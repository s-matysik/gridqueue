# gridqueue

[![tests](https://github.com/s-matysik/gridqueue/actions/workflows/ci.yml/badge.svg)](https://github.com/s-matysik/gridqueue/actions/workflows/ci.yml)
[![Python 3.10-3.13](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/s-matysik/gridqueue)
[![licence Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-green)](LICENSE.txt)
[![documentation](https://img.shields.io/badge/documentation-gh--pages-blue)](https://s-matysik.github.io/gridqueue/)
[![release](https://img.shields.io/github/v/release/s-matysik/gridqueue)](https://github.com/s-matysik/gridqueue/releases)
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

Harmonizer of statutory grid-connection disclosures for the electricity network.

Distribution system operators have a duty to publish who is applying for a connection,
where, for what capacity and at what stage the proceeding stands (Article 7(8l) of the Act of
10 April 1997, the Energy Law). In Poland the duty covers approximately 180 licensed
operators and **each one publishes in its own format**, most often as a PDF. The information is
public, but it is not processable.

`gridqueue` turns those publications into one set of rows with **measured accuracy**.

Release 1.7.0: **nine adapters in five jurisdictions** (Poland, Spain, Ireland, Portugal, Great
Britain), all 21 schema fields populated by at least one publisher, quality rules, a longitudinal
module with a linkage audit, processing times with censoring, node loading, a location resolver and
**charts for every result**. Documentation: **https://s-matysik.github.io/gridqueue/**

The code and documentation are in English. Schema field names and codes (`id_wniosku`,
`WARUNKI_WYDANE`, ...) keep the wording of the Polish statute, because they are the data format of
the panel; their English meaning is in the [glossary](https://s-matysik.github.io/gridqueue/schema.html#glossary-of-field-and-code-names).

## Three ways to run it

| | Python library | Google Colab | In the browser |
|---|---|---|---|
| Install | `pip install` (below) | nothing | nothing |
| Where | your machine | Google's free machine | your machine, offline after loading |
| Parse, validate, quality rules, column-shift audit | yes | yes | yes |
| Several files and publishers in one panel | yes | yes | yes |
| Two editions: flows, transitions, linkage precision and sensitivity | yes | yes | yes |
| Processing time (Kaplan-Meier), node loading | yes | yes | yes |
| Coordinates from a gazetteer | yes | yes | yes, with your gazetteer file |
| Charts (PNG, SVG) | yes | yes | yes |
| Export | Parquet, CSV, XLSX, JSON | Parquet, CSV, XLSX, JSON | CSV, XLSX, JSON, ZIP |
| Fetch documents from the publisher's server | yes | yes | no, the browser forbids it |

* **Colab:** [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)
* **Browser:** **https://s-matysik.github.io/gridqueue/app/**, drop the published documents on the
  page. The *simple* view needs nothing else: it recognises the publisher, compares two editions
  of one register when it gets them, and returns the main charts with one download. The *full*
  view adds every input, option and table. The package runs in a WebAssembly interpreter;
  nothing is uploaded.
* **Library:** see *Installation*.

## What it is not

It is not an index of operators' publications and not an overview map. There are tools that
index and link to operators' pages at European scale. `gridqueue` goes one step lower:
**it parses the statutory document itself into rows**. In jurisdictions with good data (Great Britain,
the United States) the data is already tabular and this layer is unnecessary; the British adapter in
this package amounts to downloading a CSV. Poland is the case in which it is not.

## Running without installation, Google Colab

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

The notebook `notebooks/gridqueue_colab.ipynb` performs **a full research run in the browser**:
it downloads two editions of the disclosure directly from the publisher, extracts and validates the
rows, assesses the quality, computes the queue flows together with the linkage precision and key
sensitivity and **compares the reproduced figures with those published in the paper, aborting
execution on a divergence**. It then parses a distribution operator's three documents for the
processing-time curves and node loading, runs the location resolver, draws every chart and exports
the results as one archive. The PSE part takes about a minute on a free machine; the ENERGA part adds
several minutes of PDF parsing and can be switched off.

The notebook does not reproduce the extraction accuracy against the reference set, because that set
requires a human reading. The national gazetteer is a separate download under the ODbL licence, so the
resolver is shown on a synthetic gazetteer, with a one-line change to use your own.

## Installation

One command, with no compilation and no external services:

```bash
pip install "gridqueue[plot] @ git+https://github.com/s-matysik/gridqueue@v1.7.0"
```

The `plot` extra adds matplotlib for the charts; without it everything else works.

For work on the code, with the test extra:

```bash
git clone https://github.com/s-matysik/gridqueue && cd gridqueue
pip install -e ".[test,plot]"
```

Dependencies: `pandas`, `pdfplumber`, `openpyxl`, `requests`, `pyarrow`. The canonical unit of
capacity is **kW** without exception; sources reporting megawatts are converted at extraction, and the
source unit is recorded in an extension.

## A quick example

```python
from gridqueue import get_adapter, run_quality, validate_frame, audit_column_shift

res = get_adapter("pl_tauron").parse("tauron_informacja.pdf")
df = res.frame                       # frame in the 21-field schema
print(res.report["n_rows"])       # 10955
print(audit_column_shift(df).share) # 0.0, share of rows with shifted columns
print(run_quality(df).as_dict()["violations_total"])
```

A row with a resolved location:

```python
from gridqueue import resolver_from_osm_json
r = resolver_from_osm_json("streets_warsaw.json")
res = r.resolve("WARSZAWA, WINCENTEGO ŚW.")
print(res.matched, res.confidence)      # Świętego Wincentego REVERSED
print(r.resolve("SKB3").reason)       # kod_stacji_bez_slownika, we do not guess
```

## CLI

```bash
gridqueue schema                                   # specification of the 21 fields
gridqueue adapters                                 # publisher declarations
gridqueue parse tauron.pdf --out tauron.parquet --report tauron.json
gridqueue parse --adapter uk_nationalgrid --out uk.parquet   # downloads from the CKAN catalogue
gridqueue validate tauron.parquet --out validation.json
gridqueue export tauron.parquet stoen.parquet --out panel.parquet --only-schema
gridqueue compare pse_07.parquet pse_08.parquet --label-a 2026-07-31 --label-b 2026-08-31 --out delta.json
gridqueue plot energa.parquet --out charts/ --format png,svg         # every chart the data supports
gridqueue plot pse_07.parquet --edition-b pse_08.parquet --out charts/pse/
```

## Charts

`gridqueue.plots` draws every result of the package. Each function takes the object the analysis
returns and gives back a matplotlib `Figure`, so a chart never recomputes a number: what it shows is
what the analysis reports. What a disclosure does not contain is drawn as absence (a grey cell, a
skipped node with the reason), never as zero.

| Function | Shows |
|---|---|
| `plot_field_coverage` | share of rows populating each of the 21 fields, per publisher |
| `plot_quality` | violations of the eight quality rules, stacked by publisher |
| `plot_column_shift` | rows in which a value stands in a field it cannot belong to |
| `plot_status_distribution` | applications by stage of the proceeding |
| `plot_capacity_by_class` | requested capacity of the active queue by resource class and voltage |
| `plot_processing_time` | Kaplan-Meier curves with censoring and a 95% band |
| `plot_node_loading` | queue over declared free capacity, per node, log scale |
| `plot_edition_flows`, `plot_transitions`, `plot_linkage_audit`, `plot_edition_comparison` | two editions |
| `plot_location_resolution` | where a coordinate comes from, and the reason where it does not |
| `plot_overview` | four panels for a first look |
| `save_all` | every chart the data supports, PNG/SVG/PDF; skipped ones listed with the reason |

```python
from gridqueue import parse_sources, plots

panel, reports = parse_sources(["applications.pdf", "demand_capacity.pdf", "generation_capacity.pdf"])
plots.plot_processing_time(panel, by="klasa_zasobu")     # displays in Jupyter / Colab
plots.save_all(panel, "charts/", formats=("png", "svg"), dpi=300)
```

`gridqueue.examples` generates a synthetic panel, two synthetic editions and a small gazetteer, labelled
as synthetic, for trying every function without a real disclosure.

## Schema

21 fields in three groups reflecting the structure of the duty (IDENTITY / CAPACITY / PROCESS),
a mandatory core of 5 fields (`id_wniosku`, `lokalizacja_tekst`, `klasa_zasobu`, `moc_pobierana`,
`status_procesu`), the rest optional and **declared per publisher**. Canonical units:
capacity in kW, ISO 8601 dates, WGS84 coordinates. Fields beyond the schema, which a given operator
supplies beyond the required minimum, go into columns with the `_` prefix and are declared explicitly
by the adapter (`adapter.declaration()`).

## Extraction method

Instead of regular expressions over flattened text, extraction from the **position of the words on the
page**:

* `ruled`, column boundaries taken from the vertical vector edges (TAURON, Stoen);
  an empty cell is fenced off by a line, so it cannot merge with the neighbouring one,
* `banded`, boundaries from the vertical corridors of whitespace (Boryszew; a document with no grid),
* multi-line rows merged column by column following the ordinal number,
* spreadsheets (PSE) read directly from the cells, together with character formatting; without that,
  the superscripts marking footnotes merge into the content, and in numeric fields they destroy the
  value.

`pdfplumber` was chosen because it gives direct access to the coordinates of the words and to the
vector edges from `pdfminer.six`. `camelot` in lattice mode reconstructs the column boundaries from a
raster image and requires Ghostscript, `tabula` requires a JVM; in both, the column boundary is the
result of detection on an image rather than a number from the file.

## A research example

Adapters are specific to the source, but **the research analysis is not**. `examples/research_use_case.py`
computes the time from the filing of the application to the issuing of the connection conditions, broken
down by resource class and publisher, without a single publisher-dependent branch, using only the fields
of the common schema:

```bash
gridqueue parse <documents...> --out panel.parquet
python examples/research_use_case.py panel.parquet
```

The result on the panel of six publishers (median, days): **consumption** connections 40 at TAURON
and 57 at ENERGA, **photovoltaics** 105 and 127, **energy storage** 119 and 146, **wind** 156 and 158.
Consumption connections are processed two to four times faster than generating ones, and the difference
between publishers persists within a class. This is a descriptive result: the register describes
administrative proceedings, so it must not be used to infer the causes of the differences or the quality
of a publisher's work; the portfolio of applications, the structure of the network and the disclosure
practice differ between operators.

## Longitudinal analysis

The register **does not publish a persistent application identifier**, so tracking a case between
editions requires a content key. `compare_editions` builds one and returns the flows together with the
status transition matrix:

```python
from gridqueue import compare_editions, linkage_audit, get_adapter

a = get_adapter("pl_pse").parse("edition_2026_07_31.xlsx").frame
b = get_adapter("pl_pse").parse("edition_2026_08_31.xlsx").frame
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
d.as_dict()["forward_share"]   # 0.9828
d.as_dict()["monotone_snapshot"]     # False

linkage_audit(a, b).as_dict()           # linkage precision: 0.9888-0.9963
```

Two results on the pair of PSE editions, July to August 2026. **98.28% of the status transitions run
in accordance with the order of the proceeding**, which is an independent test of the key's linkage,
because a key matching at random would not have produced that order. And the second: **the register is
not a monotonic snapshot**, 13 rows appear already in a closed state, and 33 rows with an active status
disappear. The difference between editions must therefore not be read as the change in the state of the
queue alone, and the tool reports this with a flag instead of letting the user fail to notice it.

Since the register has no persistent identifier, the linkage itself also requires checking.
`linkage_audit` compares every pair on nine fields **excluded from the key**; the key does not
enforce their agreement, so the agreement is independent evidence. Across all 804 pairs the
precision is **98.88-99.63%**: 795 pairs confirmed, 6 uncertain, 3 false.

```bash
python examples/longitudinal_use_case.py edition_A.xlsx edition_B.xlsx 2026-07-31 2026-08-31
```

## Reproducibility

`reproducibility/` contains a manifest of the source documents (address, date of download, SHA-256),
the versions of the libraries and the scripts that reproduce the derived figures and the figures
themselves. The documents are not redistributed, because they are replaced every quarter; the manifest
makes it possible to check whether we are working on the same edition.

## Quality control rules

Eight rules; each returns a count of violations, not an exception, because a violation is a property of
the disclosure rather than a fault of the tool: monotonicity of the proceeding dates, the two-year
validity of connection conditions (Article 7(8i)), admissibility of the process state against the dates
present, consistency of the capacity units, value ranges, duplicate identifiers, completeness of the
core, controlled vocabulary.

Since version 1.0 the core completeness rule assesses **the core appropriate to the entity of the row**,
and the capacity core is an **alternative** rather than a specific field: a generating application
declares injected capacity, a consuming one consumed capacity, and point 2 of the duty is sometimes
discharged with available capacity and sometimes with a count of free connection slots. In version 0.3.x
the core unconditionally required consumed capacity and applied the requirements of the application
entity to node rows as well, which turned a property of the schema into an apparent violation of the
disclosure; violations of that rule numbered 5,390 (28.044%) against **771 (4.011%)** now.

## Tests

```bash
python -m pytest -q      # 221 passed, 2 skipped (223 collected)
```

The two skips are conditional: they are the integration tests of the PSE and ENERGA adapters, which
require the source documents and are skipped when the documents are absent from the working tree. The
suite runs on Python 3.10-3.13 under Linux, macOS and Windows; CI checks this on every change
submitted.

Writing tests and visual measurement catch **different classes of defect** and both are present in the
package. Five mapping defects passed through the entire test suite, because none of them raised an
exception, among them one that reversed the agreement status in 88 rows of two publishers. They were
detected by comparing the output with the reference set read from the document.

## Limitations

* The reference set used to measure accuracy is **partly single-annotator**. Inter-annotator
  agreement was measured on a subsample of 35 rows read independently, blind:
  raw agreement 0,9725, Cohen's kappa 0,9690, zero perceptual discrepancies. The PSE
  and ENERGA reference sets remain single-annotator.
* The location at TAURON is an internal substation code; the operator does not publish a dictionary of
  the codes, so the resolver returns missing with the reason `kod_stacji_bez_slownika`. It does not
  guess.
* **None of the publishers reports coordinates.** The `wspolrzedne` field is populated by
  derivation from the place name against a gazetteer with geometry (13,149 names in 25 localities):
  1,225 of 19,220 panel rows. The evidential value of this field is therefore different from that of
  the fields transcribed from the document, and it is described as such in the result.
* A street name does not determine a point: 431 of 6,057 Warsaw names (7.12%) have disjoint components
  more than 2 km apart. The register gives the street but not the district, so **this ambiguity cannot
  be removed from the published data**. Every result carries the number of components and their spread,
  so that the recipient can filter such rows out.
* The UK Power Networks and Electricity North West portals return 403 at row level.
  We use only their public metadata and describe it as such. We do not circumvent access
  controls; the client identifies itself honestly in the `User-Agent` header.

## Citation

`CITATION.cff` at the root of the repository. The author entry is collective and has to be completed
with a list of individual authors before the paper is submitted.

## Licence

Apache-2.0 for **the code**. The input and output data have a separate status; official documents are not redistributed, and the geometric gazetteer is subject to ODbL with attribution and share-alike duties. Details in [`DATA_LICENSE.md`](DATA_LICENSE.md).

The licences of the input data are separate and fixed: the OpenStreetMap gazetteer under the ODbL 1.0
licence; the operators' statutory publications under their own terms of use, redistributed only
where that is permitted.

Change history: [`CHANGELOG.md`](CHANGELOG.md).
