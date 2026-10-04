# gridqueue

[![testy](https://github.com/s-matysik/gridqueue/actions/workflows/ci.yml/badge.svg)](https://github.com/s-matysik/gridqueue/actions/workflows/ci.yml)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://github.com/s-matysik/gridqueue)
[![licencja Apache-2.0](https://img.shields.io/badge/licencja-Apache--2.0-green)](LICENSE.txt)
[![dokumentacja](https://img.shields.io/badge/dokumentacja-gh--pages-blue)](https://s-matysik.github.io/gridqueue/)
[![wydanie](https://img.shields.io/github/v/release/s-matysik/gridqueue)](https://github.com/s-matysik/gridqueue/releases)
[![Otwórz w Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

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

## Uruchomienie bez instalacji — Google Colab

[![Otwórz w Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

Notatnik `notebooks/gridqueue_colab.ipynb` wykonuje **pełny przebieg badawczy w przeglądarce**:
pobiera dwie edycje ujawnienia wprost od publikującego, wydobywa wiersze, ocenia jakość, liczy
przepływy w kolejce wraz z precyzją dopasowania i **porównuje odtworzone liczby z opublikowanymi
w artykule, przerywając wykonanie przy rozjeździe**. Poniżej minuty na darmowej maszynie, bez
akceleratora i bez konfiguracji.

Notatnik nie odtwarza dokładności wydobycia wobec zbioru odniesienia, bo ten wymaga odczytu przez
człowieka, ani nie rozstrzyga współrzędnych, bo gazeter jest osobnym pobraniem na licencji ODbL.

## Instalacja

Jedno polecenie, bez kompilacji i bez usług zewnętrznych:

```bash
pip install git+https://github.com/s-matysik/gridqueue@v1.2.1
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

## Analiza wzdłużna

Rejestr **nie publikuje trwałego identyfikatora wniosku**, więc śledzenie sprawy między
edycjami wymaga klucza treściowego. `compare_editions` buduje go i zwraca przepływy oraz
macierz przejść statusu:

```python
from gridqueue import compare_editions, linkage_audit, get_adapter

a = get_adapter("pl_pse").parse("edycja_2026_07_31.xlsx").frame
b = get_adapter("pl_pse").parse("edycja_2026_08_31.xlsx").frame
d = compare_editions(a, b, "2026-07-31", "2026-08-31")
d.as_dict()["udzial_przejsc_w_przod"]   # 0.9828
d.as_dict()["migawka_monotoniczna"]     # False

linkage_audit(a, b).as_dict()           # precyzja dopasowania: 0.9888–0.9963
```

Dwa wyniki na parze edycji PSE, lipiec–sierpień 2026. **98,28 % przejść statusu biegnie
zgodnie z porządkiem postępowania** — jest to niezależny test dopasowania klucza, bo klucz
dopasowujący losowo nie wytworzyłby tego porządku. I drugi: **rejestr nie jest monotoniczną
migawką** — 13 wierszy pojawia się już w stanie zamkniętym, a 33 wiersze o statusie czynnym
znikają. Różnicy między edycjami nie wolno więc czytać jako samej zmiany stanu kolejki,
i narzędzie zgłasza to flagą, zamiast pozwolić użytkownikowi tego nie zauważyć.

Ponieważ rejestr nie ma trwałego identyfikatora, samo dopasowanie też wymaga sprawdzenia.
`linkage_audit` porównuje każdą parę na dziewięciu polach **wyłączonych z klucza** — klucz nie
wymusza ich zgodności, więc zgodność jest świadectwem niezależnym. Na wszystkich 804 parach
precyzja wynosi **98,88–99,63 %**: 795 par potwierdzonych, 6 niepewnych, 3 fałszywe.

```bash
python examples/longitudinal_use_case.py edycja_A.xlsx edycja_B.xlsx 2026-07-31 2026-08-31
```

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
python -m pytest -q      # 153 passed, 2 skipped (155 zebranych)
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

Apache-2.0 dla **kodu**. Dane wejściowe i wyjściowe mają odrębny status — dokumenty urzędowe nie są redystrybuowane, a gazeter geometryczny podlega ODbL z obowiązkiem atrybucji i share-alike. Szczegóły w [`DATA_LICENSE.md`](DATA_LICENSE.md).

Historia zmian: [`CHANGELOG.md`](CHANGELOG.md). — patrz `LICENSE.txt`. Jest to wybór **roboczy**, podyktowany tym, że czasopismo
docelowe wymaga pliku licencji w repozytorium, a tekst Apache-2.0 nie wymaga wpisywania danych
właściciela praw w samym pliku. Zmiana na inną licencję z listy dopuszczonych (MIT, BSD, GPL)
jest jednym commitem, dopóki repozytorium nie ma zewnętrznych współautorów.

Licencje danych wejściowych są osobne i niezmienne: gazeter z OpenStreetMap na licencji ODbL 1.0;
publikacje ustawowe operatorów na ich własnych warunkach korzystania, redystrybuowane wyłącznie
tam, gdzie jest to dozwolone.
