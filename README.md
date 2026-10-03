# gridqueue

Harmonizator ustawowych ujawnień przyłączeniowych do sieci elektroenergetycznej.

Operatorzy systemów dystrybucyjnych mają obowiązek publikować, kto ubiega się o przyłączenie,
gdzie, o jaką moc i na jakim etapie stoi postępowanie (art. 7 ust. 8l ustawy z dnia
10 kwietnia 1997 r. – Prawo energetyczne). W Polsce obowiązek dotyczy około 180 koncesjonowanych
operatorów i **każdy publikuje we własnym formacie** — najczęściej jako PDF. Informacja jest
jawna, ale nie jest przetwarzalna.

`gridqueue` zamienia te publikacje na jeden zbiór wierszy o **zmierzonej dokładności**.

Stan wydania 0.3.1: **sześć adapterów, 19 220 wierszy panelu, wszystkie 21 pól schematu
wypełnione**. Publikujący: TAURON Dystrybucja 10 955 wierszy, ENERGA-OPERATOR 5 382,
Stoen Operator 1 236, PSE 945, National Grid (GB) 694, Boryszew Green Energy&Gas 8.
Dokumentacja: **https://s-matysik.github.io/gridqueue/**

## Czym to nie jest

Nie jest to indeks publikacji operatorów ani mapa przeglądowa. Istnieją narzędzia, które
indeksują i linkują do stron operatorów w skali europejskiej. `gridqueue` robi krok niżej:
**parsuje sam dokument ustawowy na wiersze**. W jurysdykcjach o dobrych danych (Wielka Brytania,
USA) dane są już tabelaryczne i ta warstwa jest zbędna — adapter brytyjski w tym pakiecie
sprowadza się do pobrania CSV. Polska jest przypadkiem, w którym nie jest.

## Instalacja

Jedno polecenie, bez kompilacji i bez usług zewnętrznych:

```bash
pip install git+https://github.com/s-matysik/gridqueue@v1.0.0
```

Do pracy nad kodem, z ekstrasem testowym:

```bash
git clone https://github.com/s-matysik/gridqueue && cd gridqueue
pip install -e ".[test]"
```

Zależności: `pandas`, `pdfplumber`, `openpyxl`, `requests`, `pyarrow`. Jednostka kanoniczna mocy
to **kW** bez wyjątku; źródła podające megawaty są przeliczane przy wydobyciu, a jednostka źródłowa
zostaje odnotowana w rozszerzeniu.

## Szybki przykład

```python
from gridqueue import get_adapter, run_quality, validate_frame, audit_column_shift

res = get_adapter("pl_tauron").parse("tauron_informacja.pdf")
df = res.frame                       # ramka w 21-polowym schemacie
print(res.report["n_wierszy"])       # 10955
print(audit_column_shift(df).udzial) # 0.0 — udział wierszy z przesuniętymi kolumnami
print(run_quality(df).as_dict()["naruszen_lacznie"])
```

Wiersz z rozwiązaną lokalizacją:

```python
from gridqueue import resolver_from_osm_json
r = resolver_from_osm_json("ulice_warszawa.json")
res = r.resolve("WARSZAWA, WINCENTEGO ŚW.")
print(res.matched, res.pewnosc)      # Świętego Wincentego REVERSED
print(r.resolve("SKB3").powod)       # kod_stacji_bez_slownika — nie zgadujemy
```

## CLI

```bash
gridqueue schema                                   # specyfikacja 21 pól
gridqueue adapters                                 # deklaracje publikujących
gridqueue parse tauron.pdf --out tauron.parquet --report tauron.json
gridqueue parse --adapter uk_nationalgrid --out uk.parquet   # pobiera z katalogu CKAN
gridqueue validate tauron.parquet --out walidacja.json
gridqueue export tauron.parquet stoen.parquet --out panel.parquet --only-schema
```

## Schemat

