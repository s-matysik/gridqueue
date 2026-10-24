---
title: Renamed identifiers (1.7.0)
---

# Renamed identifiers in 1.7.0

Up to version 1.6.0 part of the code was written in Polish: function arguments, the keys of the
result objects, local names and comments. From 1.7.0 the whole package is in English. The numbers
it computes are unchanged; every result reported in the article and in the Supplement is
reproduced by both versions, and the CI checks this against `reproducibility/expected/`.

**What did not change.** The names of the schema fields (`id_wniosku`, `moc_wprowadzana`, ...),
the extension columns (`_encja`, `_kierunek`, ...), the controlled vocabularies (`WNIOSEK`, `WEZEL`,
`WARUNKI_WYDANE`, `PV`, ...) and the geolocation codes (`EXACT`, `BRAK_GEOMETRII`, ...) are the data
format of the panel. They follow the wording of the Polish statute, are listed in the Supplement and
are used by the published datasets, so they are kept as they are. Their English meaning is given in
the [schema glossary](schema.md#glossary-of-field-and-code-names).

## Functions and constants

| up to 1.6.0 | from 1.7.0 |
|---|---|
| `PRZEDROSTKI_STACJI` | `STATION_PREFIXES` |
| `normalizuj_nazwe` | `normalize_name` |
| `resolver_from_gazeter_json` | `resolver_from_gazetteer_json` |

The old names still work and emit a `DeprecationWarning`; they will be removed in 2.0.

## Keyword arguments

| function | renamed arguments |
|---|---|
| `Resolver.resolve / MultiResolver.resolve` | `miejscowosc` -> `locality`, `numer` -> `number`, `dopusc_centroid` -> `allow_centroid` |
| `assign_to_nodes` | `mapa` -> `mapping`, `kolumna_encji` -> `entity_column` |
| `compare_editions` | `edycja_a` -> `edition_a`, `edycja_b` -> `edition_b` |
| `kaplan_meier_by_group` | `od` -> `start`, `do` -> `end`, `na_dzien` -> `as_at` |
| `kaplan_meier` | `czas` -> `time`, `zdarzenie` -> `event` |
| `linkage_recall` | `pola_tozsamosci` -> `identity_fields` |
| `node_loading` | `pole_mocy` -> `capacity_field`, `kierunek` -> `direction`, `kolumna_kierunku` -> `direction_column`, `kolumna_grupy` -> `group_column`, `statusy_czynne` -> `active_statuses`, `kolumna_encji` -> `entity_column`, `napiecie` -> `voltage` |
| `plot_processing_time` | `od` -> `start`, `do` -> `end` |
| `processing_time` | `od` -> `start`, `do` -> `end`, `na_dzien` -> `as_at` |
| `resolver_from_gazetteer_json` | `domyslna` -> `default_locality` |
| `station_node_map` | `kolumna_encji` -> `entity_column`, `kolumna_grupy` -> `group_column` |
| `surrogate_key` | `zero_jako_brak` -> `zero_as_missing` |

All adapters: `data_publikacji=` -> `publication_date=`.

## Keys of result objects and columns of result tables

| function | renamed keys |
|---|---|
| `compare_editions` | `edycja_a` -> `edition_a`, `edycja_b` -> `edition_b`, `wierszy_a` -> `rows_a`, `wierszy_b` -> `rows_b`, `wierszy_netto` -> `net_rows`, `kluczy_unikalnych_a` -> `unique_keys_a`, `kluczy_unikalnych_b` -> `unique_keys_b`, `wspolnych` -> `shared`, `nowych` -> `new`, `ubylych` -> `gone`, `zmian_statusu` -> `status_changes`, `udzial_przejsc_w_przod` -> `forward_share`, `nowe_zamkniete` -> `new_closed`, `ubyle_czynne` -> `gone_active`, `przejscia_wstecz` -> `backward_transitions`, `wierszy_w_kolizji_a` -> `rows_in_collision_a`, `wierszy_w_kolizji_b` -> `rows_in_collision_b`, `odrzuconych_jako_niejednoznaczne_a` -> `rejected_as_ambiguous_a`, `odrzuconych_jako_niejednoznaczne_b` -> `rejected_as_ambiguous_b`, `migawka_monotoniczna` -> `monotone_snapshot` |
| `linkage_audit` | `par` -> `pairs`, `potwierdzonych` -> `confirmed`, `niepewnych` -> `uncertain`, `falszywych` -> `false_matches`, `precyzja_dolna` -> `precision_lower`, `precyzja_gorna` -> `precision_upper` |
| `linkage_recall` | `kluczy_a` -> `keys_a`, `kluczy_b` -> `keys_b`, `dopasowanych` -> `matched`, `odzyskanych` -> `recovered`, `czulosc_klucza` -> `key_sensitivity` |
| `run_quality` | `n_wierszy` -> `n_rows`, `n_regul` -> `n_rules`, `reguly` -> `rules`, `naruszen_lacznie` -> `violations_total` |
| `run_quality.rules[]` | `kod` -> `code`, `nazwa` -> `name`, `podstawa` -> `basis`, `naruszenia` -> `violations`, `udzial` -> `share`, `szczegoly` -> `details` |
| `audit_column_shift` | `n_wierszy` -> `n_rows`, `n_przesunietych` -> `n_shifted`, `udzial` -> `share`, `per_pole` -> `per_field` |
| `validate_frame` | `n_wierszy` -> `n_rows`, `kolumny_spoza_schematu` -> `columns_outside_schema`, `brakujace_kolumny_rdzenia` -> `missing_core_columns`, `wypelnienie` -> `completion`, `naruszenia_typu` -> `violation_type`, `wiersze_z_kompletnym_rdzeniem` -> `rows_with_complete_core`, `slownik` -> `dictionary` |
| `kaplan_meier` | `zdarzen` -> `events`, `cenzurowanych` -> `censored`, `udzial_cenzurowanych` -> `censored_share`, `mediana` -> `median`, `mediana_dolna` -> `median_lower`, `mediana_gorna` -> `median_upper` |
| `kaplan_meier_by_group` | `grupa` -> `group`, `zdarzen` -> `events`, `cenzurowanych` -> `censored`, `udzial_cenzurowanych` -> `censored_share`, `mediana` -> `median`, `mediana_dolna` -> `median_lower`, `mediana_gorna` -> `median_upper` |
| `node_loading` | `grupa` -> `group`, `moc_wnioskowana` -> `capacity_requested`, `wnioskow` -> `applications`, `moc_dostepna_zero` -> `available_capacity_zero`, `obciazenie` -> `loading`, `kierunek` -> `direction` |
| `processing_time` | `czas_dni` -> `time_days`, `zdarzenie` -> `event`, `na_dzien` -> `as_at` |
| `schema_table` | `pole` -> `field`, `typ` -> `kind`, `grupa` -> `group`, `encja` -> `entity`, `rdzen` -> `core`, `status_rdzenia` -> `core_status`, `jednostka_kanoniczna` -> `canonical_unit`, `podstawa_prawna` -> `legal_basis`, `opis` -> `description` |
| `declarations[]` | `publikujacy` -> `publisher`, `jurysdykcja` -> `jurisdiction`, `pola_deklarowane` -> `declared_fields`, `rozszerzenia` -> `extensions` |

Adapter reports (`ParseResult.report`) use `publisher`, `jurisdiction` and `publication_date`
instead of `publikujacy`, `jurysdykcja` and `data_publikacji`. The keys of
`reproducibility/expected/*.json` follow the tables above.
