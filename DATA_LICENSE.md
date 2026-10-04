# Status prawny kodu i danych

Plik `LICENSE.txt` obejmuje **wyłącznie kod** tego pakietu. Dane, na których kod pracuje,
i dane, które wytwarza, mają odrębny status i opisujemy go tutaj, bo pomylenie tych warstw
jest realnym ryzykiem przy ponownym wykorzystaniu.

## 1. Kod pakietu

Apache-2.0, zgodnie z `LICENSE.txt`. Obejmuje `src/`, `tests/`, `examples/`,
`reproducibility/` i `docs/`.

## 2. Dokumenty źródłowe publikujących

Dokumenty wydawane przez operatorów na podstawie art. 7 ust. 8l ustawy Prawo energetyczne
są **publikacjami urzędowymi wykonywanymi pod obowiązkiem ustawowym**. Pakiet ich
**nie redystrybuuje**. `reproducibility/manifest.csv` podaje dla każdego dokumentu adres,
datę pobrania, rozmiar i sumę kontrolną SHA-256, co pozwala **zweryfikować**, że pobrany
plik jest tym samym, na którym liczono wyniki.

Jest to weryfikacja, nie gwarancja odtworzenia. Obowiązek każe wymieniać publikację co
najmniej raz na kwartał, więc plik pod danym adresem **bywa zastępowany nowszym**.
Dokładne odtworzenie obliczeniowe jest zatem uwarunkowane dalszą dostępnością archiwalnych
plików źródłowych u publikujących albo ich zarchiwizowaniem przez użytkownika.

## 3. Gazeter geometryczny — OpenStreetMap

Gazeter wykorzystywany przez rozwiązywacz lokalizacji pochodzi z OpenStreetMap i podlega
**Open Database License 1.0**. Oznacza to dla użytkownika trzy obowiązki, których Apache-2.0
nie obejmuje:

- **atrybucja** — wskazanie OpenStreetMap jako źródła przy każdej publikacji wyników
  zawierających współrzędne;
- **share-alike** — udostępnienie bazy pochodnej, jeśli jest publicznie dystrybuowana,
  na tej samej licencji;
- **brak ograniczeń technicznych** — nie wolno dystrybuować bazy pochodnej w sposób
  uniemożliwiający odbiorcy korzystanie z niej na warunkach ODbL.

Rozróżnienie istotne w praktyce: *produced work* — na przykład mapa albo tabela wyników —
wymaga atrybucji, lecz nie uruchamia share-alike; *derivative database* — na przykład panel
z doklejonymi współrzędnymi, udostępniany dalej — uruchamia share-alike.

## 4. Panel wynikowy

Panel wytworzony przez pakiet jest utworem pochodnym od obu powyższych warstw.
W zakresie, w jakim zawiera **wartości wyprowadzone z gazetera** (pole `wspolrzedne`
i kolumny diagnostyczne rozwiązywacza), podlega ODbL. W zakresie, w jakim zawiera
wyłącznie treść przepisaną z dokumentów urzędowych, podlega statusowi tych dokumentów.
Kolumna `_geo_pewnosc` pozwala te dwie warstwy rozdzielić: wiersze bez rozstrzygniętej
lokalizacji nie zawierają żadnej treści pochodzącej z OpenStreetMap.

## 5. Dane osobowe

Ujawnienia dotyczą **podmiotów ubiegających się o przyłączenie**, a pole nazwy podmiotu
zawiera w zdecydowanej większości firmy spółek prawa handlowego. Ustawa nie wyłącza
jednak osób fizycznych prowadzących działalność, więc nie twierdzimy, że dane osobowe
w korpusie nie występują.

Pakiet **nie wykonuje re-identyfikacji** i nie wzbogaca rekordów danymi o osobach
z żadnego innego źródła. Rozwiązywacz lokalizacji działa na nazwie miejscowości i ulicy
podanej w dokumencie, nigdy na nazwie podmiotu. Odpowiedzialność za zgodne z prawem
dalsze wykorzystanie wyjścia, w tym za ewentualną ocenę skutków dla ochrony danych,
spoczywa na użytkowniku.
