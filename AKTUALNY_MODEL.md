# Aktualny model — KB Score 2.1

**Snapshot:** 2026-09-29  
**Status:** obowiązujący stan odniesienia.

## Codzienna praca
- Główny przebieg KB Score 2.1 pozostaje uruchamiany codziennie o **11:30 Europe/Warsaw**.
- Jedyną publikacją użytkową KB Score ma być dzienny PDF.
- GitHub jest kopią trwałej wiedzy o modelu i nie może blokować raportu 11:30.

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
