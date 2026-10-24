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
| id_wniosku | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Identifier of the entry in the publisher's register; unique within the publication, not globally. |
| id_wezla | string | identity | no |  | Art. 7(8l), item 2 | Identifier of the power station or its group, broken down by which the statute requires the available capacity to be reported. |
| nazwa_wezla | string | identity | no |  | Art. 7(8l), item 2 | Proper name of the station/supply point, if the publisher discloses it. |
| lokalizacja_tekst | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Location of the connection point exactly as given by the publisher (address, locality, station code), without interpretation. |
| wspolrzedne | geopoint | identity | no | WGS84 | Art. 7(8l), item 1/2 | Geographic coordinates (lat, lon); result of location resolution or source data. |
| poziom_napiecia | string | identity | no |  | Art. 7(8l), item 1 (>1 kV) | Voltage level of the connection; the duty applies to networks above 1 kV, so the field determines the scope of the disclosure. |
| klasa_zasobu | string | identity | **yes** |  | Art. 7(8l), item 1/3/4 | Type of installation, equipment or network, harmonized to the controlled vocabulary (PV, FW, BESS, ODB, ...). |
| moc_wprowadzana | number | capacity | alternative | kW | Art. 7(8l), item 1/3 | Connection capacity fed into the network (generation/export). |
| moc_pobierana | number | capacity | alternative | kW | Art. 7(8l), item 1/3/4 | Connection capacity drawn from the network (consumption/import); for consumption applications this is the main quantity of the application. It is not unconditionally a core field: the core requires AT LEAST ONE of the pair (moc_pobierana, moc_wprowadzana), see CORE_ALTERNATIVES. |
| moc_dostepna | number | capacity | alternative | kW | Art. 7(8l), item 2 | Total available connection capacity at the node. |
| moc_zarezerwowana | number | capacity | no | kW | Art. 7(8l), item 2 | Capacity taken up by issued and valid connection conditions / reservation. |
| ograniczenie_flaga | boolean | capacity | alternative |  | Art. 7(8l), item 2 | Whether there is a factor at the node limiting the connection. |
| pozycja_w_kolejce | number | capacity | no |  | Art. 7(8l), item 1 | Position of the application in the connection queue, if the publisher maintains one. |
| status_procesu | string | process | **yes** |  | Art. 7(8l), item 1/3/4 | Stage of the proceedings, harmonized to the controlled vocabulary. |
| data_wniosku | date | process | no | ISO-8601 | Art. 7(8l), item 3 | Date the application for determination of connection conditions was filed. |
| data_warunkow | date | process | no | ISO-8601 | Art. 7(8l), item 1/3 | Date the connection conditions were determined; the start of the two-year validity period (Article 7(8i)). |
| data_odmowy | date | process | no | ISO-8601 | Art. 7(8l), item 4 | Date the refusal to determine connection conditions was issued. |
| powod_odmowy | string | process | no |  | Art. 7(8l), item 4 | Justification for the refusal (technical / economic / other reasons). |
| data_umowy | date | process | no | ISO-8601 | Art. 7(8l), item 1 | Date the connection agreement was concluded. |
| data_energizacji | date | process | no | ISO-8601 | Art. 7(8l), item 1 | Date electricity supply began. |
| data_publikacji | date | process | no | ISO-8601 | Art. 7(8m) | Status as of the date for which the publisher prepared the disclosure; the statute requires updates at least once per quarter. |

**The core is conditional and separate for each entity.** The four fields marked `yes` are required
unconditionally for the APPLICATION entity. The fields marked `alternative` enter the core in pairs, of
which at least one has to be populated: `moc_pobierana` or `moc_wprowadzana` for the APPLICATION entity, and
`moc_dostepna` or `ograniczenie_flaga` for the NODE entity. A row of the NODE entity additionally
requires `id_wezla` rather than `id_wniosku`. The entity of the row is carried by the annotation
column `_encja`; a row without that annotation is treated as APPLICATION.

