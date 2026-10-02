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
