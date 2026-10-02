---
title: Wiersz poleceń
---

# Wiersz poleceń

```bash
gridqueue schema                                   # specyfikacja 21 pól
gridqueue adapters                                 # deklaracje publikujących
gridqueue parse tauron.pdf --out tauron.parquet --report tauron.json
gridqueue parse --adapter uk_nationalgrid --out uk.parquet   # pobiera z katalogu CKAN
gridqueue validate tauron.parquet --out walidacja.json
gridqueue export tauron.parquet stoen.parquet --out panel.parquet --only-schema
```

`parse` rozpoznaje publikującego z nazwy pliku, a gdy to nie wystarcza — z treści pierwszej
strony. `--adapter` wymusza wybór. `--report` zapisuje raport wydobycia: liczbę wierszy, strategię,
odtworzone numery porządkowe, pola wypełnione i napotkane anomalie.

`validate` uruchamia osiem reguł kontroli jakości oraz audyt przesunięcia kolumn i zapisuje
naruszenia wraz z wierszami, które je powodują — naruszenie nie przerywa przebiegu.

`export` scala wyniki wielu adapterów w jeden panel. `--only-schema` pomija kolumny rozszerzeń
z przedrostkiem `_`.

## Pochodzenie wyniku

Każdy wiersz niesie rekord pochodzenia: dokument źródłowy, stronę, wersję adaptera i wersję
gazetera użytego przy rozwiązywaniu lokalizacji. Ustawa wymaga kwartalnej wymiany dokumentów,
więc osoba odtwarzająca pracę na dokumentach z późniejszego kwartału pobierze inne dokumenty
i **powinna oczekiwać innych liczb wierszy** — dlatego edycja rejestru jest odnotowywana
w każdym wyniku, a nie zakładana.
