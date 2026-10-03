---
title: Reguły jakości
---

# Reguły kontroli jakości

Osiem reguł. Każda zwraca **liczbę naruszeń, nie wyjątek** — bo naruszenie jest zwykle
właściwością ujawnienia, a nie błędem narzędzia. Reguły są wyprowadzone z przepisu: dwuletnia
ważność warunków przyłączenia wynika z art. 7 ust. 8i, a nie z preferencji projektanta.

Zmierzone na panelu 19 220 wierszy, schemat w wersji 1.0:

| reguła | co sprawdza | TAURON | ENERGA | Stoen | PSE | National Grid | Boryszew | panel | udział |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 | monotoniczność dat postępowania | 45 | 163 | 0 | 3 | 0 | 0 | 211 | 1,098 % |
| R2 | dwuletnia ważność warunków przyłączenia | 583 | 174 | 7 | 12 | 0 | 0 | 776 | 4,038 % |
| R3 | dopuszczalność stanu procesu wobec dat | 1 | 138 | 0 | 0 | 0 | 1 | 140 | 0,728 % |
| R4 | spójność jednostek mocy | 0 | 13 | 0 | 0 | 0 | 0 | 13 | 0,068 % |
| R5 | zakresy wartości | 0 | 13 | 0 | 0 | 0 | 0 | 13 | 0,068 % |
| R6 | duplikaty identyfikatorów | 1 029 | 59 | 0 | 0 | 0 | 0 | 1 088 | 5,661 % |
| R7 | kompletność rdzenia schematu | 0 | 766 | 0 | 5 | 0 | 0 | 771 | 4,011 % |
| R8 | słownik kontrolowany | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0,000 % |

Kolumna „panel" to liczba wierszy naruszających regułę w całym panelu; domyka się do sumy kolumn
publikujących, co jest sprawdzane asercją przy generowaniu tej strony. W wersji 0.3.x strona
podawała dla R7 liczby zawyżone — przyczynę opisuje akapit o R7 niżej.

## Jak czytać wyniki

**R2** jest sumą dwóch wzajemnie rozłącznych podkontroli i tak musi być raportowana: 361 dat
wygaśnięcia przypada później niż dwa lata od wydania warunków, **oraz** 415 umów zawarto po
upływie tych dwóch lat. Pierwszy składnik ma sygnaturę ustalonej reguły administracyjnej
publikującego — mediana przekroczenia 21 dni — drugi pozostaje otwartym ustaleniem.

**R4 i R5** wskazują ten sam zbiór 13 wierszy z **ujemną mocą wprowadzaną**, najmniejsza wartość
−700 kW. Jeden z nich trafił do próby wzorcowej i odczyt wzrokowy wartość ujemną potwierdza, więc
jest to właściwość ujawnienia, nie błąd wydobycia. Reguła zadziałała w swojej właściwej roli:
jako detektor jakości źródła.

**R7 mierzy od wersji 1.0 rdzeń właściwy dla encji wiersza.** W wersji 0.3.x rdzeń wymagał
bezwarunkowo pola `moc_pobierana` i stosował wymagania encji WNIOSEK także do wierszy encji
WĘZEŁ. Obie decyzje zamieniały **właściwość schematu w pozorne naruszenie ujawnienia**: wniosek
czysto wytwórczy deklaruje moc wprowadzaną, nie pobieraną, a wiersz węzłowy nie ma ani
identyfikatora wniosku, ani mocy wniosku, bo realizuje inny punkt przepisu. Rdzeń wymaga teraz:

* dla encji **WNIOSEK** — `id_wniosku`, `lokalizacja_tekst`, `klasa_zasobu`, `status_procesu`
  oraz **co najmniej jednego** z pary (`moc_pobierana`, `moc_wprowadzana`);
* dla encji **WĘZEŁ** — `id_wezla` oraz **co najmniej jednego** z pary
  (`moc_dostepna`, `ograniczenie_flaga`), bo pkt 2 obowiązku bywa realizowany mocą dostępną albo
  liczbą wolnych miejsc przyłączeniowych.

Po tej zmianie R7 spada z 5 390 (28,044 %) do **771 (4,011 %)**, a wierszy
z kompletnym rdzeniem jest **18 449 z 19 220**. Pozostałe naruszenia są brakami
ujawnienia, nie artefaktem schematu: 570 wniosków bez żadnej mocy,
202 wniosków bez opisu lokalizacji oraz 2 węzły bez mocy dostępnej i bez
flagi ograniczenia. Encji WNIOSEK jest 19 055, encji WĘZEŁ 165.

**R8** korzysta ze słownika kontrolowanego pochodzącego z zakładki list rozwijanych wzorca
sprawozdawczego, a więc z autorytatywnego źródła sektorowego, nie z naszej konwencji.

```python
from gridqueue import run_quality
q = run_quality(df)
q.as_dict()["naruszen_lacznie"]
q.as_frame()          # jeden wiersz na regułę
```
