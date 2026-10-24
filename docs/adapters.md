---
title: Adapters
---

# Adapters

Every adapter implements the same interface and **declares** which schema fields it populates and
which extensions it contributes. The declaration is part of the result rather than of the
documentation; thanks to that, field coverage is not an assertion but a value readable from the code.

| key | publisher | jurisdiction | schema fields | extensions |
|---|---|---|---:|---:|
| `pl_tauron` | TAURON Dystrybucja S.A. | PL | 15 | 9 |
| `pl_energa` | ENERGA-OPERATOR S.A. | PL | 17 | 25 |
| `pl_pse` | PSE S.A. | PL | 17 | 24 |
| `pl_stoen` | Stoen Operator Sp. z o.o. | PL | 13 | 7 |
| `pl_boryszew` | Boryszew Green Energy&Gas Sp. z o.o. | PL | 10 | 6 |
| `uk_nationalgrid` | National Grid Electricity Distribution | UK | 10 | 9 |

The `pl_pse` and `pl_energa` adapters share the module `adapters/_ptpiree.py`, because both
publishers fill in the same agreed reporting template, one issuing it as a spreadsheet, the other as a
document meant for printing. This is not an implementation coincidence but a reflection of sector
practice.

## Adding a publisher

```python
from gridqueue.adapters.base import Adapter, ParseResult

class MojAdapter(Adapter):
    key = "pl_moj_operator"
    publikujacy = "Nazwa Operatora S.A."
    jurysdykcja = "PL"
    detekcja = [r"moj_operator", r"nazwa_operatora"]   # file name patterns

    def parse(self, source) -> ParseResult:
        ...   # return a frame in the schema + a report
```

Registration: adding the class to `REGISTRY` in `gridqueue/registry.py`. The core stays untouched.

```bash
gridqueue adapters          # declarations of all publishers
```

## Detecting the publisher

```python
from gridqueue import detect_publisher
detect_publisher("tauron_informacja_2026_06_30.pdf")   # 'pl_tauron'
```

The order is deliberate: the file name is cheap and usually sufficient, the content of the first page
settles the rest. When neither settles it, `None` is returned, with no guessing.

## E-REDES (Portugal), `pt_eredes`

The third jurisdiction in the panel and the third mode of issue: **a dataset on an open
data portal with a REST interface**, published quarterly. The unit of a row is a
substation or a cut point of the high voltage network; there are 469 rows and all of them
belong to the NODE entity.

What this adapter contributes that was not there before: **the first foreign source of the NODE
entity**. Until now the node rows came only from two Polish publishers, so the
criterion "available connection capacity" could be computed in one jurisdiction.
The Portuguese source additionally reports the **composition of the substation group**, exactly the
information which, in the Polish panel, makes it possible to assign applications to a node.

### The settlement on units

The publisher reports the reception capability and the connected capacities in **MVA**, that is in
apparent power. The canonical unit of the schema is **kW of active power**. These are different
physical quantities, and converting one into the other requires a power factor,
which the publisher does not report.

That is why `moc_dostepna` remains **empty**, and the values in MVA go into the
extension fields together with the source unit recorded explicitly:

| extension field | meaning |
|---|---|
| `_jednostka_mocy_zrodlowa` | `MVA` |
| `_moc_dostepna_mva` | MV+HV reception capability |
| `_moc_przylaczona_mva` | capacity already connected |
| `_moc_zakontraktowana_mva` | contracted capacity |
| `_moc_w_potwierdzaniu_mva` | capacity under confirmation |

This is the same principle that was applied to the publisher reporting a count of
free connection slots instead of a capacity: entering a count of slots into a field with a different
unit would be fabrication, not harmonization.

The core of the NODE entity is nevertheless satisfied, because it is discharged by the second member of
the alternative, `ograniczenie_flaga`, set on the basis of a zero reception capability. Zero is
a **disclosed** value and means a constraint; an empty cell means non-disclosure
and does not set the flag. This concerns 222 of 469 nodes.

