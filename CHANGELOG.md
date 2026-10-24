# Change history

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
semantic versioning. The version of the data schema is separate from the version of the package
and is reported as `SCHEMA_VERSION`.

## 1.7.0 (2026-10-24)

### Changed
- **The whole package is in English.** Function arguments, the keys of result objects and the
  columns of result tables, local names, comments, docstrings, error messages, the CI workflow,
  the Colab notebook and the documentation file names (`schemat.md` is now `schema.md`, and so on).
  The full list of renamed public names is in [docs/renamed.md](docs/renamed.md).
- The three renamed top-level names (`PRZEDROSTKI_STACJI`, `normalizuj_nazwe`,
  `resolver_from_gazeter_json`) keep working with a `DeprecationWarning` until 2.0. Renamed keyword
  arguments and result keys have no aliases.
- Legal citations follow the style of the article: `Art. 7(8l), item 1/3/4` instead of
  `pkt 1/3/4`. Numbers in the documentation use English formatting (`1,838`, `98.88%`).
- Chart and report text: percentages without a space before `%`, readable labels for every code.

### Not changed
- Schema field names, extension columns, controlled vocabularies and geolocation codes are the
  data format of the panel and stay as they are; their English meaning is in the new glossary of
  `docs/schema.md`.
- Every number reported in the article and in the Supplement is reproduced unchanged; the
  expected-value files under `reproducibility/expected/` carry the same values under English keys.

## 1.6.0 (2026-10-24)

### Added
- **Charts** (`gridqueue.plots`, optional extra `pip install "gridqueue[plot]"`): field coverage,
  quality rules, column-shift audit, stage of the proceeding, requested capacity by class and
  voltage, Kaplan-Meier processing-time curves with censoring and a 95% band, node loading,
  flows / transitions / linkage audit of two editions, location resolution, a four-panel
  overview, and `save_all`, which draws every chart the data supports and lists the skipped ones
  with the reason. A chart is a view of a result, never a second computation of it. Figures are
  created without `pyplot`, so the module runs unchanged in scripts, notebooks and the browser.
- **CLI**: `gridqueue compare` (flows, transitions, linkage precision and sensitivity of two
  editions) and `gridqueue plot` (every chart, PNG/SVG/PDF).
- `parse_sources`: any number of files of one or several publishers into one panel; every file is
  parsed by a fresh adapter instance, so each document keeps the as-at date it states.
  `split_editions` separates two or more editions of one register dropped together.
- `kaplan_meier_by_group`: Kaplan-Meier summary per group (or per combination of columns) with the
  inclusion criterion of the article.
- `geocode_frame`: writes the resolver's result back to the panel (`wspolrzedne` as `"lat,lon"`,
  `_geo_pewnosc`, `_geo_dokladnosc`, `_geo_powod`); source coordinates are kept.
- `node_loading(..., napiecie=...)`: voltage filter of the queue. `napiecie="110"` is the base
  variant of the article (median 6.500 / 4.688, 29 of 36 / 33 of 37 for ENERGA-OPERATOR,
  31 August 2026); the default is the all-voltage upper variant (8.611 / 7.638).
- `gridqueue.examples`: a synthetic panel with node rows, two synthetic editions and a small
  gazetteer, labelled as synthetic, for trying every function without a real disclosure.
- **Browser page, simple view** (the default): drop the documents and get the main charts, a few
  sentences with the key numbers, and one ZIP with charts, data and report. Two editions of one
  register dropped together are recognised by their as-at dates and compared.
- **Browser page, full view**: several files at once, manual choice of the adapter, a later edition
  (flows, transitions, linkage audit), an optional gazetteer, schema validation and the column-shift
  audit, processing times and node loading, all charts (PNG 300 dpi and SVG), and export to CSV,
  XLSX, JSON and one ZIP archive; two synthetic demonstration modes; a table of what runs where.
- **Colab notebook**: installs 1.6.0 with charts; adds schema validation, the column-shift audit,
  key sensitivity (checked against the article), ENERGA-OPERATOR processing times and node loading
  (both checked against the Supplementary Material), the resolver on a synthetic gazetteer, all
  charts and a downloadable results archive.

