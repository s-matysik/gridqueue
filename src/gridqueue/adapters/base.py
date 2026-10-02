"""Wspólny interfejs adapterów publikujących.

Adapter jest jedynym miejscem, w którym wolno wiedzieć cokolwiek o układzie
konkretnego dokumentu.  Na zewnątrz każdy adapter wygląda tak samo:

    adapter.parse(source) -> ParseResult(frame, report)

``frame`` jest w schemacie (moduł ``schema``), ``report`` jest raportem jakości
wydobycia -- liczbami, nie wyjątkami.  Adapter DEKLARUJE, które pola opcjonalne
wypełnia i jakie rozszerzenia poza 21-polowym schematem wnosi; deklaracja jest
częścią kontraktu, bo pokrycie pól jest tu wynikiem pomiaru, a nie założeniem.
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
    frame: Any                      # pandas.DataFrame w schemacie
    report: dict[str, Any] = field(default_factory=dict)


class Adapter:
    """Klasa bazowa adaptera."""

    #: identyfikator publikującego
    publisher: str = ""
    #: jurysdykcja (kod kraju)
    jurisdiction: str = ""
    #: pola schematu, które ten publikujący ujawnia (deklaracja, weryfikowana pomiarem)
    declared_fields: tuple[str, ...] = ()
    #: rozszerzenia poza 21-polowym schematem -> opis; w ramce z przedrostkiem "_"
    declared_extensions: dict[str, str] = {}
    #: wzorce nazw plików / treści, po których wykrywamy publikującego
    detect_patterns: tuple[str, ...] = ()

    def parse(self, source) -> ParseResult:  # pragma: no cover - interfejs
        raise NotImplementedError

    # -- pomoc wspólna -----------------------------------------------------

    def blank_frame(self, n: int):
        import pandas as pd

        return pd.DataFrame(
            {c: pd.Series([None] * n, dtype="object") for c in FIELDS + META_COLUMNS}
        )

    def finalize(self, df, *, document: str = ""):
        """Domknij ramkę: kolejność kolumn, metadane, typy kanoniczne."""
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
# harmonizacja słowników kontrolowanych
# --------------------------------------------------------------------------


_STROKE = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O"})


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    s = str(s).replace("\n", " ")
    # znaki z kreska nie rozkladaja sie przez NFKD (l/L, d/D, o/O) -- mapujemy wprost
    s = s.translate(_STROKE)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip().lower()


#: mapowanie oznaczeń rodzaju instalacji na słownik kontrolowany.
#: Skróty TAURONA pochodzą z legendy na ostatniej stronie jego dokumentu.
_KLASA_MAP: tuple[tuple[str, str], ...] = (
    (r"^pv$|fotowolta|^solar$", "PV"),
    (r"^fw$|^mfw$|farma wiatrow|^wind$", "FW"),
    (r"^ew$|elektrownia wodn|^hydro$", "EW"),
    (r"biogaz|biomas|^jbm$", "BIOGAZ"),
    # legenda TAURONA (ostatnia strona dokumentu): BG blok gazowy, BGP blok
    # gazowo-parowy, SG silnik gazowy -- to sa jednostki GAZOWE, nie biogazowe
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
    # "rozwiazan" bez dookreslenia: lista rozwijana wspolnego szablonu PTPiREE/PSE
    # deklaruje status "UMOWA O PRZYŁĄCZENIE rozwiązana", ktorego nie lapaly ani
    # "umowa rozwiazan" (brak przyleglosci), ani "rozwiazanie umowy".  Bez tej
    # poprawki rozwiazana umowa spadala na regule "umowa o przylaczenie" i byla
    # raportowana jako UMOWA_OBOWIAZUJACA -- czyli status odwrotny do prawdziwego.
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
