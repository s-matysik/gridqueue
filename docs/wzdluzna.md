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

## Algorytm dopasowania — pełna specyfikacja

Żeby wynik dało się odtworzyć i zakwestionować, podajemy reguły wprost.

1. **Klucz** jest konkatenacją sześciu pól: publikujący, lokalizacja tekstowa, poziom napięcia,
   klasa zasobu, moc wprowadzana, moc pobierana. Wartości brane są **po harmonizacji przez
   adapter**, a więc po normalizacji białych znaków, jednostek i słowników kontrolowanych;
   poza tym porównanie jest **dokładne, bez tolerancji** — także dla mocy.
2. **Brak wartości jest wartością.** Pole puste wchodzi do klucza jako pusty łańcuch, więc wiersz
   z brakującą mocą dopasuje się tylko do wiersza, w którym ta moc też jest pusta. Uzupełnienie
   mocy przez publikującego rozrywa zatem parę i daje jedno zniknięcie oraz jedno pojawienie.
   To samo dotyczy zmiany poziomu napięcia albo klasy zasobu.
3. **Unikalność jest wymagana w obu edycjach.** Wiersze o powtarzającym się kluczu są odrzucane
   przed dopasowaniem — zachowywany jest pierwszy — bo dla nich przypisanie jeden-do-wielu nie ma
   jednoznacznego rozstrzygnięcia. Liczby są raportowane: `wierszy_w_kolizji_a` i `_b` podają,
   ile wierszy stoi w grupach kolizyjnych, a `odrzuconych_jako_niejednoznaczne_a` i `_b`, ile
   faktycznie wypada z dopasowania.
4. **Nowe i ubyłe** to po prostu różnice zbiorów kluczy, liczone po odrzuceniu kolizji.
5. **Daty i status są z klucza wyłączone**: daty bywają uzupełniane między edycjami, a status
   jest właśnie tym, czego zmianę mierzymy.

Na parze edycji PSE kolizje obejmują 56 wierszy w edycji lipcowej i 48 w sierpniowej, co po
odrzuceniu daje 31 i 27 wierszy wypadających z dopasowania — odpowiednio 3,5 % i 3,1 % wierszy.

## Precyzja dopasowania zmierzona na polach wstrzymanych

Macierz przejść jest świadectwem pośrednim, więc dokładamy świadectwo bezpośrednie.
`linkage_audit` porównuje każdą dopasowaną parę na **dziewięciu polach wyłączonych z klucza**:
nazwa podmiotu ubiegającego się, nazwa obiektu, data złożenia wniosku oraz sześć pól rozbicia
mocy na technologie. Klucz nie wymusza zgodności żadnego z nich, więc ich zgodność jest
niezależnym świadectwem, że para dotyczy tego samego wniosku.

Para jest **fałszywa**, gdy rdzeń nazwy podmiotu ORAZ rdzeń nazwy obiektu są rozbieżne i żaden
nie zawiera się w drugim; **niepewna**, gdy rozbieżny jest dokładnie jeden z nich; **potwierdzona**
w pozostałych przypadkach. Rdzeń nazwy powstaje przez usunięcie formy prawnej, interpunkcji
i spacji, bo publikujący zmienia zapis formy prawnej między edycjami. Pole uzupełnione
jednostronnie — puste w jednej edycji, wypełnione w drugiej — nie jest liczone jako rozbieżność,
bo jest redakcją tego samego wniosku.

Wynik na parze edycji PSE, na **wszystkich 804 parach**, nie na próbce:

| klasa pary | liczba | udział |
|---|---:|---:|
| potwierdzona | 795 | 98,88 % |
| niepewna | 6 | 0,75 % |
| fałszywa | 3 | 0,37 % |

Precyzja dopasowania mieści się więc w przedziale **98,88 % do 99,63 %**, zależnie od tego, czy
przypadki niepewne policzyć jako błędne, czy jako trafne. Trzy pary fałszywe to różne wnioski
dzielące lokalizację, napięcie, klasę i obie moci — na przykład dwa magazyny energii tej samej
mocy w tej samej miejscowości. Wynik przejść jest wobec nich odporny: po usunięciu dziewięciu
par wątpliwych udział przejść w przód zmienia się z 98,28 % na 98,25 %.

Zastrzeżenie, którego nie pomijamy: nie jest to walidacja wobec prawdy zewnętrznej, bo dla tego
rejestru taka prawda nie istnieje — nie ma trwałego identyfikatora, wobec którego można by
dopasowanie sprawdzić. Jest to test spójności wewnętrznej na danych, których klucz nie dotyka.

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
from gridqueue import compare_editions, linkage_audit, get_adapter

a = get_adapter("pl_pse").parse("edycja_2026_07_31.xlsx").frame
b = get_adapter("pl_pse").parse("edycja_2026_08_31.xlsx").frame
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
d.as_dict()
d.przejscia          # macierz przejść statusu

linkage_audit(a, b).as_dict()   # precyzja dopasowania
```

Pełny przebieg z figurą: `examples/longitudinal_use_case.py`.