### Fixed
- **Censoring date of `processing_time`.** The default censored every open application at the
  single latest publication date of the frame, node rows included. ENERGA-OPERATOR publishes its
  applications as at 30 June and its node capacities as at 31 August 2026, so every censored time
  was two months too long (median for consumption at 110 kV 256 d instead of 240 d). Each row is
  now censored at its own publication date, which is also correct for panels of several publishers.
- **Interval of the Kaplan-Meier median**: the lower and upper bounds were swapped
  (`mediana_dolna > mediana > mediana_gorna`).
- `kaplan_meier` raised `KeyError` for a group in which every observation is censored.

## 1.5.2 (2026-10-17)

### Added
- **Running in the browser** (`docs/app/`): a page that loads this same package
  into a WebAssembly interpreter and runs it locally. The document is not
  sent anywhere, because there is no server that could receive it. The result is by
  construction identical with the result of the command line, because it is the same code and the same
  version. The page detects the publisher, extracts the schema rows, runs the eight
  quality rules and allows the table to be downloaded as CSV and the validation report as JSON.

### Fixed
- **Rule R3 returned -1 instead of a count of violations** when the `publikujacy` column
  was present but empty: `groupby` omits a group with an empty value, so a row
  without that annotation had no entry in the dictionary of disclosed fields and a lookup by
  key raised `KeyError`. The error was caught, the rule reported -1,
  and the total number of violations in the whole report became negative. A silent defect, detected
  by running the package on a frame built by hand while the browser
  page was being built. A regression test was added.

### Changed
- The em dash and en dash were removed from the prose of the repository. The only remaining occurrence
  is in the regular expression of the TAURON adapter and is load-bearing: it matches a character
  occurring in the source document.

## 1.5.1 (2026-10-08)

### Corrected
- **The arithmetic identity of the Spanish document described correctly.** Version 1.5.0
  stated that the columns "with permission" and "in progress" reconstruct the occupied capacity in 395 of 767
  rows. That was **a description of an incomplete identity**: both groups are COMPONENTS, not
  alternative breakdowns. Eleven subcolumns, nine substation items plus those
  two, sum to the occupied capacity **in exactly 1,838 of 1,838 rows, in both
  editions checked**. The previous figure was true, but it measured a fragment.

### Added
- `total_occupied_capacity_components` and the field `identity_sum_occupied_capacity` in the report of the
  Spanish adapter. For this publisher **there is no reference set** read
  independently of the parser, so the extraction accuracy cannot be measured against a reference set.
  Arithmetic closure is evidence of **consistency of reading**: for the sum of eleven cells
  to agree with the twelfth, all twelve have to be read correctly. Across two
  editions that gives 3,676 independent checks, all of them closed. This is
  evidence weaker than a reference set and it is described as such.
- `NODE_KEY_FIELDS`, a content key for rows of the NODE entity. The default key is
  built for the APPLICATION entity and on node rows it **falls apart**, because the application fields
  are empty there. Measured on a pair of Spanish issues: with the default key 916 of 1,838
  rows fall into a collision and 660 are rejected as ambiguous; with the node
  key the collisions number **zero**, all 1,838 pairs are linked unambiguously,
  at a precision and recall of **1,000**. The more general conclusion: a content key has to be
  matched to the entity just as the schema core is, and a mismatch **does not report
  an error**, it quietly produces collisions that look like events in the register.

## 1.5.0 (2026-10-08)

### Added
- The `es_edistribucion` adapter, **the first foreign source issued as a document
  meant for printing**, which closes the strongest missing test of transferability. A monthly issue,
  28 pages, 1,838 rows of the NODE entity, all declared fields populated
  at 100 %, including the geographic coordinates of every substation. Capacities in MW of active power.
- The `ie_esbnetworks` adapter, the largest source in the panel, 46,527 rows, the only one
  going below high voltage substations. Coordinates in 46,525 rows.
- Reference panel: **68,054 rows, nine publishers, five jurisdictions**
  (PL, GB, PT, ES, IE). The NODE entity grows from 634 to 48,999 rows, and the coverage of the
  coordinate field from 6.2 % to 72.9 % of the panel.

### Settled
- **Units, for the second and third time.** The Irish source mixes, in one file, apparent power
  on the offtake side with active power on the generating side; the capacity field carries the generating side
  converted from MW, and the offtake side stays in the extensions with the unit in the name. The Spanish
  source reports MW of active power, so it converts without assumptions. Three jurisdictions
  show three different unit practices in one schema field.
