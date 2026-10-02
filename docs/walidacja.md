---
title: Walidacja
---

# Zmierzona walidacja

Dokładność wydobycia jest **zmierzona, nie zadeklarowana**. Zbiór odniesienia powstał przez
wizualne odczytanie renderowanych wycinków stron (230–600 dpi, z naniesionymi granicami kolumn),
**niezależnie od wyjścia parsera**.

## Dokładność per publikujący

| publikujący | wierszy wzorca | porównań | wierszy w pełni poprawnych |
|---|---:|---:|---|
| TAURON Dystrybucja | 100 | 1 200 | **98 z 100**, 100 z 100 po wyłączeniu pary homoglifów |
| Stoen Operator | 100 | 1 200 | **99 z 100**, 100 z 100 po adjudykacji |
| PSE | 60 | 780 | **60 z 60** |
| ENERGA-OPERATOR | 60 | 780 | **60 z 60** |
| Boryszew Green Energy&Gas | 8 | 64 | **8 z 8** |

Dwie niezgodności u TAURONA to ta sama para homoglifów: wielkie `I` wobec małego `l` w kroju
bezszeryfowym. Rozstrzygnięcie wzrokowe jest tu niemożliwe **z zasady**, a nie tylko utrudnione —
oba znaki są renderowane glifami nierozróżnialnymi przy każdym powiększeniu. Jedynym dostępnym
dowodem jest warstwa tekstowa pliku. **Podajemy obie wartości i żadna nie zastępuje drugiej.**

Jedyna niezgodność u Stoena rozstrzygnęła się przy 600 dpi **na korzyść parsera** — był to błąd
anotatora. Jedna korekta wzorca ENERGI również wypadła na korzyść parsera.

## Zgodność międzyanotatorska

Podpróbkę 35 wierszy odczytał **drugi anotator pracujący w zaślepieniu**: bez dostępu do wzorca
pierwszego anotatora, do tabeli dokładności, do raportu walidacji i do wyjścia parsera.

| miara | wartość |
|---|---:|
| porównań pole-wiersz | 400 |
| zgodność surowa | **0,9725** |
| zgodność oczekiwana losowo | 0,1120 |
| **kappa Cohena** | **0,9690** |
| zgodność parsera z wzorcem uzgodnionym | **400 z 400** |

Wszystkie 11 niezgodności to **konwencja zapisu, nie różnica odczytu**: siedem dotyczy komórki
zawierającej tekst niebędący datą w polu daty, cztery — łącznika na końcu wiersza w nazwisku.
**Niezgodności percepcyjnych nie było ani jednej.** Wzorce PSE i ENERGI pozostają
jednoanotatorskie i dla nich zgodności nie mierzono.

Zastrzeżenie: podpróbka nie zawiera wierszy z parą homoglifów, więc wynik 400 z 400 dotyczy innego
zbioru wierszy i **nie unieważnia** pomiaru 98 z 100.

## Geolokalizacja

Pole współrzędnych nie jest ujawniane przez żadnego publikującego; powstaje przez wyprowadzenie
z nazwy miejsca wobec gazetera z geometrią (13 149 nazw w 25 miejscowościach, 292 punkty adresowe,
OpenStreetMap, ODbL 1.0).

| publikujący | wierszy | ze współrzędnymi | pokrycie |
|---|---:|---:|---:|
| Stoen Operator | 1 236 | 1 217 | **98,463%** |
| Boryszew Green Energy&Gas | 8 | 8 | **100,000%** |
| TAURON Dystrybucja | 10 955 | 0 | 0,000% |
| ENERGA-OPERATOR | 5 382 | 0 | 0,000% |
| PSE | 945 | 0 | 0,000% |
| National Grid | 694 | 0 | 0,000% |
| **panel** | **19 220** | **1 225** | **6,374%** |

Zera są **potwierdzone, nie naprawiane zgadywaniem**, i każde ma zapisaną przyczynę: u TAURONA
kod stacji bez opublikowanego słownika, u PSE i ENERGI przewaga wierszy bez zadeklarowanej
miejscowości, u National Grid nazwy punktów zasilania zamiast adresów ulic.

Weryfikacja na próbie warstwowej 102 punktów: zgodność nazwy ulicy z niezależnym geokodowaniem
**101 z 102 = 99,02%**; mediana odległości między dwoma niezależnie wybranymi punktami
reprezentatywnymi tej samej ulicy **259,2 m**, przy korelacji Spearmana z długością osi **0,714** —
źródła wskazują tę samą ulicę i różnią się tym, który jej punkt uznają za reprezentatywny.

**Ograniczenie zasadnicze:** jest to weryfikacja wobec drugiego odczytu tej samej bazy, nie wobec
pomiaru terenowego. Źródła są skorelowane, więc pomiar nie wyklucza błędu wspólnego dla
OpenStreetMap.

**Nazwa ulicy nie wyznacza punktu.** 431 z 6 057 nazw warszawskich (7,12%) ma rozłączne składowe
odległe o ponad 2 km. Rejestr podaje ulicę, lecz nie dzielnicę, więc tej niejednoznaczności
**nie da się usunąć z danych opublikowanych** — jest to ustalenie o zakresie obowiązku ujawnienia,
nie o jakości narzędzia. Każdy wynik niesie liczbę składowych i ich rozrzut, żeby odbiorca mógł
takie wiersze odfiltrować.

## Testy a pomiar wzrokowy

`python -m pytest -q` zgłasza **120 passed, 2 skipped** na 122 zebrane. Dwa pominięcia są
warunkowe: testy integracyjne adapterów PSE i ENERGI wymagają dokumentów źródłowych.

Obie metody wychwytują **różne klasy defektów** i oba mechanizmy są w pakiecie obecne. Pięć
defektów odwzorowania przeszło przez cały zestaw testów, bo żaden nie rzucał wyjątku — w tym
jeden zmieniający status umowy na przeciwny w 88 wierszach dwóch publikujących. Wykryło je
porównanie wyjścia z wzorcem odczytanym z dokumentu. Wszystkie są objęte testami regresyjnymi.
