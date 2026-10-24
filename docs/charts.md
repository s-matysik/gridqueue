---
title: Charts
---

# Charts

`gridqueue.plots` draws every result of the package. It needs matplotlib, installed with the
`plot` extra:

```bash
pip install "gridqueue[plot] @ git+https://github.com/s-matysik/gridqueue@v1.7.0"
```

## Principles

* **A chart is a view of a result, never a second computation of it.** Every function takes the
  object an analysis returns (a frame in the schema, an `EditionDelta`, a `LinkageAudit`, the frame
  of `node_loading`) and calls the same functions the report uses, so the numbers in a title or a
  legend are the numbers of the report.
* **Absence is drawn as absence.** A field the publisher does not disclose is a grey `-` cell, not
  a zero; a node with zero declared free capacity has an undefined loading and is counted in the
  title, not drawn as infinite; a coordinate that cannot be given is shown with its reason.
* **Inclusion criteria are fixed in advance.** Processing-time curves are drawn only for groups of
  at least `min_n` applications, and `save_all` skips them, with the reason, when fewer than 80% of
  the applications carry both dates.
* Figures are created without `pyplot`: the same code runs in a script, in Jupyter or Colab (a
  returned figure displays itself) and in the browser page.

## Functions

| Function | Input | Shows |
|---|---|---|
| `plot_field_coverage(df)` | panel | share of rows populating each of the 21 fields, per publisher |
| `plot_quality(df)` | panel | violations of the eight rules, evaluated and stacked per publisher |
| `plot_column_shift(df)` | panel | rows with a value in a field it cannot belong to |
| `plot_status_distribution(df, normalize=True)` | panel | applications by stage of the proceeding |
| `plot_capacity_by_class(df)` | panel | requested capacity of the active queue by class and voltage |
| `plot_processing_time(df, by="klasa_zasobu")` | panel | Kaplan-Meier curves, censored at the as-at date, 95% band |
| `plot_node_loading(L)` | `node_loading(...)` | queue over declared free capacity per node, log scale |
| `plot_edition_flows(delta)` | `compare_editions(...)` | shared, new and absent rows, with the warning segments |
| `plot_transitions(delta)` | `compare_editions(...)` | status transition matrix; backward moves outlined |
| `plot_linkage_audit(audit, recall)` | `linkage_audit`, `linkage_recall` | confirmed, uncertain, false and missed pairs |
| `plot_edition_comparison(delta, audit, recall)` | all three | the three views above in one figure |
| `plot_location_resolution(df)` | panel, optionally after `geocode_frame` | source of each coordinate, or the reason for its absence |
| `plot_overview(df)` | panel | coverage, quality, stage and capacity in four panels |
| `save_figure(fig, path)` | figure | PNG, SVG or PDF from the suffix, 300 dpi by default |
| `save_all(df, out_dir, edition_b=...)` | panel | every chart the data supports; skipped ones listed |

## Examples

```python
from gridqueue import (parse_sources, compare_editions, linkage_audit, linkage_recall,
                       assign_to_nodes, node_loading, station_node_map, plots)

panel, _ = parse_sources(["applications.pdf", "demand_capacity.pdf", "generation_capacity.pdf"])
plots.plot_processing_time(panel, by="klasa_zasobu", min_n=30)

L = node_loading(assign_to_nodes(panel, station_node_map(panel)), voltage="110")
plots.save_figure(plots.plot_node_loading(L), "node_loading.pdf")

a, b = parse_sources(["edition_07.xlsx"])[0], parse_sources(["edition_08.xlsx"])[0]
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
plots.plot_edition_comparison(d, linkage_audit(a, b), linkage_recall(a, b))
```

From the command line:

```bash
gridqueue plot panel.parquet --out charts/ --format png,svg
gridqueue plot edition_07.parquet --edition-b edition_08.parquet --label-a 2026-07-31 --label-b 2026-08-31 --out charts/
```

Without a real disclosure, `gridqueue.examples.synthetic_panel()` and `synthetic_editions()`
produce labelled synthetic data on which every chart can be tried.
