"""Charts drawn from the harmonised panel and from the results of the analyses.

Every function takes the same objects the rest of the package returns (a frame in the
21-field schema, an :class:`~gridqueue.longitudinal.EditionDelta`, a
:class:`~gridqueue.longitudinal.LinkageAudit`, the frame returned by
:func:`~gridqueue.analysis.node_loading`) and returns a :class:`matplotlib.figure.Figure`.
Nothing is computed here that the analysis functions do not already compute: a chart is a
view of a result, never a second implementation of it, so the numbers on a chart are the
numbers in the report by construction.

The same module draws the charts in the command line (``gridqueue plot``), in the Colab
notebook and in the browser page, which loads this package into a WebAssembly interpreter.

Design rules
------------
* **Figures are created without** ``pyplot``. A figure does not enter the global state of
  the interpreter, so a loop over many publishers does not accumulate open windows, and the
  module works unchanged on a server, in a notebook and in the browser. In Jupyter and
  Colab a returned figure is displayed automatically; in a script call
  ``fig.savefig(path)`` or :func:`save_figure`.
* **What the register does not disclose is drawn as absence**, not as zero: a field a
  publisher does not publish is a grey cell marked ``-``, a node with no declared free
  capacity has an undefined loading and is drawn apart from the others.
* ``matplotlib`` is an optional dependency (``pip install "gridqueue[plot]"``); the core of
  the package does not need it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Sequence

import pandas as pd

from .analysis import kaplan_meier, kaplan_meier_by_group, processing_time
from .layout import audit_column_shift
from .longitudinal import STATUS_ORDER, TERMINAL_NEGATIVE
from .quality import run_quality
from .schema import STATUSES, schema_table

__all__ = [
    "PUBLISHER_SHORT", "PUBLISHER_COLORS", "STATUS_LABELS", "CLASS_LABELS",
    "ACTIVE_STATUSES", "EVENT_LABELS", "publisher_label",
    "plot_field_coverage", "plot_quality", "plot_column_shift",
    "plot_status_distribution", "plot_capacity_by_class", "plot_processing_time",
    "plot_node_loading", "plot_edition_flows", "plot_transitions", "plot_linkage_audit",
    "plot_edition_comparison", "plot_location_resolution", "plot_overview",
    "save_figure", "save_all",
]

#: Short publisher names used on axes. Unknown publishers are shown under their own name.
PUBLISHER_SHORT: dict[str, str] = {
    "TAURON Dystrybucja S.A.": "TAURON",
    "ENERGA-OPERATOR S.A.": "ENERGA",
    "Stoen Operator Sp. z o.o.": "Stoen",
    "PSE S.A.": "PSE",
    "National Grid Electricity Distribution": "National Grid",
    "Boryszew Green Energy&Gas Sp. z o.o.": "Boryszew",
    "e-Distribución Redes Digitales S.L.U.": "e-Distribución",
    "ESB Networks DAC": "ESB Networks",
    "E-REDES S.A.": "E-REDES",
}

#: Colours of the publishers. The first six are those of the article figures.
PUBLISHER_COLORS: dict[str, str] = {
    "TAURON": "#1b5e8c", "ENERGA": "#2e8b78", "Stoen": "#c77a1e", "PSE": "#7a4b9c",
    "National Grid": "#6b7280", "Boryszew": "#a33b4e", "e-Distribución": "#d1495b",
    "ESB Networks": "#e9b44c", "E-REDES": "#7fb7be",
}
_FALLBACK = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#9c755f", "#edc948", "#76b7b2"]

#: English labels of the controlled status vocabulary.
STATUS_LABELS: dict[str, str] = {
    "APPLICATION_FILED": "filed", "APPLICATION_INCOMPLETE": "incomplete",
    "UNDER_REVIEW": "under review", "CONDITIONS_ISSUED": "conditions issued",
    "AGREEMENT_IN_FORCE": "agreement in force", "CONNECTED": "connected",
    "CONDITIONS_EXPIRED": "conditions expired", "REFUSED": "refused",
    "AGREEMENT_TERMINATED": "agreement terminated", "APPLICATION_WITHDRAWN": "withdrawn",
    "UNSPECIFIED": "unspecified",
}

#: English labels of the controlled resource-class vocabulary.
CLASS_LABELS: dict[str, str] = {
    "PV": "photovoltaics", "WIND": "wind", "HYDRO": "hydro", "BIOGAS": "biogas", "GAS": "gas",
    "COAL": "coal", "BESS": "energy storage", "LOAD": "consumption", "MIX": "mixed",
    "GRID": "network", "OTHER": "other", "UNSPECIFIED": "unspecified",
}

#: Statuses of an application still in the queue (the default of ``node_loading``).
ACTIVE_STATUSES: tuple[str, ...] = (
    "APPLICATION_FILED", "APPLICATION_INCOMPLETE", "UNDER_REVIEW", "CONDITIONS_ISSUED",
    "AGREEMENT_IN_FORCE")

#: Readable names of the closing events of a proceeding, for chart titles.
EVENT_LABELS: dict[str, str] = {
    "date_conditions": "issue of connection conditions", "date_agreement": "connection agreement",
    "date_refusal": "refusal", "date_energisation": "energisation",
    "date_application": "application",
}
_DIRECTION = {"generation": "generation direction", "demand": "demand direction"}

_GREY = "#6b7280"
_INK = "#222222"
_STATUS_COLORS = {
    "APPLICATION_FILED": "#c9dcea", "APPLICATION_INCOMPLETE": "#a3c4dc",
    "UNDER_REVIEW": "#5b93b8", "CONDITIONS_ISSUED": "#1b5e8c",
    "AGREEMENT_IN_FORCE": "#2e8b78", "CONNECTED": "#14532d",
    "CONDITIONS_EXPIRED": "#e0a96d", "REFUSED": "#a33b4e", "AGREEMENT_TERMINATED": "#c77a1e",
    "APPLICATION_WITHDRAWN": "#d4b8a0", "UNSPECIFIED": "#d1d5db",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mpl():
    try:
        import matplotlib  # noqa: F401
        from matplotlib.figure import Figure
    except ImportError as e:  # pragma: no cover - exercised only without matplotlib
        raise ImportError(
            "charts need matplotlib: pip install \"gridqueue[plot]\"") from e
    return Figure


def _figure(w: float, h: float, ax=None):
    """Return (fig, ax): a new figure, or the figure of the axis supplied."""
    if ax is not None:
        return ax.figure, ax
    Figure = _mpl()
    fig = Figure(figsize=(w, h), dpi=110, layout="constrained")
    return fig, fig.add_subplot(1, 1, 1)


def _style(ax, grid_axis: str | None = "x") -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#9ca3af")
    ax.tick_params(colors="#374151", labelsize=7.5)
    if grid_axis:
        ax.grid(axis=grid_axis, color="#e5e7eb", lw=0.7, zorder=0)
        ax.set_axisbelow(True)


def _th(n) -> str:
    return f"{int(round(float(n))):,}"


def publisher_label(p) -> str:
    """Short name of a publisher for an axis label."""
    if p is None or (isinstance(p, float) and p != p) or str(p).strip() == "":
        return "(publisher not set)"
    return PUBLISHER_SHORT.get(str(p), str(p))


def _color(short: str, i: int) -> str:
    return PUBLISHER_COLORS.get(short, _FALLBACK[i % len(_FALLBACK)])


def _groups(df: pd.DataFrame, by: Optional[str]) -> list[tuple[str, pd.DataFrame]]:
    """Split by publisher (or another column), largest group first."""
    if by is None or by not in df.columns or df[by].isna().all():
        return [("panel", df)]
    keys = df[by].fillna("").astype(str)
    order = keys.value_counts().index.tolist()
    return [(publisher_label(k) if by == "publisher" else (k or "(empty)"),
             df[keys == k]) for k in order]


def _filled(s: pd.Series) -> pd.Series:
    txt = s.astype(str).str.strip()
    return s.notna() & txt.ne("") & txt.str.lower().ne("nan") & txt.ne("<NA>")


def _empty_note(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=8, color=_GREY,
            transform=ax.transAxes, wrap=True)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def _group_key(df: pd.DataFrame, by) -> pd.Series:
    """The same group key as :func:`~gridqueue.analysis.kaplan_meier_by_group`."""
    col = [by] if isinstance(by, str) else list(by)
    return df[col].astype("string").fillna("(empty)").agg(" / ".join, axis=1)


def _applications(df: pd.DataFrame) -> pd.DataFrame:
    if "_entity" in df.columns:
        return df[df["_entity"].fillna("APPLICATION").astype(str).str.upper() != "NODE"]
    return df


# ---------------------------------------------------------------------------
# what a disclosure contains
# ---------------------------------------------------------------------------

def plot_field_coverage(df: pd.DataFrame, by: str = "publisher", ax=None,
                        annotate: bool = True):
    """Heat map: share of rows in which each of the 21 schema fields is populated.

    One column per publisher (or per value of ``by``), with the row count under its name.
    A field the publisher does not disclose at all is a grey ``-`` cell, distinct from a
    sparsely populated one. Core fields are marked with a bullet.
    """
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    st = schema_table()
    fields = st["field"].tolist()
    core = dict(zip(st["field"], st["core"].astype(bool)))
    groups = _groups(df, by)
    Z = np.zeros((len(fields), len(groups)))
    for j, (_, sub) in enumerate(groups):
        for i, f in enumerate(fields):
            Z[i, j] = float(_filled(sub[f]).mean()) if f in sub.columns and len(sub) else 0.0

    fig, ax = _figure(max(3.4, 1.8 + 0.72 * len(groups)), 5.8, ax)
    cmap = LinearSegmentedColormap.from_list("cov", ["#f7f7f7", "#c9dcea", "#5b93b8", "#1b5e8c"])
    im = ax.imshow(Z, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(groups)))
    import textwrap

    # long publisher names are wrapped, so that neighbouring column headers do not overlap
    ax.set_xticklabels([textwrap.fill(str(k), 12) + f"\n{_th(len(s))}" for k, s in groups],
                       fontsize=6.3)
    ax.set_yticks(range(len(fields)))
    ax.set_yticklabels([("\u2022 " if core[f] else "") + f for f in fields], fontsize=6.5)
    for i, f in enumerate(fields):
        if core[f]:
            ax.get_yticklabels()[i].set_fontweight("bold")
    if annotate:
        for i in range(len(fields)):
            for j in range(len(groups)):
                v = Z[i, j]
                txt = "-" if v == 0 else ("<1" if v < 0.005 else
                                          ("100" if v >= 0.995 else f"{v * 100:.0f}"))
                ax.text(j, i, txt, ha="center", va="center", fontsize=5.6,
                        color="#ffffff" if v > 0.62 else ("#9ca3af" if v == 0 else _INK))
    ax.set_xticks(np.arange(-.5, len(groups), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(fields), 1), minor=True)
    ax.grid(which="minor", color="#ffffff", lw=0.8)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.xaxis.tick_top()
    n_covered = int((Z.max(axis=1) > 0).sum())
    ax.set_title(f"Schema field coverage, % of rows: {n_covered} of {len(fields)} fields populated"
                 "\n\u2022 core field   - not disclosed", fontsize=8, loc="left", pad=6)
    cb = fig.colorbar(im, ax=ax, shrink=0.35, pad=0.02, aspect=14)
    cb.ax.tick_params(labelsize=6)
    cb.set_ticks([0, 0.5, 1]); cb.set_ticklabels(["0", "50", "100%"])
    cb.outline.set_visible(False)
    return fig


def plot_quality(df: pd.DataFrame, by: str = "publisher", ax=None):
    """Violations of the eight quality rules, stacked by publisher.

    The rules are evaluated per publisher with :func:`~gridqueue.quality.run_quality`, as
    in the article, so a rule that depends on the set of fields a publisher discloses is
    judged against that publisher only. A rule with no violation is drawn as a dot.
    """
    import numpy as np

    rows = []
    for k, sub in _groups(df, by):
        for x in run_quality(sub.reset_index(drop=True)).as_dict()["rules"]:
            rows.append({"code": x["code"], "name": x["name"], "pub": k,
                         "violations": max(int(x["violations"]), 0)})
    how = pd.DataFrame(rows)
    piv = (how.pivot_table(index=["code", "name"], columns="pub", values="violations",
                           aggfunc="sum", sort=False).fillna(0).astype(int))
    col = [k for k, _ in _groups(df, by)]
    piv = piv[[k for k in col if k in piv.columns]]
    tot = piv.sum(axis=1)
    piv = piv.loc[tot.sort_values(kind="stable").index]
    tot = tot.loc[piv.index]
    n = len(df)

    fig, ax = _figure(6.8, 3.0, ax)
    y = np.arange(len(piv))
    left = np.zeros(len(piv))
    for i, k in enumerate(piv.columns):
        v = piv[k].values.astype(float)
        if v.sum() == 0:
            continue
        ax.barh(y, v, left=left, height=0.62, color=_color(k, i), label=k, zorder=2)
        left += v
    width = max(int(tot.max()) if len(tot) else 0, 1)
    for yy, t in zip(y, tot.values):
        if t == 0:
            ax.plot([0], [yy], "o", ms=3.2, color="#444444", zorder=3, clip_on=False)
            ax.text(width * 0.015, yy, "0 violations", va="center", fontsize=6.5, color=_GREY)
        else:
            ax.text(t + width * 0.012, yy, f"{_th(t)}  ({t / max(n, 1) * 100:.3f}%)",
                    va="center", fontsize=6.5)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}  {nm}" for k, nm in piv.index], fontsize=7)
    ax.set_xlim(0, width * 1.45)
    from matplotlib.ticker import MaxNLocator
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(f"rows violating the rule (of {_th(n)} rows)", fontsize=7.5)
    ax.set_title("Quality rules: a count of disclosure defects, not software errors",
                 fontsize=8.5, loc="left")
    if len(piv.columns) > 1 and left.sum() > 0:
        ax.legend(loc="lower right", fontsize=6.5, ncol=2, frameon=False,
                  handlelength=1.1, columnspacing=1.0)
    _style(ax)
    ax.margins(y=0.06)
    return fig


def plot_column_shift(df: pd.DataFrame, ax=None):
    """Rows in which a value stands in a field it cannot belong to, by field.

    A view of :func:`~gridqueue.layout.audit_column_shift`. An empty chart (0%) is the
    expected result of a correct extraction.
    """
    a = audit_column_shift(df)
    d = a.as_dict()
    per = pd.Series(d.get("per_field", {}), dtype=float).sort_values()
    fig, ax = _figure(5.6, max(1.6, 0.9 + 0.28 * max(len(per), 1)), ax)
    title = (f"Column shift audit: {_th(d['n_shifted'])} of {_th(d['n_rows'])} rows "
             f"({d['share'] * 100:.3f}%)")
    if not len(per):
        _empty_note(ax, "no value stands in a field it cannot belong to")
        ax.set_title(title, fontsize=8.5, loc="left")
        return fig
    ax.barh(range(len(per)), per.values, color="#c77a1e", height=0.6, zorder=2)
    for i, v in enumerate(per.values):
        ax.text(v, i, f"  {_th(v)}", va="center", fontsize=6.5)
    ax.set_yticks(range(len(per)))
    ax.set_yticklabels(per.index, fontsize=7)
    ax.set_xlabel("rows with a type-inconsistent value", fontsize=7.5)
    ax.set_xlim(0, per.max() * 1.25)
    ax.set_title(title, fontsize=8.5, loc="left")
    _style(ax)
    return fig


# ---------------------------------------------------------------------------
# the state of the queue
# ---------------------------------------------------------------------------

def _status_order(values: Iterable[str]) -> list[str]:
    ordered = [s for s in STATUSES if s in set(values)]
    ordered.sort(key=lambda s: (s in TERMINAL_NEGATIVE or s == "AGREEMENT_TERMINATED",
                                STATUS_ORDER.get(s, 99), s))
    rest = sorted(set(values) - set(ordered))
    return ordered + rest


def plot_status_distribution(df: pd.DataFrame, by: str = "publisher",
                             normalize: bool = False, codes: bool = False, ax=None):
    """Applications by stage of the proceeding, one bar per publisher.

    Stages are ordered as the proceeding runs (filed, under review, conditions issued,
    agreement, connected), followed by the states that end it without a connection.
    ``normalize=True`` shows shares instead of counts, which makes publishers of very
    different size comparable.
    """
    import numpy as np

    app = _applications(df)
    if "process_status" not in app.columns or not _filled(app["process_status"]).any():
        fig, ax = _figure(5.5, 2.0, ax)
        _empty_note(ax, "the disclosure carries no process status")
        return fig
    groups = [(k, s) for k, s in _groups(app, by) if len(s)]
    st = _status_order(app["process_status"].dropna().astype(str).unique())
    M = pd.DataFrame({k: s["process_status"].astype(str).value_counts() for k, s in groups}
                     ).reindex(st).fillna(0).T
    if normalize:
        M = M.div(M.sum(axis=1).replace(0, 1), axis=0) * 100
    fig, ax = _figure(6.8, max(1.8, 1.2 + 0.36 * len(groups)), ax)
    y = np.arange(len(M))[::-1]
    left = np.zeros(len(M))
    for s in st:
        v = M[s].values.astype(float)
        ax.barh(y, v, left=left, height=0.62, zorder=2, label=s if codes else
                STATUS_LABELS.get(s, s), color=_STATUS_COLORS.get(s, "#d1d5db"))
        left += v
    for yy, t, (k, sub) in zip(y, left, groups):
        ax.text(t, yy, f"  {_th(len(sub))}" if not normalize else f"  n={_th(len(sub))}",
                va="center", fontsize=6.5)
    ax.set_yticks(y)
    ax.set_yticklabels([k for k, _ in groups], fontsize=7)
    ax.set_xlim(0, left.max() * 1.12 if left.max() else 1)
    ax.set_xlabel("share of applications, %" if normalize else "applications", fontsize=7.5)
    ax.set_title("Applications by stage of the proceeding", fontsize=8.5, loc="left")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), ncol=1 if len(st) <= 6 else 2,
              fontsize=6.2, frameon=False, handlelength=1.0, columnspacing=0.8,
              borderaxespad=0.3)
    _style(ax)
    return fig


def plot_capacity_by_class(df: pd.DataFrame, power: str = "auto",
                           by: str = "resource_class", hue: Optional[str] = "voltage_level",
                           statuses: Optional[Sequence[str]] | str = "active",
                           codes: bool = False, ax=None):
    """Requested capacity in MW by resource class, split by voltage level.

    ``power="auto"`` adds injected capacity for generating classes and consumed capacity for
    consumption, which is how the schema core treats the capacity alternative; give a field
    name to use one field only. ``statuses="active"`` keeps applications still in the
    queue (the default of ``node_loading``); ``None`` keeps all rows.
    """
    import numpy as np

    app = _applications(df).copy()
    if statuses == "active":
        statuses = ACTIVE_STATUSES
    if statuses is not None and "process_status" in app.columns:
        app = app[app["process_status"].isin(set(statuses))]
    if by not in app.columns:
        fig, ax = _figure(5.5, 2.0, ax)
        _empty_note(ax, f"the disclosure carries no field {by}")
        return fig
    if power == "auto":
        w = pd.to_numeric(app.get("capacity_injected"), errors="coerce") \
            if "capacity_injected" in app else pd.Series(np.nan, index=app.index)
        p = pd.to_numeric(app.get("capacity_withdrawn"), errors="coerce") \
            if "capacity_withdrawn" in app else pd.Series(np.nan, index=app.index)
        app["_mw"] = w.where(w.notna() & (w > 0), p) / 1000.0
        description = "requested capacity (injected, or consumed where no injection is declared)"
    else:
        app["_mw"] = pd.to_numeric(app.get(power), errors="coerce") / 1000.0
        description = power
    app = app[app["_mw"].notna() & (app["_mw"] > 0)]
    fig, ax = _figure(6.6, 3.0, ax)
    if not len(app):
        _empty_note(ax, "no row with a disclosed capacity in the selected statuses")
        return fig
    h = hue if hue and hue in app.columns else None
    app["_k"] = app[by].astype(object).where(app[by].notna(), "(empty)").astype(str)
    app["_h"] = app[h].astype(object).where(app[h].notna(), "(not disclosed)").astype(str) \
        if h else "all"
    if h:
        # At most five levels by capacity, the rest pooled: a multi-voltage publisher writes
        # combinations such as "110; 220 kV", and a legend of ten shades is not readable.
        top_h = app.groupby("_h")["_mw"].sum().sort_values(ascending=False).index[:5]
        app.loc[~app["_h"].isin(top_h), "_h"] = "other levels"
    P = app.pivot_table(index="_k", columns="_h", values="_mw", aggfunc="sum").fillna(0)
    P = P.loc[P.sum(axis=1).sort_values().index]
    N = app.groupby("_k").size().reindex(P.index)
    y = np.arange(len(P))
    left = np.zeros(len(P))
    pal = ["#1b5e8c", "#8fb4cc", "#2e8b78", "#c77a1e", "#7a4b9c", "#9ca3af"]
    for i, c in enumerate(P.columns):
        ax.barh(y, P[c].values, left=left, height=0.62, color=pal[i % len(pal)],
                label=c, zorder=2)
        left += P[c].values
    for yy, t, n in zip(y, left, N.values):
        ax.text(t, yy, f"  {t:,.0f} MW, {_th(n)} appl.", va="center", fontsize=6.3)
    lab = (lambda k: k) if codes or by != "resource_class" else \
        (lambda k: CLASS_LABELS.get(k, k))
    ax.set_yticks(y)
    ax.set_yticklabels([lab(k) for k in P.index], fontsize=7)
    ax.set_xlim(0, left.max() * 1.42)
    ax.set_xlabel(f"MW, {description}", fontsize=7)
    which = "applications in the queue" if statuses is not None else "all applications"
    ax.set_title(f"Requested capacity by {'resource class' if by == 'resource_class' else by}, "
                 f"{which}", fontsize=8.5, loc="left")
    if h:
        ax.legend(title=h, title_fontsize=6.5, fontsize=6.3, frameon=False,
                  loc="center left", bbox_to_anchor=(1.0, 0.5), borderaxespad=0.3)
    _style(ax)
    return fig


def plot_processing_time(df: pd.DataFrame, by: Optional[str] = "resource_class",
                         start: str = "date_application", end: str = "date_conditions",
                         min_n: int = 30, max_groups: int = 6, ci: bool = True,
                         codes: bool = False, ax=None):
    """Kaplan-Meier curves of the time from application to the event ``end``.

    Applications without the closing date are **censored** at the as-at date of the
    edition, not dropped, exactly as :func:`~gridqueue.analysis.processing_time` and
    :func:`~gridqueue.analysis.kaplan_meier` compute them. Only groups with at least
    ``min_n`` measurable applications are drawn (the inclusion criterion of the article);
    the legend gives the group size, the share censored and the median with its interval.
    """
    tab = kaplan_meier_by_group(_applications(df), by=by, start=start, end=end, min_n=min_n)
    fig, ax = _figure(6.4, 3.6, ax)
    if not len(tab):
        _empty_note(ax, f"no group with at least {min_n} applications carrying {start}")
        ax.set_title("Time to " + EVENT_LABELS.get(end, end), fontsize=8.5, loc="left")
        return fig
    tab = tab.head(max_groups)
    app = _applications(df)
    cov = min(float(_filled(app[c]).mean()) for c in (start, end))
    pt = processing_time(app, start=start, end=end)
    pal = ["#1b5e8c", "#c77a1e", "#2e8b78", "#a33b4e", "#7a4b9c", "#6b7280", "#e9b44c"]
    xmax = 0.0
    for i, r in enumerate(tab.itertuples(index=False)):
        sub = pt if by is None else pt[_group_key(pt, by) == r.group]
        km = kaplan_meier(sub["time_days"].astype("float64"), sub["event"].astype("float64"))
        t = [0.0] + km.table["t"].tolist()
        S = [1.0] + km.table["S"].tolist()
        tmax = float(pd.to_numeric(sub["time_days"], errors="coerce").max())
        t.append(tmax); S.append(S[-1])
        below = [tt for tt, ss in zip(t, S) if ss <= 0.01]
        xmax = max(xmax, below[0] if below else tmax)
        c = pal[i % len(pal)]
        name = r.group if (codes or by != "resource_class") else \
            f"{CLASS_LABELS.get(r.group, r.group)} ({r.group})"
        med = "not reached" if pd.isna(r.median) else f"{r.median:.0f} d"
        ax.step(t, [s * 100 for s in S], where="post", color=c, lw=1.4, zorder=3,
                label=f"{name}: n={_th(r.n)}, censored {r.censored_share * 100:.1f}%, "
                      f"median {med}")
        if ci and len(km.table):
            lo = [100.0] + (km.table["S_lower"] * 100).tolist() + [km.table["S_lower"].iloc[-1] * 100]
            hi = [100.0] + (km.table["S_upper"] * 100).tolist() + [km.table["S_upper"].iloc[-1] * 100]
            ax.fill_between(t, lo, hi, step="post", color=c, alpha=0.13, lw=0, zorder=2)
        if not pd.isna(r.median):
            ax.plot([r.median], [50], "o", ms=3.5, color=c, zorder=4)
    ax.axhline(50, color="#9ca3af", lw=0.8, ls="--", zorder=1)
    ax.set_ylim(0, 102)
    ax.set_xlim(0, xmax * 1.05 if xmax else 1)
    ax.set_ylabel("% still waiting", fontsize=7.5)
    ax.set_xlabel(f"days from {start} to {end} (axis ends where the curves fall below 1% or end)",
                  fontsize=7.5)
    ax.set_title(f"Time from {EVENT_LABELS.get(start, start)} to {EVENT_LABELS.get(end, end)}: "
                 "Kaplan-Meier, censored at the as-at date, 95% band"
                 f"\nboth dates populated in {cov * 100:.1f}% of applications"
                 + ("" if cov >= 0.8 else ", below the 80% inclusion criterion of the article"),
                 fontsize=8.5, loc="left")
    ax.legend(fontsize=6.3, frameon=False, loc="upper right")
    _style(ax, "both")
    return fig


def plot_node_loading(loading: pd.DataFrame, ax=None, label: str = "node_name",
                      top: int = 12, title: Optional[str] = None):
    """Node loading: requested capacity of the active queue over declared free capacity.

    Takes the frame returned by :func:`~gridqueue.analysis.node_loading`. Bars are on a
    logarithmic axis with the line at 1 (queue equal to the declared capacity). Nodes with
    zero declared free capacity have an undefined ratio; they are counted in the title and
    not drawn, rather than drawn as infinite.
    """
    import numpy as np

    d = loading.copy()
    zero = int(d.get("available_capacity_zero", pd.Series(dtype=bool)).fillna(False).sum())
    d = d[pd.to_numeric(d["loading"], errors="coerce").notna()].copy()
    d["loading"] = pd.to_numeric(d["loading"], errors="coerce").astype(float)
    fig, ax = _figure(6.4, 3.4, ax)
    if not len(d):
        _empty_note(ax, "no node with a defined loading")
        return fig
    d = d.sort_values("loading", ascending=False).reset_index(drop=True)
    nonzero = d["loading"] > 0
    n_zero_queue = int((~nonzero).sum())
    floor = float(d.loc[nonzero, "loading"].min()) * 0.4 if nonzero.any() else 0.1
    pos = d["loading"].where(nonzero, np.nan)
    cols = np.where(d["loading"] > 1, "#a33b4e", "#2e8b78")
    ax.bar(np.arange(len(d))[nonzero.values], pos[nonzero].values, color=cols[nonzero.values],
           width=0.8, zorder=2)
    if n_zero_queue:
        # loading exactly 0 (free capacity declared, no active application assigned) cannot be
        # drawn on a log axis; it is marked at the floor instead of being given a fake height
        ax.plot(np.arange(len(d))[~nonzero.values], [floor * 1.15] * n_zero_queue, marker="v",
                ls="none", ms=4, color=_GREY, zorder=3,
                label=f"\u03bb = 0: no active application assigned ({n_zero_queue})")
    ax.set_yscale("log")
    ax.axhline(1, color=_INK, lw=0.9, ls="--", zorder=3,
               label="\u03bb = 1: queue equal to the declared free capacity")
    ax.legend(loc="upper right", fontsize=6.5, frameon=False)
    if label in d.columns and top:
        for i in range(min(top, len(d))):
            if not nonzero.iloc[i]:
                continue
            ax.text(i, pos.iloc[i] * 1.12, str(d.loc[i, label])[:14], rotation=90,
                    ha="center", va="bottom", fontsize=5.4, color="#374151")
    ax.set_xticks([])
    ax.set_xlim(-0.8, len(d) - 0.2)
    ax.set_ylim(min(floor, 0.5), max(float(np.nanmax(pos.values)) if nonzero.any() else 1.0, 2.0) * 8)
    ax.set_xlabel(f"node-directions, sorted ({_th(len(d))} with declared free capacity)",
                  fontsize=7.5)
    ax.set_ylabel("loading \u03bb(n), log scale", fontsize=7.5)
    over = int((d["loading"] > 1).sum())
    direction_label = d["direction"].dropna().iloc[0] if "direction" in d and d["direction"].notna().any() else None
    ax.set_title(title or (
        f"Node loading{f', {_DIRECTION.get(direction_label, direction_label)}' if direction_label else ''}: median {d['loading'].median():.3f}, "
        f"{over} of {len(d)} above 1; {zero} {'node' if zero == 1 else 'nodes'} with zero free capacity not drawn"),
        fontsize=8.5, loc="left")
    _style(ax, "y")
    return fig


# ---------------------------------------------------------------------------
# two editions
# ---------------------------------------------------------------------------

def plot_edition_flows(delta, ax=None):
    """Flows between two editions: shared, absent from the later one, new in it.

    The two hatched segments are the warning signs of a non-monotone register: rows that
    disappear while still active, and rows that appear already closed.
    """
    d = delta.as_dict()
    fig, ax = _figure(6.4, 2.4, ax)
    ea, eb = d["edition_a"], d["edition_b"]
    shared, gone, new = d["shared"], d["gone"], d["new"]
    gone_act, new_closed = d["gone_active"], d["new_closed"]
    rejected_a = d["rejected_as_ambiguous_a"]
    rejected_b = d["rejected_as_ambiguous_b"]
    y = [1, 0]
    ax.barh(1, shared, color="#1b5e8c", height=0.55, zorder=2, label="shared (linked)")
    ax.barh(1, gone - gone_act, left=shared, color="#c9dcea", height=0.55, zorder=2,
            label="absent from the later edition")
    ax.barh(1, gone_act, left=shared + gone - gone_act, color="#c9dcea", hatch="////",
            edgecolor="#a33b4e", lw=0, height=0.55, zorder=2,
            label="absent while still active")
    ax.barh(1, rejected_a, left=shared + gone, color="#e5e7eb", height=0.55, zorder=2,
            label="key collision, not linked")
    ax.barh(0, shared, color="#1b5e8c", height=0.55, zorder=2)
    ax.barh(0, new - new_closed, left=shared, color="#e9c46a", height=0.55, zorder=2,
            label="new in the later edition")
    ax.barh(0, new_closed, left=shared + new - new_closed, color="#e9c46a", hatch="////",
            edgecolor="#a33b4e", lw=0, height=0.55, zorder=2, label="new, already closed")
    ax.barh(0, rejected_b, left=shared + new, color="#e5e7eb", height=0.55, zorder=2)
    for yy, tot, n in ((1, shared + gone + rejected_a, d["rows_a"]),
                       (0, shared + new + rejected_b, d["rows_b"])):
        ax.text(tot, yy, f"  {_th(n)} rows", va="center", fontsize=6.8)
    ax.text(shared / 2, 0.5, f"{_th(shared)} linked", ha="center", va="center",
            fontsize=6.8, color="#1b5e8c")
    ax.set_yticks(y)
    ax.set_yticklabels([str(ea), str(eb)], fontsize=7.5)
    ax.set_xlim(0, max(d["rows_a"], d["rows_b"]) * 1.18)
    ax.set_xlabel("rows", fontsize=7.5)
    mono = "monotone" if d["monotone_snapshot"] else "NOT a monotone snapshot"
    ax.set_title(f"Flows between editions: {_th(new)} new, {_th(gone)} absent; register is {mono}",
                 fontsize=8.5, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, fontsize=6.2,
              frameon=False, handlelength=1.2)
    _style(ax)
    return fig


def plot_transitions(delta, ax=None, codes: bool = False):
    """Status transition matrix among linked rows.

    Off-diagonal cells are coloured by direction: forward in the order of the proceeding
    (or to a terminal negative state) in green, backward in red. A high forward share is the
    independent test of the linkage described in the article.
    """
    import numpy as np
    from matplotlib.colors import LinearSegmentedColormap

    tr = delta.transitions
    fig, ax = _figure(5.0, 4.4, ax)
    if tr is None or not len(tr):
        _empty_note(ax, "no linked rows")
        return fig
    st = _status_order(set(tr.index) | set(tr.columns))
    M = tr.reindex(index=st, columns=st).fillna(0).astype(int)
    off = M.values.copy()
    np.fill_diagonal(off, 0)
    vmax = max(int(off.max()), 1)
    cmap = LinearSegmentedColormap.from_list("t", ["#ffffff", "#c9dcea", "#1b5e8c"])
    ax.imshow(np.where(off > 0, off, 0), cmap=cmap, vmin=0, vmax=vmax, aspect="equal")
    for i, a in enumerate(st):
        for j, b in enumerate(st):
            n = int(M.iloc[i, j])
            if not n:
                continue
            if i == j:
                ax.text(j, i, _th(n), ha="center", va="center", fontsize=6, color=_GREY)
                continue
            fwd = (a in STATUS_ORDER and b in STATUS_ORDER and STATUS_ORDER[b] > STATUS_ORDER[a]) \
                or (a in STATUS_ORDER and b in TERMINAL_NEGATIVE)
            back = a in STATUS_ORDER and b in STATUS_ORDER and STATUS_ORDER[b] < STATUS_ORDER[a]
            col = "#14532d" if fwd else ("#a33b4e" if back else _INK)
            ax.text(j, i, _th(n), ha="center", va="center", fontsize=7, fontweight="bold",
                    color="#ffffff" if n > vmax * 0.6 and not back else col)
            if back:
                ax.add_patch(__import__("matplotlib").patches.Rectangle(
                    (j - .5, i - .5), 1, 1, fill=False, ec="#a33b4e", lw=1.2))
    lab = (lambda s: s) if codes else (lambda s: STATUS_LABELS.get(s, s))
    ax.set_xticks(range(len(st)))
    ax.set_xticklabels([lab(s) for s in st], rotation=40, ha="right", fontsize=6.5)
    ax.set_yticks(range(len(st)))
    ax.set_yticklabels([lab(s) for s in st], fontsize=6.5)
    ax.set_xlabel(f"status in {delta.edition_b}", fontsize=7.5)
    ax.set_ylabel(f"status in {delta.edition_a}", fontsize=7.5)
    ax.tick_params(length=0)
    sh = delta.forward_share
    ax.set_title("Status transitions among linked rows"
                 + (f": {sh * 100:.2f}% forward" if sh is not None else ""),
                 fontsize=8.5, loc="left")
    for s in ax.spines.values():
        s.set_color("#e5e7eb")
    return fig


def plot_linkage_audit(audit, recall=None, ax=None):
    """Confirmed, uncertain and false pairs on the fields excluded from the key.

    With a :class:`~gridqueue.longitudinal.LinkageRecall` the pairs the key missed are
    added as a fourth segment, so precision and sensitivity are read from one bar.
    """
    a = audit.as_dict()
    fig, ax = _figure(6.4, 1.7, ax)
    parts = [("confirmed", a["confirmed"], "#2e8b78"),
             ("uncertain", a["uncertain"], "#e9c46a"),
             ("false", a["false_matches"], "#a33b4e")]
    if recall is not None:
        parts.append(("missed by the key, recovered", recall.as_dict()["recovered"], "#9ca3af"))
    left = 0
    for name, v, c in parts:
        ax.barh(0, v, left=left, color=c, height=0.5, label=f"{name} ({_th(v)})", zorder=2)
        left += v
    ax.set_yticks([])
    ax.set_xlim(0, max(left, 1) * 1.02)
    ax.set_xlabel("linked pairs", fontsize=7.5)
    ttl = (f"Linkage precision {a['precision_lower'] * 100:.2f} to "
           f"{a['precision_upper'] * 100:.2f}% over {_th(a['pairs'])} pairs")
    if recall is not None and recall.as_dict()["key_sensitivity"] == recall.as_dict()["key_sensitivity"]:
        ttl += f"; key sensitivity {recall.as_dict()['key_sensitivity']:.4f}"
    ax.set_title(ttl, fontsize=8.5, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.55), ncol=4, fontsize=6.3,
              frameon=False, handlelength=1.1)
    _style(ax)
    return fig


def plot_edition_comparison(delta, audit=None, recall=None):
    """Flows, transition matrix and linkage audit of two editions in one figure."""
    Figure = _mpl()
    fig = Figure(figsize=(10.5, 5.2), dpi=110, layout="constrained")
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1.0], height_ratios=[1.2, 0.8])
    plot_edition_flows(delta, ax=fig.add_subplot(gs[0, 0]))
    if audit is not None:
        plot_linkage_audit(audit, recall, ax=fig.add_subplot(gs[1, 0]))
    plot_transitions(delta, ax=fig.add_subplot(gs[:, 1]))
    return fig


# ---------------------------------------------------------------------------
# locations
# ---------------------------------------------------------------------------

_GEO_CATEGORY = {
    "source coordinates": "#14532d", "placed by the gazetteer": "#2e8b78",
    "locality centroid only": "#7fb7be", "name resolved, no geometry": "#b9d7c9",
    "station code with no dictionary": "#1b5e8c", "no locality declared": "#8fb4cc",
    "empty description": "#cfd8dd", "locality outside the gazetteer": "#c77a1e",
    "several candidates": "#7a4b9c", "no candidate in the gazetteer": "#c9a0dc",
    "not resolved, other reason": "#aaaaaa",
    "resolver not run": "#e5e7eb",
}
_WITH_POINT = ("source coordinates", "placed by the gazetteer", "locality centroid only")
_CONFIDENCE = {"EXACT": "exact", "UNIQUE_TOKEN": "unique member", "INTERSECTION": "intersection",
            "REVERSED": "reversed order", "TOKEN_SUBSET": "subset of members"}


def _geo_category(coords, confidence, reason, accuracy=None) -> str:
    p = "" if confidence is None or (isinstance(confidence, float) and confidence != confidence) \
        else str(confidence)
    if _filled(pd.Series([coords])).iloc[0]:
        if not p or p == "SOURCE":
            return "source coordinates"
        if p == "NONE" or str(accuracy) == "LOCALITY_CENTROID":
            return "locality centroid only"
        return "placed by the gazetteer"
    s = "" if reason is None or (isinstance(reason, float) and reason != reason) else str(reason)
    if not s and not p:
        return "resolver not run"
    if "without_geometry" in s or (p and p != "NONE"):
        return "name resolved, no geometry"
    if "station_code" in s:
        return "station code with no dictionary"
    if "no_locality_declared" in s:
        return "no locality declared"
    if "empty_description" in s:
        return "empty description"
    if "not_in_gazetteer" in s:
        return "locality outside the gazetteer"
    if "multiple_candidates" in s or "ambiguous" in s:
        return "several candidates"
    if "no_candidates" in s or "no_distinguishing_tokens" in s or "verbal_description" in s:
        return "no candidate in the gazetteer"
    return "not resolved, other reason"


def plot_location_resolution(df: pd.DataFrame, by: str = "publisher"):
    """Where a coordinate comes from, and where it does not, by publisher.

    Left: share of rows with source coordinates, coordinates placed by the gazetteer, and
    each stated reason for absence. Right: confidence levels of the gazetteer placements.
    Reads the resolver diagnostics ``_geo_confidence`` and ``_geo_reason`` when present.
    """
    import numpy as np

    Figure = _mpl()
    d = df.copy()
    coords = d["coordinates"] if "coordinates" in d else pd.Series(None, index=d.index)
    conf = d["_geo_confidence"] if "_geo_confidence" in d else pd.Series(None, index=d.index)
    reason_ = d["_geo_reason"] if "_geo_reason" in d else pd.Series(None, index=d.index)
    acc_level = d["_geo_accuracy"] if "_geo_accuracy" in d else pd.Series(None, index=d.index)
    d["_category"] = [_geo_category(w, p, r, k) for w, p, r, k in zip(coords, conf, reason_, acc_level)]
    groups = _groups(d, by)
    category = [k for k in _GEO_CATEGORY if (d["_category"] == k).any()]
    CT = pd.DataFrame({k: s["_category"].value_counts() for k, s in groups}).reindex(category).fillna(0).T
    placed = d.loc[d["_category"].isin(["placed by the gazetteer", "name resolved, no geometry"]),
                   "_geo_confidence"] if "_geo_confidence" in d else pd.Series(dtype=object)
    two = len(placed) > 0
    fig = Figure(figsize=(7.2 if two else 5.4, max(2.3, 1.4 + 0.3 * len(groups))), dpi=110,
                 layout="constrained")
    gs = fig.add_gridspec(1, 2 if two else 1, width_ratios=[1.6, 1.0] if two else [1])
    ax = fig.add_subplot(gs[0])
    y = np.arange(len(CT))[::-1]
    frac = CT.div(CT.sum(axis=1).replace(0, 1), axis=0) * 100
    left = np.zeros(len(CT))
    for k in CT.columns:
        ax.barh(y, frac[k].values, left=left, height=0.62, color=_GEO_CATEGORY[k], label=k, zorder=2)
        left += frac[k].values
    for yy, k in zip(y, CT.index):
        have = int(CT.loc[k, [c for c in CT.columns if c in _WITH_POINT]].sum())
        ax.text(101.5, yy, f"{_th(have)} / {_th(CT.loc[k].sum())}", va="center", fontsize=6.3)
    ax.set_yticks(y)
    ax.set_yticklabels(CT.index, fontsize=7)
    ax.set_xlim(0, 120)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("share of the publisher's rows, %", fontsize=7.5)
    n_have = int((d["_category"].isin(_WITH_POINT)).sum())
    ax.set_title(f"Coordinates in {_th(n_have)} of {_th(len(d))} rows;\n"
                 "absence is returned with a reason, not guessed", fontsize=8.5, loc="left")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=2, fontsize=6,
              frameon=False, handlelength=1.0, columnspacing=0.9)
    _style(ax)
    if two:
        ax2 = fig.add_subplot(gs[1])
        pw = placed.astype(str).value_counts()
        keys = [k for k in _CONFIDENCE if k in pw.index] + [k for k in pw.index if k not in _CONFIDENCE]
        vv = [int(pw[k]) for k in keys]
        yb = np.arange(len(keys))[::-1]
        ax2.barh(yb, vv, height=0.6, color="#2e8b78", zorder=2)
        for yy, v in zip(yb, vv):
            ax2.text(v + max(vv) * 0.02, yy, f"{v}  ({v / sum(vv) * 100:.1f}%)",
                     va="center", fontsize=6.3)
        ax2.set_yticks(yb)
        ax2.set_yticklabels([_CONFIDENCE.get(k, k) for k in keys], fontsize=6.5)
        ax2.set_xlim(0, max(vv) * 1.45)
        ax2.set_xlabel("rows", fontsize=7.5)
        ax2.set_title(f"Certainty of {_th(sum(vv))} identified place names", fontsize=8.5,
                      loc="left")
        _style(ax2)
    return fig


# ---------------------------------------------------------------------------
# one-call views
# ---------------------------------------------------------------------------

def plot_overview(df: pd.DataFrame, by: str = "publisher"):
    """Four panels for a first look: coverage, quality, status and capacity."""
    Figure = _mpl()
    n_pub = len(_groups(df, by))
    fig = Figure(figsize=(13, 9.6), dpi=100, layout="constrained")
    gs = fig.add_gridspec(3, 2, width_ratios=[0.22 + 0.06 * min(n_pub, 9), 1.0],
                          height_ratios=[1.0, 0.75, 1.15])
    plot_field_coverage(df, by=by, ax=fig.add_subplot(gs[:, 0]))
    plot_quality(df, by=by, ax=fig.add_subplot(gs[0, 1]))
    plot_status_distribution(df, by=by, normalize=True, ax=fig.add_subplot(gs[1, 1]))
    plot_capacity_by_class(df, ax=fig.add_subplot(gs[2, 1]))
    return fig


def save_figure(fig, path, dpi: int = 300) -> Path:
    """Save a figure (format from the suffix: .png, .svg, .pdf) and return the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, dpi=dpi, bbox_inches="tight", facecolor="white")
    return p


