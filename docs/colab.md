---
title: Google Colab
---

# Uruchomienie w przeglądarce

[![Otwórz w Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/s-matysik/gridqueue/blob/main/notebooks/gridqueue_colab.ipynb)

Notatnik `notebooks/gridqueue_colab.ipynb` usuwa barierę instalacyjną: recenzent albo analityk
regulatora uruchamia pełny przebieg bez instalowania czegokolwiek, bez konta i bez akceleratora.

## Co notatnik wykonuje

1. instaluje pakiet z **oznaczonego wydania**, nie z gałęzi głównej, więc wynik nie zależy od
   bieżącego stanu repozytorium;
2. pobiera dwie kolejne edycje ujawnienia wprost od publikującego i wypisuje sumy kontrolne;
3. rozpoznaje publikującego **z zawartości dokumentu** i wydobywa wiersze wspólnego schematu;
4. ocenia osiem reguł kontroli jakości;
5. liczy przepływy w kolejce między edycjami oraz **precyzję dopasowania** na polach wyłączonych
   z klucza;
6. porównuje odtworzone liczby z opublikowanymi w artykule i **przerywa wykonanie przy rozjeździe**.

Punkt szósty jest odpowiednikiem asercji z katalogu `reproducibility/`. Rozjazd nie musi oznaczać
błędu — publikujący mógł wymienić edycję — ale musi być widoczny, a nie przemilczany.

## Czego notatnik nie robi

Nie odtwarza dokładności wydobycia wobec zbioru odniesienia, bo ten wymaga odczytu przez człowieka.
Nie rozstrzyga współrzędnych, bo gazeter geometryczny jest osobnym pobraniem i podlega ODbL,
a notatnik nie powinien po cichu wciągać użytkownika w obowiązki licencyjne. Nie uruchamia też
przykładu przekrojowego na tym publikującym, bo **nie spełnia on kryterium pokrycia dat**
postawionego przed policzeniem wyniku — notatnik pokazuje to wprost, zamiast policzyć medianę
na kilkunastu procentach rekordów.

## Gdy pobranie się nie powiedzie

Dwie sytuacje są przewidziane i obie kończą się komunikatem, nie wyjątkiem.

**Kod 404.** Edycje przesuwają się w czasie, a starsze bywają usuwane po wymianie. Pobierz bieżący
wykaz ze strony publikującego, wgraj go przez panel plików i wpisz nazwę do słownika `pliki`.

**Błąd weryfikacji certyfikatu.** Typowe w sieciach firmowych i instytucjonalnych z serwerem
pośredniczącym, który podmienia łańcuch certyfikatów; w Colab nie występuje. Notatnik **nie obchodzi
tej kontroli** i kieruje do wgrania pliku ręcznie.

## Pozycja notatnika wobec CI

Ciągła integracja **nie uruchamia** notatnika, bo ten sięga po dokumenty wymieniane kwartalnie,
a zadanie zależne od zewnętrznej publikacji psułoby się bez związku z kodem. Osobne zadanie
sprawdza natomiast to, co sprawdzić można bez sieci: czy wszystkie komórki kodu są poprawne
składniowo i czy każda nazwa importowana z pakietu faktycznie w nim istnieje. To właśnie ta
druga kontrola odpowiada defektowi, który ujawniło pierwsze uruchomienie notatnika —
dokumentacja obiecywała metodę `as_frame`, której pakiet nie miał.
