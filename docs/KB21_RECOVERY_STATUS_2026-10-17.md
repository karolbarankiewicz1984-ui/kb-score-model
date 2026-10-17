# KB Score 2.1 — stan odzyskiwania 2026-10-17

## Obowiązujący model (NIE ZMIENIAĆ)
- Oryginalne LIVE KB Score 2.1: STR/35 + QUAL/35 + MATCH/30 = Sport Score/100.
- P(model) ustala analityk na podstawie dowodów PRZED obserwacją kursów;
  NIE istnieje odzyskany deterministyczny wzór Sport Score -> P(model).
- xG jest pomocnicze, nie jest obligatoryjne.
- Price/EV, Market Signal, Data Quality, Lineup Risk, consensus to odrębne kontrole.
- Do PLAY wymagane: oficjalny i niezależny pełny terminarz, udokumentowany
  pre-match freeze, uzasadniona analiza i komplet wymaganych kontroli.
- Google Sheet "KB Score – Rejestr i Backtest" tylko do odczytu w fazie odzyskiwania.
- Nie rekonstruować historii ani N bez oryginalnego freeze; nie używać API Market
  ani eksperymentalnego Poissona jako zastępczego KB Score.

## Co już działa
- Codzienny przebieg diagnostyczny w GitHub Actions, zaplanowany 09:00 UTC
  (około 11:00 czasu polskiego latem / 10:00 zimą); GitHub może uruchomić go później.
  To NIE jest wymagany docelowy LIVE PDF 11:30.
- Trzy dni kart pomocniczych ESPN oraz analiza zakresu rozgrywek (5 głównych
  lig, dodatkowe ligi i rozgrywki reprezentacyjne).
- Zestawienie z football-data.org: tylko druga opinia o terminarzu, NIGDY
  automatyczne zatwierdzenie oficjalnej karty. Dla przyszłych dni opcjonalne
  odświeżenie niezależnych snapshotów przy dostępnej tajemnicy w Actions.
- Ostrożne dołączanie już zapisanych próbek faktycznych goli z API-Football:
  wyłącznie przed rozpoczęciem meczu, NIE xG ani nowy Sport Score.
- Przedmeczowa krótka lista do maksymalnie 10 spotkań w celu sprawdzenia
  spójności odzyskiwanej metody, NIE limit modelu ani rekomendacje.
- Strukturalna walidacja ręcznie uzasadnianego STR/QUAL/MATCH, P(model)
  i osobno kursu/EV. Żadne automatyczne PLAY.
- Zweryfikowany udany przebieg diagnostyczny GitHub Actions:
  https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/39024774932
  55 testów, 61 kandydatów / 3 dni, 5 zgodnych pozycji u 2 dostawców,
  14 kart z prawidłowo podłączonymi danymi o wcześniejszych golach,
  10 wybranych przyszłych kandydatów do przeglądu.

## Co nadal nie działa jako LIVE KB Score 2.1
1. Calendar Gate pozostaje BLOCKED: brak formalnego dowodu pełnego oficjalnego
   terminarza organizatorów i niezależnego porównania wszystkich rozgrywek.
2. Nie ma odtworzonych ocen analityka z wartościowaniem dowodów dla
   poszczególnych komponentów 35/35/30.
3. Nie ma odzyskanej procedury generowania P(model) w pełni odpowiadającej
   oryginałowi. Nie wolno użyć formuły Poissona ze starego CORE v1R.
4. Brak dziennego oryginalnego PDF z rzetelnymi PLAY/LEARN/CONTROL:
   generowane raporty diagnostyczne to nie rekomendacje.
5. Po zatwierdzeniu źródeł i oceny trzeba testować co najmniej 10 NOWYCH,
   timestampowanych analiz przedmeczowych; bez wpisów do starego N.

## Następny krok
- Dla przyszłych spotkań z review-shortlist zweryfikować kalendarze oficjalne
  i dowody, uzupełnić przedkursem ręczne oceny STR/QUAL/MATCH i P(model).
- Weryfikować metodę porównując ją z historycznymi przypadkami i zamrozić
  oceny przed wydarzeniami; dopiero następnie przywrócić publikację PDF.
- Wszystkie blokady i źródła ustaleń pozostawić jawne: brak danych != brak
  spotkań; brak xG != automatyczna dyskwalifikacja.

## Rozdzielenie systemów
- KB Score 2.1 = pierwotna analityczna metodologia i oddzielne N.
- API Market = odrębny silnik analityczny, nie przejmuje P(model) KB21.
- PitchAPI = pomocniczy dostawca danych, nie trzeci automat typujący.


