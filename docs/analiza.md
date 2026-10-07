---
title: Warstwa analityczna
---

# Warstwa analityczna

Adaptery są specyficzne dla publikującego. Wszystko powyżej schematu już nie —
i o to w całym pakiecie chodzi. Ta strona opisuje dwie analizy, które stają się
możliwe dopiero po harmonizacji.

## Obciążenie węzła, czyli kryterium „dostępna moc przyłączeniowa"

Przeglądy literatury o lokalizowaniu infrastruktury sieciowej wymieniają
dostępną moc przyłączeniową jako kryterium częste i zarazem niemierzalne —
z powodu braku danych w źródłach otwartych. Jest mierzalne, o ile publikujący
ujawnia jednocześnie moc dostępną w węźle **i** skład stacji wchodzących do
węzła. W panelu robi to jeden publikujący.

```python
from gridqueue import station_node_map, assign_to_nodes, node_loading

mapa = station_node_map(panel)              # stacja -> grupa stacji
panel = assign_to_nodes(panel, mapa)        # przypisanie wniosków do grup
L = node_loading(panel, pole_mocy="moc_wprowadzana")
L[["nazwa_wezla", "wnioskow", "moc_wnioskowana", "moc_dostepna", "obciazenie"]]
```

**Kluczem jest grupa stacji, nie wiersz węzłowy.** Publikujący wystawia tę samą
grupę dwa razy — osobno dla kierunku wytwórczego i odbiorczego — więc
odwzorowanie po identyfikatorze wiersza czyniłoby każdą stację dwuznaczną.
Byłby to artefakt układu dokumentu, a nie własność sieci.

**Przypisanie jest nazwowe, nie topologiczne.** Opiera się na zgodności nazw
ujawnionych przez publikującego, nie na modelu sieci, a jego trafności nie
walidowano wobec wzorca zewnętrznego, bo taki nie istnieje. Status dopasowania
jest zwracany jawnie i rozróżnia pięć przypadków:

| status | znaczenie |
|---|---|
| `EXACT` | nazwa stacji równa lokalizacji po normalizacji |
| `EXTENDED` | lokalizacja zawiera nazwę stacji jako ciągły podciąg tokenów |
| `LINE` | obiekt planowany **na linii** między stacjami — nie w węźle |
| `AMBIGUOUS` | pasuje więcej niż jedna grupa |
| `NONE` | brak trafienia albo brak lokalizacji |

Kategoria `LINE` istnieje, bo wpisy w rodzaju „planowany RS w linii 110 kV
relacji A – B" opisują obiekt leżący **między** węzłami. Dopasowanie po nazwie
przypisałoby im pełną moc do tego końca linii, który akurat występuje w wykazie
stacji — co jest arbitralne. Takie wnioski zostają nieprzypisane i policzone
osobno.

Węzeł o zerowej ujawnionej mocy dostępnej dostaje iloraz `NaN`, nie
nieskończoność: iloraz jest tam **nieokreślony**, a uśrednianie go byłoby
błędem. Moc wnioskowana jest przy nim mimo to zachowana, bo kolejka do węzła
bez wolnej mocy jest informacją, nie brakiem danych.

## Czas rozpatrywania z cenzurowaniem

Wniosek bez daty rozstrzygnięcia **nie jest brakiem danych**: jest obserwacją
uciętą na dacie publikacji edycji. Liczenie mediany wyłącznie na przypadkach
kompletnych zaniża ją, i to tym silniej, im dłuższy jest rzeczywisty czas
rozpatrywania — czyli najmocniej tam, gdzie zależy nam na wyniku.

```python
from gridqueue import processing_time, kaplan_meier

d = processing_time(panel)                       # czas_dni + zdarzenie (1/0)
km = kaplan_meier(d["czas_dni"], d["zdarzenie"])
km.as_dict()["mediana"], km.as_dict()["udzial_cenzurowanych"]
```

Estymator Kaplana-Meiera zaimplementowano wprost, z wariancją Greenwooda, żeby
nie wprowadzać zależności od biblioteki analizy przeżycia dla jednego
estymatora. Przedział dla mediany wyznaczany jest przez odwrócenie pasa ufności
krzywej.

## Czułość dopasowania wzdłużnego

`linkage_audit` mierzy **precyzję**: czy połączone pary dotyczą tej samej
sprawy. `linkage_recall` mierzy **czułość**: ile par klucz pominął. Te drugie
są groźniejsze, bo rozerwana para pojawia się jako jeden wiersz „ubyły" i jeden
„nowy", więc wygląda jak zdarzenie w rejestrze, a jest artefaktem dopasowania.

```python
from gridqueue import linkage_recall

r = linkage_recall(edycja_a, edycja_b)
r.as_dict()["czulosc_klucza"]
r.odzyskane["pola_klucza_rozne"].value_counts()
```

Pola tożsamości użyte do odzyskania muszą być **rozłączne z kluczem**. Pole
wspólne z kluczem nie wykryje pary rozerwanej zmianą właśnie tego pola, bo
tożsamość rozjedzie się razem z kluczem. Zmierzone na parze edycji operatora
przesyłowego: dołożenie lokalizacji do zestawu tożsamości podnosi pozorną
czułość z 0,9652 do 0,9757, a w rzeczywistości ukrywa dziesięć par.
