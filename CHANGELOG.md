# Historia zmian

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/);
wersjonowanie semantyczne. Wersja schematu danych jest odrębna od wersji pakietu
i podawana jako `SCHEMA_VERSION`.

## 1.2.1 — 2026-10-04

### Dodane
- `notebooks/gridqueue_colab.ipynb` — pełny przebieg badawczy w przeglądarce, bez instalacji:
  pobranie dwóch edycji wprost od publikującego, wydobycie, kontrola jakości, przepływy w kolejce
  z precyzją dopasowania oraz **asercja zgodności z liczbami opublikowanymi w artykule**.
  Dokumentacja: `docs/colab.md`.
- `QualityReport.as_frame()` — metoda **obiecywana przez dokumentację, lecz nieobecna w kodzie**.
  Defekt ujawnił się dopiero przy uruchomieniu notatnika, który korzystał z publicznego API
  tak, jak opisuje je dokumentacja.
- Dwa zadania ciągłej integracji: przebieg na `pandas>=3.0` oraz kontrola notatnika
  (poprawność składniowa komórek i istnienie w API każdej nazwy z niego importowanej).

### Naprawione
- **Niezgodność z pandas 3.** Klucz wzdłużny budowano przez `.astype(str)`, co w pandas 2
  zamieniało brak na łańcuch `"nan"`, a w pandas 3 zachowuje wartość brakującą — złączenie
  składowych rzucało `TypeError` i cała analiza wzdłużna była na tej wersji niewykonalna.
  Klucz buduje się teraz jawną konwersją, identycznie w obu wersjach; **wszystkie opublikowane
  liczby pozostają bez zmian**, co sprawdzono porównaniem. Ta sama poprawka czyni regułę
  „brak jest wartością" własnością kodu, a nie ubocznym skutkiem rzutowania typu.
  Analogiczne założenie usunięto z adaptera operatora przesyłowego.

### Zmienione
- Macierz CI testowała wersje Pythona, lecz nie wersje bibliotek — stąd defekt przeszedł.
  Zadanie `pandas3` zamyka tę lukę.

## 1.2.0 — 2026-10-04

### Dodane
- `linkage_audit` — ocena precyzji dopasowania wzdłużnego na dziewięciu polach
  **wyłączonych z klucza** (nazwa podmiotu, nazwa obiektu, data wniosku, sześć pól
  rozbicia mocy). Klucz nie wymusza zgodności tych pól, więc ich zgodność jest
  niezależnym świadectwem. Na parze edycji PSE precyzja wynosi 98,88–99,63 %
  na wszystkich 804 parach.
- `EditionDelta` raportuje teraz kolizje klucza i liczbę wierszy odrzuconych
  z dopasowania jako niejednoznaczne.
- `DATA_LICENSE.md` — rozdzielenie licencji kodu od statusu danych wejściowych
  i wyjściowych, w tym obowiązków wynikających z ODbL dla gazetera.
- `CHANGELOG.md`.
- Odznaki stanu w `README.md`.
- `reproducibility/expected/` — oczekiwane wyniki wraz z asercjami w skryptach
  odtwarzających; rozbieżność kończy przebieg kodem niezerowym.

### Zmienione
- Dokumentacja analizy wzdłużnej podaje pełną specyfikację algorytmu dopasowania:
  zachowanie przy braku wartości, wymóg unikalności, obsługę kolizji, brak tolerancji
  na mocach.
- Przykład wzdłużny wypisuje precyzję dopasowania i liczby kolizji.

## 1.1.0 — 2026-10-03

### Dodane
- Moduł `longitudinal`: `compare_editions`, `surrogate_key`, `EditionDelta`.
  Rejestr nie publikuje trwałego identyfikatora wniosku, więc dopasowanie między
  edycjami idzie po kluczu treściowym.
- `examples/longitudinal_use_case.py` i `docs/wzdluzna.md`.

### Naprawione
- **Wielokrotne komórki mocy.** Gdy wniosek dotyczy kilku miejsc przyłączenia,
  publikujący wpisuje do jednej komórki kilka wartości rozdzielonych złamaniem linii.
  Normalizacja białych znaków zamieniała złamanie linii na spację, a konwersja mocy
  traktuje spację jako separator tysięczny, więc „129⏎240" (129 MW + 240 MW) stawało się
  129 240 MW. W edycji ze średnikami ta sama komórka nie konwertowała się wcale.
  Moc jest teraz rozbijana po złamaniu linii i średniku — i celowo nie po spacji —
  składowe sumowane, a podział zachowany w rozszerzeniach.

## 1.0.0 — 2026-10-03

### Zmienione
- **Rdzeń schematu jest warunkowy i osobny dla każdej encji.** Reguła kompletności
  rdzenia wymagała bezwarunkowo pola `moc_pobierana` i stosowała wymagania encji
  WNIOSEK także do wierszy encji WĘZEŁ. Obie decyzje zamieniały własność schematu
  w pozorne naruszenie ujawnienia. Naruszeń reguły R7 jest 771 (4,011 %) zamiast
  5 390 (28,044 %).
- Wprowadzono `SCHEMA_VERSION`, wystawiany w raporcie walidacji i w publicznym API.

### Dodane
- `examples/research_use_case.py`, katalog `reproducibility/`, `CITATION.cff`,
  przepływ ciągłej integracji na trzech systemach i czterech wersjach Pythona.