- **The semantics of the Spanish columns established by arithmetic, not by the header.** A header
  with merged cells suggested that two columns belonged to the unsettled capacity;
  the sums showed that they belong to the occupied capacity. Taking the header on trust would have given a silent
  transposition of two capacity fields. **Made precise in 1.5.1**, see below.
- **An empty constraint cell in the Irish source** is read as no constraint.
  The publisher does not describe this convention, so it is an interpretation, not the content of the source:
  the raw phrase stays in an extension, and the decision is pinned by a test.

### Changed
- The registry test covers nine adapters in five jurisdictions.
- `reproducibility/manifest.csv` counts 16 entries.

## 1.4.0 (2026-10-07)

### Added
- The `pt_eredes` adapter, the reception capability of the national distribution network of Portugal,
  469 rows of the NODE entity, published quarterly. **The third jurisdiction in the panel
  and the third mode of issue**: not a document meant for printing and not a file on a page, but a dataset
  on an open data portal with a REST interface.
- The first foreign source of the NODE entity. That entity grows in the panel from 165 rows
  to 634, and both jurisdictions satisfy its core **through different members of the same
  alternative**: Poland with available capacity (58% of the node rows), Portugal with the
  constraint flag (100%). The conditional core introduced in version 1.0 for a Polish
  category error turned out to be the condition for absorbing a foreign jurisdiction.

### Settled
- **Units.** The Portuguese publisher reports capacities in MVA, that is in apparent power,
  whereas the canonical unit of the schema is kW of active power. Conversion would require
  an undisclosed power factor, so `moc_dostepna` remains empty, and the source
  values go into the extension fields with the unit recorded explicitly. This is the same
  principle that was applied to the publisher reporting a count of free connection
  slots instead of a capacity.

### Fixed
- **The adapter declaration test carried an out-of-date core contract.** It required
  the core of the APPLICATION entity from every adapter, that is it repeated the category error fixed
  in rule R7 in version 1.0: a publisher discharging only point 2 of the duty
  discloses nodes rather than applications, so it has neither an application identifier nor an application capacity.
  The defect was revealed only by the Portuguese adapter. The test now checks the core **appropriate
  to the adapter's entity**.

### Changed
- `reproducibility/manifest.csv` covers the Portuguese export with a checksum.
- The reference panel counts 19,689 rows from seven publishers in three jurisdictions.


## 1.3.0 (2026-10-07)

### Added
- The `analysis` module with a research layer above the schema: `station_node_map`,
  `assign_to_nodes`, `node_loading`, `processing_time`, `kaplan_meier`.
  It makes it possible to compute **node loading**, the ratio of the active capacity of the queue to
  the disclosed available capacity, that is the criterion which literature reviews
  describe as unmeasurable because of the absence of the data.
- `linkage_recall`, the **recall** of the longitudinal linkage, alongside the precision
  measured so far. On a pair of editions of the transmission operator the recall of the key is
  0.9652: of the 29 missed pairs, 10 are broken by the notation of the location, 15 by a change of capacity,
  4 by a change of voltage.
- `surrogate_key(..., zero_as_missing=True)`, an option equating zero with a missing
  value. It recovers 12 of the 51 pairs lost by the key. **Disabled
  by default**: zero is a disclosed value and a gap is a non-disclosure of it, so
  equating them is a decision of the analyst and is meant to be visible in the code.
- `schema_table()` returns the columns `entity` and `core_status`; the core is
  conditional per entity, which the two-valued `core` column did not convey.
- `reproducibility/fetch_sources.py`, downloads the source documents from the manifest
  and verifies the SHA-256 checksums. It supports a custom bundle of trusted issuers through
  `GRIDQUEUE_CA_BUNDLE`, without disabling verification.

### Fixed
- **Name normalization split words containing the letter `ł`.** The canonical Unicode
  decomposition does not separate the diacritic from it, because it is a separate letter,
  so cleaning the characters turned it into a space and "Białogard" became
  "bia ogard". This also concerns `đ`, `ø`, `ß`, `æ`, `œ`. It is the second occurrence
  of the same trap in the project; the first concerned the harmonization of statuses.
- **Objects planned on a line were arbitrarily assigned to a node.** The entry
  "planowany RS w linii relacji A, B" describes an object lying between nodes;
  matching by name assigned its full capacity to whichever end happened
  to appear in the list of substations. Such applications now have their own status `LINE`
  and are not assigned. On the data of one publisher this concerns 63 applications.

