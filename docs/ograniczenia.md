---
title: Ograniczenia
---

# Ograniczenia

Podajemy je razem z liczbami, nie tylko w osobnej sekcji, bo bez nich część wyników byłaby użyta
niepoprawnie.

## Czym rejestr nie jest

* **Nie jest oszacowaniem dostępnej mocy przyłączeniowej.** Ujawnia **kolejkę, nie zapas**.
  Pole mocy dostępnej należy do encji węzła z pkt 2 obowiązku i jest wypełnione tylko tam, gdzie
  publikujący ten punkt realizuje mocą.
* **Nie jest odwzorowaniem stanu sieci.** Opisuje postępowania administracyjne, których część
  nigdy nie dojdzie do realizacji. Rozstrzygnięcie procesu jest zdarzeniem prawnym, nie fizycznym.
* **Nie jest rankingiem lokalizacji.** Nie zawiera modelu preferencji.
* **Nie jest indeksem publikacji.** Istnieją narzędzia indeksujące strony operatorów w skali
  europejskiej; ten pakiet schodzi warstwę niżej i parsuje sam dokument.

## Niewspółmierność ujawnień tego samego przepisu

Dwóch publikujących wykonuje ten sam punkt obowiązku w postaciach nieporównywalnych: jeden podaje
**moc dostępną**, drugi **liczbę wolnych miejsc przyłączeniowych**. Odwzorowaliśmy to drugie na
flagę ograniczenia i pole rozszerzenia, pozostawiając pole mocy puste — wpisanie liczby miejsc
w pole mocy byłoby fabrykacją jednostki. Jest to wynik empiryczny, nie niedogodność
implementacyjna.

## Zakres pokrycia

Sześciu publikujących wierszowo na tle około 180 koncesjonowanych operatorów systemów
dystrybucyjnych w Polsce. Czterech z nich należy do sześciu objętych uzgodnionym wzorcem
sprawozdawczym, co wyznacza sprawdzalny horyzont rozszerzenia, ale **nie uprawnia do żadnego
twierdzenia o rozkładzie formatów wśród pozostałych publikujących**.

## Dostęp do źródeł

* **Jeden duży operator pozostaje niedostępny, i nie z powodu certyfikatu.** Brakujący certyfikat
  pośredni pozyskano ze wskazania AIA w certyfikacie serwera i po jego dołożeniu serwis odpowiada
  kodem 200 przy pełnej weryfikacji. Blokadą jest **filtrowanie klienta po stronie serwera**:
  na uczciwy nagłówek identyfikacyjny serwis zwraca stronę odrzucenia. Odtworzenie odcisku
  przeglądarki byłoby obejściem kontroli postawionej świadomie przez operatora, więc go nie
  podjęliśmy.
* Dwa zagraniczne portale zwracają 403 na poziomie wierszy. Korzystamy wyłącznie z ich publicznych
  metadanych i tak to opisujemy. **Kontroli dostępu nie obchodzimy**; klient przedstawia się
  uczciwie w nagłówku identyfikacyjnym.

## Pomiar dokładności

* Zbiór odniesienia jest **częściowo jednoanotatorski**: zgodność międzyanotatorską zmierzono na
  podpróbce 35 wierszy, natomiast wzorce dwóch publikujących pozostają jednoanotatorskie.
* Próba jest **klastrowa** — ciągi kolejnych wierszy na losowo wybranych stronach — a nie prosta
  próba losowa, więc efektywna precyzja jest niższa, niż dałaby ta sama liczba niezależnych
  losowań.
* Wzorzec obejmuje **encję wniosku**; dokładności tabel węzłowych, w tym pola mocy dostępnej
  i horyzontów pięcioletnich, nie mierzono osobno.
* Udziału procentowego z pierwszego przebiegu pomiaru **nie wolno cytować jako punktu odniesienia**
  dla wartości końcowej, bo zmienił się zbiór mierzonych pól; porównywalne jest rozbicie per pole.

## Lokalizacja

* Lokalizacja u największego publikującego to **wewnętrzny kod stacji**; operator nie publikuje
  słownika kodów, więc rozwiązywacz zwraca brak z przyczyną. **Nie zgaduje.** Pozyskanie słowników
  kodów stacji jednym krokiem przekształciłoby ten rejestr z aprzestrzennego w przestrzenny.
* Nazwa ulicy nie wyznacza punktu — zob. [walidacja](walidacja.md).

## Przenoszalność

Sześć źródeł wierszowych w dwóch jurysdykcjach to **demonstracja przenoszalności, nie dowód
ogólności**. Adapter zagraniczny działa na danych **już tabelarycznych**, więc przenoszalność
wykazano na przypadku łatwiejszym niż polski; druga jurysdykcja publikująca dokumenty do druku
byłaby dowodem mocniejszym.

## Licencja

Do ustalenia. Licencje danych wejściowych są osobne i niezmienne: gazeter z OpenStreetMap na
licencji ODbL; publikacje ustawowe operatorów na ich własnych warunkach korzystania,
redystrybuowane wyłącznie tam, gdzie jest to dozwolone.
