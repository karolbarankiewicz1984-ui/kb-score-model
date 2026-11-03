# Integracja producenta MULTIMODEL v2 — kod do przeglądu

Wyłącznie `codex/multimodel-v2`. Kod obserwatora działa offline; produkcyjne
workflow i producent nie zostały zmienione. Nie ustawiono zmiennych repozytorium,
nie wykonano uploadu źródeł w Actions ani wywołania API. Pakiet nie ma klienta
API ani funkcji uruchomienia skanu poza jawnie wybranym oryginalnym etapem.

## Co obserwuje recorder

`producer.NativeProducerRecorder` opakowuje istniejący `api_market_scan.api_get`:
wywołuje oryginał dokładnie raz, po jego zwrocie zapisuje redagowaną odpowiedź
JSON, zachowując tożsamość zwróconego tuple/body/headers i oryginalne wyjątki.
Nie zapisuje nagłówków uwierzytelniających. Alias funkcji publikacji jest
obserwowany również w `api_market_report_diversify`; zapis capsule następuje
po oryginalnym `archive_publication`, z jego ID i hashem rzeczywistego pliku.

Pełna pula obejmuje wiersze odrzucone i poniżej 67. Trace powstaje wyłącznie
przed kickoffem przez niezmieniony czysty `playable.evaluate` i jego oryginalną
konfigurację. TOP i natywny payload pozostają bez zmian. Przy spóźnionym capture
zachowywana jest tylko kopia rzeczywistego oryginału, bez odtwarzania decyzji;
status pozostaje SOURCE_BLOCKED. Błąd recordera nie zmienia natywnego wyniku.

Wyjście musi znajdować się fizycznie poza oboma checkoutami, np. w runner.temp.
Exclusive atomic writes nie nadpisują dowodów. Retencja 30 dni, walidacja
rozmiaru/sekretów/ścieżek/digestów obowiązuje również po odczycie. Osobne procesy
etapów czytają wcześniejsze immutable raw receipts z tego samego runu/revision.
Archiwa źródłowe są tylko odczytywane; ich oryginalne zapisy wykonuje producent.

Etapy: prefetch → scan → enrich → publish → playable → freeze → pdf → status.
Ostatni kopiuje oryginalny dated status napisany przez istniejący workflow.
Wspierany jest również osobny etap `settle`, obserwujący już zapisane natywne
rozliczenia i już otrzymane odpowiedzi fixtures/statistics.

## Upload i ponowny odczyt

`bundle.prepare_upload` jest domyślnie DISABLED. W trybie opt-in
`inspect_bundle` weryfikuje wszystkie trzy daty, oryginalne statusy, kolejność
etapów, raw/capsule/output digests, przedział czasu i wspólny cutoff 11:30 Warsaw,
powiązanie run/workflow-head/native-checkout oraz oczekiwany recorder SHA.
Pusty katalog, partial, błędy providerów, wygaśnięcie lub obca rewizja blokują
upload. Jawna zaobserwowana pusta pula nie tworzy żadnej kandydatury.

`CAPTURE_COMPLETE` potwierdza wyłącznie kompletny zapis techniczny.
`source_ready` pozostaje osobną bramą exact market/quote/freeze;
`full_shadow_passed` jest zawsze false w tej kontroli. Kompletne dowody
niekompletnego źródła można zachować jako dowody, bez uznania źródła za gotowe.
Manifest kontroli jest osobnym plikiem poza bundle, aby nie podpisywał sam siebie.

Po pobraniu ZIP należy najpierw użyć `artifact_audit.read_artifact` z metadanymi
GitHub i rzeczywistymi bajtami. `bundle.inspect_uploaded_bundle` ponownie
weryfikuje pliki i oczekiwaną rewizję recordera w izolowanym katalogu; nie ufa
fladze COMPLETE. `repair_pipeline` nadal wykonuje odrębną ścisłą kwalifikację
źródeł i nie uruchamia automatycznie matematycznego shadow. Test pokrywa cały
przepływ native producent → bundle → ZIP → konsument tej samej rewizji.

