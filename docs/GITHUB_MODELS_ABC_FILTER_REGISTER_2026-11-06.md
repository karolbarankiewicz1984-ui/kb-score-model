# GitHub Models V2 — A/B/C | rejestr zmian (od 2026-11-06)

Zakres: projekt **GitHub Models V2 — A/B/C**, gałąź `codex/multimodel-v2`; harmonogram na `main`. Wcześniejszy MULTIMODEL i KB Score 3.0 pozostają bez zmian. Historyczne wpisy poniżej zachowują oryginalne nazwy sprzed rebrandingu.

## Zmiany
- `github_models/abc_filter_policy.json`: eksperymentalne progi A 70%, B 75%, C 80%, zgodność Elo/Dixon-Coles maks. 10 p.p.
- `github_models/abc_filter.py`: równoległe filtrowanie 1X2 i par over/under z kontrolą matematyki. Nie przypisuje fikcyjnego V2 Score.
- `tests/test_github_models_abc_filter.py`: testy progów, błędnych sum i par rynków.
- `github_models/abc_report.py`: czytelny raport PDF i pełny JSON kandydatów.
- `.github/workflows/github-models-independent.yml`: osobny krok generowania A/B/C na zamrożonych danych z bieżącego przebiegu; JSON i PDF w artefakcie.

## Ograniczenia i bramki
- A/B/C to klasyfikacja badawcza, nie dowód kalibracji ani wartości zakładu.
- Brak kompletnych i zweryfikowanych składowych V2 Score: nie liczyć arbitralnych 0–100.
- Przed uznaniem za zamknięte: wymagane CI SUCCESS dla commitu zawierającego workflow, rzeczywiste liczniki kandydatów i sprawdzony PDF z tego samego artefaktu.
- Stare 1226/1226 testów dotyczą wcześniejszego przebiegu.
- Nie scalać do main ani nie dotykać innych modeli.

## 2026-11-07 — naprawa opóźnionych rozliczeń
**Diagnoza z rzeczywistego przebiegu 42355073948:** 0 rozliczonych A/B/C przy 5 archiwach. Baza wyników bramkowych miała najnowszy `match_date` 2026-11-05, baza dodatkowych statystyk 2026-11-04. Importer CSV celowo dopuszcza tylko wyniki po dacie meczu + 2 dni. Nie wynika z tego, że typy przegrały.

**Nowe rozwiązanie (badawcze):**
- `github_models/fast_final_parser.py`: ścisłe parsowanie wyników `FT` i statystyk API-Football. Bez potwierdzonego kraju, ligi, jednoznacznej nazwy drużyn i rzeczywistego statusu FT — nie rozliczać.
- `github_models/fast_final_collect.py`: maks. 2 dni historii; do 24 zapytań o statystyki na przebieg. Dwa ostatnie dni dotyczą wyłącznie ROZLICZANIA, nie treningu ani rewizji prognoz. Timestamp to rzeczywisty moment obserwacji zakończonego wyniku, a nie wymyślony czas gwizdka.
- Bezpieczna agregacja: identycznych wyników dostawców nie dublować; sprzeczne zachować do oznaczenia jako niejednoznaczne. Nie imputować brakujących kartek, fauli i rożnych.
- `tests/test_github_models_fast_results.py`: testy statusów, zgodności wyników, drużyn, braku klucza i duplikatów.
- `github_models/abc_settlement.py`: zachowuje dokładną linię rynku i przyczynę nierozliczenia.
- `github_models/abc_audit_runner.py`: deduplikacja tej samej prognozy meczu/rynku/strony/linii we wszystkich migawkach. Wcześniejsze 749/475/247 były liczebnościami ze zduplikowanych archiwów, a nie unikalną próbą do oceny trafialności.
- `github_models/abc_audit_pdf.py`: raportuje deduplikację i przyczyny odmowy rozliczenia.
- Główny harmonogram: `.github/workflows/github-models-v2-daily-audit.yml` na `main`, uruchamiany codziennie i przy zmianie workflow. Nowy etap pozyskiwania API-Football ma dostęp wyłącznie do danych końcowych, a w fazie forecast korzysta się nadal z poprzedniej bazy.

