# Legal status of the code and of the data

The file `LICENSE.txt` covers **the code of this package only**. The data the code works on,
and the data it produces, have a separate status, and we describe it here, because confusing those
layers is a real risk on reuse.

## 1. The code of the package

Apache-2.0, in accordance with `LICENSE.txt`. It covers `src/`, `tests/`, `examples/`,
`reproducibility/` and `docs/`.

## 2. The publishers' source documents

The documents issued by the operators under Article 7(8l) of the Energy Law
are **official publications made under a statutory duty**. The package
**does not redistribute** them. For each document, `reproducibility/manifest.csv` gives the address,
the date of download, the size and the SHA-256 checksum, which makes it possible to **verify** that
the downloaded file is the same one on which the results were computed.

This is verification, not a guarantee of reproduction. The duty requires the publication to be
replaced at least once per quarter, so the file at a given address **is sometimes superseded by a
newer one**. Exact computational reproduction is therefore conditional on the continued availability
of archival source files at the publishers, or on their being archived by the user.

## 3. The geometric gazetteer, OpenStreetMap

The gazetteer used by the location resolver comes from OpenStreetMap and is subject to the
**Open Database License 1.0**. For the user this means three duties that Apache-2.0
does not cover:

- **attribution**, naming OpenStreetMap as the source in every publication of results
  containing coordinates;
- **share-alike**, making a derivative database available under the same licence if it is publicly
  distributed;
- **no technical restrictions**, a derivative database must not be distributed in a way that
  prevents the recipient from using it on ODbL terms.

A distinction that matters in practice: a *produced work*, for example a map or a table of results,
requires attribution but does not trigger share-alike; a *derivative database*, for example a panel
with coordinates attached, made available onwards, does trigger share-alike.

## 4. The resulting panel

The panel produced by the package is a work derived from both of the layers above.
To the extent that it contains **values derived from the gazetteer** (the `coordinates` field
and the resolver's diagnostic columns), it is subject to ODbL. To the extent that it contains
only content transcribed from official documents, it is subject to the status of those documents.
The `_geo_confidence` column makes it possible to separate those two layers: rows with no resolved
location contain no content originating from OpenStreetMap.

## 5. Personal data

The disclosures concern **entities applying for a connection**, and the entity name field
contains, in the vast majority, the business names of commercial-law companies. The statute does not,
however, exclude natural persons conducting a business activity, so we do not claim that personal data
do not occur in the corpus.

The package **performs no re-identification** and does not enrich the records with data about persons
from any other source. The location resolver works on the name of the locality and street
given in the document, never on the name of the entity. Responsibility for lawful
further use of the output, including for any data protection impact assessment,
rests with the user.


## Why the source documents are not included in the repository

The repository contains a **manifest** of the documents (address, date of download, size,
SHA-256 checksum) and the script `reproducibility/fetch_sources.py`, which downloads them
and verifies them. It does not contain the documents themselves. There are two reasons and both are
practical rather than precautionary.

**First, we do not settle the legal status of redistribution.** Polish copyright
law excludes official materials from protection, but the disclosures in question
are compiled and published by companies conducting a business activity, discharging
a statutory duty, and whether they fall within that category is not
settled. Independently of copyright, *sui generis* protection may apply
to databases. We are not in a position to settle this
and we do not pretend to be; a team intending to include the documents in
a publication should obtain a legal opinion.

**Second, the documents are replaced.** The duty requires an update at least
quarterly, so a copy deposited in the repository would, after a few months,
present a state that no longer exists, and would be the more misleading the
more current it looked.

The consequence has to be stated openly, because it is inconvenient: **byte-for-byte
reproduction ceases to be possible once a publisher replaces or moves a document.**
While the package was being prepared, the link to the disclosure of one of the operators
stopped leading to the file and began returning a page of the service; the download script
recognizes that case and reports it separately instead of saving the page as
a document. That is why the checksums are in the manifest: a mismatch is a signal that
the figures will not be identical with the published ones, not a fault to be ignored.

To a team preparing a publication we recommend a **deposit of the documents in an archive
with a permanent identifier**, provided a legal opinion permits it. That is the only
way for the link in the paper to lead to what was actually analysed.
