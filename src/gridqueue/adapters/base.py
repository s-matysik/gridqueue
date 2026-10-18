"""Common interface for publishing adapters.

The adapter is the only place that is allowed to know anything about the layout
of a specific document.  From the outside, every adapter looks the same:

    adapter.parse(source) -> ParseResult(frame, report)

``frame`` is in the schema (``schema`` module), ``report`` is a quality report of
the extraction: numbers, not exceptions.  The adapter DECLARES which optional fields
it fills in and what extensions beyond the 21-field schema it contributes; the declaration
is part of the contract, because field coverage here is the result of measurement, not
an assumption.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Optional

from ..schema import FIELDS, META_COLUMNS, canonical_date, canonical_power_kw

__all__ = ["Adapter", "ParseResult", "harmonize_klasa", "harmonize_status", "norm_text"]


@dataclass
class ParseResult:
    frame: Any                      # pandas.DataFrame in the schema
    report: dict[str, Any] = field(default_factory=dict)


class Adapter:
    """Base adapter class."""

    #: publisher identifier
    publisher: str = ""
    #: jurisdiction (country code)
    jurisdiction: str = ""
    #: schema fields that this publisher discloses (declaration, verified by measurement)
    declared_fields: tuple[str, ...] = ()
    #: extensions beyond the 21-field schema -> description; in the frame with a "_" prefix
    declared_extensions: dict[str, str] = {}
    #: filename / content patterns used to detect the publisher
    detect_patterns: tuple[str, ...] = ()

    def parse(self, source) -> ParseResult:  # pragma: no cover - interface
        raise NotImplementedError

    # -- shared helpers -----------------------------------------------------

    def blank_frame(self, n: int):
        import pandas as pd

        return pd.DataFrame(
            {c: pd.Series([None] * n, dtype="object") for c in FIELDS + META_COLUMNS}
        )

    def finalize(self, df, *, document: str = ""):
        """Close out the frame: column order, metadata, canonical types."""
        import pandas as pd

        for c in FIELDS + META_COLUMNS:
            if c not in df.columns:
                df[c] = None
        df["publikujacy"] = self.publisher
        df["jurysdykcja"] = self.jurisdiction
        if document:
            df["dokument_zrodlowy"] = document
        extra = [c for c in df.columns if c not in FIELDS + META_COLUMNS]
        df = df[list(FIELDS) + list(META_COLUMNS) + sorted(extra)]
        return df.reset_index(drop=True)

    def declaration(self) -> dict[str, Any]:
        return {
            "publikujacy": self.publisher,
            "jurysdykcja": self.jurisdiction,
            "pola_deklarowane": list(self.declared_fields),
            "rozszerzenia": dict(self.declared_extensions),
        }


# --------------------------------------------------------------------------
# harmonization of controlled vocabularies
# --------------------------------------------------------------------------


_STROKE = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O"})


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).replace("\n", " ")
    # characters with a stroke do not decompose via NFKD (l/L, d/D, o/O): we map them directly
    s = s.translate(_STROKE)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().lower()


#: mapping of installation type designations to the controlled vocabulary.
#: TAURON's abbreviations come from the legend on the last page of its document.
_KLASA_MAP: tuple[tuple[str, str], ...] = (
    (r"^pv$|fotowolta|^solar$", "PV"),
    (r"^fw$|^mfw$|farma wiatrow|^wind$", "FW"),
    (r"^ew$|elektrownia wodn|^hydro$", "EW"),
    (r"biogaz|biomas|^jbm$", "BIOGAZ"),
    # TAURON legend (last page of the document): BG gas block, BGP gas-steam
    # block, SG gas engine: these are GAS units, not biogas ones
    (r"^bg$|^bgp$|^sg$|blok gazow|silnik gazow", "GAZ"),
    (r"^jw$|jednostka weglow", "WEGIEL"),
    (r"^mee|magazyn energii|^bess$|^battery", "BESS"),
    (r"^odb$|instalacja odbiorcz|^demand$|odbiorc", "ODB"),
    (r"^mix$", "MIX"),
    (r"^osd|^siec$|^network$|stacja transformator|siec dystrybucyjn|^sieci$", "SIEC"),
    (r"^inne zrodla$|^inne$|^other$|^ej$|^esp$|^ogw$|^js$|^mfw$", "INNE"),
    (r"wytworcz", "INNE"),
)

_STATUS_MAP: tuple[tuple[str, str], ...] = (
    (r"wniosek niekompletny|uzupelnien", "WNIOSEK_NIEKOMPLETNY"),
    (r"w trakcie analiz|w trakcie rozpatr|wniosek kompletny", "W_TRAKCIE_ANALIZY"),
    (r"wniosek wycofan|wycofan", "WNIOSEK_WYCOFANY"),
    (r"utracil\w* waznosc|utrata waznosci|wygasl", "WARUNKI_WYGASLE"),
    (r"odmow|refus", "ODMOWA"),
    # "rozwiazan" without further determination: the drop-down list of the common
    # PTPiREE/PSE template declares the status "UMOWA O PRZYŁĄCZENIE rozwiązana",
    # which was not caught by either "umowa rozwiazan" (lacking adjacency), or
    # "rozwiazanie umowy".  Without this fix, a terminated agreement fell under
    # the "umowa o przylaczenie" rule and was reported as UMOWA_OBOWIAZUJACA:
    # i.e., the opposite status of the true one.
    (r"rozwiazan", "UMOWA_ROZWIAZANA"),
    (r"obiekt przylaczony|recently connected|^connected$|przylaczon", "PRZYLACZONY"),
    (r"umowa o przylaczenie|umowa obowiazuj|accepted not yet connected|^accepted", "UMOWA_OBOWIAZUJACA"),
    (r"warunki przylaczenia|warunki wydane|warunki okreslone", "WARUNKI_WYDANE"),
    (r"wniosek", "WNIOSEK_ZLOZONY"),
)


def harmonize_klasa(raw: Any) -> str:
    t = norm_text(raw)
    if not t:
        return "NIEOKRESLONA"
    for rx, out in _KLASA_MAP:
        if re.search(rx, t):
            return out
    return "INNE"


def harmonize_status(raw: Any) -> str:
    t = norm_text(raw)
    if not t:
        return "NIEOKRESLONY"
    for rx, out in _STATUS_MAP:
        if re.search(rx, t):
            return out
    return "NIEOKRESLONY"
