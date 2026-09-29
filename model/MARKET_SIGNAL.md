# Market Signal

Aktywny od 27.09.2026 jako warstwa kontrolna KB Score 2.1.

## Kolejność
Najpierw wyliczane jest P(model) niezależnie od bieżącego ruchu kursu. Dopiero potem oceniany jest rynek.

## Analiza rynku
Gdy dane są dostępne:
- opening → current → closing,
- no-vig probability,
- kierunek i siła ruchu,
- rozbieżności między wiarygodnymi źródłami.

## Status
- **CONFIRM** — istotny ruch zgodny z tezą KB,
- **NEUTRAL** — brak istotnego sygnału,
- **CONFLICT** — istotny ruch przeciw tezie.

## Zasada
Market Signal:
- nie zmienia mechanicznie P(model),
- nie zmienia mechanicznie P(cal),
- nie zmienia Sport Score,
- nie tworzy samodzielnie PLAY,
- może potwierdzić, osłabić lub zablokować awans.

Preferowane źródła price discovery: Pinnacle i Betfair Exchange. Historia / porównanie: OddsPortal / Oddschecker. Gdy możliwe, co najmniej dwa niezależne źródła kursowe.
