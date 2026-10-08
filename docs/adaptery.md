---
title: Adaptery
---

# Adaptery

Każdy adapter realizuje ten sam interfejs i **deklaruje**, które pola schematu wypełnia oraz jakie
rozszerzenia wnosi. Deklaracja jest częścią wyniku, nie dokumentacji — dzięki temu pokrycie pól
nie jest twierdzeniem, a wartością odczytywalną z kodu.

| klucz | publikujący | jurysdykcja | pól schematu | rozszerzeń |
|---|---|---|---:|---:|
| `pl_tauron` | TAURON Dystrybucja S.A. | PL | 15 | 9 |
| `pl_energa` | ENERGA-OPERATOR S.A. | PL | 17 | 25 |
| `pl_pse` | PSE S.A. | PL | 17 | 24 |
| `pl_stoen` | Stoen Operator Sp. z o.o. | PL | 13 | 7 |
| `pl_boryszew` | Boryszew Green Energy&Gas Sp. z o.o. | PL | 10 | 6 |
| `uk_nationalgrid` | National Grid Electricity Distribution | UK | 10 | 9 |

Adaptery `pl_pse` i `pl_energa` dzielą moduł `adapters/_ptpiree.py`, bo oba publikujące wypełniają
ten sam uzgodniony wzorzec sprawozdawczy — jeden wydaje go jako arkusz, drugi jako dokument do
druku. To nie jest zbieg okoliczności implementacyjny, lecz odwzorowanie praktyki sektora.

## Dodanie publikującego

```python
from gridqueue.adapters.base import Adapter, ParseResult

class MojAdapter(Adapter):
    klucz = "pl_moj_operator"
    publikujacy = "Nazwa Operatora S.A."
    jurysdykcja = "PL"
    detekcja = [r"moj_operator", r"nazwa_operatora"]   # wzorce nazwy pliku

    def parse(self, source) -> ParseResult:
        ...   # zwróć ramkę w schemacie + raport
```

Rejestracja: dopisanie klasy do `REGISTRY` w `gridqueue/registry.py`. Rdzeń pozostaje nietknięty.

```bash
gridqueue adapters          # deklaracje wszystkich publikujących
```

## Wykrywanie publikującego

```python
from gridqueue import detect_publisher
detect_publisher("tauron_informacja_2026_06_30.pdf")   # 'pl_tauron'
```

Kolejność jest celowa: nazwa pliku jest tania i zwykle wystarcza, treść pierwszej strony
rozstrzyga resztę. Gdy nie rozstrzyga żadna z nich, zwracane jest `None` — bez zgadywania.

## E-REDES (Portugalia) — `pt_eredes`

Trzecia jurysdykcja w panelu i trzeci tryb wydania: **zbiór na portalu otwartych
danych z interfejsem REST**, publikowany kwartalnie. Jednostką wiersza jest
podstacja albo punkt cięcia sieci wysokiego napięcia; wierszy jest 469 i wszystkie
należą do encji WĘZEŁ.

Co ten adapter wnosi, czego nie było: **pierwsze zagraniczne źródło encji WĘZEŁ**.
Dotąd wiersze węzłowe pochodziły wyłącznie od dwóch publikujących polskich, więc
kryterium „dostępna moc przyłączeniowa" dawało się policzyć w jednej jurysdykcji.
Źródło portugalskie podaje ponadto **skład grupy podstacji** — dokładnie tę
informację, która w panelu polskim umożliwia przypisanie wniosków do węzła.

### Rozstrzygnięcie o jednostkach

Publikujący podaje zdolność przyjęcia i moce przyłączone w **MVA**, czyli w mocy
pozornej. Jednostką kanoniczną schematu jest **kW mocy czynnej**. Są to różne
wielkości fizyczne, a przeliczenie jednej na drugą wymaga współczynnika mocy,
którego publikujący nie podaje.

Dlatego `moc_dostepna` pozostaje **puste**, a wartości w MVA trafiają do pól
rozszerzenia wraz z jawnie zapisaną jednostką źródłową:

| pole rozszerzenia | znaczenie |
|---|---|
| `_jednostka_mocy_zrodlowa` | `MVA` |
| `_moc_dostepna_mva` | zdolność przyjęcia SN+WN |
| `_moc_przylaczona_mva` | moc już przyłączona |
| `_moc_zakontraktowana_mva` | moc zakontraktowana |
| `_moc_w_potwierdzaniu_mva` | moc w trakcie potwierdzania |

Jest to ta sama zasada, którą zastosowano wobec publikującego podającego liczbę
wolnych miejsc przyłączeniowych zamiast mocy: wpisanie liczby w pole o innej
jednostce byłoby fabrykacją, nie harmonizacją.

