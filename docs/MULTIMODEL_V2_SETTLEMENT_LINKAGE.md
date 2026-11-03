# MULTIMODEL v2 — oryginalne powiązanie rozliczeń

Izolowany moduł `multimodel_v2/settlement.py`; bez źródłowych wywołań API,
zapisu danych, zmian prognoz/TOP/progów ani liczników N.

## Kontrakt wejścia

`build_native_settlements(snapshot, outcomes, *, as_of, report_date=None,
full_pool_complete=None, full_pool_verification=None)` przyjmuje niezmieniony
oryginalny payload `api-market-scan-v3` z:

- `date` i natywnym `publication.id`, `captured_at_utc`, `provenance=live_pre_match`;
- oryginalnymi `background_candidates` i `top_positions` w zapisanej kolejności;
- dokładnym fixture/market/scope/team/direction/line/settlement_period i kickoffem;
- samodzielnymi `market_data.quotes[].market_identity`, bookmakerem, selected_odd
  i provider_updated_at oraz **jawnie zapisanym** `frozen_quote` wybranej pozycji.

Quote musi spełniać `provider_updated_at <= publication.captured_at_utc < kickoff`.
Jawnie zapisane quote_id/provider_quote_id/source_id/source_reference, jeśli
występują, również wchodzą do klucza dopasowania i nie mogą zostać pominięte.
Nie uzupełnia się tożsamości notowania danymi kandydatury. Brak frozen_quote
nie jest zastępowany best_quote ani maksimum z później dostępnych cen.

Pełne pokrycie tła deklaruje wyłącznie zewnętrzny, zweryfikowany eksport:
`full_pool_verification` przyjmuje wynik `read_full_pool`, z osobnymi
`full_pool_complete`, `source_eligible`, `original_top_eligible` i `status`.
TOP wymaga własnej, ponownie obliczonej oryginalnej kwalifikacji. Nie dodaje się fikcyjnego
pola kompletności do natywnego payloadu. Jawna deklaracja full_pool_complete
jest alternatywnym interfejsem dla wywołującego, który wcześniej sprawdził
oryginalny receipt; sama nazwa schematu nie potwierdza pełnej populacji.

Wiersz outcome musi zachować:

| Pole | Znaczenie |
| --- | --- |
| publication_id lub prediction_id | Ten sam oryginalny natywny ID; jeśli oba pola występują, muszą być zgodne |
| market_identity | Dokładna tożsamość rynku i fixture, bez tolerancji linii lub przybliżonego dopasowania |
| frozen_quote | To samo oryginalne notowanie, z tożsamością/bukmacherem/ceną/czasem i zapisanymi referencjami |
| date | Data wydarzenia Europe/Warsaw oryginalnej publikacji |
| outcome | Jawne WIN, LOSS, VOID lub UNRESOLVED; bez wyliczania z niepowiązanego hit/score |
| result_source | Oryginalne źródło końcowego rozliczenia |
| fixture_status, finished_at, settled_at | Dla FT: kickoff < finished_at <= settled_at <= as_of |

VOID dla CANC/ABD/PST wymaga dodatkowo jawnego `void_reason` i
`settlement_reference` oryginalnej decyzji oraz czasu rozliczenia nie
wcześniejszego od publikacji. Samo odwołanie/przełożenie lub brak statystyk
nie tworzy VOID. Nieobsługiwane rozliczenia częściowe pozostają UNRESOLVED.

## Kohorty i miary

TOP zachowuje oryginalny skład/kolejność, weryfikowany względem jednego
background; nie jest przebudowywany z wyników. Wszystkie kwalifikujące API
zachowują dotychczasowe score >=67 i quote >=1.20. FAULE UNDER zachowują
90 minut, pasmo 1.50–2.00 i również rzeczywiście zapisane rekordy poniżej 67;
to kohorta obserwacyjna, nie nadanie statusu PLAY.

Natywny TOP może zapisać własny jawny frozen_quote, podczas gdy background
zachował tylko uniwersum niezależnych quotes bez wybranej ceny. TOP jest wtedy
łączony po swoim oryginalnym notowaniu do tego uniwersum; nie wymaga fikcyjnego
wyboru w background. Jego wiersz nie dostaje nowych pól. API/FAULE UNDER nadal
wymagają własnych uprzednio zamrożonych wyborów cen do finansowego rozliczenia.
Niepełna populacja lub brak trace odrzuceń nie ukrywa źródłowo poprawnego TOP:
pełna pula korzysta z source_eligible, a TOP osobno z original_top_eligible.
Brak tego jawnego flagu przy dostarczonej weryfikacji pozostaje blokadą TOP;
sam flag nie omija natywnego ID, dat, quote, czasu lub zgodności z background.