That settlement is at the same time an observational finding: **both jurisdictions satisfy
the core of the NODE entity through different members of the same alternative**, Poland with available
capacity, Portugal with the constraint flag. The conditional core, introduced in version 1.0 for
a Polish category error, turned out to be the condition for absorbing a foreign jurisdiction.

```python
from gridqueue import get_adapter
r = get_adapter("pt_eredes").parse("pt_eredes_capacidade_rececao_rnd_2T2026.csv")
r.frame[["id_wezla", "nazwa_wezla", "lokalizacja_tekst", "ograniczenie_flaga"]]
r.report["note_units"]
```

## e-Distribución (Spain), `es_edistribucion`

**The first foreign source issued as a document meant for printing.** Until now both foreign
adapters read data that was already tabular, so transferability had been shown on a case
easier than the Polish one; this source closes that gap. The publisher issues a **monthly PDF**
in a series covering the years 2023-2025, under Article 33(9) of Law 24/2013,
Article 5(4) of Decree 1183/2020 and Article 12 of Circular 1/2021 of the regulator CNMC, that is
in a legal construction identical to the Polish one: a statutory duty, a fixed frequency, the format
left to the publisher.

The issue of 1 August 2025: 28 pages, **1,838 rows of the NODE entity**, all declared fields
populated at 100 %, including **the geographic coordinates of every substation**,
which no Polish publisher does. The capacities are in **MW of active power**, so conversion
to the canonical kW is an ordinary change of order of magnitude.

### Column semantics established by arithmetic, not by the header

The header has cells merged at two levels and suggests that the columns "Con permiso de AyC"
and "En trámite con capacidad" belong to the group of **accepted and unsettled** capacity.
The arithmetic of the document settles it. Eleven subcolumns, nine substation items plus those two,
sum to the **occupied** capacity, in exactly **1,838 of 1,838 rows, in both editions
checked**; the technology breakdown sums to the accepted and unsettled capacity in
all rows with a non-zero value. Both groups are therefore **components** rather than
alternative breakdowns. Taking the header on trust would have given a silent transposition of two
capacity fields.

### Arithmetic closure instead of a reference set

For this publisher there is **no reference set read independently of the parser**, so the extraction
accuracy cannot be measured the way it was measured for the Polish publishers. Arithmetic closure
is a substitute piece of evidence: for the sum of eleven cells to agree with the twelfth, all
twelve have to be read correctly. Across two editions that gives **3,676 independent
checks, all of them closed**. This is evidence of **consistency of reading, not a measurement of
accuracy**, weaker than a reference set, but checkable on every new edition, without an annotator's
work. The adapter report gives it in the field `identity_sum_occupied_capacity`.

## ESB Networks (Ireland), `ie_esbnetworks`

The largest source in the panel: **46,527 rows**, the only one going below the level of high
voltage substations all the way down to MV/LV substations. The unit of a row is a group of
transformers at a substation. Coordinates are present in 46,525 rows.

### Two units in one file

The publisher reports the **offtake side in MVA** (apparent power) and the **generating side in MW**
(active power). The `moc_dostepna` field therefore carries the available **firm generating**
capacity, converted from MW to kW, while the offtake side stays in the extensions with the unit in the
field name. Summing MW with MVA would give a figure with no physical sense, and choosing one side
without saying so openly would be hiding a decision.

### One interpretation, recorded explicitly

The constraint columns carry the phrase `Constrained, otherwise capacity available = X kVA` or are
empty. We assume that **an empty cell means no constraint** rather than no declaration:
the column is a binary indicator in which the positive value carries an explanation and the negative
one is expressed by emptiness. The publisher nowhere describes this convention, so it is **an
interpretation, not the content of the source**; the raw phrase stays in an extension, the figure in
it is extracted separately and **is not converted**, because it is in kVA. The decision is recorded in
the adapter report and pinned by a test, so that a change to it would be visible.

The two source flags (offtake and generating) enter one schema field as an
**alternative that preserves indeterminacy**: `None` combined with `False` gives `None`,
not `False`.
