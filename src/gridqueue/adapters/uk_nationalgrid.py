"""Adapter: National Grid Electricity Distribution (UK), the "Connection Queue" dataset.

This adapter exists to prove the portability of the schema, not to
parse another PDF.  The British publisher issues the same information as
45 separate CSV files in the CKAN catalog; the data is already tabular, so the ENTIRE
extraction layer after the page layout is unnecessary here.  This is exactly the
asymmetry that the tool is meant to show: in a jurisdiction with good data the parser
is unnecessary, in Poland it is a precondition for access to the content of the duty.

Access: public ``package_search`` CKAN endpoint, no key required.  The client
identifies itself honestly in the User-Agent header; we do not impersonate a browser.
"""

from __future__ import annotations

import io
import re
from typing import Any, Optional

from ..schema import canonical_date, canonical_power_kw
from .base import Adapter, ParseResult, harmonize_klasa, harmonize_status

CKAN_BASE = "https://connecteddata.nationalgrid.co.uk/api/3/action"
USER_AGENT = (
    "gridqueue/0.1 (research prototype; harmonisation of statutory "
    "grid-connection disclosures; contact via repository)"
)


class NationalGridAdapter(Adapter):
    publisher = "National Grid Electricity Distribution"
    jurisdiction = "UK"
    declared_fields = (
        "id_wniosku", "id_wezla", "nazwa_wezla", "lokalizacja_tekst", "klasa_zasobu",
        "moc_wprowadzana", "moc_pobierana", "ograniczenie_flaga", "pozycja_w_kolejce",
        "status_procesu",
    )
    declared_extensions = {
        "_licence_area": "operator's licence area",
        "_gsp": "Grid Supply Point",
        "_machine_id": "unit identifier within the location",
        "_machine_export_kw": "export capacity of a single unit",
        "_machine_import_kw": "import capacity of a single unit",
        "_tanm": "Transmission Area Network Management (constraint flag)",
        "_danm": "Distribution Area Network Management (constraint flag)",
        "_plik_zrodlowy": "name of the CSV resource in the CKAN catalog",
        "_status_raw": "status exactly as in the source",
    }
    detect_patterns = (r"connection.?queue", r"national.?grid")

    def __init__(self, dataset: str = "connection-queue", timeout: int = 90):
        self.dataset = dataset
        self.timeout = timeout

    # ------------------------------------------------------------------
    def fetch(self) -> tuple["Any", dict]:
        """Download all CSV resources of the dataset from the CKAN catalog."""
        import pandas as pd
        import requests

        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        r = s.get(f"{CKAN_BASE}/package_search",
                  params={"q": self.dataset, "rows": 50}, timeout=self.timeout)
        r.raise_for_status()
        pkgs = [p for p in r.json()["result"]["results"] if p["name"] == self.dataset]
        if not pkgs:
            raise LookupError(f"dataset {self.dataset!r} not found in the CKAN catalog")
        pkg = pkgs[0]
        resources = [res for res in pkg["resources"]
                     if (res.get("format") or "").upper() == "CSV"]
        frames, ok, failed = [], [], []
        for res in resources:
            try:
                rr = s.get(res["url"], timeout=self.timeout)
                rr.raise_for_status()
                d = pd.read_csv(io.BytesIO(rr.content))
                d["_plik_zrodlowy"] = res.get("name") or res["url"].rsplit("/", 1)[-1]
                frames.append(d)
                ok.append(res.get("name"))
            except Exception as exc:  # we record it, not hide it
                failed.append({"zasob": res.get("name"), "blad": f"{type(exc).__name__}: {exc}"})
        raw = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        meta = {
            "zbior": pkg["name"],
            "tytul": pkg.get("title"),
            "n_zasobow_csv": len(resources),
            "pobrane": len(ok),
            "nieudane": failed,
            "ostatnia_modyfikacja": pkg.get("metadata_modified"),
        }
        return raw, meta

    # ------------------------------------------------------------------
    def parse(self, source=None) -> ParseResult:
        """``source``: None -> download from CKAN; path/DataFrame -> use locally."""
        import pandas as pd

        if source is None:
            raw, meta = self.fetch()
        elif isinstance(raw_src := source, pd.DataFrame):
            raw, meta = raw_src.copy(), {"zrodlo": "DataFrame"}
        else:
            raw, meta = pd.read_csv(raw_src), {"zrodlo": str(raw_src)}

        def col(*names):
            for n in names:
                if n in raw.columns:
                    return raw[n]
            return pd.Series([None] * len(raw), index=raw.index)

        out = pd.DataFrame(index=raw.index)
        site = col("Site ID").astype("object")
        app = col("Application ID").astype("object")
        mach = col("Machine ID").astype("object")
        out["id_wniosku"] = [
            "nged:" + ":".join(str(x) for x in t if x is not None and str(x) != "nan")
            for t in zip(site, app, mach)
        ]
        out["id_wezla"] = col("Bus Number").map(
            lambda v: None if pd.isna(v) else str(int(v)) if float(v).is_integer() else str(v))
        out["nazwa_wezla"] = col("Bus Name")
        out["lokalizacja_tekst"] = col("GSP")
        out["klasa_zasobu"] = col("Fuel type").map(harmonize_klasa)
        out["moc_wprowadzana"] = col("Site Export Capacity (MW)").map(
            lambda v: canonical_power_kw(v, "MW"))
        out["moc_pobierana"] = col("Site Import Capacity (MW)").map(
            lambda v: canonical_power_kw(v, "MW"))
        tanm = col("TANM").map(_as_bool)
        danm = col("DANM").map(_as_bool)
        out["ograniczenie_flaga"] = [bool(a) or bool(b) for a, b in zip(tanm, danm)]
        out["pozycja_w_kolejce"] = col("Position").map(
            lambda v: None if pd.isna(v) else float(v))
        out["status_procesu"] = col("Status").map(harmonize_status)
        out["_status_raw"] = col("Status")
        out["_licence_area"] = col("Licence Area")
        out["_gsp"] = col("GSP")
        out["_machine_id"] = mach
        out["_machine_export_kw"] = col("Machine Export Capacity (MW)").map(
            lambda v: canonical_power_kw(v, "MW"))
        out["_machine_import_kw"] = col("Machine Import Capacity (MW)").map(
            lambda v: canonical_power_kw(v, "MW"))
        out["_tanm"] = tanm
        out["_danm"] = danm
        out["_plik_zrodlowy"] = col("_plik_zrodlowy", "_plik")

        report = {
            "publikujacy": self.publisher,
            "strategia_wydobycia": "CSV from the CKAN catalog (data already tabular)",
            "n_wierszy": int(len(out)),
            "katalog": meta,
        }
        return ParseResult(self.finalize(out, document=str(meta.get("zbior", source))), report)


def _as_bool(v) -> Optional[bool]:
    import pandas as pd

    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y", "tak"}:
        return True
    if s in {"false", "0", "no", "n", "nie"}:
        return False
    return None
