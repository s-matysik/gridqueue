# gridqueue — SoftwareX code metadata table

Companion to `gridqueue_SoftwareX_manuscript.md`. Fields whose value depends on the packaging
band carry `⟦PAKIET: …⟧`; fields that require a team decision carry `⟦DECYZJA ZESPOŁU⟧` and are
listed again in the final section.

## Required Metadata — Current code version

| Nr | Item | Value |
|----|------|-------|
| C1 | Current code version | `0.3.1` (declared identically in `pyproject.toml` and in `gridqueue.__version__`; the 0.3.0 distribution carried a stale `__version__` of 0.1.0, corrected in 0.3.1) |
| C2 | Permanent link to code / repository used for this code version | ⟦DECYZJA ZESPOŁU⟧ — repository host and URL not yet chosen |
| C3 | Permanent link to Reproducible Capsule | ⟦DECYZJA ZESPOŁU⟧ — archive DOI (e.g. Zenodo deposit of the source distribution) |
| C4 | Legal Code License | ⟦DECYZJA ZESPOŁU⟧ — code licence not yet chosen. Input data licences are fixed and separate: OpenStreetMap gazetteer under ODbL; operators' statutory publications under their own terms of use, redistributed only where permitted |
| C5 | Code versioning system used | git |
| C6 | Software code languages, tools and services used | Python, `requires-python >= 3.10`; build backend `setuptools.build_meta` (`setuptools>=68`); test runner `pytest` |
| C7 | Compilation requirements, operating environments and dependencies | No compilation (pure Python). Runtime: `pandas>=2.0`, `pdfplumber>=0.11`, `openpyxl>=3.1`, `requests>=2.31`, `pyarrow>=14`. Test extra: `pytest>=8.0`. Build: `setuptools>=68`. The location resolver needs no third-party string-matching library; matching is implemented in `geoloc.py` |
| C8 | If available, link to developer documentation / manual | `README.md` at the root of the distribution (installation, quick example, CLI, schema, extraction method, quality rules) ⟦DECYZJA ZESPOŁU⟧ — no documentation site exists; decide whether one is published before submission |
| C9 | Support email for questions | ⟦DECYZJA ZESPOŁU⟧ |

## Required Metadata — Software

| Nr | Item | Value |
|----|------|-------|
| S1 | Current software version | `0.3.1`, matching C1 |
| S2 | Permanent link to executables of this version | Source distribution only — `gridqueue-0.3.1.tar.gz`, pure Python, no binaries, no compiled extensions. Confirmed against the built archive |
| S3 | Legal Software License | ⟦DECYZJA ZESPOŁU⟧ — same licence as C4 |
| S4 | Computing platforms / Operating Systems | Linux, macOS, Windows (pure Python, no platform-specific code). ⟦PAKIET: the packaging band reported a passing suite on one platform only; the platform/Python-version test matrix was not measured⟧ |
| S5 | Installation requirements & dependencies | As C7. No GPU, no network access required at run time once the source documents and the gazetteer are local |
| S6 | If available, link to user manual | `README.md`. There is no separate example script; the end-to-end path is the CLI sequence `gridqueue parse … --out …parquet --report …json` → `gridqueue validate … --out walidacja.json` → `gridqueue export … --out panel.parquet --only-schema`, given in full in the README |
| S7 | Support email for questions | ⟦DECYZJA ZESPOŁU⟧ — same address as C9 |

## Software characterisation (for the "Software description" section)

**Name.** `gridqueue`

**Problem.** Statutory disclosures of grid-connection applications and available connection
capacity, published under Article 7(8l) of the Polish Energy Law, are legally compelled,
republished at least quarterly, and enforced by the regulator — but published as documents rather
than data. Approximately 180 licensed distribution operators publish in Poland, each in its own
format. The information is public, guaranteed current, and not countable.

**Gap addressed.** Pan-European resources such as Capacitypedia (since May 2026, 27 states
including Poland) and several commercial products index and link to operators' publications.
`gridqueue` parses the statutory documents into rows against a schema derived from the obligation.
In jurisdictions whose disclosures are already tabular — Great Britain, the United States — the
parsing stage is unnecessary and only the schema mapping applies; Poland is the case where it is
not.