21 pól w trzech grupach odwzorowujących strukturę obowiązku (TOŻSAMOŚĆ / MOC / PROCES),
rdzeń obowiązkowy 5 pól (`id_wniosku`, `lokalizacja_tekst`, `klasa_zasobu`, `moc_pobierana`,
`status_procesu`), reszta opcjonalna i **deklarowana per publikujący**. Jednostki kanoniczne:
moc w kW, daty ISO 8601, współrzędne WGS84. Pola spoza schematu, których dany operator
dostarcza więcej niż wymaga minimum, trafiają do kolumn z przedrostkiem `_` i są jawnie
deklarowane przez adapter (`adapter.declaration()`).

## Metoda wydobycia

Zamiast wyrażeń regularnych na spłaszczonym tekście — wydobycie z **położenia słów na stronie**:

* `ruled` — granice kolumn brane z pionowych krawędzi wektorowych (TAURON, Stoen);
  pusta komórka jest odgrodzona linią, więc nie może zlać się z sąsiednią,
* `banded` — granice z pionowych korytarzy bieli (Boryszew; dokument bez siatki),
* wiersze wielolinijkowe scalane kolumna po kolumnie po numerze porządkowym,
* arkusze (PSE) czytane wprost z komórek, wraz z formatowaniem znaku — bez tego indeksy górne
  oznaczające przypisy sklejają się z treścią, a w polach liczbowych niszczą wartość.

Wybrano `pdfplumber`, bo daje bezpośredni dostęp do współrzędnych słów i krawędzi wektorowych
z `pdfminer.six`. `camelot` w trybie lattice odtwarza granice kolumn z rastra i wymaga
Ghostscriptu, `tabula` wymaga JVM — w obu granica kolumny jest wynikiem detekcji na obrazie,
a nie liczbą z pliku.

## Przykład badawczy

Adaptery są specyficzne dla źródła, ale **analiza badawcza już nie**. `examples/research_use_case.py`
liczy czas od złożenia wniosku do wydania warunków przyłączenia, w podziale na klasę zasobu
i publikującego — bez ani jednej gałęzi zależnej od publikującego, wyłącznie na polach wspólnego
schematu:

```bash
gridqueue parse <dokumenty...> --out panel.parquet
python examples/research_use_case.py panel.parquet
```

Wynik na panelu sześciu publikujących (mediana, dni): przyłączenia **odbiorcze** 40 u TAURONA
i 57 u ENERGI, **fotowoltaika** 105 i 127, **magazyny energii** 119 i 146, **wiatr** 156 i 158.
Przyłączenia odbiorcze rozpatrywane są dwa do czterech razy szybciej niż wytwórcze, a różnica
między publikującymi utrzymuje się w obrębie klasy. Jest to wynik opisowy: rejestr opisuje
postępowania administracyjne, więc nie wolno z niego wnosić o przyczynach różnic ani o jakości
pracy publikującego — portfel wniosków, struktura sieci i praktyka ujawniania różnią się między
operatorami.

## Odtwarzalność

`reproducibility/` zawiera manifest dokumentów źródłowych (adres, data pobrania, SHA-256), wersje
bibliotek oraz skrypty odtwarzające liczby pochodne i figury. Dokumenty nie są redystrybuowane,
bo są wymieniane co kwartał — manifest pozwala sprawdzić, czy pracujemy na tej samej edycji.

## Reguły kontroli jakości

Osiem reguł; każda zwraca liczbę naruszeń, nie wyjątek — bo naruszenie jest własnością
ujawnienia, a nie błędem narzędzia: monotoniczność dat postępowania, dwuletnia ważność
warunków przyłączenia (art. 7 ust. 8i), dopuszczalność stanu procesu wobec obecnych dat,
spójność jednostek mocy, zakresy wartości, duplikaty identyfikatorów, kompletność rdzenia,
słownik kontrolowany.

Od wersji 1.0 reguła kompletności rdzenia ocenia **rdzeń właściwy dla encji wiersza**, a rdzeń
mocy jest **alternatywą**, nie konkretnym polem: wniosek wytwórczy deklaruje moc wprowadzaną,
odbiorczy pobieraną, a pkt 2 obowiązku bywa realizowany mocą dostępną albo liczbą wolnych miejsc
przyłączeniowych. W wersji 0.3.x rdzeń wymagał bezwarunkowo mocy pobieranej i stosował wymagania
encji wniosku także do wierszy węzłowych, co zamieniało własność schematu w pozorne naruszenie
ujawnienia — naruszeń tej reguły było 5 390 (28,044 %) wobec **771 (4,011 %)** teraz.

