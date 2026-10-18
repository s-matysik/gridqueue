#!/usr/bin/env python3
"""Downloads the source documents from the addresses in the manifest and checks the checksums.

Why downloading instead of shipping the files
---------------------------------------------
The documents are NOT distributed in this repository. The reason is given in
`DATA_LICENSE.md` and comes down to this: we have not settled the legal status of
redistributing them, and the publishers replace them every quarter, so a copy in
the repository would be misleading after a few months.

For every file the manifest gives the address, the download date and the SHA-256
checksum, so the reproduction is checkable: if the publisher has replaced the
document with a newer edition, the checksum will not match and the script will
REPORT that instead of quietly computing results on different data.

Usage
-----
    python reproducibility/fetch_sources.py [target_directory]

Exit codes: 0, everything downloaded and matching; 1, something is missing or a
checksum does not match; 2, the manifest cannot be read.
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
#: Addresses that point at the publisher's website rather than at a file.
#: Downloading one means finding the current edition by hand; the publisher
#: does not expose a stable link to the file.
BEZ_TRWALEGO_ODSYLACZA = ("https://www.stoen.pl/", "https://www.elana-energetyka.pl/")

#: Environment variable pointing at a custom bundle of trusted issuers. Needed
#: in networks where traffic goes through a proxy that substitutes its own
#: certificate; chain verification then fails even though the server is sound.
#: We point at a bundle and do NOT switch verification off: switching it off
#: would make the downloaded file untrustworthy and void the whole point of the
#: checksums.
ZMIENNA_CA = "GRIDQUEUE_CA_BUNDLE"


def _kontekst_ssl() -> ssl.SSLContext | None:
    paczka = os.environ.get(ZMIENNA_CA) or os.environ.get("SSL_CERT_FILE") \
        or os.environ.get("REQUESTS_CA_BUNDLE")
    if not paczka:
        return None
    return ssl.create_default_context(cafile=paczka)


#: File header signatures. An address that no longer leads to the document
#: usually returns an HTML page with code 200; without this check the script
#: would diagnose that as a replaced edition, which looks confusingly similar
#: but calls for a completely different reaction from the user.
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
        print(f"cannot read the manifest: {e}", file=sys.stderr)
        return 2

    ok, recznie, bledy = [], [], []
    for w in wiersze:
        plik, url, suma = w["plik"], w["url"], w["sha256"]
        docelowy = cel / plik
        if docelowy.exists() and sha256(docelowy) == suma:
            ok.append(plik)
            print(f"[have ]  {plik}")
            continue
        if url in BEZ_TRWALEGO_ODSYLACZA:
            recznie.append((plik, url))
            print(f"[hand ]  {plik}  <- {url}  (no stable link to the file)")
            continue
        try:
            zad = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(zad, timeout=180, context=_kontekst_ssl()) as odp:
                dane = odp.read()
            if not wyglada_na_dokument(dane, plik):
                bledy.append((plik, "the address no longer returns the document"))
                print(f"[ADDR ]  {plik}: the address returned content that is not a document"
                      f" ({len(dane)} B).")
                print( "         The publisher has probably rebuilt the website. Find the")
                print( "         current edition there and update the manifest.")
                continue
            docelowy.write_bytes(dane)
        except urllib.error.URLError as e:
            powod = getattr(e, "reason", e)
            if isinstance(powod, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(powod):
                bledy.append((plik, "certificate verification failed"))
                print(f"[CERT ]  {plik}: verification of the certificate chain failed.")
                print(f"         If your network uses a proxy with its own certificate,")
                print(f"         point at its bundle: {ZMIENNA_CA}=/path/to/ca-bundle.pem")
                print( "         Do not switch verification off; the checksums would lose their point.")
            else:
                bledy.append((plik, f"download failed: {powod}"))
                print(f"[ERROR]  {plik}: {powod}")
            continue
        except OSError as e:
            bledy.append((plik, f"write failed: {e}"))
            print(f"[ERROR]  {plik}: {e}")
            continue
        faktyczna = sha256(docelowy)
        if faktyczna != suma:
            bledy.append((plik, "the checksum does not match"))
            print(f"[HASH ]  {plik}: expected {suma[:12]}…, got {faktyczna[:12]}…")
            print("         the publisher has probably replaced the document with a newer edition;")
            print("         results from this file will NOT be identical with the published ones.")
        else:
            ok.append(plik)
            print(f"[got  ]  {plik}")

    print(f"\nmatching: {len(ok)}/{len(wiersze)} | to download by hand: {len(recznie)}"
          f" | errors: {len(bledy)}")
    if recznie:
        print("\nFiles with no stable link; find the current edition on the publisher's")
        print("website and save it under the name from the manifest:")
        for plik, url in recznie:
            print(f"  {plik}  <-  {url}")
    return 0 if not bledy and not recznie else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
