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