**Design decisions on the record.**
1. The 21-field schema models the structure of the legal obligation, not the layout of any
   document — 7 identity fields, 6 capacity fields, 8 process fields, each carrying a reference to
   the point of the provision it derives from, over two entities (APPLICATION, points 1/3/4, and
   NODE, point 2); mandatory core of 5 fields, 16 optional and declared per publisher; canonical
   units kW, ISO-8601 dates, WGS84 coordinates; controlled vocabularies of 12 resource classes and
   11 process statuses. Verified by measured coverage across the six packaged row-level sources
   (`gridqueue_macierz_pokrycia_6publ.csv`): ENERGA-OPERATOR 17/21, PSE 17/21, TAURON 15/21,
   Stoen 13/21, National Grid (GB) 10/21, Boryszew 8/21. **All 21 schema fields are populated
   somewhere in the 19,220-row panel.** `moc_dostepna` is closed from sources by 96 ENERGA node
   rows (0–175,000 kW); PSE discharges the same obligation point as a **count of free connection
   slots rather than a power figure** (69 switchgears), mapped to `ograniczenie_flaga` and an
   extension field, leaving `moc_dostepna` empty rather than fabricating a unit. `wspolrzedne` is
   populated by derivation from the place name, not by disclosure: no publisher reports coordinates.
   Extensions across publishers are complementary, not conflicting.
   **Open decision:** the core requires `moc_pobierana`, which purely generating applications do
   not carry — 5,390 of 19,220 rows (28.044%), the whole of rule R7. The core should require
   either capacity, consumed or injected.
2. Every location resolution carries an explicit confidence level on a six-point scale (`EXACT`,
   `UNIQUE_TOKEN`, `TOKEN_SUBSET`, `REVERSED`, `SKRZYZOWANIE`, `NONE` with a reason), plus a second,
   independent placement-accuracy level (address point, intersection point, point on the street
   axis, locality centroid, no geometry, none). A failure is returned as missing-with-reason, never
   as a guess. Street identification, Stoen Warsaw subset (1,179 positions): `EXACT` 884,
   `UNIQUE_TOKEN` 152, `SKRZYZOWANIE` 70, `REVERSED` 54, `TOKEN_SUBSET` 5, `NONE` 14 — 1,165 of
   1,179 resolved, 98.81%; without the intersection rule 1,095 of 1,179 = 92.88%; without both the
   inverted-order and the intersection rule 1,041 of 1,179 = 88.30%.
   Coordinate coverage after the gazetteer was rebuilt with geometry (13,149 street names in 25
   localities, 292 address points, OpenStreetMap under ODbL): **1,225 of 19,220 panel rows = 6.374%**
   — Stoen 1,217 of 1,236 = 98.463% (Warsaw 1,167 of 1,179 = 98.982%; outside Warsaw 50 of 57 =
   87.719%), Boryszew 8 of 8, and **zero for TAURON, PSE, ENERGA and National Grid**, each with a
   recorded reason. **No publisher discloses coordinates**; the field is derived from the place name,
   which is why the manuscript reports it separately from transcribed fields. Verification against
   independent geocoding: street-name agreement 101 of 102 = 99.02%; median distance between the two
   representative points 259.2 m, driven by street length (Spearman 0.714), not by misidentification.
   Name ambiguity measured and reported rather than hidden: 431 of 6,057 Warsaw names (7.12%) have
   disjoint components more than 2 km apart.

**Measured source inventory.**

| publisher | document | rows in panel | location encoding | capacity unit |
|---|---|---:|---|---|
| TAURON Dystrybucja (PL) | *Informacja o przyłączanych obiektach i wydanych odmowach*, PDF 99 pp. | 10,955 | internal substation code (`SKB3`, `RCB4`); no dictionary published | MW |
| ENERGA-OPERATOR (PL) | application/refusal register, PDF 37 pp., plus two available-capacity documents (demand, generation) | 5,382 (5,286 application + 96 node) | node / locality, often undeclared | MW |
| Stoen Operator (PL) | three statements, as of 30 June 2026 | 1,236 | locality + street address | kW |
| PSE (PL) | spreadsheet and its print-document twin, plus a list of switchgears with no connection capability | 945 (876 application + 69 node) | substation name / object id | MW |
| National Grid (GB) | *Connection Queue*, 45 CSV files | 694 (53 grid supply points, 4 licence areas) | grid node | MW |
| Boryszew Green Energy&Gas (Elana) (PL) | disclosure, PDF 4 pp. | 8 (plus a separate node record) | prose, locality + street | MW |
| UK Power Networks (GB) | capacity map — **public metadata only**, rows return HTTP 403 | 967 records / 37 fields, metadata level | coordinates (in metadata) | MW |

