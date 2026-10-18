---
title: Schema
---

# The 21-field schema

The schema models the **structure of the legal obligation, not the layout of the document**. Two
entities follow from the points of the provision: WNIOSEK (points 1, 3, 4) and WĘZEŁ (point 2). The
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
| id_wniosku | string | tozsamosc | **yes** |, | pkt 1/3/4 | Identifier of the position in the publisher's register; unique within the publication, not globally. |
| id_wezla | string | tozsamosc | no |, | pkt 2 | Identifier of the electricity substation or of its group, by which the statute requires the available capacity to be reported. |
| nazwa_wezla | string | tozsamosc | no |, | pkt 2 | Proper name of the substation / supply point, if the publisher discloses it. |
| lokalizacja_tekst | string | tozsamosc | **yes** |, | pkt 1/3/4 | Location of the connection point exactly as the publisher gave it (address, locality, substation code), with no interpretation. |
| wspolrzedne | geopoint | tozsamosc | no | WGS84 | pkt 1/2 | Geographic coordinates (lat, lon); the result of location resolution or a source datum. |
| poziom_napiecia | string | tozsamosc | no |, | pkt 1 (>1 kV) | Voltage level of the connection; the duty covers networks above 1 kV, so this field settles the scope of the disclosure. |
| klasa_zasobu | string | tozsamosc | **yes** |, | pkt 1/3/4 | Type of installation, equipment or network, harmonized to a controlled vocabulary (PV, FW, BESS, ODB, ...). |
| moc_wprowadzana | number | moc | alternative | kW | pkt 1/3 | Connection capacity injected into the network (generation/export). |
| moc_pobierana | number | moc | alternative | kW | pkt 1/3/4 | Connection capacity consumed from the network (offtake/import); for consumption applications this is the main quantity of the application.  It is not a core field unconditionally: the core requires AT LEAST ONE of the pair (moc_pobierana, moc_wprowadzana), see CORE_ALTERNATIVES. |
| moc_dostepna | number | moc | alternative | kW | pkt 2 | Total available connection capacity at the node. |
| moc_zarezerwowana | number | moc | no | kW | pkt 2 | Capacity taken up by issued and valid conditions / by a reservation. |
| ograniczenie_flaga | boolean | moc | alternative |, | pkt 2 | Whether a factor constraining connection occurs at the node. |
| pozycja_w_kolejce | number | moc | no |, | pkt 1 | Position of the application in the connection queue, if the publisher keeps one. |
| status_procesu | string | proces | **yes** |, | pkt 1/3/4 | Stage of the proceeding, harmonized to a controlled vocabulary. |
| data_wniosku | date | proces | no | ISO-8601 | pkt 3 | Date on which the application for determination of connection conditions was filed. |
| data_warunkow | date | proces | no | ISO-8601 | pkt 1/3 | Date on which the connection conditions were determined; the start of the two-year validity period (Article 7(8i)). |
| data_odmowy | date | proces | no | ISO-8601 | pkt 4 | Date on which the refusal to determine connection conditions was issued. |
| powod_odmowy | string | proces | no |, | pkt 4 | Justification of the refusal (technical / economic / other reasons). |
| data_umowy | date | proces | no | ISO-8601 | pkt 1 | Date on which the connection agreement was concluded. |
| data_energizacji | date | proces | no | ISO-8601 | pkt 1 | Date on which the supply of electricity began. |
| data_publikacji | date | proces | no | ISO-8601 | art. 7 ust. 8m | The date as of which the publisher compiled the disclosure; the statute requires an update at least once per quarter. |

**The core is conditional and separate for each entity.** The four fields marked `yes` are required
unconditionally for the WNIOSEK entity. The fields marked `alternative` enter the core in pairs, of
which at least one has to be populated: `moc_pobierana` or `moc_wprowadzana` for the WNIOSEK entity, and
`moc_dostepna` or `ograniczenie_flaga` for the WĘZEŁ entity. A row of the WĘZEŁ entity additionally
requires `id_wezla` rather than `id_wniosku`. The entity of the row is carried by the annotation
column `_encja`; a row without that annotation is treated as WNIOSEK.

The reason is substantive, not technical: a connection application always declares a capacity, but not
always the same one, a generating one the injected capacity, a consuming one the consumed capacity, a
bidirectional one both, and point 2 of the duty is sometimes discharged with available capacity and
sometimes with a count of free connection slots. Requiring one specific field would turn a property of
the schema into an apparent violation of the disclosure.


```bash
gridqueue schema            # the same specification from the command line
```