def save_all(df: pd.DataFrame, out_dir, *, edition_b: Optional[pd.DataFrame] = None,
             labels: tuple[str, str] = ("A", "B"), formats: Sequence[str] = ("png",),
             dpi: int = 200, min_n: int = 30,
             min_coverage: float = 0.8) -> dict[str, list[Path]]:
    """Draw every chart the data supports and save it to ``out_dir``.

    Charts that need data the disclosure does not carry are skipped and listed under the
    key ``"_skipped"`` with the reason, rather than drawn empty. With ``edition_b`` the
    edition-comparison charts are added, ``df`` being the earlier edition.

    The processing-time curves follow the inclusion criterion of the article, fixed before
    the result is computed: both dates populated in at least ``min_coverage`` of the
    applications and at least ``min_n`` applications in a group.
    """
    from .analysis import assign_to_nodes, node_loading, station_node_map
    from .longitudinal import compare_editions, linkage_audit, linkage_recall

    out = Path(out_dir)
    saved: dict[str, list[Path]] = {}
    skipped: list[str] = []

    def put(name, fig):
        saved[name] = [save_figure(fig, out / f"{name}.{fmt}", dpi=dpi) for fmt in formats]

    put("field_coverage", plot_field_coverage(df))
    put("quality_rules", plot_quality(df))
    put("column_shift", plot_column_shift(df))
    if "process_status" in df and _filled(_applications(df)["process_status"]).any():
        put("status_distribution", plot_status_distribution(df))
    else:
        skipped.append("status_distribution: no process status disclosed")
    if "resource_class" in df and _filled(_applications(df)["resource_class"]).any():
        put("capacity_by_class", plot_capacity_by_class(df))
    else:
        skipped.append("capacity_by_class: no resource class disclosed")
    app = _applications(df)
    cov = min((float(_filled(app[c]).mean()) if c in app and len(app) else 0.0)
              for c in ("date_application", "date_conditions"))
    km = kaplan_meier_by_group(app, min_n=min_n) if cov >= min_coverage else []
    if cov < min_coverage:
        skipped.append(f"processing_time: date coverage {cov * 100:.1f}% is below the "
                       f"{min_coverage * 100:.0f}% inclusion criterion")
    elif len(km):
        put("processing_time", plot_processing_time(df, min_n=min_n))
    else:
        skipped.append(f"processing_time: no group of {min_n} applications with date_application")
    if "coordinates" in df:
        put("location_resolution", plot_location_resolution(df))
    if "capacity_available" in df and "_entity" in df and (df["_entity"] == "NODE").any() \
            and (df["_entity"] != "NODE").any():
        mapping = station_node_map(df)
        if len(mapping):
            assigned = assign_to_nodes(df, mapping)
            for field, name in (("capacity_injected", "generation"), ("capacity_withdrawn", "demand")):
                L = node_loading(assigned, capacity_field=field)
                if pd.to_numeric(L["loading"], errors="coerce").notna().any():
                    put(f"node_loading_{name}", plot_node_loading(L))
        else:
            skipped.append("node_loading: node rows carry no station list")
    else:
        skipped.append("node_loading: needs both node rows and application rows")
    if edition_b is not None:
        delta = compare_editions(df, edition_b, labels[0], labels[1])
        aud = linkage_audit(df, edition_b)
        rec = linkage_recall(df, edition_b)
        put("edition_comparison", plot_edition_comparison(delta, aud, rec))
    saved["_skipped"] = skipped  # type: ignore[assignment]
    return saved