Rdzeń encji WĘZEŁ jest mimo to spełniony, bo realizuje go drugi człon alternatywy —
`ograniczenie_flaga`, ustawiana na podstawie zerowej zdolności przyjęcia. Zero jest
wartością **ujawnioną** i oznacza ograniczenie; pusta komórka oznacza nieujawnienie
i flagi nie ustawia. Dotyczy to 222 z 469 węzłów.

To rozstrzygnięcie jest zarazem wynikiem obserwacyjnym: **obie jurysdykcje spełniają
rdzeń encji WĘZEŁ różnymi członami tej samej alternatywy** — Polska mocą dostępną,
Portugalia flagą ograniczenia. Warunkowy rdzeń, wprowadzony w wersji 1.0 dla
polskiego błędu kategorialnego, okazał się warunkiem wchłonięcia obcej jurysdykcji.

```python
from gridqueue import get_adapter
r = get_adapter("pt_eredes").parse("pt_eredes_capacidade_rececao_rnd_2T2026.csv")
r.frame[["id_wezla", "nazwa_wezla", "lokalizacja_tekst", "ograniczenie_flaga"]]
r.report["uwaga_jednostki"]
```

## e-Distribución (Hiszpania) — `es_edistribucion`

**Pierwsze zagraniczne źródło wydawane jako dokument do druku.** Dotąd oba adaptery
zagraniczne czytały dane już tabelaryczne, więc przenoszalność była wykazana na przypadku
łatwiejszym niż polski; to źródło ten brak zamyka. Publikujący wydaje **PDF miesięczny**
w serii obejmującej lata 2023–2025, na podstawie art. 33 ust. 9 ustawy 24/2013,
art. 5 ust. 4 dekretu 1183/2020 i art. 12 okólnika 1/2021 regulatora CNMC — czyli
w konstrukcji prawnej takiej samej jak polska: obowiązek ustawowy, stała częstość, format
pozostawiony publikującemu.

Wydanie z 1 sierpnia 2025: 28 stron, **1 838 wierszy encji WĘZEŁ**, wszystkie pola
zadeklarowane wypełnione w 100 %, w tym **współrzędne geograficzne każdej podstacji** —
czego nie robi żaden publikujący polski. Moce są w **MW mocy czynnej**, więc przeliczenie
na kanoniczne kW jest zwykłą zmianą rzędu wielkości.

### Semantyka kolumn ustalona arytmetyką, nie nagłówkiem

Nagłówek ma komórki scalone w dwóch poziomach i sugeruje, że kolumny „Con permiso de AyC"
oraz „En trámite con capacidad" należą do grupy mocy **przyjętej i nierozstrzygniętej**.
Sprawdzenie sumami pokazuje co innego: ich suma odtwarza moc **zajętą** (395 wierszy zgodnych
dokładnie przy 767 wierszach o niezerowej mocy zajętej), a rozbicie technologiczne odtwarza
moc przyjętą i nierozstrzygniętą we **wszystkich** wierszach o niezerowej wartości.
Odwzorowanie idzie za arytmetyką. Przyjęcie nagłówka na wiarę dałoby ciche przestawienie
dwóch pól mocy.

## ESB Networks (Irlandia) — `ie_esbnetworks`

Najliczniejsze źródło w panelu: **46 527 wierszy**, jedyne schodzące poniżej poziomu stacji
wysokiego napięcia aż do stacji SN/nn. Jednostką wiersza jest grupa transformatorów w stacji.
Współrzędne są w 46 525 wierszach.

### Dwie jednostki w jednym pliku

Publikujący podaje stronę **odbiorczą w MVA** (moc pozorna), a **wytwórczą w MW** (moc czynna).
Pole `moc_dostepna` niesie zatem dostępną moc **wytwórczą trwałą**, przeliczoną z MW na kW,
a strona odbiorcza zostaje w rozszerzeniach z jednostką w nazwie pola. Zsumowanie MW z MVA
dałoby liczbę bez sensu fizycznego, a wybór jednej strony bez powiedzenia tego wprost byłby
ukryciem decyzji.

### Jedna interpretacja, zapisana jawnie

Kolumny ograniczenia niosą frazę `Constrained, otherwise capacity available = X kVA` albo są
puste. Przyjmujemy, że **pusta komórka oznacza brak ograniczenia**, a nie brak deklaracji:
kolumna jest wskaźnikiem binarnym, w którym wartość dodatnia niesie objaśnienie, a ujemna jest
wyrażona pustką. Publikujący tej konwencji nigdzie nie opisuje, więc jest to **interpretacja,
nie treść źródła** — surowa fraza zostaje w rozszerzeniu, liczba z niej jest wydobywana
osobno i **nie jest przeliczana**, bo jest w kVA. Decyzja jest odnotowana w raporcie adaptera
i przypięta testem, żeby jej zmiana była widoczna.

Dwie flagi źródłowe (odbiorcza i wytwórcza) wchodzą do jednego pola schematu jako
**alternatywa zachowująca nieokreśloność**: `None` w połączeniu z `False` daje `None`,
a nie `False`.
