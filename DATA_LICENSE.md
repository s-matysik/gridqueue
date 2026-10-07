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


## Dlaczego dokumenty źródłowe nie są dołączone do repozytorium

Repozytorium zawiera **manifest** dokumentów (adres, data pobrania, rozmiar,
suma SHA-256) oraz skrypt `reproducibility/fetch_sources.py`, który je pobiera
i weryfikuje. Nie zawiera samych dokumentów. Powody są dwa i oba są praktyczne,
a nie ostrożnościowe.

**Po pierwsze, statusu prawnego redystrybucji nie rozstrzygamy.** Polskie prawo
autorskie wyłącza z ochrony materiały urzędowe, ale ujawnienia, o których mowa,
sporządzają i publikują spółki prowadzące działalność gospodarczą, wykonując
obowiązek ustawowy — a to, czy mieszczą się one w tej kategorii, nie jest
przesądzone. Niezależnie od prawa autorskiego do zbiorów danych może mieć
zastosowanie ochrona *sui generis*. Nie jesteśmy w stanie tego rozstrzygnąć
i nie udajemy, że jesteśmy; zespół zamierzający dołączyć dokumenty do
publikacji powinien uzyskać opinię prawną.

**Po drugie, dokumenty są wymieniane.** Obowiązek wyznacza co najmniej
kwartalną aktualizację, więc kopia złożona w repozytorium po kilku miesiącach
przedstawiałaby stan, którego już nie ma, i byłaby myląca tym bardziej, im
bardziej wyglądałaby na aktualną.

Konsekwencję trzeba powiedzieć wprost, bo jest niewygodna: **odtworzenie co do
bajtu przestaje być możliwe, gdy publikujący wymieni albo przeniesie dokument.**
Podczas przygotowania wydania 1.3.0 odsyłacz do ujawnienia jednego z operatorów
przestał prowadzić do pliku i zaczął zwracać stronę serwisu — skrypt pobierający
rozpoznaje ten przypadek i zgłasza go osobno, zamiast zapisać stronę jako
dokument. Dlatego sumy kontrolne są w manifeście: niezgodność jest sygnałem, że
liczby nie będą identyczne z opublikowanymi, a nie usterką do zignorowania.

Zespołowi przygotowującemu publikację zalecamy **depozyt dokumentów w archiwum
z trwałym identyfikatorem**, o ile opinia prawna na to pozwoli. Jest to jedyny
sposób, by odsyłacz w artykule prowadził do tego, co faktycznie analizowano.
