"""Adapter: National Grid Electricity Distribution (UK) -- zbiór "Connection Queue".

Ten adapter istnieje po to, żeby udowodnić przenoszalność schematu, a nie żeby
sparsować kolejny PDF.  Brytyjski publikujący wystawia te same informacje jako
45 osobnych plików CSV w katalogu CKAN -- dane są już tabelaryczne, więc CAŁA
warstwa wydobycia po układzie strony jest tu zbędna.  To jest dokładnie ta
asymetria, którą narzędzie ma pokazać: w jurysdykcji o dobrych danych parser
jest niepotrzebny, w Polsce jest warunkiem dostępu do treści obowiązku.

Dostęp: publiczny endpoint ``package_search`` CKAN, bez klucza.  Klient
przedstawia się uczciwie w nagłówku User-Agent; nie podszywamy się pod przeglądarkę.
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
        "_licence_area": "obszar licencyjny operatora",
        "_gsp": "Grid Supply Point",
        "_machine_id": "identyfikator jednostki w ramach lokalizacji",
        "_machine_export_kw": "moc eksportowa pojedynczej jednostki",
        "_machine_import_kw": "moc importowa pojedynczej jednostki",
        "_tanm": "Transmission Area Network Management (flaga ograniczenia)",
        "_danm": "Distribution Area Network Management (flaga ograniczenia)",
        "_plik_zrodlowy": "nazwa zasobu CSV w katalogu CKAN",
        "_status_raw": "status tak, jak w źródle",
    }
    detect_patterns = (r"connection.?queue", r"national.?grid")

    def __init__(self, dataset: str = "connection-queue", timeout: int = 90):
        self.dataset = dataset
        self.timeout = timeout

    # ------------------------------------------------------------------
    def fetch(self) -> tuple["Any", dict]:
        """Pobierz wszystkie zasoby CSV zbioru z katalogu CKAN."""
        import pandas as pd
        import requests

        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        r = s.get(f"{CKAN_BASE}/package_search",
                  params={"q": self.dataset, "rows": 50}, timeout=self.timeout)
        r.raise_for_status()
        pkgs = [p for p in r.json()["result"]["results"] if p["name"] == self.dataset]
        if not pkgs:
            raise LookupError(f"nie znaleziono zbioru {self.dataset!r} w katalogu CKAN")
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
            except Exception as exc:  # zapisujemy, nie ukrywamy
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
        """``source``: None -> pobierz z CKAN; ścieżka/DataFrame -> użyj lokalnie."""
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
            "strategia_wydobycia": "CSV z katalogu CKAN (dane już tabelaryczne)",
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