**Ograniczenia i bramki:**
- API-Football może nie pokrywać wszystkich lig oraz statystyk; brak wyniku jest `unresolved`, nigdy porażką.
- Potwierdzenie działania: testy PASS, cały przebieg SUCCESS, dodatnia liczba rzeczywiście zweryfikowanych wyników 2026-11-06 i niezależna kontrola liczb Brier/log loss. Brak sukcesu na którejkolwiek bramce pozostaje otwartą usterką.
- Progi A/B/C i model produkcyjny bez zmian. Nie podnosić oceny skuteczności bez nowej próby.

## 2026-11-07 — pierwsza rzeczywista weryfikacja naprawy
- GitHub Actions QUICK run: `42365011332`, status **SUCCESS**, artefakt `v2-repair-verified-results-42365011332`.
- Źródło API-Football 2026-11-06: 347 finalnych rekordów, 20 zaakceptowanych zweryfikowanych wyników zgodnych z obowiązującymi mapowaniami, 9 spotkań ze statystykami zdarzeń; 12 odpytań szczegółowych.
- Audyt 6 archiwów: 3129 rekordów surowych, 1922 unikalnych propozycji, 1207 powtórzonych rekordów odjętych; 3 rewizje prawdopodobieństw odnotowane.
- A: 51 rozliczonych / 40 trafień, 19 unikalnych meczów, Brier 0.1632, log loss 0.5003. B: 27 / 22, 14 meczów, Brier 0.1431, log loss 0.4490. C: 15 / 13, 7 meczów, Brier 0.1087, log loss 0.3613.
- 1X2: 0 rozliczonych. Liczebność nadal niewystarczająca do kalibracji; brak jakichkolwiek uzasadnionych zmian A/B/C.
- Wystąpiły błędy HTTP w odpytywaniu 2026-11-05 i części statystyk; te dane pozostają nierozliczone. 316 lig/rekordów nie przeszło rygorystycznego zatwierdzenia tożsamości rozgrywek.
- Dodano później osiem nowych, ligowo ograniczonych aliasów po sprawdzeniu dosłownego historycznego odpowiednika. Nie dopuszczono Swiss Challenge League bez historii. Te aliasy nie uczestniczyły w powyższym wyniku.
- Osobny szybki test zakończony SUCCESS; pełny zaktualizowany dzienny przebieg pozostaje do odrębnego potwierdzenia. Automatyczne zmiany progów zabronione.


## 2026-11-07 — ujednolicenie raportów PDF A/B/C (wyłącznie prezentacja)
- Nowy wspólny standard graficzny: `github_models/abc_pdf_style.py` (DejaVu Sans, polskie znaki, A4, nagłówki, tabele, paginacja, stopka).
- `github_models/abc_report.py`: każdy codzienny PDF ma te same sekcje: informacja o dacie i cutoff, porównanie A/B/C, trzy czytelne wykazy rynków, krótki przekrój do 3 najwyższych prognoz na rynek w każdym wariancie oraz ograniczenia.
- Pełna lista kandydatów zachowana w `ABC_YYYY-MM-DD.json`. PDF to przegląd: selekcja wyświetlanych pozycji nie zmienia progów ani listy JSON.
- `github_models/abc_audit_pdf.py`: ten sam wygląd, podsumowanie rozliczeń A/B/C, Brier i log loss, rozliczenia rynków i jawne powody nierozliczenia.
- Brak zweryfikowanego kursu jest oznaczony jako `brak`; nie pobiera się ani nie wymyśla kursów. Warunek przyszłej selekcji bukmacherskiej: tylko kurs exact-market **>= 1,20**, potwierdzony przed meczem.
- Wprowadzono `tests/test_github_models_abc_pdf.py` (bezpieczne prezentowanie braków, nazwy rynków, zachowanie pełnego JSON, kontrola wygenerowania i odczytu PDF).
- **Brak ingerencji w modele, ich wagi, progi 70/75/80%, źródła, archiwa, rozliczanie i workflow**. Gałąź wyłącznie `codex/multimodel-v2`; brak merge do `main`.

