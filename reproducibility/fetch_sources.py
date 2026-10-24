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
WITHOUT_PERMANENT_LINK = ("https://www.stoen.pl/", "https://www.elana-energetyka.pl/")

#: Environment variable pointing at a custom bundle of trusted issuers. Needed
#: in networks where traffic goes through a proxy that substitutes its own
#: certificate; chain verification then fails even though the server is sound.
#: We point at a bundle and do NOT switch verification off: switching it off
#: would make the downloaded file untrustworthy and void the whole point of the
#: checksums.
VARIABLE_CA = "GRIDQUEUE_CA_BUNDLE"


def _ssl_context() -> ssl.SSLContext | None:
    package = os.environ.get(VARIABLE_CA) or os.environ.get("SSL_CERT_FILE") \
        or os.environ.get("REQUESTS_CA_BUNDLE")
    if not package:
        return None
    return ssl.create_default_context(cafile=package)


#: File header signatures. An address that no longer leads to the document
#: usually returns an HTML page with code 200; without this check the script
#: would diagnose that as a replaced edition, which looks confusingly similar
#: but calls for a completely different reaction from the user.
SIGNATURES = {".pdf": b"%PDF", ".xlsx": b"PK\x03\x04", ".csv": None, ".json": None}


def looks_like_document(data: bytes, name: str) -> bool:
    extension = Path(name).suffix.lower()
    signature = SIGNATURES.get(extension)
    if signature is None:
        start = data[:512].lstrip()[:15].lower()
        return not (start.startswith(b"<!doctype") or start.startswith(b"<html"))
    return data.startswith(signature)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    goal = Path(argv[1]) if len(argv) > 1 else Path("sources")
    goal.mkdir(parents=True, exist_ok=True)
    try:
        rows = list(csv.DictReader(MANIFEST.open(encoding="utf-8")))
    except OSError as e:
        print(f"cannot read the manifest: {e}", file=sys.stderr)
        return 2

    ok, manually, errors = [], [], []
    for w in rows:
        file_name, url, total = w["file_name"], w["url"], w["sha256"]
        target = goal / file_name
        if target.exists() and sha256(target) == total:
            ok.append(file_name)
            print(f"[have ]  {file_name}")
            continue
        if url in WITHOUT_PERMANENT_LINK:
            manually.append((file_name, url))
            print(f"[hand ]  {file_name}  <- {url}  (no stable link to the file)")
            continue
        try:
            zad = urllib.request.Request(url, headers={"User-Agent": AGENT})
            with urllib.request.urlopen(zad, timeout=180, context=_ssl_context()) as answer:
                data = answer.read()
            if not looks_like_document(data, file_name):
                errors.append((file_name, "the address no longer returns the document"))
                print(f"[ADDR ]  {file_name}: the address returned content that is not a document"
                      f" ({len(data)} B).")
                print( "         The publisher has probably rebuilt the website. Find the")
                print( "         current edition there and update the manifest.")
                continue
            target.write_bytes(data)
        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
                errors.append((file_name, "certificate verification failed"))
                print(f"[CERT ]  {file_name}: verification of the certificate chain failed.")
                print(f"         If your network uses a proxy with its own certificate,")
                print(f"         point at its bundle: {VARIABLE_CA}=/path/to/ca-bundle.pem")
                print( "         Do not switch verification off; the checksums would lose their point.")
            else:
                errors.append((file_name, f"download failed: {reason}"))
                print(f"[ERROR]  {file_name}: {reason}")
            continue
        except OSError as e:
            errors.append((file_name, f"write failed: {e}"))
            print(f"[ERROR]  {file_name}: {e}")
            continue
        actual = sha256(target)
        if actual != total:
            errors.append((file_name, "the checksum does not match"))
            print(f"[HASH ]  {file_name}: expected {total[:12]}…, got {actual[:12]}…")
            print("         the publisher has probably replaced the document with a newer edition;")
            print("         results from this file will NOT be identical with the published ones.")
        else:
            ok.append(file_name)
            print(f"[got  ]  {file_name}")

    print(f"\nmatching: {len(ok)}/{len(rows)} | to download by hand: {len(manually)}"
          f" | errors: {len(errors)}")
    if manually:
        print("\nFiles with no stable link; find the current edition on the publisher's")
        print("website and save it under the name from the manifest:")
        for file_name, url in manually:
            print(f"  {file_name}  <-  {url}")
    return 0 if not errors and not manually else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
