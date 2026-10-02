---
title: Schemat
---

# Schemat 21 pól

Schemat odwzorowuje **strukturę obowiązku prawnego, nie układ dokumentu**. Dwie encje wynikają
z punktów przepisu: WNIOSEK (pkt 1, 3, 4) oraz WĘZEŁ (pkt 2). Rdzeń obowiązkowy liczy pięć pól,
pozostałe szesnaście jest opcjonalne i **deklarowane per publikujący** — schemat oparty na
najmniejszym wspólnym mianowniku odrzuciłby poziom napięcia i pozycję w kolejce, czyli dokładnie
te pola, których potrzebuje analityk sieci.

Jednostki kanoniczne: moc w **kW**, daty w **ISO 8601**, współrzędne w **WGS84**.
Pola, których dany operator dostarcza więcej niż wymaga minimum, trafiają do kolumn
z przedrostkiem `_` i są jawnie deklarowane przez adapter.

| pole | typ | grupa | rdzeń | jednostka | podstawa prawna | opis |
|---|---|---|---|---|---|---|
| id_wniosku | string | tozsamosc | **tak** | — | pkt 1/3/4 | Identyfikator pozycji w rejestrze publikującego; unikalny w obrębie publikacji, nie globalnie. |
| id_wezla | string | tozsamosc | nie | — | pkt 2 | Identyfikator stacji elektroenergetycznej lub jej grupy, w podziale na które ustawa każe podawać dostępną moc. |
| nazwa_wezla | string | tozsamosc | nie | — | pkt 2 | Nazwa własna stacji/punktu zasilania, jeśli publikujący ją ujawnia. |
| lokalizacja_tekst | string | tozsamosc | **tak** | — | pkt 1/3/4 | Lokalizacja miejsca przyłączenia tak, jak ją podał publikujący (adres, miejscowość, kod stacji) -- bez interpretacji. |
| wspolrzedne | geopoint | tozsamosc | nie | WGS84 | pkt 1/2 | Współrzędne geograficzne (lat, lon); wynik rozwiązania lokalizacji albo dana źródłowa. |
| poziom_napiecia | string | tozsamosc | nie | — | pkt 1 (>1 kV) | Poziom napięcia przyłączenia; obowiązek dotyczy sieci powyżej 1 kV, więc pole rozstrzyga o zakresie ujawnienia. |
| klasa_zasobu | string | tozsamosc | **tak** | — | pkt 1/3/4 | Rodzaj instalacji, urządzeń lub sieci, zharmonizowany do słownika kontrolowanego (PV, FW, BESS, ODB, ...). |
| moc_wprowadzana | number | moc | nie | kW | pkt 1/3 | Moc przyłączeniowa wprowadzana do sieci (generacja/eksport). |
| moc_pobierana | number | moc | **tak** | kW | pkt 1/3/4 | Moc przyłączeniowa pobierana z sieci (odbiór/import); dla wniosków odbiorczych jest to główna wielkość wniosku. |
| moc_dostepna | number | moc | nie | kW | pkt 2 | Łączna dostępna moc przyłączeniowa w węźle. |
| moc_zarezerwowana | number | moc | nie | kW | pkt 2 | Moc zajęta wydanymi i ważnymi warunkami / rezerwą. |
| ograniczenie_flaga | boolean | moc | nie | — | pkt 2 | Czy w węźle występuje czynnik ograniczający przyłączenie. |
| pozycja_w_kolejce | number | moc | nie | — | pkt 1 | Pozycja wniosku w kolejce przyłączeniowej, jeśli publikujący ją prowadzi. |
| status_procesu | string | proces | **tak** | — | pkt 1/3/4 | Etap postępowania, zharmonizowany do słownika kontrolowanego. |
| data_wniosku | date | proces | nie | ISO-8601 | pkt 3 | Data złożenia wniosku o określenie warunków przyłączenia. |
| data_warunkow | date | proces | nie | ISO-8601 | pkt 1/3 | Data określenia warunków przyłączenia; początek dwuletniego terminu ważności (art. 7 ust. 8i). |
| data_odmowy | date | proces | nie | ISO-8601 | pkt 4 | Data wydania odmowy określenia warunków przyłączenia. |
| powod_odmowy | string | proces | nie | — | pkt 4 | Uzasadnienie odmowy (przyczyny techniczne / ekonomiczne / inne). |
| data_umowy | date | proces | nie | ISO-8601 | pkt 1 | Data zawarcia umowy o przyłączenie. |
| data_energizacji | date | proces | nie | ISO-8601 | pkt 1 | Data rozpoczęcia dostarczania energii elektrycznej. |
| data_publikacji | date | proces | nie | ISO-8601 | art. 7 ust. 8m | Stan na dzień, dla którego publikujący sporządził ujawnienie; ustawa wymaga aktualizacji co najmniej raz na kwartał. |

```bash
gridqueue schema            # ta sama specyfikacja z wiersza poleceń
```
