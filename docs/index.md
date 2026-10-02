---
title: gridqueue
---

# gridqueue

Harmonizator ustawowych ujawnień przyłączeniowych do sieci elektroenergetycznej.
Wersja **0.3.1** · [repozytorium](https://github.com/s-matysik/gridqueue)

> **In English.** `gridqueue` parses the statutory grid-connection disclosures that Polish
> distribution system operators must publish under Article 7(8l) of the Energy Law, and emits
> rows in a single 21-field schema with **measured** extraction accuracy. Six adapters cover two
> jurisdictions; the schema is derived from the legal obligation, not from any one document.
> Failures are returned as missing-with-reason, never as guesses.

## Problem

Operatorzy systemów dystrybucyjnych mają obowiązek publikować, kto ubiega się o przyłączenie,
gdzie, o jaką moc i na jakim etapie stoi postępowanie. W Polsce obowiązek dotyczy około
180 koncesjonowanych operatorów i **każdy publikuje we własnym formacie** — najczęściej jako
dokument do druku. Informacja jest jawna, ale nie jest przetwarzalna.

Niejednorodność dotyczy jednak **nośnika, nie pojęć**. Arkusz operatora przesyłowego zawiera
listę dopuszczalnych wartości pola publikującego, wymieniającą sześciu największych operatorów
w kraju — formularz jest więc uzgodnionym wzorcem sprawozdawczym, który każdy z nich wypełnia,
tylko jeden wydaje go jako arkusz, a drugi jako dokument do druku. Wspólny schemat tego pakietu
jest odtworzeniem tego uzgodnienia.

## Czego pakiet nie robi

Nie jest indeksem publikacji operatorów ani mapą przeglądową. Nie jest też oszacowaniem dostępnej
mocy przyłączeniowej: rejestr ujawnia **kolejkę, nie zapas**. Nie jest rankingiem lokalizacji —
nie zawiera żadnego modelu preferencji.

## Stan wydania

| publikujący | wierszy w panelu | pól z ujawnienia | pól łącznie z wyprowadzonym |
|---|---:|---:|---:|
| TAURON Dystrybucja S.A. | 10955 | 15 | 15 |
| ENERGA-OPERATOR S.A. | 5382 | 17 | 17 |
| Stoen Operator Sp. z o.o. | 1236 | 13 | 14 |
| PSE S.A. | 945 | 17 | 17 |
| National Grid Electricity Distribution | 694 | 10 | 10 |
| Boryszew Green Energy&Gas Sp. z o.o. | 8 | 8 | 9 |

**Wszystkie 21 pól schematu jest wypełnionych w panelu.** Pole współrzędnych nie jest ujawniane
przez żadnego publikującego i powstaje przez wyprowadzenie z nazwy miejsca — dlatego w tabeli
rozdzielono pola z ujawnienia od pola wyprowadzonego, a w wyniku każdego rozwiązania zapisany jest
poziom pewności i poziom dokładności umiejscowienia.

## Strony

* [Schemat 21 pól](schemat.md)
* [Adaptery i jak dodać publikującego](adaptery.md)
* [Metoda wydobycia](wydobycie.md)
* [Reguły kontroli jakości](jakosc.md)
* [Zmierzona walidacja](walidacja.md)
* [Wiersz poleceń](cli.md)
* [Ograniczenia](ograniczenia.md)

## Instalacja

```bash
git clone https://github.com/s-matysik/gridqueue
cd gridqueue
pip install -e ".[test]"
python -m pytest -q
```

## Najkrótszy przykład

```python
from gridqueue import get_adapter, run_quality, audit_column_shift

res = get_adapter("pl_tauron").parse("tauron_informacja.pdf")
df = res.frame                        # ramka w 21-polowym schemacie
res.report["n_wierszy"]               # 10955
audit_column_shift(df).udzial         # 0.0
run_quality(df).as_dict()["naruszen_lacznie"]
```
