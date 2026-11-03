# MULTIMODEL v2 — naprawy 1–4, 2026-11-03

**Kod: DONE. Rzeczywiste źródła: SOURCE_BLOCKED. Pełny shadow: nie wykonany, nie PASS.**
Gałąź `codex/multimodel-v2`, baza `9a3a803`. Prace wykonano równolegle,
z niezależnym przeglądem i wspólnymi testami integracyjnymi. Dowody:
[raport JSON](MULTIMODEL_V2_REPAIR_1_4_REPORT_2026-11-03.json).

## Wynik każdego zadania

| Zadanie | Rzeczywista poprawka | Stan kodu | Pozostała blokada danych / działania |
| --- | --- | --- | --- |
| 1. Trzy daty i termin | `planner.py`: dokładnie D/D+1/D+2, 11:30 Warsaw, nominalny DST vs opóźniony start, SKIPPED bez kwalifikacji źródła, statusy/digest/run/checkout, kompletna pula i prematch; spójność fixture także między datami | DONE, 41 testów | Badany run ma tylko 1/2 XI. Workflow nadal przekazuje 2; patch 2→3 przygotowano, ale nie zastosowano |
| 2. Formalne KB/Konsensus | `formal_freeze.py`: natywne ID publikacji/selekcji, fixture i drużyny, exact market, bookmaker/quote/source, publikacja/cutoff/KO; historyczny rejestr nie staje się prognozą. Wyłączny atomowy zapis świeżej autentycznej publikacji poza checkout | DONE, 35 testów | Ponowny odczyt 3 XI nadal ma 202/214 historycznych selekcji, bez nowych formalnych freeze |
| 3. Pełna pula API | `full_pool.py` i `capture.py`: opcjonalny pełny eksport z zachowaniem poniżej-67/odrzuconych wierszy, pierwotnego TOP, decyzji per-row z niezmienionego filtra, oryginalnych odpowiedzi i odrębnych SHA; digest, limity, retencja, brak nadpisania, redakcja kluczy | DONE, 42+11 testów | Nie odzyskano brakujących 1473/999 wierszy z liczników. Stare quotes nie uzyskały sztucznej identity. Hooki producenta i opcjonalny upload pozostają niewdrożone |
| 4. Native settlement | `settlement.py`: publication/prediction ID + fixture/exact market + oryginalny frozen_quote; trzy niezależne kohorty, WIN/LOSS/VOID/UNRESOLVED, ROI tylko przy komplecie. TOP ma osobną ponownie obliczaną bramę źródłową | DONE, 40 testów | 1391 dostępnych obserwacji dotyczy innej publikacji; nie rozlicza badanego freeze, wszystkie rzeczywiste ROI pozostają null |

Spójny przepływ `repair_pipeline.py` łączy cztery naprawy i PitchAPI.
**20 testów integracyjnych** używa rzeczywistych walidatorów ZIP/capsule,
bez mockowania ich wyników. Jawnie testowe, kompletne źródła mogą uzyskać
READY_FOR_PARALLEL_TEST, ale nigdy automatyczny full_shadow_passed.
Testowe dane nie trafiają do raportów użytkowych ani archiwów.

## Powtórzony ostatni krok

Na prośbę o powtórzenie sprawdzono ponownie aktywną gałąź i lokalny zestaw
testów: 354/354 na tamtym stanie pracy. Nie powtórzono publikacji ani wywołań
providerów. Po końcowych poprawkach wykonano pełny zestaw opisany poniżej.

## Kontrole wspólnego przepływu

- Capsule musi rzeczywiście znajdować się w artefakcie potwierdzonym bajtowo.
  Ponownie weryfikowane są członkowie ZIP, capsule digest, retencja i natywne
  powiązanie run/workflow-head/checkout. Nie wystarcza dostarczona flaga COMPLETE.
- Formalna publikacja KB/Konsensusu musi być dostępna przed oryginalnym freeze
  API. PitchAPI musi być dostępny przed najwcześniejszym użytym capture modelu.
  Późniejszy kontekst nie zostaje wpisany do wcześniejszego stanu.
- Wymagane jest pokrycie wszystkich fixture oryginalnej puli, z tożsamymi
  natywnymi ID drużyn, nazwami i kickoffem. Samo jedno dopasowanie nie kwalifikuje
  całej daty. Rynki i oryginalne kohorty modeli pozostają niezależne.