The reason is substantive, not technical: a connection application always declares a capacity, but not
always the same one, a generating one the injected capacity, a consuming one the consumed capacity, a
bidirectional one both, and point 2 of the duty is sometimes discharged with available capacity and
sometimes with a count of free connection slots. Requiring one specific field would turn a property of
the schema into an apparent violation of the disclosure.


```bash
gridqueue schema            # the same specification from the command line
```

## Glossary of field and code names

Field names and codes are kept in the Polish of the statute (Art. 7(8l) of the Energy Law) because
they are the data format of the panel, listed in the Supplement and used by the published datasets.
Everything else in the package, including function arguments and result keys, is in English
(see [renamed identifiers](renamed.md)).

| field | meaning |
|---|---|
| `id_wniosku` | application ID |
| `id_wezla` | node ID |
| `nazwa_wezla` | node name |
| `lokalizacja_tekst` | location as published |
| `wspolrzedne` | coordinates |
| `poziom_napiecia` | voltage level |
| `klasa_zasobu` | resource class |
| `moc_wprowadzana` | injected (generation) capacity |
| `moc_pobierana` | withdrawn (demand) capacity |
| `moc_dostepna` | available capacity |
| `moc_zarezerwowana` | reserved capacity |
| `ograniczenie_flaga` | constraint flag |
| `pozycja_w_kolejce` | queue position |
| `status_procesu` | process status |
| `data_wniosku` | application date |
| `data_warunkow` | date of connection conditions |
| `data_odmowy` | refusal date |
| `powod_odmowy` | refusal reason |
| `data_umowy` | agreement date |
| `data_energizacji` | energisation date |
| `data_publikacji` | publication (as-at) date |
| `publikujacy` | publisher |
| `jurysdykcja` | jurisdiction |
| `dokument_zrodlowy` | source document |

| column / code | meaning |
|---|---|
| `_encja` | entity of the row |
| `WNIOSEK` | application |
| `WEZEL` | node |
| `_kierunek` | direction of available capacity |
| `wytworcza` | generation |
| `odbiorcza` | demand |

| `status_procesu` | meaning |
|---|---|
| `WNIOSEK_ZLOZONY` | filed |
| `WNIOSEK_NIEKOMPLETNY` | incomplete |
| `W_TRAKCIE_ANALIZY` | under review |
| `WARUNKI_WYDANE` | conditions issued |
| `WARUNKI_WYGASLE` | conditions expired |
| `ODMOWA` | refused |
| `UMOWA_OBOWIAZUJACA` | agreement in force |
| `UMOWA_ROZWIAZANA` | agreement terminated |
| `PRZYLACZONY` | connected |
| `WNIOSEK_WYCOFANY` | withdrawn |
| `NIEOKRESLONY` | unspecified |

| `klasa_zasobu` | meaning |
|---|---|
| `PV` | photovoltaics |
| `FW` | wind |
| `EW` | hydro |
| `BIOGAZ` | biogas |
| `GAZ` | gas |
| `WEGIEL` | coal |
| `BESS` | energy storage |
| `ODB` | consumption |
| `MIX` | mixed |
| `SIEC` | network |
| `INNE` | other |
| `NIEOKRESLONA` | unspecified |

| `_geo_pewnosc` / `_geo_dokladnosc` | meaning |
|---|---|
| `EXACT` | exact name match |
| `UNIQUE_TOKEN` | unique distinguishing token |
| `TOKEN_SUBSET` | token subset |
| `REVERSED` | inverted word order ("WINCENTEGO ŚW.") |
| `SKRZYZOWANIE` | intersection of two streets |
| `ZRODLO` | coordinates given by the publisher |
| `NONE` | not resolved |
| `PUNKT_ADRESOWY` | address point |
| `PUNKT_SKRZYZOWANIA` | intersection point |
| `PUNKT_NA_OSI_ULICY` | point on the street axis |
| `CENTROID_MIEJSCOWOSCI` | locality centroid |
| `BRAK_GEOMETRII` | name resolved, no geometry |
| `BRAK` | no point |
