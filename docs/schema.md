---
title: Schema
---

# The 21-field schema

The schema models the **structure of the legal obligation, not the layout of the document**. Two
entities follow from the points of the provision: APPLICATION (points 1, 3, 4) and NODE (point 2). The
mandatory core counts five fields, the remaining sixteen are optional and **declared per publisher**;
a schema based on the smallest common denominator would discard the voltage level and the queue
position, that is precisely the fields a network analyst needs.

The schema has version **1.0**, recorded in the validation report and in the export metadata.
Canonical units: capacity in **kW** without exception, sources reporting megawatts are converted at
extraction and the source unit is recorded in an extension. Dates in **ISO 8601**,
coordinates in **WGS84**.
Fields that a given operator supplies beyond the required minimum go into columns
with the `_` prefix and are declared explicitly by the adapter.

| field | type | group | core | unit | legal basis | description |
|---|---|---|---|---|---|---|
| application_id | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Identifier of the entry in the publisher's register; unique within the publication, not globally. |
| node_id | string | identity | no |  | Art. 7(8l), item 2 | Identifier of the electricity substation or its group, by which the statute requires the available capacity to be reported. |
| node_name | string | identity | no |  | Art. 7(8l), item 2 | Proper name of the station/supply point, if the publisher discloses it. |
| location_text | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Location of the connection point exactly as given by the publisher (address, locality, station code), without interpretation. |
| coordinates | geopoint | identity | no | WGS84 | Art. 7(8l), item 1/2 | Geographic coordinates (lat, lon); result of location resolution or source data. |
| voltage_level | string | identity | no |  | Art. 7(8l), item 1 (>1 kV) | Voltage level of the connection; the duty applies to networks above 1 kV, so the field determines the scope of the disclosure. |
| resource_class | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Type of installation, equipment or network, harmonized to the controlled vocabulary (PV, FW, BESS, ODB, ...). |
| capacity_injected | number | capacity | alternative | kW | Art. 7(8l), item 1/3 | Connection capacity fed into the network (generation/export). |
| capacity_withdrawn | number | capacity | alternative | kW | Art. 7(8l), item 1/3/4 | Connection capacity drawn from the network (consumption/import); for consumption applications this is the main quantity of the application. It is not unconditionally a core field: the core requires AT LEAST ONE of the pair (capacity_withdrawn, capacity_injected), see CORE_ALTERNATIVES. |
| capacity_available | number | capacity | alternative | kW | Art. 7(8l), item 2 | Total available connection capacity at the node. |
| capacity_reserved | number | capacity | no | kW | Art. 7(8l), item 2 | Capacity taken up by issued and valid connection conditions / reservation. |
| constraint_flag | boolean | capacity | alternative |  | Art. 7(8l), item 2 | Whether there is a factor at the node limiting the connection. |
| queue_position | number | capacity | no |  | Art. 7(8l), item 1 | Position of the application in the connection queue, if the publisher maintains one. |
| process_status | string | process | **yes** |  | Art. 7(8l), item 1/3/4 | Stage of the proceedings, harmonized to the controlled vocabulary. |
| date_application | date | process | no | ISO-8601 | Art. 7(8l), item 3 | Date the application for determination of connection conditions was filed. |
| date_conditions | date | process | no | ISO-8601 | Art. 7(8l), item 1/3 | Date the connection conditions were determined; the start of the two-year validity period (Article 7(8i)). |
| date_refusal | date | process | no | ISO-8601 | Art. 7(8l), item 4 | Date the refusal to determine connection conditions was issued. |
| refusal_reason | string | process | no |  | Art. 7(8l), item 4 | Justification for the refusal (technical / economic / other reasons). |
| date_agreement | date | process | no | ISO-8601 | Art. 7(8l), item 1 | Date the connection agreement was concluded. |
| date_energisation | date | process | no | ISO-8601 | Art. 7(8l), item 1 | Date electricity supply began. |
| date_published | date | process | no | ISO-8601 | Art. 7(8m) | Status as of the date for which the publisher prepared the disclosure; the statute requires updates at least once per quarter. |

**The core is conditional and separate for each entity.** The four fields marked `yes` are required
unconditionally for the APPLICATION entity. The fields marked `alternative` enter the core in pairs, of
which at least one has to be populated: `capacity_withdrawn` or `capacity_injected` for the APPLICATION entity, and
`capacity_available` or `constraint_flag` for the NODE entity. A row of the NODE entity additionally
requires `node_id` rather than `application_id`. The entity of the row is carried by the annotation
column `_entity`; a row without that annotation is treated as APPLICATION.

The reason is substantive, not technical: a connection application always declares a capacity, but not
always the same one, a generating one the injected capacity, a consuming one the consumed capacity, a
bidirectional one both, and point 2 of the duty is sometimes discharged with available capacity and
sometimes with a count of free connection slots. Requiring one specific field would turn a property of
the schema into an apparent violation of the disclosure.