**Not retrieved: PGE Dystrybucja only.** PSE and ENERGA-OPERATOR were retrieved after repairing
the trust chain — the missing intermediate certificate was fetched from the AIA `caIssuers`
pointer in the server certificate and added to the trusted issuers, which is a standard TLS repair
and not a circumvention. The same repair also makes `https://pgedystrybucja.pl/` answer 200 under
full verification, so **certificate verification is not the reason PGE is absent**; the remaining
blocker is server-side client filtering — the site returns a rejection page to the honest
`gridqueue-research/0.1` identifier. Reproducing a browser fingerprint would circumvent an access
control the operator put in place deliberately, so it was not attempted. Electricity North West:
rows behind the same access control as UK Power Networks; metadata only.

**Size.** Read from the built source distribution `gridqueue-0.3.1.tar.gz`: 7 core modules under
`src/gridqueue`, 2,016 lines — `geoloc.py` 672, `schema.py` 406, `layout.py` 353, `quality.py` 339,
`cli.py` 148, `registry.py` 64, `__init__.py` 34 — and 9 adapter modules, 1,777 lines
(`pl_pse.py` 303, `pl_energa.py` 282, `_ptpiree.py` 278, `pl_boryszew.py` 232, `pl_stoen.py` 194,
`uk_nationalgrid.py` 166, `base.py` 156, `pl_tauron.py` 161, `adapters/__init__.py` 5); 3,793 lines
in total under `src`. `_ptpiree.py` is shared by the PSE and ENERGA adapters because both publishers
fill the same agreed industry template, one as a spreadsheet and one as a print document. Tests:
7 files, 965 lines (`test_geoloc_wspolrzedne.py` 280, `test_pse_energa.py` 147,
`test_adapters.py` 144, `test_schema.py` 124, `test_geoloc.py` 95, `test_quality.py` 89,
`test_layout.py` 86). `python -m pytest -q`: **120 passed, 2 skipped (122 collected), 0 failed,
0 errors** — the two skips are the PSE and ENERGA integration tests, which require the source
documents and are skipped when those are absent from the working tree.

**Functionalities.** Document ingest with per-row provenance; layout-based extraction; unit
normalisation (kW→MW); resource-class and process-status vocabulary mapping; composite-date
decomposition; gazetteer-based location resolution with six-level confidence, a second independent
placement-accuracy level, and missing-with-reason; quality-rule evaluation with a violations report (eight rules); Parquet/CSV
export plus a summary panel; adapter registry for adding a publisher without touching the core;
a command-line entry point (`gridqueue schema | adapters | parse | validate | export`).

---

## Open decisions — team, before submission

1. **C2 / repository host and URL.** Needed before the archive DOI can be minted.
2. **C3 / archive DOI.** Depends on (1).
3. **C4 = S3 / code licence.** Note the separation: the code licence is ours to choose; the
   OpenStreetMap gazetteer is ODbL, and the operators' publications carry their own terms, which
   govern whether source documents can be redistributed with the package or only linked.
4. **C8 = S6 / documentation site.** The distribution ships `README.md`; decide whether a
   separate documentation service is published and linked.
5. **C9 = S7 / support email.**
6. **S4 / platform test matrix.** The 122-test suite reports 120 passed and 2 conditionally skipped (integration tests requiring the source documents); the Python-version
   and operating-system matrix behind that run was not measured and must be either measured or
   stated narrowly before submission.
7. **Whether source documents ship with the package.** Decide per publisher against their terms of
   use; the reproducibility section currently promises retrieval locations where redistribution is
   not permitted.
