# KB Score 2.1 — przywracanie oryginalnych ocen sportowych (etap przed kursem)

## Co zostało odtworzone
Nowy odczyt `tools/kb21_premarket_intake.py` umożliwia bezpieczne przyjęcie
**osobno przygotowanej oceny analityka** dla spotkań pochodzących wyłącznie z
kanonicznego terminarza API-Football na dzisiaj i jutro.

Przypominamy oryginalne trzy komponenty Sport Score:
- `str` od 0 do 35 — siła strukturalna drużyn i przewaga jakościowa;
- `qual` od 0 do 35 — rzeczywista bieżąca forma/jakość i przeciwnicy;
- `match` od 0 do 30 — dopasowanie stylów, miejsce meczu, absencje, odpoczynek, motywacja.

To **maksima bloków, a nie narzucone nowe subwagi**. Nie jest to automatyczna
formuła liczenia ocen. Brak źródła lub oceny pozostaje brakiem, nigdy zerem.

## P(model)
`p_model` jest odrębną, wyrażoną ułamkiem 0–1, udokumentowaną oceną
prawdopodobieństwa konkretnego, jawnie zdefiniowanego rynku.
**Nie wolno** wyliczać go jako `Sport Score / 100`, przekształcać z ceny
bukmachera ani podstawiać za niego prognozy Poissona z SHADOW.

Wymagane jest osobne wyjaśnienie `p_model_method`: jak analityk ważył
dowody, silne i słabe strony obu zespołów, ryzyka i wybrany rynek.
Dokumentacja oryginału nie zawiera pełnego deterministycznego wzoru, dlatego
taki zapis pozostaje **oceną analityka wymagającą kontroli**; nie ma gwarancji
odtworzenia historycznej metody.

## Procedura przedmeczowa
1. Z artefaktu `kb21-api-football-two-days` pobierz
   `KB21_ANALYST_WORKLIST_MANIFEST.json` i obydwa dzienne pliki
   `KB21_ANALYST_WORKLIST_YYYY-MM-DD.json`.
2. Dla danego `fixture_id` sprawdź faktograficzne dane sprzed meczu.
   Nie dopisuj brakujących statystyk; uwzględnij ich niepewność.
3. Wypełnij oddzielnie `str`, `qual`, `match` wraz z listami
   `str_evidence`, `qual_evidence`, `match_evidence`, każda z URL,
   notatką i rzeczywistym czasem odczytu.
4. Zanim zobaczysz kursy, zapisz wybór rynku, opis metody `p_model_method`,
   `p_model`, `confidence`, `reasoning`, `freeze_at`, `submitted_at`.
   Stosuj rzeczywiste czasy ISO ze strefą, NIE wpisy dopełniane wstecz.
5. Umieść takie analizy w prywatnym pliku JSON
   `{"assessments":[...oceny...]}`. Każdy rekord musi mieć też dokładnie
   zgodne z kolejką `fixture_id`, `fixture`, `kickoff`,
   `source_snapshot_utc`, `date_warsaw`.
6. Przeprowadź tylko walidację:

```bash
python -m tools.kb21_premarket_intake \
  --worklist-dir /sciezka/do/oryginalnego/artefaktu \
  --submissions-file /sciezka/do/przedmeczowych_ocen.json \
  --output-dir /sciezka/do/wynikow
```

Wynik `REVIEW_REQUIRED` oznacza jedynie poprawność formalną; nie jest
zatwierdzeniem prognozy przez niezależnego recenzenta. `INVALID` zawiera
powody odrzucenia. W szczególności:
- nieznane i zduplikowane `fixture_id` są odrzucane;
- niezgodne nazwy, daty, moment źródła oraz podpisy po kickoff nie przechodzą;
- analiza nie może wyprzedzać utworzenia źródła i kolejki;
- dowody odczytane po `freeze_at` są niedozwolone;
- pola kursów, wyniku, zysku, rozliczenia i konsensusu są niedozwolone.

**Data w ręcznie wprowadzonym JSON nie jest kryptograficznym dowodem**, że
ocena faktycznie powstała w danym momencie. Do pomiaru skuteczności
prospektywnej potrzebne są dodatkowo niezależne, niezmienne czasowo
artefakty tworzone przed początkiem meczu. Historia N nie może zostać
uzupełniona na podstawie samych późniejszych deklaracji.

## Co wykonuje automat dzienny
Po utworzeniu pełnej kolejki meczów generuje:
- `KB21_PREMARKET_REVIEW_YYYY-MM-DD.json` i `.md` na dziś i jutro;
- `KB21_PREMARKET_REVIEW_MANIFEST.json` z sumą i SHA-256 źródłowej kolejki.

**Nie podaje ocen ani P(model) automatycznie.** Bez dostarczonych
autentycznych analiz liczba gotowych ocen wynosi 0; informacja ta nie jest
awarią algorytmu. Nie dotyka żadnego innego modelu ani istniejących
rejestrów.

## Co nadal pozostaje do zrobienia
- rzeczywista seria minimum 10 NOWYCH, udokumentowanych ocen przedmeczowych,
  odseparowanych od starego N;
- niezależna kontrola jakości ocen i zapisów czasu;
- oddzielny etap *po* freeze: rzeczywisty kurs z dokładną linią, EV,
  Market Signal, Data Quality, Lineup Risk i jawna decyzja;
- dopiero po kontroli można rozważyć właściwy LIVE PDF.

Nie przełączaj `REVIEW_REQUIRED` na PLAY automatem. API Market,
Konsensus, SHADOW i PitchAPI pozostają odrębnymi procesami.