## Kalendarz: ukończona ścieżka audytu, ale jeszcze BEZ zatwierdzenia
- tools/kb21_official_review.py: katalog oficjalnych stron organizatorów
  dla wszystkich 14 rozgrywek (5 kluczowych + 9 dodatkowych) i raport
  42 kontroli dla 3 dni; strony są punktami wejścia, NIE dowodem odczytu.
- reports/kb21_legacy/official-review.md: osobne zestawienia na każdą
  ligę i dzień; pola niezgodności dostawców są jawne.
- tools/kb21_calendar_signoff.py --prepare-template: tworzy dokument
  official-inventory-template.json do zapisu faktycznie sprawdzonych
  pełnych terminarzy poszczególnych organizatorów, wraz z czasem odczytu,
  osobą kontrolującą i potwierdzeniem dnia bez spotkań, jeśli dotyczy.
- Następnie validator wymaga 1:1 zgodności pełnej oficjalnej karty
  z niezależnie pozyskanymi kandydatami ESPN, właściwych dat/godzin,
  braku duplikatów, poprawnego zakresu oraz jawnego osobistego zatwierdzenia.
- Wyłącznie po dostarczeniu REALNYCH dowodów i ręcznym zatwierdzeniu
  może pojawić się PASS_MANUAL. To nie jest automatycznie
  uwierzytelniona treść strony internetowej, lecz odnotowana
  odpowiedzialność analityka za audyt źródła.
- Calendar Gate PASS_MANUAL NIE zatwierdza PLAY; nadal potrzebne są
  oryginalne oceny STR/QUAL/MATCH, pre-price P(model) i kontrole rynku.
- Istniejące zestawienia uruchamiane w GitHub nie zawierają
  zatwierdzonej oficjalnej inwentaryzacji, więc nadal mają status BLOCKED.
- Oficjalne URL: Premier League, LaLiga, Lega Serie A, Bundesliga,
  Ligue 1, Liga Portugal, Eredivisie, Pro League (Belgia), TFF,
  UEFA Champions, Europa, Conference, Nations i European Qualifiers.


## Oficjalne terminarze — rzeczywisty audyt 17–19 października 2026
- Data badania: 2026-10-17. Szczegółowe źródła i dane:
  `data/kb21_official_research/2026-10-17_to_2026-10-19.json`.
- Po raz pierwszy zestawiono kompletny trzydniowy zbiór 61 kandydatów ESPN
  ze źródłami organizatorów dla wszystkich 14 kategorii konkursowych.
- 60/61 dopasowano po rozgrywkach, gospodarzach/gościach i godzinach.
  Jedna różnica: Real Betis–FC Barcelona 2026-10-17: La Liga 18:30
  Europe/Warsaw, ESPN 18:00 Europe/Warsaw.
- Zapisany przed meczem snapshot API-Football dla tego spotkania
  `data/api_football/kb21_inputs/2026-10-17.json` potwierdza 18:30;
  `tools/kb21_calendar_conflict_evidence.py` zachowuje konflikt
  i dokumentuje zgodność oficjalnego terminarza z trzecim źródłem.
  NIE usuwa ani nie nadpisuje oryginalnego odczytu ESPN.
- Źródła pięciu CORE lig: Premier League, La Liga, Serie A, Bundesliga,
  Ligue 1. Dalsze: oficjalny KNVB dla 8 spotkań Eredivisie, TFF dla
  8 spotkań Süper Lig, UEFA dla pięciu rozgrywek (bez gier w oknie),
  Pro League Belgia (weekend pucharowy, brak ligowych gier),
  Portugal: tylko klubowy + ligowy dowód Braga–Gil Vicente 19.10
  i termin 3. rundy Taça de Portugal 17–18.10.
- Uwaga Portugalia: pełny dzienny katalog ligi NIE został osobno
  zweryfikowany. Oficjalny klub Gil Vicente podaje 20:15 czasu
  lokalnego (21:15 Polska). Portal ligi prezentuje 19:15 bez
  jawnej strefy czasowej; należy wyjaśnić sposób prezentowania czasu
  przed zatwierdzeniem pełnego terminu.
- Kompletne zestawienia KNVB/Ligue 1/Bundesliga nie zawierają
  spotkań ligowych w poniedziałek 19.10, ale to wciąż badanie
  z URL, nie formalny podpisany odczyt.
- Aktualny kod `tools/kb21_official_research_compare.py` czyta
  WYŁĄCZNIE to historyczne okno 17–19.10; workflow w kolejnych
  dniach świadomie pomija przestarzałe źródła zamiast pozorować
  aktualną weryfikację. Nowe trzy dni wymagają nowego zestawienia.
