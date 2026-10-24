"""Synthetic data in the schema, for trying the package without a real disclosure.

Nothing here comes from a publisher. The frames are generated from a seed, they carry the
publisher names ``"Synthetic operator A"`` and ``"Synthetic operator B"`` so that they
cannot be mistaken for a register, and they are built to exercise every function of the
package: application and node rows (for node loading), process dates with censoring (for
the processing-time curves), two editions with linked, new, absent and status-changed rows
(for the longitudinal module), and a small gazetteer with coordinates (for the resolver).

The browser page and the Colab notebook use these frames for their demonstration mode.
The figures they produce describe the generator, not any grid.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

import pandas as pd

from .schema import empty_frame

__all__ = ["SYNTHETIC_PUBLISHERS", "synthetic_panel", "synthetic_editions",
           "synthetic_gazetteer"]

SYNTHETIC_PUBLISHERS = ("Synthetic operator A", "Synthetic operator B")

_STATIONS = {
    1: ("Alder", "Birch"), 2: ("Cedar",), 3: ("Elm", "Fir"), 4: ("Hazel",),
    5: ("Larch", "Maple"), 6: ("Oak",), 7: ("Pine", "Rowan"), 8: ("Spruce",),
}
_CLASSES = (("PV", 0.42), ("LOAD", 0.28), ("BESS", 0.12), ("WIND", 0.08), ("MIX", 0.06),
            ("BIOGAS", 0.04))
_MEDIAN_DAYS = {"PV": 130, "LOAD": 60, "BESS": 200, "WIND": 210, "MIX": 125, "BIOGAS": 150}
_TOWNS = {"RIVERTON": (53.43, 14.55), "HILLSIDE": (53.56, 14.20), "LAKEVIEW": (53.30, 14.90)}
_STREETS = ("Station Road", "Mill Lane", "Harbour Street", "Orchard Way", "Quarry Road")


def _iso(d: date) -> str:
    return d.isoformat()


def _pick(rng: random.Random, weighted):
    x, acc = rng.random(), 0.0
    for v, w in weighted:
        acc += w
        if x <= acc:
            return v
    return weighted[-1][0]


def synthetic_panel(n: int = 600, *, seed: int = 7, as_at: str = "2026-06-30",
                    with_nodes: bool = True) -> pd.DataFrame:
    """A synthetic panel of ``n`` applications (plus node rows) in the 21-field schema."""
    rng = random.Random(seed)
    asat = date.fromisoformat(as_at)
    rows = []
    for i in range(n):
        pub = SYNTHETIC_PUBLISHERS[0] if rng.random() < 0.6 else SYNTHETIC_PUBLISHERS[1]
        resource_class = _pick(rng, _CLASSES)
        filed = asat - timedelta(days=rng.randint(20, 900))
        wait = int(rng.expovariate(1 / _MEDIAN_DAYS[resource_class]) * 1.1) + 14
        cond = filed + timedelta(days=wait)
        r = {"application_id": f"SYN-{i:05d}", "publisher": pub, "resource_class": resource_class,
             "date_application": _iso(filed), "date_published": as_at, "_entity": "APPLICATION"}
        grp = rng.randint(1, len(_STATIONS))
        stn = rng.choice(_STATIONS[grp])
        town = rng.choice(list(_TOWNS))
        if rng.random() < 0.55:
            r["location_text"] = stn
        else:
            r["location_text"] = f"{town.title()}, {rng.choice(_STREETS)}"
        r["voltage_level"] = "SN" if rng.random() < 0.7 else "110 kV"
        mw = round(rng.lognormvariate(0.4 if resource_class != "LOAD" else -0.3, 1.0), 3)
        r["capacity_withdrawn" if resource_class == "LOAD" else "capacity_injected"] = round(mw * 1000, 1)
        if cond <= asat:
            r["date_conditions"] = _iso(cond)
            u = rng.random()
            if u < 0.35:
                r["date_agreement"] = _iso(min(asat, cond + timedelta(days=rng.randint(20, 200))))
                r["process_status"] = "AGREEMENT_IN_FORCE"
            elif u < 0.42:
                r["process_status"] = "CONDITIONS_EXPIRED"
            else:
                r["process_status"] = "CONDITIONS_ISSUED"
        else:
            u = rng.random()
            if u < 0.08:
                r["process_status"] = "REFUSED"
                r["date_refusal"] = _iso(filed + timedelta(days=rng.randint(20, 120)))
                r["refusal_reason"] = "no technical conditions for connection"
            elif u < 0.14:
                r["process_status"] = "APPLICATION_INCOMPLETE"
            else:
                r["process_status"] = "UNDER_REVIEW"
        rows.append(r)
    if with_nodes:
        for grp, stations in _STATIONS.items():
            for direction_label in ("generation", "demand"):
                free = 0.0 if grp == 8 else round(rng.uniform(2, 60) * 1000, 1)
                rows.append({"_entity": "NODE", "node_id": f"N{grp}-{direction_label[0].upper()}",
                             "node_name": stations[0], "_group_no": grp, "_direction": direction_label,
                             "location_text": ", ".join(stations), "capacity_available": free,
                             "publisher": SYNTHETIC_PUBLISHERS[0],
                             "date_published": as_at})
    df = pd.DataFrame(rows)
    cols = list(empty_frame().columns) + [c for c in df.columns
                                          if c not in empty_frame().columns]
    return df.reindex(columns=cols)


_FORWARD = {"UNDER_REVIEW": "CONDITIONS_ISSUED", "APPLICATION_INCOMPLETE": "UNDER_REVIEW",
            "CONDITIONS_ISSUED": "AGREEMENT_IN_FORCE", "AGREEMENT_IN_FORCE": "CONNECTED"}


def synthetic_editions(n: int = 400, *, seed: int = 11) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two consecutive synthetic editions of one register (applications only).

    Between them about 6% of rows disappear, 5% are added, 8% advance one stage, and a
    handful move backwards, so the flows, the transition matrix and the linkage audit all
    have something to show.
    """
    rng = random.Random(seed)
    a = synthetic_panel(n, seed=seed, as_at="2026-05-31", with_nodes=False)
    a["publisher"] = SYNTHETIC_PUBLISHERS[0]
    b = a.copy()
    b["date_published"] = "2026-06-30"
    keep = [rng.random() > 0.06 for _ in range(len(b))]
    b = b[keep].copy()
    back = 0
    for idx in b.index:
        s = b.at[idx, "process_status"]
        u = rng.random()
        if u < 0.08 and s in _FORWARD:
            b.at[idx, "process_status"] = _FORWARD[s]
            if s == "UNDER_REVIEW":
                b.at[idx, "date_conditions"] = "2026-06-15"
        elif back < 2 and u > 0.97 and s == "CONDITIONS_ISSUED":
            # two deliberate backward moves: the transition matrix should show what a
            # register that rewrites its own history looks like
            b.at[idx, "process_status"] = "UNDER_REVIEW"
            back += 1
    new = synthetic_panel(int(n * 0.05) + 1, seed=seed + 1, as_at="2026-06-30",
                          with_nodes=False)
    new["publisher"] = SYNTHETIC_PUBLISHERS[0]
    new["application_id"] = [f"SYN-NEW-{i:04d}" for i in range(len(new))]
    new["date_application"] = "2026-06-10"
    new["date_conditions"] = None
    new["date_agreement"] = None
    new["process_status"] = "APPLICATION_FILED"
    b = pd.concat([b, new], ignore_index=True)
    return a.reset_index(drop=True), b


def synthetic_gazetteer() -> dict:
    """A small gazetteer in the layout read by :func:`~gridqueue.geoloc.resolver_from_gazeter_json`."""
    out = {}
    for k, (lat, lon) in _TOWNS.items():
        streets = {}
        for j, st in enumerate(_STREETS):
            if k == "LAKEVIEW" and j > 2:
                continue  # streets missing from the gazetteer, to show an honest "no candidate"
            streets[st] = {"lat": round(lat + 0.004 * (j - 2), 6),
                         "lon": round(lon + 0.006 * (j - 2), 6), "length_m": 400 + 150 * j}
        out[k] = {"name": k.title(), "lat": lat, "lon": lon, "streets": streets}
    return {"localities": out}