### Changed
- `reproducibility/manifest.csv` covers the July edition of the disclosure of the transmission
  operator, used in the longitudinal analysis.
- `DATA_LICENSE.md` explains why the documents are not redistributed,
  and records that the link of one of the publishers stopped leading to the file,
  which the download script recognizes by the signature of the file and reports separately.


## 1.2.1 (2026-10-04)

### Added
- `notebooks/gridqueue_colab.ipynb`, a full research run in the browser, with no installation:
  downloading two editions directly from the publisher, extraction, quality control, queue flows
  with the linkage precision, and **an assertion of agreement with the figures published in the paper**.
  Documentation: `docs/colab.md`.
- `QualityReport.as_frame()`, a method **promised by the documentation but absent from the code**.
  The defect came to light only when the notebook was run, since it used the public API
  the way the documentation describes it.
- Two continuous integration jobs: a run on `pandas>=3.0` and a check of the notebook
  (syntactic correctness of the cells and the existence in the API of every name imported from it).

### Fixed
- **Incompatibility with pandas 3.** The longitudinal key was built using `.astype(str)`, which in pandas 2
  turned a gap into the string `"nan"`, whereas in pandas 3 it preserves the missing value; concatenating
  the components raised `TypeError` and the whole longitudinal analysis was impossible on that version.
  The key is now built by an explicit conversion, identically in both versions; **all the published
  figures remain unchanged**, which was checked by comparison. The same fix makes the rule
  "a gap is a value" a property of the code rather than a side effect of a type cast.
  An analogous assumption was removed from the adapter of the transmission operator.

### Changed
- The CI matrix tested Python versions but not library versions, which is how the defect got through.
  The `pandas3` job closes that gap.

## 1.2.0 (2026-10-04)

### Added
- `linkage_audit`, an assessment of the precision of the longitudinal linkage on nine fields
  **excluded from the key** (entity name, object name, application date, six fields of the
  capacity breakdown). The key does not enforce the agreement of these fields, so their agreement is
  independent evidence. On the pair of PSE editions the precision is 98.88-99.63%
  across all 804 pairs.
- `EditionDelta` now reports key collisions and the number of rows rejected
  from the linkage as ambiguous.
- `DATA_LICENSE.md`, separating the licence of the code from the status of the input
  and output data, including the duties following from ODbL for the gazetteer.
- `CHANGELOG.md`.
- Status badges in `README.md`.
- `reproducibility/expected/`, the expected results together with assertions in the reproducing
  scripts; a divergence ends the run with a non-zero code.

### Changed
- The documentation of the longitudinal analysis gives the full specification of the linkage algorithm:
  behaviour on a missing value, the uniqueness requirement, the handling of collisions, the absence of tolerance
  on the capacities.
- The longitudinal example prints the linkage precision and the collision counts.

## 1.1.0 (2026-10-03)

### Added
- The `longitudinal` module: `compare_editions`, `surrogate_key`, `EditionDelta`.
  The register does not publish a persistent application identifier, so linkage between
  editions goes by a content key.
- `examples/longitudinal_use_case.py` and `docs/longitudinal.md`.

### Fixed
- **Multiple capacity cells.** When an application concerns several connection points,
  the publisher enters several values into one cell, separated by a line break.
  Whitespace normalization turned the line break into a space, and the capacity conversion
  treats a space as a thousands separator, so "129⏎240" (129 MW + 240 MW) became
  129,240 MW. In the edition with semicolons the same cell did not convert at all.
  The capacity is now split on the line break and on the semicolon, and deliberately not on the space;
  the components are summed and the split is preserved in the extensions.

## 1.0.0 (2026-10-03)

### Changed
- **The schema core is conditional and separate for each entity.** The core completeness
  rule required the `moc_pobierana` field unconditionally and applied the requirements of the
  APPLICATION entity to rows of the NODE entity as well. Both decisions turned a property of the schema
  into an apparent violation of the disclosure. Violations of rule R7 number 771 (4.011%) instead of
  5,390 (28.044%).
- `SCHEMA_VERSION` was introduced, exposed in the validation report and in the public API.

### Added
- `examples/research_use_case.py`, the `reproducibility/` directory, `CITATION.cff`,
  a continuous integration workflow on three systems and four Python versions.
