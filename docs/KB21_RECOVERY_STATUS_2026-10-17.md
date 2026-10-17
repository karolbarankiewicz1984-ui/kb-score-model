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
