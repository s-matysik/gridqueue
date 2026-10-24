---
title: Analytical layer
---

# Analytical layer

Adapters are specific to the publisher. Everything above the schema is not,
and that is the whole point of the package. This page describes two analyses that
become possible only after harmonization.

## Node loading, that is the criterion "available connection capacity"

Literature reviews on siting network infrastructure list available connection
capacity as a criterion that is frequent and at the same time unmeasurable,
because of the absence of the data in open sources. It is measurable, provided the
publisher discloses both the available capacity at the node **and** the composition
of the substations belonging to the node. In the panel, one publisher does so.

```python
from gridqueue import station_node_map, assign_to_nodes, node_loading

mapping = station_node_map(panel)              # station -> group of stations
panel = assign_to_nodes(panel, mapping)        # assignment of applications to groups
L = node_loading(panel, capacity_field="capacity_injected")
L[["node_name", "applications", "capacity_requested", "capacity_available", "loading"]]
```

**The key is the group of stations, not the node row.** The publisher lists the same
group twice, separately for the generating and the consuming direction, so a mapping
based on the row identifier would make every substation ambiguous.
That would be an artefact of the document layout, not a property of the network.

**The assignment is by name, not topological.** It rests on the agreement of the names
disclosed by the publisher, not on a model of the network, and its correctness was not
validated against an external reference set, because none exists. The matching status
is returned explicitly and distinguishes five cases:

| status | meaning |
|---|---|
| `EXACT` | substation name equal to the location after normalization |
| `EXTENDED` | the location contains the substation name as a contiguous subsequence of tokens |
| `LINE` | an object planned **on a line** between substations, not at a node |
| `AMBIGUOUS` | more than one group matches |
| `NONE` | no hit or no location |

The `LINE` category exists because entries of the kind "planowany RS w linii 110 kV
relacji A, B" describe an object lying **between** nodes. Matching by name
would assign their full capacity to whichever end of the line happens to appear in the
list of substations, which is arbitrary. Such applications are left unassigned and
counted separately.

A node with zero disclosed available capacity gets a quotient of `NaN`, not
infinity: the quotient there is **undefined**, and averaging it would be an
error. The applied capacity is nevertheless retained for it, because a queue to a node
with no free capacity is information, not missing data.

## Processing time with censoring

An application with no settlement date **is not missing data**: it is an observation
truncated at the publication date of the edition. Computing the median only on complete
cases understates it, and the more strongly the longer the real processing
time is, that is most strongly exactly where the result matters to us.

```python
from gridqueue import processing_time, kaplan_meier

d = processing_time(panel)                       # time_days + event (1/0)
km = kaplan_meier(d["time_days"], d["event"])
km.as_dict()["median"], km.as_dict()["censored_share"]
```

The Kaplan-Meier estimator was implemented directly, with Greenwood variance, so as
not to introduce a dependency on a survival analysis library for the sake of one
estimator. The interval for the median is determined by inverting the confidence band
of the curve.

## Recall of the longitudinal linkage

`linkage_audit` measures **precision**: whether the linked pairs concern the same
case. `linkage_recall` measures **recall**: how many pairs the key missed. The latter
are the more dangerous, because a broken pair appears as one "departed" row and one
"new" one, so it looks like an event in the register when it is an artefact of the
linkage.

```python
from gridqueue import linkage_recall

r = linkage_recall(edition_a, edition_b)
r.as_dict()["key_sensitivity"]
r.recovered_keys["different_key_fields"].value_counts()
```

The identity fields used for recovery have to be **disjoint from the key**. A field
shared with the key will not detect a pair broken by a change in exactly that field,
because the identity diverges together with the key. Measured on a pair of editions of the
transmission operator: adding the location to the set of identity fields raises the apparent
recall from 0.9652 to 0,9757, and in reality hides ten pairs.
