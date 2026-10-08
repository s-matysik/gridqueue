"""Adapter: e-Distribución Redes Digitales (ES) — zdolność przyłączeniowa węzłów.

Dlaczego to źródło jest dla pakietu ważniejsze niż kolejny plik tabelaryczny
--------------------------------------------------------------------------
Manuskrypt wskazywał jako najmocniejszy brakujący test **drugą jurysdykcję
publikującą dokumenty przeznaczone do druku**: dotąd oba źródła zagraniczne
wydawały dane już tabelaryczne, więc przenoszalność wykazano na przypadku
łatwiejszym niż polski. To źródło ten brak zamyka. Publikujący wydaje **PDF
miesięczny**, w serii obejmującej lata 2023-2025, na podstawie art. 33 ust. 9
ustawy 24/2013, art. 5 ust. 4 dekretu 1183/2020 oraz art. 12 okólnika 1/2021
regulatora CNMC — konstrukcja prawna jest więc taka sama jak polska: obowiązek
ustawowy, stała częstość, format pozostawiony publikującemu.

Układ strony niesie linie wektorowe tabeli, więc wydobycie opiera się na nich,
a nie na odstępach między słowami.

Semantyka kolumn ustalona arytmetyką, nie nagłówkiem
----------------------------------------------------
Nagłówek ma komórki scalone w dwóch poziomach i sugeruje, że kolumny „Con
permiso de AyC" oraz „En trámite con capacidad" należą do grupy mocy przyjętej
i nierozstrzygniętej. **Jest to mylące.** Rozstrzyga arytmetyka dokumentu:

* jedenaście podkolumn — dziewięć pozycji stacji oraz te dwie — **sumuje się do
  mocy ZAJĘTEJ**, dokładnie, w 1838 z 1838 wierszy, w obu sprawdzonych wydaniach;
* rozbicie technologiczne sumuje się do mocy **przyjętej i nierozstrzygniętej**
  we wszystkich wierszach o niezerowej wartości.

Obie grupy są więc SKŁADNIKAMI mocy zajętej, a nie jej alternatywnymi
rozbiciami: część węzłów ma wypełnione tylko pozycje, część tylko dwie
pozostałe, a część obie, i dopiero suma wszystkich jedenastu zamyka się do
wartości łącznej.

Ma to wartość wykraczającą poza odwzorowanie pól. Dla tego publikującego **nie
istnieje zbiór odniesienia odczytany niezależnie od parsera**, więc dokładności
wydobycia nie da się zmierzyć w sposób, w jaki zmierzono ją dla publikujących
polskich. Domknięcie sumy jest tu zastępczym, słabszym, ale sprawdzalnym
świadectwem: aby suma jedenastu komórek zgadzała się z dwunastą, wszystkie
dwanaście musi być odczytane poprawnie. Na dwóch wydaniach daje to 3676
niezależnych sprawdzeń, wszystkie domknięte. Jest to świadectwo spójności
odczytu, NIE pomiar dokładności wobec wzorca — i tak należy je czytać.

Jednostki
---------
Publikujący podaje moce w **MW mocy czynnej**, więc przeliczenie na kanoniczne
kW jest zwykłą zmianą rzędu wielkości, bez założeń. Różni to to źródło od
portugalskiego, które podaje moc pozorną w MVA i dlatego pola mocy nie wypełnia.

Źródło podaje też **współrzędne geograficzne każdej podstacji**, czego nie robi
żaden publikujący polski.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "e-Distribución Redes Digitales S.L.U."
JURISDICTION = "ES"

#: Indeksy kolumn w wydobytej tabeli. Ustalone na wydaniu z sierpnia 2025
#: i zweryfikowane sumami; patrz nagłówek modułu.
K_WSPOLNOTA, K_PROWINCJA, K_GMINA, K_PODSTACJA = 0, 1, 2, 3
K_SZEROKOSC, K_DLUGOSC, K_NAPIECIE = 4, 5, 6
K_DOSTEPNA, K_ZAJETA_TOTAL = 7, 8
K_POZYCJE = tuple(range(9, 18))          # rozbicie mocy zajętej po pozycjach stacji
K_ZAJETA_Z_POZWOLENIEM, K_ZAJETA_W_TOKU = 18, 19
K_PRZYJETA_TOTAL = 20                     # przyjęta i nierozstrzygnięta
K_TECHNOLOGIE = (21, 22, 23, 24, 25)
K_SCC, K_WEZEL_PRZESYLOWY, K_KOMENTARZ = 26, 27, 28
SZEROKOSC_WIERSZA = 29

_WSPOLNOTA = re.compile(r"^\d{2}\s*-\s*")


def _liczba(v) -> float | None:
    """Liczba w zapisie hiszpańskim: przecinek dziesiętny, kropka tysięcy."""
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s in {"", "-", "--"}:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _mw_na_kw(v) -> float | None:
    """MW mocy czynnej -> kW mocy czynnej. Zmiana rzędu, nie wielkości fizycznej."""
    x = _liczba(v)
    return None if x is None else x * 1000.0


def _data_z_nazwy(nazwa: str) -> str | None:
    """'EDRD_Capacidad_de_Acceso_2025_08_01.pdf' -> '2025-08-01'.

    Data brana jest z nazwy pliku, a nie ze strony tytułowej, bo nazwa jest
    maszynowa i rozstrzygalna, a strona tytułowa podaje ją słownie po hiszpańsku.
    """
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", nazwa)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def suma_skladnikow_mocy_zajetej(wiersze) -> "tuple[int, int]":
    """Ile wierszy domyka tożsamość arytmetyczną dokumentu.

    Jedenaście podkolumn mocy zajętej (dziewięć pozycji stacji plus „z
    pozwoleniem" i „w toku") sumuje się do wartości łącznej. Funkcja zwraca
    parę (domkniętych, wszystkich).

    Po co to jest: dla tego publikującego nie ma zbioru odniesienia odczytanego
    niezależnie od parsera, więc dokładności wydobycia nie da się zmierzyć wobec
    wzorca. Domknięcie sumy jest zastępczym świadectwem spójności odczytu —
    słabszym niż wzorzec, ale sprawdzalnym na każdym wydaniu, bo wymaga
    poprawnego odczytania wszystkich dwunastu komórek bloku.
    """
    domkniete = 0
    for w in wiersze:
        if not w or len(w) != SZEROKOSC_WIERSZA:
            continue
        laczna = _liczba(w[K_ZAJETA_TOTAL])
        if laczna is None:
            continue
        skladniki = [_liczba(w[i]) or 0.0
                     for i in (*K_POZYCJE, K_ZAJETA_Z_POZWOLENIEM, K_ZAJETA_W_TOKU)]
        if round(sum(skladniki), 2) == round(laczna, 2):
            domkniete += 1
    return domkniete, sum(1 for w in wiersze
                          if w and len(w) == SZEROKOSC_WIERSZA
                          and _liczba(w[K_ZAJETA_TOTAL]) is not None)


class EDistribucionAdapter(Adapter):
    publisher = PUBLISHER
    jurisdiction = JURISDICTION
    declared_fields = (
        "id_wezla", "nazwa_wezla", "lokalizacja_tekst", "wspolrzedne", "poziom_napiecia",
        "moc_dostepna", "moc_zarezerwowana", "ograniczenie_flaga", "data_publikacji",
    )
    declared_extensions = {
        "_wspolnota_autonomiczna": "wspólnota autonomiczna",
        "_prowincja": "prowincja",
        "_moc_przyjeta_nierozstrzygnieta_kw": "moc wniosków przyjętych i nierozstrzygniętych",
        "_moc_zajeta_z_pozwoleniem_kw": "część mocy zajętej objęta pozwoleniem na przyłączenie",
        "_moc_zajeta_w_toku_kw": "część mocy zajętej w toku postępowania",
        "_rozbicie_technologiczne_kw": "moc nierozstrzygnięta w podziale na technologie",
        "_rozbicie_pozycyjne_kw": "moc zajęta w podziale na pozycje stacji",
        "_wezel_przesylowy": "węzeł sieci przesyłowej o największym oddziaływaniu",
        "_komentarz": "komentarz publikującego",
    }
    detect_patterns = (r"edrd[_ ]?capacidad", r"capacidad[_ ]de[_ ]acceso", r"e-?distribuci")

    def parse(self, source) -> ParseResult:
        import pandas as pd
        import pdfplumber

        path = Path(str(source))
        data_pub = _data_z_nazwy(path.name)

        surowe, stron = [], 0
        with pdfplumber.open(path) as pdf:
            stron = len(pdf.pages)
            for strona in pdf.pages:
                for tabela in strona.extract_tables():
                    for wiersz in tabela:
                        if (wiersz and len(wiersz) == SZEROKOSC_WIERSZA
                                and _WSPOLNOTA.match(str(wiersz[K_WSPOLNOTA] or ""))):
                            surowe.append(wiersz)

        domkniete, sprawdzonych = suma_skladnikow_mocy_zajetej(surowe)
        rekordy, ograniczonych, bez_wspolrzednych = [], 0, 0
        for w in surowe:
            def kom(i):
                v = w[i]
                return None if v is None or str(v).strip() == "" else str(v).strip()

            lat, lon = _liczba(w[K_SZEROKOSC]), _liczba(w[K_DLUGOSC])
            if lat is None or lon is None:
                bez_wspolrzednych += 1
            scc = (kom(K_SCC) or "").upper()
            ogr = {"SI": True, "SÍ": True, "NO": False}.get(scc)
            if ogr:
                ograniczonych += 1
            napiecie = kom(K_NAPIECIE)
            podstacja = kom(K_PODSTACJA)

            tech = {i: _mw_na_kw(w[i]) for i in K_TECHNOLOGIE}
            poz = {i: _mw_na_kw(w[i]) for i in K_POZYCJE}

            rekordy.append({
                # Identyfikator musi rozróżniać poziomy napięcia tej samej podstacji:
                # publikujący wydaje osobny wiersz dla każdego poziomu.
                "id_wezla": f"{podstacja}|{napiecie}" if podstacja and napiecie else podstacja,
                "nazwa_wezla": podstacja,
                "lokalizacja_tekst": ", ".join(x for x in (kom(K_GMINA), kom(K_PROWINCJA)) if x) or None,
                "wspolrzedne": f"{lat},{lon}" if lat is not None and lon is not None else None,
                "poziom_napiecia": f"{napiecie} kV" if napiecie else None,
                "moc_dostepna": _mw_na_kw(w[K_DOSTEPNA]),
                "moc_zarezerwowana": _mw_na_kw(w[K_ZAJETA_TOTAL]),
                "ograniczenie_flaga": ogr,
                "data_publikacji": data_pub,
                "_encja": "WEZEL",
                "_wspolnota_autonomiczna": kom(K_WSPOLNOTA),
                "_prowincja": kom(K_PROWINCJA),
                "_moc_przyjeta_nierozstrzygnieta_kw": _mw_na_kw(w[K_PRZYJETA_TOTAL]),
                "_moc_zajeta_z_pozwoleniem_kw": _mw_na_kw(w[K_ZAJETA_Z_POZWOLENIEM]),
                "_moc_zajeta_w_toku_kw": _mw_na_kw(w[K_ZAJETA_W_TOKU]),
                "_rozbicie_technologiczne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in tech.items() if v) or None,
                "_rozbicie_pozycyjne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in poz.items() if v) or None,
                "_wezel_przesylowy": kom(K_WEZEL_PRZESYLOWY),
                "_komentarz": kom(K_KOMENTARZ),
            })

        df = self.finalize(pd.DataFrame(rekordy), document=path.name)
        notes = {
            "publikujacy": PUBLISHER,
            "jurysdykcja": JURISDICTION,
            "tryb_wydania": "dokument przeznaczony do druku, wydanie miesięczne",
            "stron": stron,
            "wierszy": int(len(df)),
            "wezlow_ograniczonych_przez_Scc": ograniczonych,
            "wierszy_bez_wspolrzednych": bez_wspolrzednych,
            "jednostka_mocy_zrodlowa": "MW",
            "przeliczenie": "MW -> kW, obie wielkości to moc czynna",
            "data_publikacji": data_pub,
            "tozsamosc_sumy_mocy_zajetej": f"{domkniete}/{sprawdzonych}",
            "uwaga_tozsamosc": (
                "Jedenaście podkolumn mocy zajętej sumuje się do wartości łącznej. "
                "Jest to świadectwo SPÓJNOŚCI odczytu, nie pomiar dokładności wobec "
                "wzorca odczytanego niezależnie od parsera — takiego wzorca dla tego "
                "publikującego nie ma."
            ),
        }
        return ParseResult(frame=df, report=notes)