```bash
gridqueue schema            # the same specification from the command line
```

## Names in the wording of the statute

The Supplementary Material of the article and the panels exported by the first drafts of the
package name the fields and codes in the Polish wording of Art. 7(8l) of the Energy Law. The tables
below give the correspondence. `gridqueue.from_legacy_names(df)` converts such a table to the
English schema; `gridqueue.LEGACY_COLUMNS`, `LEGACY_CODES` and `LEGACY_REASONS` hold the same
mapping in code.

| field | statute wording |
|---|---|
| `application_id` | `id_wniosku` |
| `node_id` | `id_wezla` |
| `node_name` | `nazwa_wezla` |
| `location_text` | `lokalizacja_tekst` |
| `coordinates` | `wspolrzedne` |
| `voltage_level` | `poziom_napiecia` |
| `resource_class` | `klasa_zasobu` |
| `capacity_injected` | `moc_wprowadzana` |
| `capacity_withdrawn` | `moc_pobierana` |
| `capacity_available` | `moc_dostepna` |
| `capacity_reserved` | `moc_zarezerwowana` |
| `constraint_flag` | `ograniczenie_flaga` |
| `queue_position` | `pozycja_w_kolejce` |
| `process_status` | `status_procesu` |
| `date_application` | `data_wniosku` |
| `date_conditions` | `data_warunkow` |
| `date_refusal` | `data_odmowy` |
| `refusal_reason` | `powod_odmowy` |
| `date_agreement` | `data_umowy` |
| `date_energisation` | `data_energizacji` |
| `date_published` | `data_publikacji` |
| `publisher` | `publikujacy` |
| `jurisdiction` | `jurysdykcja` |
| `source_document` | `dokument_zrodlowy` |

| `_entity` | statute wording | meaning |
|---|---|---|
| `APPLICATION` | `WNIOSEK` |  |
| `NODE` | `WEZEL` |  |

| `_direction` | statute wording | meaning |
|---|---|---|
| `generation` | `wytworcza` |  |
| `demand` | `odbiorcza` |  |

| `process_status` | statute wording | meaning |
|---|---|---|
| `APPLICATION_FILED` | `WNIOSEK_ZLOZONY` | filed |
| `APPLICATION_INCOMPLETE` | `WNIOSEK_NIEKOMPLETNY` | incomplete |
| `UNDER_REVIEW` | `W_TRAKCIE_ANALIZY` | under review |
| `CONDITIONS_ISSUED` | `WARUNKI_WYDANE` | conditions issued |
| `CONDITIONS_EXPIRED` | `WARUNKI_WYGASLE` | conditions expired |
| `REFUSED` | `ODMOWA` | refused |
| `AGREEMENT_IN_FORCE` | `UMOWA_OBOWIAZUJACA` | agreement in force |
| `AGREEMENT_TERMINATED` | `UMOWA_ROZWIAZANA` | agreement terminated |
| `CONNECTED` | `PRZYLACZONY` | connected |
| `APPLICATION_WITHDRAWN` | `WNIOSEK_WYCOFANY` | withdrawn |
| `UNSPECIFIED` | `NIEOKRESLONY` | unspecified |

| `resource_class` | statute wording | meaning |
|---|---|---|
| `WIND` | `FW` | wind |
| `HYDRO` | `EW` | hydro |
| `BIOGAS` | `BIOGAZ` | biogas |
| `GAS` | `GAZ` | gas |
| `COAL` | `WEGIEL` | coal |
| `LOAD` | `ODB` | consumption |
| `GRID` | `SIEC` | network |
| `OTHER` | `INNE` | other |
| `UNSPECIFIED` | `NIEOKRESLONA` | unspecified |

| `_geo_confidence` | statute wording | meaning |
|---|---|---|
| `INTERSECTION` | `SKRZYZOWANIE` |  |
| `SOURCE` | `ZRODLO` |  |

| `_geo_accuracy` | statute wording | meaning |
|---|---|---|
| `ADDRESS_POINT` | `PUNKT_ADRESOWY` |  |
| `INTERSECTION_POINT` | `PUNKT_SKRZYZOWANIA` |  |
| `STREET_AXIS_POINT` | `PUNKT_NA_OSI_ULICY` |  |
| `LOCALITY_CENTROID` | `CENTROID_MIEJSCOWOSCI` |  |
| `NO_GEOMETRY` | `BRAK_GEOMETRII` |  |
| `NO_POINT` | `BRAK` |  |

Extension columns (prefix `_`) follow the same rule; their statute wording is listed in
`gridqueue.LEGACY_COLUMNS`. Voltage-level classes (`SN`, `nN`, `WN`) are kept as the publishers
write them, because they are values of the documents, not names chosen by the package.