## Testy

```bash
python -m pytest -q      # 125 passed, 2 skipped (127 zebranych)
```

Dwa pominięcia są warunkowe: to testy integracyjne adapterów PSE i ENERGI, wymagające
dokumentów źródłowych, pomijane gdy dokumentów nie ma w drzewie roboczym. Zestaw działa na
Pythonie 3.10–3.13 pod Linuksem, macOS i Windows — sprawdza to CI przy każdym zgłoszeniu zmiany.

Pisanie testów i pomiar wzrokowy wychwytują **różne klasy defektów** i oba są w pakiecie obecne.
Pięć defektów odwzorowania przeszło przez cały zestaw testów, bo żaden nie rzucał wyjątku —
w tym jeden zmieniający status umowy na przeciwny w 88 wierszach dwóch publikujących. Wykryło je
porównanie wyjścia z wzorcem odczytanym z dokumentu.

## Ograniczenia

* Zbiór odniesienia do pomiaru dokładności jest **częściowo jednoanotatorski**. Zgodność
  międzyanotatorską zmierzono na podpróbce 35 wierszy odczytanej niezależnie, w zaślepieniu:
  zgodność surowa 0,9725, kappa Cohena 0,9690, zero niezgodności percepcyjnych. Wzorce PSE
  i ENERGI pozostają jednoanotatorskie.
* Lokalizacja u TAURONA to wewnętrzny kod stacji; operator nie publikuje słownika kodów,
  więc rozwiązywacz zwraca brak z powodem `kod_stacji_bez_slownika`. Nie zgaduje.
* **Żaden z publikujących nie podaje współrzędnych.** Pole `wspolrzedne` jest wypełniane
  wyprowadzeniem z nazwy miejsca wobec gazetera z geometrią (13 149 nazw w 25 miejscowościach):
  1 225 z 19 220 wierszy panelu. Wartość dowodowa tego pola jest więc inna niż pól przepisanych
  z dokumentu i jest tak opisana w wyniku.
* Nazwa ulicy nie wyznacza punktu: 431 z 6 057 nazw warszawskich (7,12%) ma rozłączne składowe
  odległe o ponad 2 km. Rejestr podaje ulicę, lecz nie dzielnicę, więc **tej niejednoznaczności
  nie da się usunąć z danych opublikowanych**. Każdy wynik niesie liczbę składowych i ich rozrzut,
  żeby odbiorca mógł takie wiersze odfiltrować.
* Portale UK Power Networks i Electricity North West zwracają 403 na poziomie wierszy.
  Korzystamy wyłącznie z ich publicznych metadanych i tak to opisujemy. Kontroli dostępu
  nie obchodzimy; klient przedstawia się uczciwie w nagłówku `User-Agent`.

## Cytowanie

`CITATION.cff` w korzeniu repozytorium. Wpis autorski jest zbiorczy i wymaga uzupełnienia listą
autorów osobowych przed zgłoszeniem artykułu.

## Licencja

Apache-2.0 — patrz `LICENSE.txt`. Jest to wybór **roboczy**, podyktowany tym, że czasopismo
docelowe wymaga pliku licencji w repozytorium, a tekst Apache-2.0 nie wymaga wpisywania danych
właściciela praw w samym pliku. Zmiana na inną licencję z listy dopuszczonych (MIT, BSD, GPL)
jest jednym commitem, dopóki repozytorium nie ma zewnętrznych współautorów.

Licencje danych wejściowych są osobne i niezmienne: gazeter z OpenStreetMap na licencji ODbL 1.0;
publikacje ustawowe operatorów na ich własnych warunkach korzystania, redystrybuowane wyłącznie
tam, gdzie jest to dozwolone.