**Bramka weryfikacyjna:** nowy układ jest zapisany w kodzie; testy jednostkowe i pełny przebieg dzienny na nowym commicie wymagają osobnego potwierdzenia. Nie uznawać statusu CI SUCCESS bez dowodu.

- Dodano lekki workflow kontroli PDF: `.github/workflows/github-models-abc-pdf-check.yml` (tylko gałąź badawcza, smoke test generatorów). Jego wynik nie został jeszcze potwierdzony; nie przypisywać PASS przed odczytem GitHub Actions.

**Potwierdzenie testu (2026-11-07):** GitHub Actions `42397986020` — `GitHub Models ABC PDF regression (research branch)`, wynik **SUCCESS**, commit `aefb5f4586c4b8a2fa8db23afd857e7567fcb520`. Testy obejmują renderowanie A/B/C i audytu na danych syntetycznych oraz podstawowe zabezpieczenia formatowania; nie stanowią dowodu zakończenia pełnego dziennego przebiegu na najnowszym kodzie. Raport demonstracyjny z archiwum `42365229210` odtworzony lokalnie ma 408 meczów, A=815, B=538, C=295 (odrębny przebieg od wcześniejszego PDF 413/819/542/297).

## 2026-11-07 — PODSUMOWANIE DECYZJI I STAN REALIZACJI (wpis porządkujący)

**Decyzja użytkownika: „Ujednolić” i „Zapisz wszystko do rejestru”.** Ten wpis jest aktualnym podsumowaniem końcowym zmian prezentacyjnych; wcześniejsze robocze uwagi „test jeszcze niepotwierdzony” pozostają historią, ale w zakresie krótkiego testu PDF zostały zastąpione poniższym potwierdzeniem. Nie nadpisuje on prognoz ani źródeł danych.

### Wymagany stały format codziennego raportu A/B/C
1. Jeden konsekwentny układ A4 we wszystkich dniach i również w PDF audytowym: DejaVu Sans, polskie opisy, tabele, sekcje, paginacja i stopka.
2. Strona otwierająca: data, strefa Europe/Warsaw dla godziny meczu, czas zamrożenia (lub jawny brak jego potwierdzenia), liczba meczów, podsumowanie A/B/C, ostrzeżenia.
3. Progi **A 70%, B 75%, C 80%** pozostają bez zmian. Zawsze podawać liczbę propozycji *i* liczbę unikalnych meczów; warianty są zagnieżdżone/nakładające się, dlatego nie sumować ich jako niezależnych próbek.
4. Każdy wariant: czytelny przekrój najważniejszych propozycji w każdym rynku (maksymalnie trzy najwyższe niekalibrowane P na rynek; nie przedstawiać tego jako TOP do gry). Rynek po polsku: „Bramki/Faule/Żółte kartki/Rożne: Powyżej/Poniżej X,X” albo „Wynik meczu 1/X/2”; identyfikacja meczu, P modelu, godzina rozpoczęcia, jawny status kursu.
5. Pełny, nieskrócony zbiór kandydatów nadal w **`ABC_YYYY-MM-DD.json`**; PDF stanowi krótkie podsumowanie do czytania. Nie wolno przez skracanie PDF modyfikować JSON, progów, wag, wyboru modelu czy archiwów.
6. **Kursy:** nie wymyślać kursów ani bukmachera. Dopiero po potwierdzeniu dokładnego rynku, źródła, czasu notowania przed meczem i kursu **>= 1,20** można zakwalifikować propozycję do części bukmacherskiej. Bez tych dowodów oznaczać „brak” / „OBSERWACJA”; nie wyliczać nieuzasadnionego ROI, „value”, V2 Score ani pewności gry.
7. Osobny PDF rozliczeniowy w identycznej stylistyce: A/B/C, liczby rozliczonych/trafionych/nierozliczonych, **unikalne mecze**, rynki, Brier, log loss, powody odmowy rozliczenia; brak wyniku ≠ przegrana. Zawsze pokazywać ograniczenia próby.
8. Brak zmian w bazowym MULTIMODELU, KB Score 3.0 ani na `main`. Zmiany wyłącznie na `codex/multimodel-v2`.

