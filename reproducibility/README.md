# Pakiet odtwarzalności

Co tu jest i czego to dowodzi.

| plik | zawartość |
|---|---|
| `manifest.csv` | jeden wiersz na dokument źródłowy: publikujący, jurysdykcja, adapter, adres, data pobrania, rozmiar, SHA-256 |
| `checksums.txt` | te same sumy w formacie `sha256sum -c` |
| `requirements-lock.txt` | wersje bibliotek odczytane ze środowiska, w którym policzono opublikowane liczby |
| `environment.yml` | środowisko do odtworzenia od zera |
| `run_validation.py` | odtwarza liczby pochodne z panelu: pokrycie pól, osiem reguł jakości, kompletność rdzenia |
| `run_figures.py` | odtwarza trzy figury wyliczane z panelu |

## Dokumenty źródłowe nie są tu redystrybuowane

Dwa powody, oba rzeczowe. Część dokumentów jest objęta prawami publikujących, a wszystkie są
**wymieniane co najmniej raz na kwartał** na mocy art. 7 ust. 8l Prawa energetycznego — kopia
w repozytorium zestarzałaby się w ciągu trzech miesięcy i zaczęłaby fałszywie sugerować, że
opisuje stan bieżący.

Zamiast kopii jest manifest. Dla każdego dokumentu podaje adres, datę pobrania i SHA-256, więc
osoba odtwarzająca pracę może:

1. pobrać plik z podanego adresu i sprawdzić sumę — zgodność oznacza identyczne wejście;
2. stwierdzić niezgodność sumy, co oznacza, że publikujący wydał **inną edycję rejestru**, i wtedy
   należy oczekiwać innych liczb wierszy. To nie jest awaria odtwarzania, lecz właściwość
   kwartalnego obowiązku.

```bash
cd <katalog_z_dokumentami> && sha256sum -c /ścieżka/do/checksums.txt
```

## Odtworzenie

```bash
pip install git+https://github.com/s-matysik/gridqueue@v1.0.0
gridqueue parse <dokumenty...> --out panel.parquet
python reproducibility/run_validation.py panel.parquet
python reproducibility/run_figures.py panel.parquet
python examples/research_use_case.py panel.parquet
```

`run_validation.py` kończy się kodem niezerowym, jeśli suma naruszeń po publikujących nie domyka
się do liczby panelowej — ta asercja wyłapała realną pomyłkę w wersji 0.3.x, gdzie tabela
w dokumentacji podwajała wynik.

## Czego te skrypty nie odtwarzają

**Dokładności wobec zbioru odniesienia.** Wzorzec powstał przez wzrokowy odczyt renderowanych
wycinków stron przez człowieka, niezależnie od wyjścia parsera. Jest opublikowany jako artefakt
pomiarowy i nie da się go wyliczyć kodem — gdyby się dało, nie byłby niezależny.

**Figury architektury.** Jest schematem rysowanym ręcznie i nie ma danych wejściowych.