- Native quote jest sprawdzany osobno: exact line/scope/team/direction/90 min,
  bookmaker, cena, timestamp oraz oryginalne referencje, jeśli zapisane.
  Sprzeczny side-specific odd lub fixture blokuje kwalifikację.
- Jawne `quotes=[]` oznacza zaobserwowany brak oferty; brak pola quotes oznacza
  nieznaną informację. Żaden przypadek nie generuje ceny ani odrzuconego rekordu.
- TOP może mieć autentyczny frozen_quote przy braku wyboru ceny w background.
  Nie kopiuje się tego wyboru do background. `original_top_eligible` jest
  obliczane niezależnie, a API/FAULE UNDER nie pożyczają finansowego wyboru TOP.
- Czytniki odróżniają historyczny replay od bieżącego raportu. Zapis forward
  wymaga rzeczywistego zegara; podanie starego recorded_at ani callback kończący
  się po kickoffie nie tworzy nowej przedmeczowej publikacji.
- Niepoprawne shape, duplikaty, podmienione digesty, obce runy i brak raw receipt
  kończą się odrzuceniem lub SOURCE_BLOCKED, bez fikcyjnego sukcesu i bez N.

## Sprawdzenie na rzeczywistych danych

Oryginalne ZIP i pliki z audytu 2 XI porównano bez zmian. To zamrożony zestaw
testowy, nie nowy skan ani twierdzenie o kompletnym odkryciu wszystkich nowych
globalnych źródeł. Dla niego sprawdzono też bieżący horyzont 3/4/5 XI.

| Sprawdzenie | Wynik |
| --- | --- |
| Porównanie przed/po na eksportach 28 i 20 | 0 różnic fixture/market/quote/status/score/TOP/freeze i bram audytu; oryginalna kolejność zachowana |
| Osobny istniejący pełny native API z 29 X | 222/222 wiersze i TOP 51/51 zachowane, w tym 171 ocen poniżej 67; równość całego payloadu oraz hashe źródła potwierdzone |
| Kwalifikacja starego pełnego native | INCOMPLETE, source_eligible=false i original_top_eligible=false — brakujących historycznych quote identity/wyborów/trace nie uzupełniono |
| Rzeczywiste filtrowane eksporty 1473/999 | Są tylko 28/20 opublikowanych wierszy. Nowy pełny eksport odrzuca je jako full_candidate_pool_not_recorded; odzyskanych brakujących wierszy: 0 |
| Rozliczenia produkcyjne | 1391/1391 odrzuconych jako wrong_native_publication_id; TOP/API/FAULE UNDER bez zatwierdzonych rzeczywistych ROI |
| Ponowny odczyt Google 3 XI, 09:42:45 Warsaw | KB: 202 selekcje i 294 szablony, ostatnia data 6 X. Konsensus: 214 selekcji, ostatnia Date 14 X. W obu precyzyjne braki natywnego formalnego freeze |
| Rzeczywisty wspólny pakiet wejściowy | SOURCE_BLOCKED; brak nowych pełnych capsule na trzy wymagane daty i formalnych źródeł. Nie uruchomiono pełnego matematycznego shadow |

Kopia istniejącego pliku native została testowo zapisana i odczytana wyłącznie
w tymczasowym izolowanym katalogu. Zachowała oryginalny publication ID/czas
i cały payload, z fresh_predictions_created=0, n_effect=0. Nie jest nową
historyczną prognozą i nie zastępuje plików eksperymentalnego runu.
Prywatne wiersze Google, uwagi i autorzy pozostają poza repo.

## Testy i kontrola zakresu

- Baza: **806/806**, MULTIMODEL v2 **198/198**.
- Po naprawach: **995/995**, MULTIMODEL v2 **387/387**; **189 nowych testów**.
- Podział nowych: planer 41, formal freeze 35, full pool 42, settlement 40,
  raw capture 11, integracja 20.
- Pełna regresja: Python 3.12.14 i bieżący izolowany zestaw zależności PDF jak
  w CI. Testy offline; bez źródłowych providerów i płatnych skanów.
- `git diff --check` i oba `git apply --check` propozycji: OK.
- Zero zmian modeli, wag, algorytmów źródłowych, progów, produkcyjnych workflow,
  oryginalnych forecast/TOP/freeze, archiwów, danych i checkpointów/N względem bazy.

## Gotowość oraz działania pozostające poza tym wykonaniem

**Kod jest gotowy do kontrolowanego testu z poprawnymi oryginalnymi wejściami.
Dostępny rzeczywisty pakiet nadal nie jest gotowy do pełnego testu 1:1.**
Źródłowe progi i skład TOP nie zostały zmienione, a full_shadow_passed=false
nie jest podnoszone na podstawie samych testów lub zielonego workflow.