### Zapisane pliki i dowody
- Wspólny szablon: `github_models/abc_pdf_style.py`.
- Raport prognoz: `github_models/abc_report.py`.
- Raport audytu: `github_models/abc_audit_pdf.py`.
- Test regresyjny: `tests/test_github_models_abc_pdf.py`.
- Wydzielony workflow testowy: `.github/workflows/github-models-abc-pdf-check.yml`.
- Rejestr zmian: `docs/GITHUB_MODELS_ABC_FILTER_REGISTER_2026-11-06.md`.
- **Potwierdzenie:** [GitHub Actions #42397986020](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42397986020), status `SUCCESS`; regresja formatu PDF na danych testowych, nie pełne przebiegi modeli.
- **Raport przykładowy:** lokalnie odtworzony `MULTIMODEL_V2_ABC_2026-11-07_UJEDNOLICONY.pdf` z archiwalnego artefaktu run `42365229210`. Nie jest to commitowany plik repo ani dowód uruchomienia nowego codziennego workflow w produkcji.
- **Różnice danych:** wcześniejszy `ABC_2026-11-07.pdf`: 413 meczów / A 819 / B 542 / C 297; nowszy odtworzony artefakt: 408 meczów / A 815 / B 538 / C 295. Rozbieżność wynika z różnych przebiegów/artefaktów, nie należy łączyć ich w jedną próbę.
- **Dotychczasowy audyt wyników (bez związku z korektą szablonu):** A 40/51 (78,4%, 19 meczów), B 22/27 (81,5%, 14 meczów), C 13/15 (86,7%, 7 meczów); liczebności zbyt małe do wnioskowania o trwałej skuteczności. Rynki fauli 10/10 w A na małej próbie; bramki 21/30 w A wymagają osobnej analizy. Wyniki A/B/C nakładają się.

### Pozostałe bramki i dalsze działania
- **ZROBIONE:** wdrożenie kodu i rejestru na gałęzi badawczej, ujednolicenie obu generatorów oraz test smoke/regresyjny ze statusem SUCCESS.
- **NIEPOTWIERDZONE:** pełny, nowy dzienny workflow po aktualizacji kodu, jego PDF/JSON z tego samego zamrożonego przebiegu i prawidłowe dostarczenie raportu użytkownikowi. Do czasu potwierdzenia nie ogłaszać pełnego wdrożenia.
- **NIEZROBIONE:** integracja rzeczywistych kursów bukmacherskich exact-market i wynikający z tego test ROI; prognozy nadal niekalibrowane. Nie sugerować, że wymóg >=1,20 filtruje już aktualny arkusz kandydatów.
- **WYMAGANE:** zweryfikować pełny workflow oraz identyczność liczb i źródeł JSON ↔ PDF; sprawdzić szczególnie czas freeze, brakujące kursy, kompletność identyfikacji rynków i statystyk; zebrać 100–150 unikalnych rozliczonych spotkań przed decyzjami o kalibracji.
- **ZAKAZ:** brak automatycznych zmian progów, modelu, danych historycznych i merge do `main` bez odrębnej decyzji.

**Kryterium zamknięcia zadania:** test formatu **ZALICZONY**, zapis w rejestrze **WYKONANY**; pełne uruchomienie i automatyczna publikacja nowego standardu **DO POTWIERDZENIA**.


## 2026-11-08 — zmiana formatu A/B/C na TOP + pełen harmonogram meczów

**Wymaganie użytkownika:** Na początku PDF mają znajdować się najsilniejsze pozycje, a następnie wszystkie zakwalifikowane rynki i linie każdego spotkania dnia, zgodnie z godziną rozpoczęcia w Europe/Warsaw. Każda pozycja ma własną procentową ocenę modelu.

**Nowy standard prezentacji:**
1. Nagłówek podaje datę, strefę Europe/Warsaw, źródło i cutoff lub brak potwierdzenia cutoff. Niekalibrowane P i brak zweryfikowanego kursu zawsze pozostają jawne.
2. Tabela liczebności dla A (70%), B (75%), C (80%) oraz unikalne mecze.
3. Skrót TOP: maksymalnie 12 najwyższych surowych ocen P, maksymalnie 3 propozycje z jednego rynku, maksymalnie 1 pozycja na mecz. Jest to ranking orientacyjny, a nie rekomendacja stawek.
4. **Pełny harmonogram:** każdy mecz daty raportu występuje raz, chronologicznie według polskiej godziny rozpoczęcia. Poniżej wszystkie zakwalifikowane pozycje bez limitu: wynik 1X2, bramki, faule, kartki, rożne, wszystkie linie i kierunki, procent P, wariant(y), status kursu.
5. Identyczna prognoza występująca równolegle w A, B, C jest pokazywana raz z oznaczeniem A, A/B albo A/B/C. Osobne linie (np. faule powyżej 19,5 i 22,5) oraz prognozy różnych modeli pozostają oddzielne. Sprzeczności P powodują błąd jawny, nie ciche pominięcie.
6. Pozycje spoza dnia raportu pozostają w pełnym JSON. Dla pozycji o niepewnej dacie/godzinie PDF zawiera osobny blok ostrzegawczy; nie wolno arbitralnie przypisywać ich do daty.
7. Kurs co najmniej 1,20 ma sens wyłącznie po potwierdzeniu rzeczywistej przedmeczowej oferty dokładnego rynku; bez tego jawnie „brak”. Nie generować fikcyjnych kursów ani ROI.
8. Żadnych zmian progów, modeli, źródeł, zamrożonych prognoz, danych historycznych ani produkcyjnego MULTIMODELU i KB Score 3.0.

**Wdrożone pliki na gałęzi codex/multimodel-v2:**
- github_models/abc_chronological_pdf.py — generator pełnego chronologicznego raportu, z kontrolą kompletności.
- github_models/abc_report.py — wywołuje nowy renderer po zapisaniu pełnego, niezmienionego ABC_YYYY-MM-DD.json.
- tests/test_github_models_abc_pdf.py — testy chronologii, wszystkich kategorii i linii, deduplikacji wariantów oraz zachowania pełnego JSON.
- Przykładowy PDF utworzony lokalnie: MULTIMODEL_V2_ABC_2026-11-08_PELNY_CHRONOLOGICZNY.pdf, 19 stron, 103 mecze i 353 unikalne propozycje z 7-listopadowego archiwum run 42365229210, po filtrze spotkań jeszcze nierozpoczętych o 12:30 dnia 8 listopada. Warianty archiwalne: A 353, B 243, C 133.
- Kontrola regresyjna przez GitHub Actions: GitHub Models ABC PDF regression (research branch). Dopiero ukończony SUCCESS potwierdza test.

**Stan:** kod i testy zapisane, przykładowy PDF odtworzony i sprawdzony. Pełny automatyczny przebieg dzienny najnowszej wersji nie został jeszcze potwierdzony; bez merge do main.


**Potwierdzenie regresji nowego formatu 2026-11-08:** GitHub Actions run 42479953940, commit f78a3eb7dfe4ca68c1c1c737d6091aed99e34651, wynik **SUCCESS**: https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42479953940. Weryfikacja obejmuje kompletność wielu linii/rynków w meczu, chronologię w pełnej części, rozdzielność dziennych PDF i pełnego JSON oraz PDF audytowy. Wcześniejsze dwie próby CI skończyły się błędnymi oczekiwaniami testów: w wariancie testowym próg B/C błędnie policzono oraz porównywano kolejność meczów w sekcji TOP zamiast harmonogramie. Poprawiono testy; finalny przebieg PASS. Pełny dzienny workflow nadal do osobnego sprawdzenia.

## 2026-11-09 — harmonogram, publikacja PDF przed audytem i nowa nazwa projektu

**Decyzja użytkownika:** sprawdzić i naprawić automatyczne codzienne raporty oraz odróżnić badawczy projekt od wcześniejszego MULTIMODELU. Nowa nazwa użytkowa: **GitHub Models V2 — A/B/C** (skrót GH Models V2). Nazwy istniejącego repozytorium `kb-score-model`, gałęzi `codex/multimodel-v2`, klasyfikatorów i danych historycznych nie zmieniano, aby zachować linki i zgodność wsteczną.

### Dowody diagnozy
- Workflow `.github/workflows/github-models-v2-daily-audit.yml` na **main** posiadał `schedule: cron '0 7 * * *'` oraz `timeout-minutes: 40`. GitHub schedule działa według UTC, a nie Europe/Warsaw.
- Zaplanowany przebieg [42488628492](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42488628492) z **2026-11-08 14:12 UTC** był uruchomiony jako `event=schedule`, ale wystartował z istotnym opóźnieniem względem deklarowanego 07:00 UTC.
- Przebiegi [42488628492](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42488628492) i [42420153742](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42420153742) zakończyły się `cancelled` po ok. 40 minutach na etapie `Settle previous predictions and audit A/B/C`. Weryfikacja kroków i logów potwierdziła, że wcześniejsze pobieranie danych i prognozowanie zdążyły się zakończyć, natomiast PDF A/B/C był generowany dopiero na końcu długiego kroku audytu. Skutkiem były archiwa ze źródłami bez właściwego nowego PDF A/B/C.
- Dnia 2026-11-09 do ok. 11:10 Europe/Warsaw brak było nowego przebiegu GitHub Models V2. To nie jest dowód wyłączenia workflow: GitHub może opóźniać lub pomijać uruchomienia harmonogramowe. Nie twierdzić bez dodatkowych danych, że harmonogram na pewno był `disabled`.

### Zastosowane naprawy
1. **Workflow na main**: wyświetlana nazwa `GitHub Models V2 — A/B/C | daily forecast and audit`. Zmieniono harmonogram na `17 7 * * *`, tj. **08:17 CET zimą / 09:17 CEST latem**, aby unikać przeciążonej pełnej godziny. Jest to godzina docelowa, nie gwarantowana godzina wykonania GitHub Actions. Pozostawiono `workflow_dispatch`, a aktualizacja samego workflow wyzwala kontrolny `push`.
2. **Zwiększono limit pojedynczego joba z 40 do 90 minut.** Nie zmienia to ograniczeń czasowych GitHub Actions ani nie gwarantuje, że każdy audyt się zakończy.
3. **Poprawiono kolejność:** po `daily_queue`, `predict` i `market_runner` najpierw generować `GITHUB_MODELS_V2_ABC_YYYY-MM-DD.pdf` i kompletny `ABC_YYYY-MM-DD.json`. Następnie **od razu publikować osobny artefakt `github-models-v2-abc-forecast-<run_id>`** wraz z wejściami. PDF nie może już zależeć od ukończenia historycznego `daily_settlement` i `abc_audit_runner`.
4. **Zapis niezmiennych prognoz do gałęzi `research/github-models-frozen` przeniesiono przed długim audytem.** Wcześniej anulowanie audytu omijało zapis archiwum. Zapis zachowuje dotychczasowy mechanizm nieprzepisywania istniejących rekordów.
5. Następnie oddzielnie wykonywać rozliczenie historyczne i audyt (bez API-Football) oraz wytwarzać `GITHUB_MODELS_V2_AUDIT_YYYY-MM-DD.pdf`; końcowy artefakt całego przebiegu to `github-models-v2-abc-complete-<run_id>`. Wyniki zerowej liczby rozliczeń to brak próby, nie porażka prognoz.
6. W gałęzi badawczej zaktualizowano tytuły A/B/C i audytu w `github_models/abc_chronological_pdf.py`, `abc_pdf_style.py` i `abc_audit_pdf.py`, w tym nagłówek i stopki. `abc_report.py` rozpoznaje datę również w nowej nazwie PDF. W `.github/workflows/github-models-independent.yml` usunięto `schedule` (pozostawiono ręczne uruchamianie), aby po ewentualnym przeniesieniu na default branch nie uruchamiać drugiego konkurencyjnego harmonogramu. Uaktualniono zakres triggerów testu PDF.
7. **Oddzielność projektów:** żadnych zmian w pierwotnym MULTIMODELU, automatyzacji trzech PDF, KB Score 3.0, progach A/B/C, logice forecast, kursach ani sposobie zbierania treningowych danych.

### Stan i warunki potwierdzenia
- Zapis naprawy workflow na `main`: commit `f6e4396dc122711e91824e2c1ecb4511db6faa47`, zainicjowany przez `push` przebieg kontrolny [42600261774](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42600261774).
- Testy prezentacji nowego brandingu na gałęzi badawczej: końcowy workflow GitHub Models V2 ABC PDF regression — odczytać wynik po zakończeniu, nie deklarować SUCCESS przed sprawdzeniem. Wcześniejsze regresje 42600186200, 42600191912 i 42600203494 miały SUCCESS dla wcześniejszych commitów.
- **Bramka 1:** dzienny run dochodzi do kroku `Publish today's PDF and sources BEFORE historical audit` i publikuje pobieralny artefakt zawierający rzeczywisty PDF/JSON z tej samej prognozy. Samo `in_progress` nie potwierdza publikacji.
- **Bramka 2:** sprawdzić poprawność czasu kickoff, nazw/rynków, pełnej listy, wersji A/B/C i `input_cutoff_utc`. W razie braków oznaczać otwarty problem.
- **Bramka 3:** sprawdzić końcowy audyt, zamrożenie w archiwum i końcowy artefakt. Długi audyt może wymagać optymalizacji w osobnym kroku, nawet przy 90 minutach.
- **Bramka 4:** dopiero kolejne rzeczywiste automatyczne uruchomienie `event=schedule` potwierdzi działanie nowej godziny. Pojedynczy `push` dowodzi tylko uruchomienia ręcznie inicjowanego przez zmianę pliku, nie punktualności planowania.

**Aktualizacja kontroli 2026-11-09:** GitHub Models V2 ABC PDF regression [42600510904](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42600510904) zakończył się **SUCCESS** dla commitu `948611a7ef7fb4104b8ba74c49dd4a4117c56849`, obejmując nową nazwę pliku raportu i dotychczasowe testy pełnego PDF. Kontrolny przebieg dzienny [42600261774](https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/42600261774), wyzwolony zmianą workflow na `main`, był **in_progress** na etapie pobierania źródeł podczas odczytu. Zapis kodu i PASS testów PDF ≠ potwierdzenie ukończonego dziennego raportu. Dowód publikacji PDF, rzeczywistego `event=schedule` o nowej godzinie i końcowego audytu pozostaje otwarty.