## Formalne źródła i rozliczenia

`publication_bridge.ForwardPublicationObserver.after_publish` wymaga jawnego
podłączenia do autentycznego producenta, jego oryginalnego source_reference,
pełnego natywnego kontraktu i świeżych oryginalnych IDs. Domyślnie jest wyłączony;
zwraca dokładnie oryginalny obiekt także przy błędzie zapisu. W repo nie znaleziono
autentycznych publisherów KB Score 2.1 i Konsensusu. KB21 CANDIDATE_ONLY,
DIAGNOSTIC/NO PLAY, RESEARCH_ONLY_NOT_PLAY i UNSIGNED nie są ich zamiennikami.

Zgodnie z nową `transition_policy.py` KB/Konsensus są nieaktywne; observer nie
jest pozornie włączany. Ich brak nie blokuje niezależnej ścieżki API-only.
PitchAPI pozostaje kontekstem, bez przekształcenia w kurs lub composite TOP.

`outcome_bridge` wymaga tego samego oryginalnego publication ID, exact market,
wyraźnie wybranego frozen_quote oraz oryginalnych odpowiedzi final fixtures i
statistics z tego samego runu. Weryfikuje rzeczywiste actual/hit niezmienionymi
natywnymi funkcjami. Nie wybiera ceny z dostępnej oferty ani nie domyśla okresu.
`final_observed_at` oznacza czas odczytu FT, a nie wymyślony `finished_at`.
Settlement weryfikuje oba receipts; dotychczasowy kontrakt finished_at pozostaje
obsługiwany. Trzy kohorty i ich ROI pozostają niezależne, braki dają UNRESOLVED/null.

## Oddzielne, niezastosowane propozycje produkcyjne

1. `proposals/multimodel-v2-recorder-bootstrap.patch`: pin rzeczywistego native
   checkoutu, osobny checkout recordera na zatwierdzonym 40-znakowym SHA,
   opt-in wrapper tych samych etapów. Domyślnie oryginalne komendy bez recordera.
2. `proposals/multimodel-v2-full-source-upload.patch`: stosowany po bootstrapie;
   upload dopiero po pomyślnej kontroli rzeczywiście wypełnionego katalogu.
   Oczekiwane run/SHA pochodzą z kontekstu workflow, nie z samodeklaracji bundle.
3. `proposals/multimodel-v2-native-provenance.patch`: osobna propozycja dla
   producenta eksperymentalnego. Obecne `publication.code_revision=GITHUB_SHA`
   może wskazywać workflow zamiast kodu producenta. Propozycja zapisuje oba SHA
   oddzielnie, wyłącznie w przyszłych publikacjach. Po jej zatwierdzeniu potrzebny
   będzie nowy native pin i powtórzony test jego kodu. Nie wolno przepisywać starych
   plików ani IDs. Zmiana metadanych wpływa naturalnie na hash przyszłego ID.

Patche 1–2 sprawdzono łącznie w scratch, patch 3 na niezmienionej kopii kodu
producenta. Wszystkie bloki shell przechodzą `bash -n`. Żaden patch nie został
zastosowany do aktywnego workflow, ustawień repo ani gałęzi eksperymentalnej.
Nie utworzono produkcyjnych PR z niezatwierdzonego kodu; przegląd pozostaje
w draft PR #55. Wdrożenie i świadoma decyzja o kosztach trzeciej daty pozostają
poza wykonanym zakresem.

API-Football wygasa 4 XI według inwentaryzacji operatora. Recorder zachowuje
tylko odpowiedzi już uzyskane; nie odblokowuje abonamentu i nie uruchamia zapytań
uzupełniających. Raporty przyszłe respektują też osobną nową politykę FAULE UNDER:
bez nowej sekcji/preferencji; zwykłe kwalifikujące się rynki pozostają w TOP.
Istniejący renderer historyczny zachowano do regresji; nie opublikowano nim
nowych raportów użytkowych. Włączenie nowego raportowania wymaga integracji
tej polityki prezentacji, niezależnie od samego capture/upload.