Przepływ i konkretne punkty wpięcia opisuje [mechanizm zbierania na przyszłość](MULTIMODEL_V2_FORWARD_CAPTURE.md).
Oba patche workflow pozostają niezastosowane. Wymagane są autoryzowany producent
bieżących freeze KB/Konsensusu, rzeczywiste surowe quote evidence i pełne pule
z nowego wykonania, a następnie właściwe rozliczenia tego samego native ID.
Nie wolno zastępować ich późniejszą ceną, wynikiem ani inną publikacją.

Odczyt Google działa; nie żądano dostępu do zapisu. Nie czytano kluczy providerów.
Wpięcie hooków do istniejącego kolektora, przypięcie rewizji recorderów,
włączenie repository variable i zastosowanie propozycji workflow są osobnymi
czynnościami operatora po przeglądzie. Żadna nie została wykonana w tym audycie.
Testy i offline replay nie wymagają takich sekretów ani uruchomienia skanu.

## Rejestr

2026-11-03 | REPAIR-001 | Trzy daty, deadline/DST i transport/run/checkout | kod DONE; patch workflow nie zastosowany; dane BLOCKED.
2026-11-03 | REPAIR-002 | Formalne freeze KB/Konsensusu i forward-only receipt | kod DONE; rzeczywiste aktualne formalne publikacje BLOCKED.
2026-11-03 | REPAIR-003 | Pełna pula, oryginalny runtime trace, raw response evidence, limity/retencja/redakcja | kod DONE; historycznych braków nie odtworzono; przyszłe hooki niewdrożone.
2026-11-03 | REPAIR-004 | Native settlement, niezależny TOP/API/FAULE UNDER i kompletne miary | kod DONE; 1391 obcych obserwacji odrzuconych; dane BLOCKED.
2026-11-03 | REPAIR-005 | Wspólna kwalifikacja i niezależny przegląd | 20 testów integracji; brak false-ready dla późnych źródeł, sprzecznych drużyn i częściowego pokrycia.
2026-11-03 | REPAIR-006 | Regresja 995/995, v2 387/387, 189 nowych; porównanie 28/20 bez różnic | TESTED; no paid scans, no merge, no production changes.

## Zmienione pliki

- `docs/MULTIMODEL_V2_CODEX_PLAN.md`
- `docs/MULTIMODEL_V2_CODEX_REPAIR_1_4.md`
- `docs/MULTIMODEL_V2_E2E_AUDIT_2026-11-02.md`
- `docs/MULTIMODEL_V2_FORWARD_CAPTURE.md`
- `docs/MULTIMODEL_V2_FORWARD_FREEZE.md`
- `docs/MULTIMODEL_V2_FULL_POOL.md`
- `docs/MULTIMODEL_V2_REPAIR_1_4_REPORT_2026-11-03.json`
- `docs/MULTIMODEL_V2_REPAIR_1_4_REPORT_2026-11-03.md`
- `docs/MULTIMODEL_V2_SETTLEMENT_LINKAGE.md`
- `docs/MULTIMODEL_V2_SOURCES.md`
- `docs/proposals/multimodel-v2-full-source-upload.patch`
- `docs/proposals/multimodel-v2-three-day.patch`
- `multimodel_v2/capture.py`
- `multimodel_v2/formal_freeze.py`
- `multimodel_v2/full_pool.py`
- `multimodel_v2/planner.py`
- `multimodel_v2/repair_pipeline.py`
- `multimodel_v2/settlement.py`
- `tests/test_multimodel_v2_capture.py`
- `tests/test_multimodel_v2_formal_freeze.py`
- `tests/test_multimodel_v2_full_pool.py`
- `tests/test_multimodel_v2_planner.py`
- `tests/test_multimodel_v2_repair_pipeline.py`
- `tests/test_multimodel_v2_settlement.py`

## Commity napraw

- `f28551f` — fix(multimodel-v2): require three verified dates and Warsaw deadline
- `8c64155` — feat(multimodel-v2): verify and retain native forward formal freezes
- `243f72b` — feat(multimodel-v2): retain full native pools and raw source evidence
- `ec2be9e` — feat(multimodel-v2): link native settlements with independent cohorts

Integracja, dowody i wspólny rejestr znajdują się w commicie zawierającym ten raport; pełny końcowy SHA oraz wynik CI zapisano w PR #55.
