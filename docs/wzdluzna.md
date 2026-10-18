---
title: Longitudinal analysis
---

# Comparison of register editions

The statutory duty requires the disclosure to be replaced at least once per quarter, so consecutive
editions of the same register are natural material for longitudinal analysis. One thing stands in the
way of this and has to be declared rather than passed over in silence.

## The register does not publish a persistent application identifier

At some publishers the object identifier field is empty in almost every row,
at PSE in 866 of 876, and the package then inserts a surrogate based on the ordinal number
in the document. Such a surrogate is stable **within a single edition and worthless between
editions**: position 869 in one edition is not the same application as position 869
in the next, because the rows shift. A join on the identifier would give a result that looks
sensible and is entirely false.

`compare_editions` therefore uses a **content key** built from the publisher, the location,
the voltage level, the resource class and both capacities. Dates and status are deliberately excluded
from the key: dates are sometimes filled in between editions, and the status is precisely what we are
measuring the change of.

A limitation of the content key: it diverges when the publisher corrects any of the fields
it is built from, and then the same application looks like a disappearance paired
with an appearance. The measure below makes it possible to judge how often this happens.

## The linkage algorithm, full specification

So that the result can be reproduced and challenged, we state the rules openly.

1. **The key** is the concatenation of six fields: publisher, location text, voltage level,
   resource class, injected capacity, consumed capacity. The values are taken **after harmonization by
   the adapter**, that is after normalization of whitespace, units and controlled vocabularies;
   apart from that the comparison is **exact, with no tolerance**, including for the capacities.
2. **A missing value is a value.** An empty field enters the key as an empty string, so a row
   with a missing capacity will match only a row in which that capacity is also empty. Filling in
   the capacity by the publisher therefore breaks the pair and gives one disappearance and one appearance.
   The same applies to a change of the voltage level or the resource class.
3. **Uniqueness is required in both editions.** Rows with a repeating key are rejected
   before linkage, the first being retained, because for them a one-to-many assignment has no
   unambiguous settlement. The figures are reported: `wierszy_w_kolizji_a` and `_b` give
   how many rows stand in colliding groups, and `odrzuconych_jako_niejednoznaczne_a` and `_b`, how many
   actually drop out of the linkage.
4. **New and departed** are simply differences of the sets of keys, computed after the collisions have
   been rejected.
5. **Dates and status are excluded from the key**: dates are sometimes filled in between editions, and
   the status is precisely what we are measuring the change of.

On the pair of PSE editions the collisions cover 56 rows in the July edition and 48 in the August one,
which after rejection leaves 31 and 27 rows dropping out of the linkage, respectively 3,5 % and 3,1 % of
the rows.

## Linkage precision measured on held-out fields

The transition matrix is indirect evidence, so we add direct evidence.
`linkage_audit` compares every linked pair on **nine fields excluded from the key**:
the name of the applying entity, the name of the object, the date the application was filed and six fields of the
capacity breakdown by technology. The key does not enforce the agreement of any of them, so their
agreement is independent evidence that the pair concerns the same application.

A pair is **false** when the stem of the entity name AND the stem of the object name diverge and
neither is contained in the other; **uncertain** when exactly one of them diverges; **confirmed**
in the remaining cases. The stem of a name arises by removing the legal form, punctuation
and spaces, because the publisher changes the way the legal form is written between editions. A field
filled in on one side only, empty in one edition, populated in the other, is not counted as a divergence,
because it is an editing of the same application.

The result on the pair of PSE editions, on **all 804 pairs**, not on a sample:

| class of pair | count | share |
|---|---:|---:|
| confirmed | 795 | 98,88 % |
| uncertain | 6 | 0,75 % |
| false | 3 | 0,37 % |

The linkage precision therefore falls in the range **98,88 % to 99,63 %**, depending on whether
the uncertain cases are counted as wrong or as right. The three false pairs are different applications
sharing location, voltage, class and both capacities, for example two energy storage facilities of the same
capacity in the same locality. The transition result is robust against them: after removing the nine
doubtful pairs the share of forward transitions changes from 98,28 % to 98,25 %.

A caveat we do not leave out: this is not validation against an external truth, because for this
register no such truth exists, there is no persistent identifier against which the
linkage could be checked. It is a test of internal consistency on data the key does not touch.

## The transition matrix as a test of the linkage

If the key links the right rows, the status transitions should run in the direction of the
administrative proceeding. If it links at random, they will be distributed without that order.
On the pair of PSE editions of 31 July and 31 August 2026, **98,28 % of the transitions run forward**
(57 of 58), with one backward transition from an agreement in force to conditions issued.
This is a test independent of the linkage itself, and that is exactly why it has value.

## The register is not a monotonic snapshot

The second result from the same pair of editions is a warning to anyone who might want to read the
difference between editions as a change in the state of the queue:

| quantity | value |
|---|---:|
| rows in the July edition | 892 |
| rows in the August edition | 876 |
| unique keys | 861 and 849 |
| common | 804 |
| new | 45 |
| departed | 57 |
| status changes | 58 |
| **new, already in a closed state** | **13** |
| **departed with an active status** | **33** |

Thirteen rows appear in the newer edition already as a withdrawn application, a refusal or expired
conditions, which means the register **adds completed cases retrospectively**. Thirty-three rows
with an active status disappear, which cannot be explained by the proceeding having ended. The
`migawka_monotoniczna` property returns `False` on this pair and that is meant to be a signal, not a
technical detail.

```python
from gridqueue import compare_editions, linkage_audit, get_adapter

a = get_adapter("pl_pse").parse("edycja_2026_07_31.xlsx").frame
b = get_adapter("pl_pse").parse("edycja_2026_08_31.xlsx").frame
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
d.as_dict()
d.przejscia          # status transition matrix

linkage_audit(a, b).as_dict()   # linkage precision
```

A full run with a figure: `examples/longitudinal_use_case.py`.

## Running without installation

This whole analysis is reproduced by the Colab notebook on the publisher's live data, with an assertion of agreement with the published figures, see [Google Colab](colab.md).


## The key has to be matched to the entity

The default content key is built for the WNIOSEK entity. On rows of the WĘZEŁ entity it
**falls apart**, because the application fields, the resource class and both capacities, are empty there.
A mismatch **does not report an error**: it quietly produces collisions, which in further analysis look like
events in the register.

Measured on a pair of issues of the Spanish publisher (1 July and 1 August 2025, 1 838
rows each):

| key | collisions | rejected as ambiguous | linked pairs | precision | recall |
|---|---:|---:|---:|---:|---:|
| `DEFAULT_KEY_FIELDS` (application) | 916 | 660 | 1 178 |, |, |
| `NODE_KEY_FIELDS` (node) | 0 | 0 | **1 838** | **1,000** | **1,000** |

For comparison: on the Polish transmission register the same method gives a precision of 98,88-99,63 %
and a recall of 0,9652. The difference is not a property of the method but of the **disclosure
practice**: the Spanish publisher issues a stable node identifier, whereas the Polish one does not
publish a persistent application identifier. The method therefore also measures how far a register
lends itself to tracking over time.

```python
from gridqueue import NODE_KEY_FIELDS, compare_editions, linkage_audit

d = compare_editions(a, b, "2025-07-01", "2025-08-01", fields=NODE_KEY_FIELDS)
linkage_audit(a, b, fields=NODE_KEY_FIELDS,
              held_out=("nazwa_wezla", "wspolrzedne", "_wezel_przesylowy")).as_dict()
```
