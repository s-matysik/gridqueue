---
title: Quality rules
---

# Quality control rules

Eight rules. Each returns **a count of violations, not an exception**, because a violation is
usually a property of the disclosure rather than a fault of the tool. The rules are derived from the
provision: the two-year validity of connection conditions follows from Article 7(8i), not from the
designer's preference.

Measured on the panel of 19,220 rows, schema version 1.0:

| rule | what it checks | TAURON | ENERGA | Stoen | PSE | National Grid | Boryszew | panel | share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 | monotonicity of the proceeding dates | 45 | 163 | 0 | 3 | 0 | 0 | 211 | 1.098% |
| R2 | two-year validity of connection conditions | 583 | 174 | 7 | 12 | 0 | 0 | 776 | 4.037% |
| R3 | admissibility of the process status against the dates | 1 | 138 | 0 | 0 | 0 | 1 | 140 | 0.728% |
| R4 | consistency of the capacity units | 0 | 13 | 0 | 0 | 0 | 0 | 13 | 0.068% |
| R5 | value ranges | 0 | 13 | 0 | 0 | 0 | 0 | 13 | 0.068% |
| R6 | duplicate identifiers | 1,029 | 59 | 0 | 0 | 0 | 0 | 1,088 | 5.661% |
| R7 | completeness of the schema core | 0 | 766 | 0 | 5 | 0 | 0 | 771 | 4.011% |
| R8 | controlled vocabulary | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.000% |

The "panel" column is the number of rows violating the rule across the whole panel; it closes to the
sum of the publisher columns, which is checked by an assertion when this page is generated. In
version 0.3.x the page reported inflated figures for R7; the reason is described in the paragraph on
R7 below.

## How to read the results

**R2** is the sum of two mutually disjoint sub-checks and has to be reported as such: 361 expiry
dates fall later than two years after the conditions were issued, **and** 415 agreements were
concluded after those two years had elapsed. The first component has the signature of a settled
administrative rule of the publisher, with a median overrun of 21 days; the second remains an open
finding.

**R4 and R5** point to the same set of 13 rows with a **negative injected capacity**, the smallest
value being −700 kW. One of them ended up in the reference sample and the visual reading confirms the
negative value, so this is a property of the disclosure, not an extraction error. The rule did what
it is there for: it acted as a detector of source quality.

**R7 has, since version 1.0, measured the core appropriate to the entity of the row.** In version 0.3.x
the core required the `capacity_withdrawn` field unconditionally and applied the requirements of the
APPLICATION entity to rows of the NODE entity as well. Both decisions turned **a property of the schema
into an apparent violation of the disclosure**: a purely generating application declares injected
capacity, not consumed capacity, and a node row has neither an application identifier nor an
application capacity, because it discharges a different point of the provision. The core now
requires:

* for the **APPLICATION** entity, `application_id`, `location_text`, `resource_class`, `process_status`
  and **at least one** of the pair (`capacity_withdrawn`, `capacity_injected`);
* for the **NODE** entity, `node_id` and **at least one** of the pair
  (`capacity_available`, `constraint_flag`), because point 2 of the duty is sometimes discharged with
  available capacity and sometimes with a count of free connection slots.

After that change R7 falls from 5,390 (28.044%) to **771 (4.011%)**, and the number of rows
with a complete core is **18,449 of 19,220**. The remaining violations are gaps in the
disclosure, not an artefact of the schema: 570 applications with no capacity at all,
202 applications with no location description and 2 nodes with neither available capacity nor a
constraint flag. There are 19,055 rows of the APPLICATION entity and 165 of the NODE entity.

**R8** uses a controlled vocabulary taken from the drop-down list tab of the reporting template, that
is from an authoritative sector source rather than from a convention of our own.

```python
from gridqueue import run_quality
q = run_quality(df)
q.as_dict()["violations_total"]
q.as_frame()          # one row per rule
```

The shares on this page are computed from the raw counters (violations / panel rows) rather than from
the rounded values of the `share` field, so that they do not diverge from the figures in the last
digit.
