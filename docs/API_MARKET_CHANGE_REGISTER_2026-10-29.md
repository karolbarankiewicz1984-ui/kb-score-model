# API Market — rejestr zmian i protokół eksperymentu
Data utworzenia: 2026-10-29 (Europe/Warsaw)
Status: PLAN / audyt wstępny. Brak zgody na automatyczne wdrożenie do produkcji.
Zakres: wyłącznie API Market; bez zmian KB Score 2.1, MULTIMODEL, KB Score 3.0.

## Zasady niezmienności
- Produkcyjne oceny, progi >=67, kurs >=1.20, wagi, historia, PDF i mechanizm publikacji pozostają bez zmian.
- Wszystkie propozycje eksperymentalne powstają z tego samego snapshotu PRZED meczem, z datą UTC, ID runu i hashem danych. Zamrożone selekcje są nieedytowalne.
- Wynik dołączany po meczu jako osobny settlement; brak statystyki = unresolved, nie loss.
- Nie wolno selekcjonować historycznych propozycji po obejrzeniu wyników ani używać przyszłych danych do kalibracji.

## RZ-01 — audyt selekcji krótkiej listy
Cel: odróżnić pełny skan, główną listę opublikowaną, późniejszy freeze i praktyczny PDF.
Dane: fixture_id, kickoff, market/scope/team/direction/line, score, quote/odds/bookmaker/time, snapshot/run/commit, published flag, selected flag, settlement/VOID.
Kontrole: zgodność dat i hashy, dokładna tożsamość rynku, liczba unikalnych meczów, pozycje nieustalone, wykluczenie look-ahead i zduplikowanych linii.
Miary: hit-rate z n i CI grupowanym po meczu; dzienny raport krótkiej listy osobno; wyniki według rynków, kierunków, score band (api vs final).
Termin: natychmiast audyt historyczny tylko tam, gdzie zachowano rzeczywiste pre-match freeze; następnie codziennie po settlement.

## RZ-02 — eksperyment A/B/C/D w trybie shadow
A: obecna reguła, score >=67 i quote >=1.20, najwyżej jedna propozycja na mecz.
B: jak A, ale score >=75.
C: ranking po niezależnej historycznej wiarygodności danego market/scope/direction; tylko kalibracja trenowana na wcześniejszych datach; fallback A przy zbyt małej próbie.
D: ranking po szacowanym EV na dokładnym kursie pre-match, ale wyłącznie po zweryfikowanej kalibracji i dostępności kursu; w przeciwnym razie abstain.
Wszystkie warianty: identyczny zbiór snapshotów, identyczne zasady settlement, max 1/mecz; każda decyzja z kodem reguły i wersją. Raport coverage, n picks, n fixtures, hit-rate, Brier/logloss tylko dla rzeczywistych prognoz p, ROI tylko przy identycznych zapisanych pre-match odds. Test bez zmiany produkcji.
Termin: po audycie RZ-01 i weryfikacji pól źródłowych; checkpoint po 50 unikalnych meczach (diagnostyczny), 100–150 (pierwsza ocena), wdrożenie wyłącznie po silniejszej walidacji poza próbą.

## RZ-03 — rozdzielenie prognozy od wyniku finansowego
Warstwa predykcyjna: kalibracja p, Brier, logloss, reliability plots, oddzielne rynki i kierunki; score /100 NIE jest p.
Warstwa finansowa: kurs tego samego market/team/line/scope i czas quote < kickoff, wynik przy jednostkowej stawce, ROI z n; brak kursu = ROI unavailable; nie zakładać STS/Superbet.
Dodatkowo: klastrowanie po fixture i daty chronologiczne, brak niezależności wielu wariantów jednego spotkania.
Termin: równolegle z RZ-02; miesięczne zestawienia i porównanie do A.

## RZ-04 — zasady podejmowania decyzji
Do 100–150 unikalnych spotkań: zero automatycznej zmiany wag/progów.
Po 100–150: porównanie A/B/C/D na tych samych meczach, rozkład po ligach i rynkach, próba niezależna chronologicznie, niepewność klastrowa, liczba braków, stabilność.
Warunki kandydata do wdrożenia: brak przecieków; wystarczająca liczba niezależnych meczów; istotna i stabilna przewaga nad A w z góry wybranym celu (accuracy-first), bez nieakceptowalnego spadku coverage; ROI tylko gdy komplet kursów. W przeciwnym razie kontynuować zbieranie.
Wdrożenie: osobna decyzja użytkownika, PR, testy i możliwość rollback. Nigdy samoczynnie.

## Stan kontroli 2026-10-29
Repo: karolbarankiewicz1984-ui/kb-score-model.
Odczytano data/api_football/calibration/_summary.json: 56142 obserwacje, 405 fixtures, published:True 8724/9743; published:False 18892/46399; status:ACCEPT 6468/7370.
Uwaga: _summary zawiera odrębne api_band i final_band, nie wolno ich scalać.
Odczytano reports/api_market_scan/2026-10-28.md: 5 spotkań, 137 wariantów, 7 na liście głównej; quote timestamp 2026-10-28T16:12:18Z.
Odczytano .github/workflows/api-market-scan.yml: osobne etapy raw scan i ranking/PDF, co wymaga pilnowania identycznego snapshotu.
Na tym etapie nie ma udowodnionego przewagi B/C/D nad A. Brak nowego produkcyjnego wdrożenia.

## Rejestr decyzji
2026-10-29: zatwierdzono wyłącznie plan badawczy; bez zmian produkcji. Każdą przyszłą zmianę dopisać z datą, powodem, n fixtures, metrykami, wersją i decyzją użytkownika.