- `tools/kb21_official_inventory_prefill.py` przygotowuje
  61 kart meczów do **ręcznego** sprawdzenia, ALE nie wpisuje
  recenzenta, daty oficjalnego odczytu ani flagi kompletności.
  `tools/kb21_calendar_signoff.py` nie dopuści sztucznego PASS
  bez tych danych.
- Przebieg GitHub #39028120135: 90 testów OK, 1 konflikt rozpoznany
  i potwierdzony trzecim źródłem, 61 rekordów prefill, 0
  automatycznie zatwierdzonych. Calendar Gate pozostaje BLOCKED.
- Wobec rozegranych/rozpoczętych spotkań nie tworzyć
  retrospektywnego freeze ani P(model) i nie dopisywać ich do N.


## Poprawa porównania dostawców — 109 testów

- Komplet zapisanych przez nas danych 17.10: ESPN 28 meczów, z tego
  24 w ligach występujących także w football-data.org, 4 tureckie
  poza katalogiem drugiego dostawcy.
- Poprzedni crosscheck w football-data.org potwierdzał tylko **5** spotkań,
  głównie przez różne pisownie nazw drużyn.
- `tools/kb21_fixture_crosscheck.py` używa teraz współdzielonej,
  wyraźnej listy aliasów klubów z `kb21_official_research_compare.py`.
  Dopasowanie pozostaje ścisłe w zakresie ligi i godziny.
- Aktualnie **23** mecze crosscheck oznacza `MATCHED_FOR_REVIEW`,
  a **jeden** (Betis–Barcelona) jako `START_TIME_CONFLICT`
  z zachowanymi dowodami z drugiego źródła. Pozostałe cztery
  mecze pochodzą z Süper Lig nieobjętej subskrypcją football-data.org.
  Zgodność 23 nie zatwierdza oficjalnego Calendar Gate.
- Zapisane snapshoty football-data.org istnieją tylko dla 17.10;
  18 i 19.10 wciąż wymagają pobrania niezależnych danych w odpowiednich
  przebiegach, niezależnie od posiadanych oficjalnych materiałów badawczych.
- `tools/kb21_official_source_probe.py` odwiedza 14 oficjalnych stron
  organizatorów, zachowując metadane HTTP, URL, czas odczytu, typ zawartości
  i hash pierwszych 128 KiB (bez przechowywania strony).
  Przebieg 17.10: **9** dostępnych stron z próbką nieprzekraczającą
  limitu, **5** dłuższych, wszystkie odpowiedziały przez HTTP.
  Nie jest to dowód, że listę meczów udało się pobrać, odczytać
  ani że jest kompletna.
- Raport `official-source-http-probes.md` i jego JSON są dodawane
  do artefaktu dziennego. Wszystkie etykiety jednoznacznie
  informują `BLOCKED / DIAGNOSTIC / NO PLAY`.
- Weryfikacja najnowszego kodu:
  https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/39029902011
  — **109 testów, OK**. Żaden stary rejestr ani N nie został ruszony.

### Najbliższe działania
1. Zebrać rzeczywiste zestawienia dzienne z **oficjalnych** źródeł na
   kolejne 3 dni (program nie może utożsamiać HTTP 200 z terminarzem).
2. Zaktualizować listy przełożonych spotkań, zwłaszcza Portugalii.
3. Zweryfikować ESPN/football-data.org dla każdego z trzech dni.
4. Dla poszczególnych dni sporządzić niezależnie sprawdzone podpisane
   inwentaryzacje. Bez takiej kontroli nie wydawać PASS_MANUAL.
5. Dopiero po przejściu Calendar Gate wracać do oryginalnych ocen
   STR/QUAL/MATCH i P(model) bez zastępczych formuł.


## Pierwsze automatyczne oficjalne terminarze — Premier League i Bundesliga

- `tools/kb21_official_fpl.py`: dwie publiczne usługi JSON organizatora Premier
  League (`fantasy.premierleague.com/api/bootstrap-static/` i `fixtures/`).
  Faktyczny udany odczyt 17.10.2026 objął komplet **380 spotkań** sezonu
  oraz 20 drużyn. 10 spotkań z 17–19.10 z oryginalnej kolejki ESPN
  pasuje **10/10** po gospodarzach, gościach i czasie. Daty/godziny
  przeliczane na `Europe/Warsaw`; błędne ID, brak godziny i godzina
  `provisional_start_time` są raportowane, a nie ukrywane.
