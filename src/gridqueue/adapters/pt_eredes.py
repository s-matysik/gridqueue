"""Adapter: E-REDES (PT) — zdolność przyjęcia krajowej sieci dystrybucyjnej.

Źródło jest trzecim trybem wydania w panelu: nie dokument do druku i nie plik
na stronie, lecz **zbiór na portalu otwartych danych z interfejsem REST**.
Publikacja jest kwartalna, tak jak polski obowiązek, a jednostką wiersza jest
podstacja albo punkt cięcia sieci wysokiego napięcia.

Co ten adapter wnosi do panelu
------------------------------
Pierwsze zagraniczne źródło wypełniające encję **WĘZEŁ**. Dotąd moc dostępną
w węźle ujawniał wyłącznie jeden publikujący polski, więc kryterium „dostępna
moc przyłączeniowa" dało się policzyć w jednej jurysdykcji. Źródło portugalskie
podaje ponadto **skład grupy podstacji**, czyli dokładnie tę informację, która
w panelu polskim umożliwia przypisanie wniosków do węzła.

Rozstrzygnięcie jednostek — przeczytaj, zanim zaczniesz porównywać
------------------------------------------------------------------
Publikujący podaje zdolność przyjęcia i moce przyłączone w **MVA**, czyli
w mocy pozornej. Jednostką kanoniczną schematu jest **kW mocy czynnej**. Są to
różne wielkości fizyczne i przeliczenie jednej na drugą wymaga założenia
o współczynniku mocy, którego publikujący nie podaje.

Dlatego pole `moc_dostepna` pozostaje **puste**, a wartości w MVA trafiają do
pól rozszerzenia wraz z jawnie zapisaną jednostką źródłową. Jest to ta sama
zasada, którą zastosowano wobec publikującego podającego liczbę wolnych miejsc
przyłączeniowych zamiast mocy: wpisanie liczby w pole o innej jednostce byłoby
fabrykacją, a nie harmonizacją.

Rdzeń encji WĘZEŁ jest mimo to spełniony, bo realizuje go drugi człon
alternatywy — `ograniczenie_flaga`, ustawiana na podstawie zerowej zdolności
przyjęcia. Zero zdolności przyjęcia jest wartością ujawnioną i oznacza
ograniczenie, a nie brak danych.

Format wejścia
--------------
Eksport CSV z portalu (separator średnik, nagłówki techniczne, nie etykiety).
Adapter celowo czyta PLIK, a nie odpytuje interfejsu przy parsowaniu: dzięki
temu wynik jest odtwarzalny z manifestu z sumą kontrolną, tak jak u pozostałych
publikujących.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "E-REDES S.A."
JURISDICTION = "PT"
#: Jednostka, w której publikujący podaje moce. NIE jest to jednostka kanoniczna
#: schematu (kW mocy czynnej) i nie jest na nią przeliczana.
SOURCE_POWER_UNIT = "MVA"

#: Kolumny zdolności przyjęcia w podziale na poziomy napięcia, od najwyższego.
#: Służą wyłącznie do ustalenia poziomu napięcia, na którym zdolność występuje;
#: ich wartości nie wchodzą do pola mocy z powodu różnicy jednostek.
_KOLUMNY_NAPIEC = [
    ("capacidade_de_recepcao_at_mva_ultimo_trimestre", "AT"),
    ("capacidade_de_recepcao_mt_30kv_mva_ultimo_trimestre", "30 kV"),
    ("capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre", "15 kV"),
    ("capacidade_de_recepcao_mt_10kv_mva_ultimo_trimestre", "10 kV"),
]

_TYP_INSTALACJI = {
    "SE AT": "substation_HV",
    "PC AT": "cutting_point_HV",
}


def _liczba(v) -> float | None:
    """Liczba z zapisu portalowego; przecinek dziesiętny dopuszczony."""
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s == "" or s.lower() in {"none", "nan"}:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _kwartal_na_date(v) -> str | None:
    """'2T2026' -> '2026-06-30'. Publikacja kwartalna, dzień ostatni kwartału."""
    s = str(v or "").strip().upper()
    if len(s) == 6 and s[1] == "T" and s[0].isdigit() and s[2:].isdigit():
        kw, rok = int(s[0]), int(s[2:])
        koniec = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}.get(kw)
        if koniec:
            return f"{rok}-{koniec}"
    return None


class EredesAdapter(Adapter):
    publisher = PUBLISHER
    jurisdiction = JURISDICTION
    declared_fields = (
        "id_wezla", "nazwa_wezla", "lokalizacja_tekst", "poziom_napiecia",
        "ograniczenie_flaga", "data_publikacji",
    )
    declared_extensions = {
        "_jednostka_mocy_zrodlowa": "jednostka, w której publikujący podaje moce (MVA)",
        "_moc_dostepna_mva": "zdolność przyjęcia SN+WN w MVA, tak jak w źródle",
        "_moc_przylaczona_mva": "moc przyłączona w MVA",
        "_moc_zakontraktowana_mva": "moc zakontraktowana w MVA",
        "_moc_w_potwierdzaniu_mva": "moc w trakcie potwierdzania w MVA",
        "_typ_instalacji": "podstacja albo punkt cięcia sieci wysokiego napięcia",
        "_dystrykt": "dystrykt administracyjny",
        "_gmina": "gmina",
        "_nuts3": "jednostka statystyczna NUTS 3",
        "_wezel_rnt": "węzeł sieci przesyłowej, z którym połączona jest podstacja",
    }
    detect_patterns = (r"capacidade.?rececao", r"e.?redes", r"\brnd\b")

    def parse(self, source) -> ParseResult:
        path = Path(str(source))
        with path.open(encoding="utf-8-sig", newline="") as f:
            wiersze = list(csv.DictReader(f, delimiter=";"))

        rekordy, bez_kodu, zerowa = [], 0, 0
        for w in wiersze:
            kod = (w.get("codigo") or "").strip()
            if not kod:
                bez_kodu += 1
            zdolnosc = _liczba(w.get("capacidade_de_recepcao_mt_at_mva_ultimo_trimestre"))
            ograniczenie = None
            if zdolnosc is not None:
                ograniczenie = zdolnosc == 0.0
                zerowa += int(ograniczenie)

            napiecia = [etykieta for kol, etykieta in _KOLUMNY_NAPIEC
                        if (_liczba(w.get(kol)) or 0.0) > 0.0]

            rekordy.append({
                "id_wezla": kod or None,
                "nazwa_wezla": (w.get("instalacao") or "").strip() or None,
                # Skład grupy podstacji — odpowiednik listy stacji w wierszu
                # węzłowym publikującego polskiego, więc trafia w to samo pole.
                "lokalizacja_tekst": (w.get("grupo_de_subestacoes_rari") or "").strip() or None,
                "poziom_napiecia": ", ".join(napiecia) or None,
                "moc_dostepna": None,       # jednostka źródłowa to MVA — patrz nagłówek modułu
                "moc_zarezerwowana": None,  # jw.
                "ograniczenie_flaga": ograniczenie,
                "data_publikacji": _kwartal_na_date(w.get("data_ultimo_trimestre")),
                "_encja": "WEZEL",
                "_jednostka_mocy_zrodlowa": SOURCE_POWER_UNIT,
                "_moc_dostepna_mva": zdolnosc,
                "_moc_przylaczona_mva": _liczba(w.get("potencia_de_ligacao_ligado_mva_ultimo_trimestre")),
                "_moc_zakontraktowana_mva": _liczba(w.get("potencia_de_ligacao_comprometido_mva_ultimo_trimestre")),
                "_moc_w_potwierdzaniu_mva": _liczba(w.get("potencia_de_ligacao_em_confirmacao_mva_ultimo_trimestre")),
                "_typ_instalacji": _TYP_INSTALACJI.get(
                    (w.get("tipo_de_instalacao") or "").strip(),
                    (w.get("tipo_de_instalacao") or "").strip() or None),
                "_dystrykt": (w.get("distrito") or "").strip() or None,
                "_gmina": (w.get("concelho") or "").strip() or None,
                "_nuts3": (w.get("nut3") or "").strip() or None,
                "_wezel_rnt": (w.get("ligacao_rnt_barramento_60kv_ultimo_trimestre") or "").strip() or None,
            })

        import pandas as pd

        df = self.finalize(pd.DataFrame(rekordy), document=path.name)
        notes = {
            "publikujacy": PUBLISHER,
            "jurysdykcja": JURISDICTION,
            "tryb_wydania": "portal otwartych danych, eksport CSV z interfejsu REST",
            "wierszy": int(len(df)),
            "wierszy_bez_kodu_instalacji": bez_kodu,
            "wezlow_o_zerowej_zdolnosci_przyjecia": zerowa,
            "jednostka_mocy_zrodlowa": SOURCE_POWER_UNIT,
            "moc_dostepna_pusta_z_powodu_jednostki": True,
            "uwaga_jednostki": (
                "Publikujący podaje moce w MVA (moc pozorna); jednostką kanoniczną schematu "
                "jest kW mocy czynnej. Przeliczenie wymagałoby nieujawnionego współczynnika "
                "mocy, więc pole moc_dostepna pozostaje puste, a wartości źródłowe są "
                "w polach rozszerzenia z jawną jednostką."
            ),
        }
        return ParseResult(frame=df, report=notes)
