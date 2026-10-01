# Aktualny model — KB Score 2.1

**Snapshot:** 2026-10-01  
**Status:** obowiązujący stan odniesienia.

## Codzienna praca
- Główny przebieg KB Score 2.1 pozostaje uruchamiany codziennie o **11:30 Europe/Warsaw**.
- Jedyną publikacją użytkową KB Score ma być dzienny PDF.
- GitHub jest kopią trwałej wiedzy o modelu i nie może blokować raportu 11:30.

## Calendar Gate — obowiązkowy przed skanem
Przed wyliczeniem P(model), rozpoczęciem głównego skanu lub zapisem jakiejkolwiek obserwacji należy najpierw ustalić kompletny kalendarz wydarzeń sportowych objętych zakresem KB Score na dany dzień.

Zasady:
- kalendarz należy potwierdzić w **oficjalnym źródle rozgrywek** (liga / federacja / organizator) oraz co najmniej **jednym niezależnym źródle kontrolnym**;
- trzeba jawnie sprawdzić obowiązkowy zakres głównego skanu: Premier League, La Liga, Serie A, Bundesliga, Ligue 1 oraz — jeśli grają i dane są dobre — Portugalia, Holandia, Belgia, Turcja i europejskie puchary; dodatkowo należy wykrywać inne istotne rozgrywki reprezentacyjne, w tym Ligę Narodów, eliminacje i turnieje międzynarodowe;
- dopiero po potwierdzeniu kompletności karty można przejść do P(model), Market Signal, Data/Lineup i freeze;
- jeśli źródła są niekompletne lub sprzeczne i nie da się potwierdzić pełnej karty, obowiązuje **STOP TRANSAKCJI** — bez normalnego PDF i bez zapisu nowych obserwacji;
- jeżeli pominięcie wydarzeń zostanie wykryte dopiero po rozpoczęciu spotkań, nie wolno retroaktywnie rekonstruować pre-match freeze, P(model), kursów ani sygnałów z wiedzą post-start;
- historycznych luk nie rekonstruujemy bez oryginalnego freeze.

Calendar Gate jest kontrolą kompletności danych wejściowych, a nie nową warstwą punktową. Nie zmienia mechanicznie P(model), P(cal), Sport Score ani P(HIT).

## Główny model
Sport Score / KB Score ma trzy części:
- Siła strukturalna: **35**
- Aktualna jakość gry: **35**
- Matchup / kontekst: **30**

Razem: **100**.

Sport Score nie zawiera ceny, EV, Market Signal ani Consensus.

## Prawdopodobieństwa
- **P(model)** — surowe prawdopodobieństwo modelu sportowego.
- **P(cal)** — warstwa kalibracyjna / diagnostyczna.
- P(cal) nie tworzy samodzielnie PLAY.
- Rynek nie zmienia mechanicznie P(model).

## Decyzje
Główne klasy:
- **PLAY**
- **LEARN**
- **CONTROL**

KB PLAY działa według bramki sprzed 13.09.2026, ale z podejściem Accuracy-First oraz z obecnymi warstwami kontrolnymi.

## Warstwy kontrolne
Aktywne:
- **Calendar Gate**
- **Market Signal**
- **Data Quality**
- **Lineup Risk**
- **Markets DEV**

Reddit i X są usunięte z KB Score 2.1 jako warstwy decyzyjne.

## Dane i zapis
Głównym rejestrem obserwacji pozostaje Google Sheet **„KB Score – Rejestr i Backtest”**.

Do N liczą się wyłącznie faktycznie zapisane obserwacje. Pustych przygotowanych wierszy nie liczymy.

Historycznych luk nie rekonstruujemy bez oryginalnego freeze.

## Zasada stabilności
Model nie powinien być dostrajany po pojedynczym wyniku. Między checkpointami zbierany jest czysty forward / out-of-sample, a korekty mają być wykonywane tylko przy stabilnym, powtarzalnym sygnale.
