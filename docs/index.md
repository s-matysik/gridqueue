---
title: gridqueue
---

# gridqueue

Harmonizer of statutory grid-connection disclosures for the electricity network.
Version **1.0.0** · [repository](https://github.com/s-matysik/gridqueue) ·
[run in the browser](app/) · [open in Colab](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

> **In English.** `gridqueue` parses the statutory grid-connection disclosures that Polish
> distribution system operators must publish under Article 7(8l) of the Energy Law, and emits
> rows in a single 21-field schema with **measured** extraction accuracy. Nine adapters cover five
> jurisdictions; the schema is derived from the legal obligation, not from any one document.
> Failures are returned as missing-with-reason, never as guesses.

## The problem

Distribution system operators have a duty to publish who is applying for a connection, where, for
what capacity and at what stage the proceeding stands. In Poland the duty covers approximately
180 licensed operators and **each one publishes in its own format**, most often as a document meant
for printing. The information is public, but it is not processable.

The heterogeneity concerns the **medium, not the concepts**, however. The transmission operator's
spreadsheet contains a list of the permitted values of the publisher field, naming the six largest
operators in the country; the form is therefore an agreed reporting template which each of them
fills in, only one issues it as a spreadsheet and another as a document meant for printing. The
common schema of this package is a reconstruction of that agreement.

## What the package does not do

It is not an index of operators' publications and not an overview map. Nor is it an estimate of the
available connection capacity: the register discloses the **queue, not the reserve**. It is not a
ranking of locations, it contains no model of preferences.

## State of the release

| publisher | rows in panel | fields from disclosure | fields including the derived one |
|---|---:|---:|---:|
| ESB Networks DAC | 46527 | 7 | 7 |
| TAURON Dystrybucja S.A. | 10955 | 15 | 15 |
| ENERGA-OPERATOR S.A. | 5382 | 17 | 17 |
| e-Distribución Redes Digitales S.L.U. | 1838 | 9 | 9 |
| Stoen Operator Sp. z o.o. | 1236 | 13 | 14 |
| PSE S.A. | 945 | 17 | 17 |
| National Grid Electricity Distribution | 694 | 10 | 10 |
| E-REDES S.A. | 469 | 6 | 6 |
| Boryszew Green Energy&Gas Sp. z o.o. | 8 | 8 | 9 |

**All 21 schema fields are populated in the panel.** The coordinate field is disclosed directly by
two publishers, ESB Networks and e-Distribucion, which together account for 48,363 rows. For the
Polish publishers it is not disclosed and arises by derivation from the place name, which covers
1,225 further rows; those two origins are kept apart, which is why the table separates the fields
coming from the disclosure from the derived field, and why the result of every resolution records a
confidence level and a placement accuracy level. Coordinates are present in 49,588 of 68,054 rows,
that is 72.9 per cent.

## Pages

* [**Run in the browser**](app/) with no installation: the same library in a WebAssembly
  interpreter, the document processed locally and sent nowhere
* [The 21-field schema](schema.md)
* [Adapters and how to add a publisher](adapters.md)
* [Extraction method](extraction.md)
* [Quality control rules](quality.md)
* [Measured validation](validation.md)
* [Longitudinal analysis, comparison of editions](longitudinal.md)
* [Charts](charts.md): every result as a figure, in the library, the command line, Colab and the browser
* [Running in Google Colab](colab.md)
* [Command line](cli.md)
* [Limitations](limitations.md)
* [Names in the wording of the statute](schema.md#names-in-the-wording-of-the-statute)

## Installation

```bash
git clone https://github.com/s-matysik/gridqueue
cd gridqueue
pip install -e ".[test]"
python -m pytest -q
```

## The shortest example

```python
from gridqueue import get_adapter, run_quality, audit_column_shift

res = get_adapter("pl_tauron").parse("tauron_informacja.pdf")
df = res.frame                        # frame in the 21-field schema
res.report["n_rows"]               # 10955
audit_column_shift(df).share         # 0.0
run_quality(df).as_dict()["violations_total"]
```
- [Analytical layer](analysis.md)