Jawna tablica `quotes=[]` oznacza znanego nieczłonka kohorty kursowej.
Brak tablicy lub brak niezależnej tożsamości ceny oznacza nieznaną populację.
Przy niepełnym tle positions=null; znane wiersze są pokazane osobno jako
known_positions. Nie przedstawia się zera kwalifikujących typów jako wyniku
sprawdzenia całej populacji. Duble kandydatur lub wyników są niejednoznaczne,
nie dodatkowymi N; sprzeczne wyniki nie są wybierane według korzystniejszego ROI.

Wszystkie rynki tego samego fixture muszą również zachować zgodny kickoff,
home/away i natywne home_id/away_id tam, gdzie je zapisano. Równoważne offsety
czasu i zapis tego samego ID jako liczby/tekstu są zgodne. Sprzeczne fakty
blokują wszystkie objęte rynki oraz TOP, zachowując oryginalne wiersze i
ujawniając conflicting_fixture_ids; nie pozostaje korzystny podzbiór ROI.
Jawne team_side musi odpowiadać zachowanemu native team_id, gdy zapisano
home_id/away_id; TOP nie może podmienić tych identyfikatorów względem tła.

ROI jednostkowe i fixture-equal ROI powstają tylko dla kompletnej, źródłowo
zweryfikowanej, całkowicie rozliczonej niepustej kohorty. WIN daje odd-1, LOSS
daje -1, a jawny VOID 0; jednostkowy mianownik obejmuje wszystkie pozycje.
Fixture-equal ROI najpierw uśrednia zyski pozycji tego samego fixture, potem
uśrednia mecze z równymi wagami. Nie usuwa się przegranych lub nierozliczonych
pozycji, by policzyć miarę na korzystniejszym podzbiorze. Braki dają ROI=null
i AUDYT NIEPEŁNY. Pusta, ale jawnie kompletna kohorta nie ma mianownika ROI.

## Mechanizm zbierania na przyszłość

Przyszły opcjonalny producent rozliczeń powinien odczytać pełny niezmienny
eksport i przenieść **już zapisany** publication ID oraz frozen_quote do
osobnego rekordu rozliczenia. Oryginalne dane końcowe/źródło/znacznik czasu
muszą pochodzić z faktycznego odczytu lub decyzji bukmachera. Nowy rekord może
być zapisany append-only w izolowanym rejestrze według publication ID i daty;
nie zastępuje historycznego pliku prognozy ani oficjalnego rejestru N.
Moduł konsumencki odrzuca każdy rekord bez wymaganego oryginalnego klucza.
Nie uruchomiono takiego producenta ani płatnego skanu.

## Rzeczywisty dowód odrzucenia obcej publikacji

Odczytano oryginalny snapshot 222/TOP 51 z 29 X oraz rzeczywisty zapis 1391
obserwacji z 1 XI. Wszystkie obserwacje mają natywny ID inny od snapshotu;
moduł odrzuca **1391/1391** jako wrong_native_publication_id, zanim spróbuje
łączyć fixture/rynki lub uzupełniać brakujące quote. Wszystkie trzy ROI są null,
register_writes=false i n_effect=0.

- Snapshot SHA-256: `4a757603db9d1cd2dc66e10da11fa4a23cb8c7c3001d60459b70596e396f1308`.
- Zapis rozliczeń SHA-256: `64ae4a2feb9e6b33f3e4638bdc9b1dec61b6b9a049d01186d816bb6a654b7c28`.

Nie oznacza to odzyskania brakujących 1473/999 rekordów eksperymentalnych ani
potwierdzenia ich rozliczeń. Oryginalnych danych nie przepisano.

Testy: `python -B -m unittest tests.test_multimodel_v2_settlement` — 40/40 OK.
Obejmują obcy ID, różne quote/linie/okresy, duble, niepełne fixture/pule,
brak ceny, zera quote vs brak pola, VOID, skorelowane rynki, sprzeczne fakty
fixture, lookahead i
deterministyczny odczyt bez zmian wejść/N.
