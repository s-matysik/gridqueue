#!/usr/bin/env python3
"""Pobiera dokumenty źródłowe z adresów podanych w manifeście i sprawdza sumy.

Dlaczego pobieranie zamiast dołączenia plików
---------------------------------------------
Dokumenty NIE są rozpowszechniane w tym repozytorium. Powód jest podany
w `DATA_LICENSE.md` i sprowadza się do tego, że status prawny ich redystrybucji
nie jest przez nas rozstrzygnięty, a publikujący wymieniają je co kwartał —
kopia w repozytorium po kilku miesiącach wprowadzałaby w błąd.

Manifest podaje dla każdego pliku adres, datę pobrania i sumę SHA-256, więc
odtworzenie jest sprawdzalne: jeśli publikujący zastąpił dokument nowszą
edycją, suma się nie zgodzi i skrypt to ZGŁOSI, zamiast po cichu policzyć
wyniki na innych danych.

Użycie
------
    python reproducibility/fetch_sources.py [katalog_docelowy]

Kody wyjścia: 0 — wszystko pobrane i zgodne; 1 — czegoś brakuje albo suma
się nie zgadza; 2 — manifest nieczytelny.
"""

from __future__ import annotations

import csv
import hashlib
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).with_name("manifest.csv")
AGENT = "gridqueue-reproducibility/1.3 (statutory grid connection disclosure)"
#: Adresy, które wskazują stronę publikującego, a nie plik. Pobranie wymaga
#: ręcznego odszukania bieżącej edycji — publikujący nie wystawia trwałego
#: odsyłacza do pliku.
BEZ_TRWALEGO_ODSYLACZA = ("https://www.stoen.pl/", "https://www.elana-energetyka.pl/")

#: Zmienna środowiskowa wskazująca własny pakiet zaufanych wystawców. Potrzebna
#: w sieciach, w których ruch przechodzi przez pośrednika podstawiającego własny
#: certyfikat — wtedy weryfikacja łańcucha zawodzi mimo poprawnego serwera.
#: Wskazujemy pakiet, a NIE wyłączamy weryfikacji: wyłączenie sprawiłoby, że
#: pobrany plik przestaje być wiarygodny, a cały sens sum kontrolnych znika.
ZMIENNA_CA = "GRIDQUEUE_CA_BUNDLE"


def _kontekst_ssl() -> ssl.SSLContext | None:
    paczka = os.environ.get(ZMIENNA_CA) or os.environ.get("SSL_CERT_FILE") \
        or os.environ.get("REQUESTS_CA_BUNDLE")
    if not paczka:
        return None
    return ssl.create_default_context(cafile=paczka)


#: Sygnatury początku pliku. Adres, który przestał prowadzić do dokumentu,
#: zwykle zwraca stronę HTML z kodem 200 — bez tego sprawdzenia skrypt
#: zdiagnozowałby to jako podmianę edycji, co jest myląco podobne, a wymaga
#: zupełnie innej reakcji użytkownika.
SYGNATURY = {".pdf": b"%PDF", ".xlsx": b"PK\x03\x04", ".csv": None, ".json": None}


def wyglada_na_dokument(dane: bytes, nazwa: str) -> bool:
    rozszerzenie = Path(nazwa).suffix.lower()
    sygnatura = SYGNATURY.get(rozszerzenie)
    if sygnatura is None:
        poczatek = dane[:512].lstrip()[:15].lower()
        return not (poczatek.startswith(b"<!doctype") or poczatek.startswith(b"<html"))
    return dane.startswith(sygnatura)


def sha256(sciezka: Path) -> str:
    h = hashlib.sha256()
    with sciezka.open("rb") as f:
        for kawalek in iter(lambda: f.read(1 << 20), b""):
            h.update(kawalek)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    cel = Path(argv[1]) if len(argv) > 1 else Path("sources")
    cel.mkdir(parents=True, exist_ok=True)
    try:
        wiersze = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    except OSError as e:
        print(f"nie można odczytać manifestu: {e}", file=sys.stderr)
        return 2

    ok, recznie, bledy = [], [], []
    for w in wiersze:
        plik, url, suma = w["plik"], w["url"], w["sha256"]
        docelowy = cel / plik
        if docelowy.exists() and sha256(docelowy) == suma:
            ok.append(plik)
            print(f"[jest ]  {plik}")
            continue
        if url in BEZ_TRWALEGO_ODSYLACZA:
            recznie.append((plik, url))
            print(f"[ręczn]  {plik}  <- {url}  (brak trwałego odsyłacza do pliku)")
            continue
        try:
            zad = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(zad, timeout=180, context=_kontekst_ssl()) as odp:
                dane = odp.read()
            if not wyglada_na_dokument(dane, plik):
                bledy.append((plik, "adres nie zwraca już dokumentu"))
                print(f"[ADRES]  {plik}: adres zwrócił treść, która nie jest dokumentem"
                      f" ({len(dane)} B).")
                print( "         Publikujący prawdopodobnie przebudował serwis. Odszukaj")
                print( "         bieżącą edycję na jego stronie i zaktualizuj manifest.")
                continue
            docelowy.write_bytes(dane)
        except urllib.error.URLError as e:
            powod = getattr(e, "reason", e)
            if isinstance(powod, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(powod):
                bledy.append((plik, "weryfikacja certyfikatu nieudana"))
                print(f"[CERT ]  {plik}: weryfikacja łańcucha certyfikatów nie powiodła się.")
                print(f"         Jeśli Twoja sieć używa pośrednika z własnym certyfikatem,")
                print(f"         wskaż jego pakiet: {ZMIENNA_CA}=/ścieżka/do/ca-bundle.pem")
                print( "         Nie wyłączaj weryfikacji — sumy kontrolne straciłyby sens.")
            else:
                bledy.append((plik, f"pobranie nieudane: {powod}"))
                print(f"[BŁĄD ]  {plik}: {powod}")
            continue
        except OSError as e:
            bledy.append((plik, f"zapis nieudany: {e}"))
            print(f"[BŁĄD ]  {plik}: {e}")
            continue
        faktyczna = sha256(docelowy)
        if faktyczna != suma:
            bledy.append((plik, "suma kontrolna się nie zgadza"))
            print(f"[SUMA ]  {plik}: oczekiwano {suma[:12]}…, otrzymano {faktyczna[:12]}…")
            print("         publikujący prawdopodobnie zastąpił dokument nowszą edycją;")
            print("         wyniki z tego pliku NIE będą identyczne z opublikowanymi.")
        else:
            ok.append(plik)
            print(f"[pobr ]  {plik}")

    print(f"\nzgodnych: {len(ok)}/{len(wiersze)} | do pobrania ręcznie: {len(recznie)}"
          f" | błędów: {len(bledy)}")
    if recznie:
        print("\nPliki bez trwałego odsyłacza — odszukaj bieżącą edycję na stronie")
        print("publikującego i zapisz pod nazwą z manifestu:")
        for plik, url in recznie:
            print(f"  {plik}  <-  {url}")
    return 0 if not bledy and not recznie else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
