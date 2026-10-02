---
title: Metoda wydobycia
---

# Metoda wydobycia

Zamiast wyrażeń regularnych na spłaszczonym tekście — wydobycie z **położenia słów na stronie**.

* **`ruled`** — granice kolumn brane z pionowych **krawędzi wektorowych** zapisanych w pliku
  (TAURON, Stoen, ENERGA). Pusta komórka jest odgrodzona linią, więc nie może zlać się
  z sąsiednią. W dokumencie ENERGI siatki nie tworzą obiekty linii, lecz 176 cienkich
  prostokątów — strategia działa na nich poprawnie.
* **`banded`** — granice z pionowych korytarzy bieli (Boryszew; dokument bez siatki).
* **arkusz** — PSE czytany wprost z komórek, **wraz z formatowaniem znaku**. Bez tego indeksy
  górne oznaczające przypisy sklejają się z treścią, a w polach liczbowych niszczą wartość.
  Odcięcie następuje po formatowaniu, nie po zgadywaniu końca napisu — zgadywanie okaleczyłoby
  prawdziwe nazwy stacji kończące się literą.
* Wiersze wielolinijkowe scalane kolumna po kolumnie po numerze porządkowym.
* Zawijany nagłówek w wąskich kolumnach odczytywany geometrycznym przypisaniem słów nagłówka
  do kolumn.

## Dlaczego `pdfplumber`

Daje bezpośredni dostęp do współrzędnych słów i krawędzi wektorowych. `camelot` w trybie lattice
odtwarza granice kolumn z rastra i wymaga Ghostscriptu, `tabula` wymaga JVM — w obu granica
kolumny jest **wynikiem detekcji na obrazie**, a nie liczbą z pliku.

## Co to zmieniło, zmierzone

Audyt zlicza wiersze, w których niepusta wartość stoi w polu, do którego nie może należeć.
W dokumencie TAURONA: **767 z 10 559 = 7,264%** przy wydobyciu regexowym, **0 z 10 955 = 0,000%**
przy wydobyciu z układu kolumn. Stary parser **gubił także wiersze**: numery porządkowe w nowym
wydobyciu biegną 1…10 955 bez luk i duplikatów, czyli odzyskiwał o 396 wierszy mniej.

Wynik 0,000% należy czytać zgodnie z tym, co mierzy: audyt jest **detektorem wewnętrznej
sprzeczności typu**, nie porównaniem ze wzorcem. Bezbłędność mierzy zbiór odniesienia —
zob. [walidacja](walidacja.md).

```python
from gridqueue import audit_column_shift
a = audit_column_shift(df)
a.udzial, a.n_wierszy, a.szczegoly[:3]
```
