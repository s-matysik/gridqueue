# Historia zmian

Format oparty na [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/);
wersjonowanie semantyczne. Wersja schematu danych jest odrębna od wersji pakietu
i podawana jako `SCHEMA_VERSION`.

## 1.4.0 — 2026-10-07

### Dodane
- Adapter `pt_eredes` — zdolność przyjęcia krajowej sieci dystrybucyjnej Portugalii,
  469 wierszy encji WĘZEŁ, publikacja kwartalna. **Trzecia jurysdykcja w panelu
  i trzeci tryb wydania**: nie dokument do druku i nie plik na stronie, lecz zbiór
  na portalu otwartych danych z interfejsem REST.
- Pierwsze zagraniczne źródło encji WĘZEŁ. Encja ta rośnie w panelu ze 165 wierszy
  do 634, a obie jurysdykcje spełniają jej rdzeń **różnymi członami tej samej
  alternatywy**: Polska mocą dostępną (58 % wierszy węzłowych), Portugalia flagą
  ograniczenia (100 %). Warunkowy rdzeń wprowadzony w wersji 1.0 dla polskiego
  błędu kategorialnego okazał się warunkiem wchłonięcia obcej jurysdykcji.

### Rozstrzygnięte
- **Jednostki.** Publikujący portugalski podaje moce w MVA, czyli w mocy pozornej,
  a jednostką kanoniczną schematu jest kW mocy czynnej. Przeliczenie wymagałoby
  nieujawnionego współczynnika mocy, więc `moc_dostepna` pozostaje puste, a wartości
  źródłowe trafiają do pól rozszerzenia z jawnie zapisaną jednostką. Jest to ta sama
  zasada, którą zastosowano wobec publikującego podającego liczbę wolnych miejsc
  przyłączeniowych zamiast mocy.

### Naprawione
- **Test deklaracji adapterów niósł nieaktualny kontrakt rdzenia.** Wymagał od
  każdego adaptera rdzenia encji WNIOSEK, czyli powielał błąd kategorialny naprawiony
  w regule R7 w wersji 1.0: publikujący realizujący wyłącznie punkt 2 obowiązku
  ujawnia węzły, a nie wnioski, więc nie ma ani identyfikatora wniosku, ani jego mocy.
  Defekt ujawnił dopiero adapter portugalski. Test sprawdza teraz rdzeń **właściwej
  dla adaptera encji**.

### Zmienione
- `reproducibility/manifest.csv` obejmuje eksport portugalski z sumą kontrolną.
- Panel wzorcowy liczy 19 689 wierszy od siedmiu publikujących w trzech jurysdykcjach.


## 1.3.0 — 2026-10-07

### Dodane
- Moduł `analysis` z warstwą badawczą nad schematem: `station_node_map`,
  `assign_to_nodes`, `node_loading`, `processing_time`, `kaplan_meier`.
  Pozwala policzyć **obciążenie węzła** — stosunek mocy czynnej kolejki do
  ujawnionej mocy dostępnej — czyli kryterium, które przeglądy literatury
  opisują jako niemierzalne z powodu braku danych.
- `linkage_recall` — **czułość** dopasowania wzdłużnego, obok mierzonej dotąd
  precyzji. Na parze edycji operatora przesyłowego czułość klucza wynosi
  0,9652: z 29 pominiętych par 10 rozrywa zapis lokalizacji, 15 zmiana mocy,
  4 zmiana napięcia.
- `surrogate_key(..., zero_jako_brak=True)` — opcja zrównująca zero z brakiem
  wartości. Odzyskuje 12 z 51 par traconych przez klucz. **Domyślnie
  wyłączona**: zero jest wartością ujawnioną, a brak jej nieujawnieniem, więc
  zrównanie ich jest decyzją analityka i ma być widoczne w kodzie.
- `schema_table()` zwraca kolumny `encja` oraz `status_rdzenia` — rdzeń jest
  warunkowy per encja, czego dwuwartościowa kolumna `rdzen` nie oddawała.
- `reproducibility/fetch_sources.py` — pobiera dokumenty źródłowe z manifestu
  i weryfikuje sumy SHA-256. Obsługuje własny pakiet zaufanych wystawców przez
  `GRIDQUEUE_CA_BUNDLE`, bez wyłączania weryfikacji.

### Naprawione
- **Normalizacja nazw rozcinała wyrazy z literą `ł`.** Rozkład kanoniczny
  Unicode nie oddziela od niej znaku diakrytycznego, bo jest to osobna litera,
  więc czyszczenie znaków zamieniało ją na spację i „Białogard" stawał się
  „bia ogard". Dotyczy też `đ`, `ø`, `ß`, `æ`, `œ`. Jest to drugie wystąpienie
  tej samej pułapki w projekcie — pierwsze dotyczyło harmonizacji statusów.
- **Obiekty planowane na linii były arbitralnie przypisywane do węzła.** Wpis
  „planowany RS w linii relacji A – B" opisuje obiekt leżący między węzłami;
  dopasowanie po nazwie przypisywało mu pełną moc do tego końca, który akurat
  występował w wykazie stacji. Takie wnioski mają teraz własny status `LINE`
  i nie są przypisywane. Na danych jednego publikującego dotyczy to 63 wniosków.

### Zmienione
- `reproducibility/manifest.csv` obejmuje edycję lipcową ujawnienia operatora
  przesyłowego, używaną w analizie wzdłużnej.
- `DATA_LICENSE.md` wyjaśnia, dlaczego dokumenty nie są redystrybuowane,
  i odnotowuje, że odsyłacz jednego z publikujących przestał prowadzić do pliku
  — co skrypt pobierający rozpoznaje po sygnaturze pliku i zgłasza osobno.


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
