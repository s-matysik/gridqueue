---
title: Analiza wzdłużna
---

# Porównanie edycji rejestru

Obowiązek ustawowy każe wymieniać ujawnienie co najmniej raz na kwartał, więc kolejne edycje
tego samego rejestru są naturalnym materiałem do analizy wzdłużnej. Jedna rzecz stoi temu
na drodze i trzeba ją zadeklarować, a nie obejść milczeniem.

## Rejestr nie publikuje trwałego identyfikatora wniosku

U części publikujących pole identyfikatora obiektu jest puste w niemal każdym wierszu —
u PSE w 866 z 876 — a pakiet wstawia wtedy zastępnik oparty na liczbie porządkowej
w dokumencie. Taki zastępnik jest stabilny **w obrębie jednej edycji i bezwartościowy między
edycjami**: pozycja 869 w jednej edycji nie jest tym samym wnioskiem co pozycja 869
w następnej, bo wiersze się przesuwają. Złączenie po identyfikatorze dałoby wynik pozornie
sensowny i całkowicie fałszywy.

`compare_editions` używa więc **klucza treściowego** zbudowanego z publikującego, lokalizacji,
poziomu napięcia, klasy zasobu i obu mocy. Daty i status są z klucza celowo wyłączone: daty
bywają uzupełniane między edycjami, a status jest właśnie tym, czego zmianę mierzymy.

Ograniczenie klucza treściowego: rozjeżdża się, gdy publikujący skoryguje którekolwiek z pól
wchodzących w jego skład, i wtedy ten sam wniosek wygląda jak zniknięcie w parze
z pojawieniem. Miara niżej pozwala ocenić, jak często to się zdarza.

## Macierz przejść jako test dopasowania

Jeśli klucz dopasowuje właściwe wiersze, przejścia statusu powinny biec zgodnie z kierunkiem
postępowania administracyjnego. Jeśli dopasowuje losowo — będą rozłożone bez tego porządku.
Na parze edycji PSE z 31 lipca i 31 sierpnia 2026 roku **98,28 % przejść biegnie w przód**
(57 z 58), przy jednym przejściu wstecznym z umowy obowiązującej do warunków wydanych.
Jest to test niezależny od samego dopasowania i właśnie dlatego ma wartość.

## Rejestr nie jest monotoniczną migawką

Drugi wynik tej samej pary edycji jest ostrzeżeniem dla każdego, kto chciałby czytać różnicę
między edycjami jako zmianę stanu kolejki:

| wielkość | wartość |
|---|---:|
| wierszy w edycji lipcowej | 892 |
| wierszy w edycji sierpniowej | 876 |
| kluczy unikalnych | 861 i 849 |
| wspólnych | 804 |
| nowych | 45 |
| ubyłych | 57 |
| zmian statusu | 58 |
| **nowych już w stanie zamkniętym** | **13** |
| **ubyłych o statusie czynnym** | **33** |

Trzynaście wierszy pojawia się w nowszej edycji już jako wniosek wycofany, odmowa albo warunki
wygasłe — czyli rejestr **dopisuje sprawy zakończone wstecz**. Trzydzieści trzy wiersze
o statusie czynnym znikają, czego zakończeniem postępowania wyjaśnić nie można. Własność
`migawka_monotoniczna` zwraca w tej parze `False` i ma to być sygnał, nie szczegół techniczny.

```python
from gridqueue import compare_editions, get_adapter

a = get_adapter("pl_pse").parse("edycja_2026_07_31.xlsx").frame
b = get_adapter("pl_pse").parse("edycja_2026_08_31.xlsx").frame
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
d.as_dict()
d.przejscia          # macierz przejść statusu
```

Pełny przebieg z figurą: `examples/longitudinal_use_case.py`.
