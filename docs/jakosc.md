---
title: Reguły jakości
---

# Reguły kontroli jakości

Osiem reguł. Każda zwraca **liczbę naruszeń, nie wyjątek** — bo naruszenie jest zwykle
właściwością ujawnienia, a nie błędem narzędzia. Reguły są wyprowadzone z przepisu: dwuletnia
ważność warunków przyłączenia wynika z art. 7 ust. 8i, a nie z preferencji projektanta.

Zmierzone na panelu 19 220 wierszy:

| reguła | co sprawdza | Boryszew | ENERGA-OPERATOR | National | PANEL | PSE | Stoen | TAURON | panel |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| R1 | monotoniczność dat postępowania | 0 | 163 | 0 | 211 | 3 | 0 | 45 | 422 |
| R2 | dwuletnia ważność warunków przyłączenia | 0 | 174 | 0 | 776 | 12 | 7 | 583 | 1552 |
| R3 | dopuszczalność stanu procesu wobec dat | 1 | 138 | 0 | 140 | 0 | 0 | 1 | 280 |
| R4 | spójność jednostek mocy | 0 | 13 | 0 | 13 | 0 | 0 | 0 | 26 |
| R5 | zakresy wartości | 0 | 13 | 0 | 13 | 0 | 0 | 0 | 26 |
| R6 | duplikaty identyfikatorów | 0 | 59 | 0 | 1088 | 0 | 0 | 1029 | 2176 |
| R7 | kompletność rdzenia schematu | 0 | 2433 | 0 | 5390 | 113 | 0 | 2844 | 10780 |
| R8 | słownik kontrolowany | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Jak czytać wyniki

**R2** jest sumą dwóch wzajemnie rozłącznych podkontroli i tak musi być raportowana: 361 dat
wygaśnięcia przypada później niż dwa lata od wydania warunków, **oraz** 415 umów zawarto po
upływie tych dwóch lat. Pierwszy składnik ma sygnaturę ustalonej reguły administracyjnej
publikującego — mediana przekroczenia 21 dni — drugi pozostaje otwartym ustaleniem.

**R4 i R5** wskazują ten sam zbiór 13 wierszy z **ujemną mocą wprowadzaną**, najmniejsza wartość
−700 kW. Jeden z nich trafił do próby wzorcowej i odczyt wzrokowy wartość ujemną potwierdza, więc
jest to właściwość ujawnienia, nie błąd wydobycia. Reguła zadziałała tu w swojej właściwej roli:
jako detektor jakości źródła.

**R7** jest w całości spowodowana pustym polem mocy pobieranej we wnioskach czysto generacyjnych.
Jest to własność rdzenia schematu w obecnej specyfikacji, a nie ujawnień — rdzeń powinien wymagać
*którejkolwiek* mocy, pobieranej albo wprowadzanej. Jest to odnotowana decyzja do podjęcia.

**R8** korzysta ze słownika kontrolowanego pochodzącego z zakładki list rozwijanych wzorca
sprawozdawczego, a więc z autorytatywnego źródła sektorowego, nie z naszej konwencji.

```python
from gridqueue import run_quality
q = run_quality(df)
q.as_dict()["naruszen_lacznie"]
q.as_frame()          # jeden wiersz na regułę
```