- `tools/kb21_official_dfl.py`: publiczna tabela `products.bundesliga.com/fixtures`,
  własność Bundesliga Media (DFL). HTML łączy dzień tygodnia i datę
  w jednej kolumnie; parser obsługuje ten rzeczywisty układ i bierze
  **wyłącznie kolumnę Kick-off (UTC)**, aby uniknąć pomyłek CET/CEST.
  W rzeczywistym przebiegu znalazł 9 spotkań kolejki 6, 8 z nich w
  dniach 17–19.10. `tools/kb21_dfl_compare.py`: **8/8**
  zgodnych z ESPN po drużynach i godzinie.
  UWAGA: oficjalna strona pokazuje aktualnie **jedną kolejkę**,
  więc brak wiersza dla danego dnia nie dowodzi braku zaległego meczu.
- Razem **18/18** meczów z 2 osobnych oficjalnych systemów
  organizatorów w badanym trzydniowym oknie pokrywa się z ESPN.
  Ten wynik nie oznacza zatwierdzenia wszystkich 14 rozgrywek.
- `tools/kb21_official_source_seed.py` wzbogaca `official-inventory-direct-sources-draft.json`
  aktualnymi oficjalnymi meczami Premier League / Bundesligi dla
  bieżących trzech dni; nie nadpisuje istniejących ręcznych faktów.
  Zapisuje jawnie sprzeczności i nie dopisuje daty **ręcznego** sprawdzenia,
  nazwiska kontrolującego, flagi kompletności ani `approval`.
  Dla 17–19.10 istniejące ręcznie zebrane dane były zgodne
  (0 sprzeczności), a nowy proces potwierdził je niezależnie.
- Przepływ GitHub Actions `.github/workflows/kb21-legacy-recovery.yml`
  został nazwany `KB21 recovery (official fixture diagnostics)`,
  ponieważ korzysta teraz z publicznych usług oficjalnych organizatorów
  (nie jest już prawdą, że w ogóle nie pobiera API).
- Ostatni sprawdzony kompletny przebieg:
  https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/39030980810
  **137/137 testów**, odczyty FPL i DFL + dwa porównania + 3-dniowy
  audyt oraz zestaw roboczych kart do podpisanej kontroli.
- **Calendar Gate = BLOCKED** nadal. Brak podpisanej oficjalnej kontroli
  całych kart 14 kategorii na każdy z trzech dni; pozostałe
  dwanaście kategorii nie mają jeszcze automatycznego oficjalnego
  parsera. 18/18 to zgodność danych, nie finalna atestacja.
- Następny praktyczny krok: analogiczny bezpośredni, programowy
  odczyt z pozostałych lig, szczególnie La Liga, Serie A, Ligue 1,
  następnie pełne sprawdzenie meczów przełożonych (Portugalia)
  i akceptacja dni przed ich pierwszym rozpoczętym spotkaniem.


## Integracja La Liga, Serie A i Ligue 1 — 17.10.2026 (NOWE, DO WERYFIKACJI W ACTIONS)

- La Liga: `tools/kb21_official_laliga.py` odczytuje ścisłe
  kolumny FECHA / HORARIO / PARTIDO z oficjalnych stron kolejki
  `https://www.laliga.com/laliga-easports/resultados/2026-27/jornada-9`
  i okolicznych kolejek. `tools/kb21_laliga_compare.py` porównuje
  gospodarz–gość i godzinę z ESPN. Strony są dynamiczne, więc
  rzeczywistą skuteczność parsera i kompletność wierszy trzeba
  najpierw potwierdzić w artefakcie CI; HTTP 200 nie wystarcza.
- Serie A: `tools/kb21_official_press_fixtures.py` pobiera
  **bezpośredni komunikat organizatora** Lega Serie A z obsadami
  sędziowskimi na 7. kolejkę (16–19.10.2026), z konkretną listą
  10 spotkań, gospodarzy, gości, dat i godzin:
  https://en.legaseriea.it/serie-a/news/the-referees-for-the-7th-round-x8311
  Zakres artykułu jest HISTORYCZNY/KONKRETNY, nie stanowi
  uniwersalnego codziennego feedu. Od kolejnych terminów wymagany
  jest nowszy oficjalny komunikat.
- Ligue 1: ten sam moduł pobiera komunikat LFP dotyczący
  telewizyjnych harmonogramów 7. i 8. kolejki, m.in. 16–18.10
  i 23–25.10.2026:
  https://ligue1.com/fr/articles/l1_article_5797-
  Parser zachowuje mecze rozgrywane jednocześnie, przelicza
  godziny z Europe/Paris na Europe/Warsaw i oznacza nieobjęte
  zakresem artykułu daty zamiast udawać potwierdzony brak meczu.
- W obu ligach `tools/kb21_official_press_compare.py`
  pokazuje `MATCHED_FOR_REVIEW`, `KICKOFF_CONFLICT`,
  `MISSING_IN_ORGANIZER_ARTICLE`, `ORGANIZER_ONLY`,
  konflikt powtórzonej tożsamości i źródłowe błędy.
- `tools/kb21_official_source_seed.py` przyjmuje `--laliga`,
  `--serie-a`, `--ligue1`; uzupełnia **wyłącznie niepodpisaną**
  kartę kontroli, zachowuje ręczne dane, wypisuje sprzeczności,
  nigdy nie zatwierdza pustego dnia ani Calendar Gate.
- Workflow `.github/workflows/kb21-legacy-recovery.yml`
  został zaktualizowany o testy, pobranie dwóch komunikatów,
  porównanie godzin i publikację JSON/Markdown w artefakcie.
  **Nie należy podawać liczby faktycznie odczytanych meczów ani
  sukcesu tego nowego przebiegu do czasu sprawdzenia logów CI.**
- Nadal nie mamy pełnego, automatycznego i zatwierdzonego
  kalendarza wszystkich 14 kategorii dla bieżących trzech dni.
  **Calendar Gate BLOCKED; DIAGNOSTIC / NO PLAY**, brak
  automatycznego P(model), freeze, PDF LIVE i wpisów N.


## Siódme źródło — KNVB + TFF, zweryfikowane w CI 17.10.2026

- KNVB `https://www.knvb.nl/competities/eredivisie/programma`:
  `tools/kb21_official_knvb.py` pobrał bezpośrednio widoczny
  program Eredivisie, rozpoznał **8 spotkań w dniach 17–18.10**;
  `tools/kb21_knvb_compare.py` dopasował **8/8** do ESPN.
  Wyraźnie odróżnia dzień niepokazany w programie (19.10)
  od podpisanego potwierdzenia, że meczów nie ma. Dodatkowe
  daty widoczne na stronie nie stanowią gwarancji pokrycia
  wszystkich meczów przełożonych.
- TFF `https://www.tff.org/?pageID=198`:
  `tools/kb21_official_tff.py` wydobywa tylko aktualnie
  widoczną kolejkę Trendyol Süper Lig. Rozpoznał pełne
  **9 spotkań jednej kolejki**, z czego **8 w dniach 17–19.10**.
  `tools/kb21_tff_compare.py` uzyskał **8/8 zgodności**
  z ESPN, z przeliczeniem Turkey/Europe/Istanbul na
  Europe/Warsaw; nieczytelny/niekompletny zestaw 9 meczów
  jest blokowany. Strona może pokazywać inną kolejkę
  kolejnego dnia, więc nie jest pełnym kalendarzem sezonu.
- Codzienny diagnostyczny workflow pobiera oba źródła,
  publikuje surowe JSON i porównania Markdown, uzupełnia
  niepodpisaną roboczą kartę weryfikacji i nigdy nie otwiera
  Calendar Gate automatycznie.
- Weryfikacja na rzeczywistych danych i regresji:
  https://github.com/karolbarankiewicz1984-ui/kb-score-model/actions/runs/39040175483
  — **189/189 testów, sukces**, KNVB **8/8**, TFF **8/8**.
- Łącznie siedem oficjalnych źródeł ligowych dało
  **59 dopasowań na 60 meczów** obecnych w tych oficjalnych
  źródłach w oknie 17–19.10 (pozostaje konflikt godziny
  Real Betis – Barcelona po stronie ESPN). To NIE dowodzi
  kompletności pozostałych rozgrywek ani dat.
- W logu `organizer_live_seed_summary` liczba `0`
  przy `fixtures_prefilled` oznacza *brak nowych wierszy do
  dodania* przy już wypełnionej historycznej karcie roboczej;
  nie jest dowodem pustego terminarza ani błędu pobierania.
  Podpisy / zatwierdzenie: **0**, pełne 42 kontrole
  rozgrywka–dzień nadal wymagane, Calendar Gate **BLOCKED**.
- Następny priorytet: oficjalny terminarz Portugalii
  (w tym mecze przełożone) oraz pełne harmonogramy UEFA
  i potwierdzanie zera spotkań osobno dla każdej daty
  i rozgrywek; potem terminowe podpisane sprawdzenie.
