# Checkpointy

## Główny KB Score

### N150
Status: wykonany / obowiązuje korekta od 25.09.2026.

Po N150:
- rdzeń Sport Score 35/35/30 bez zmiany,
- P(model) pozostaje surowe,
- P(cal) jest aktywnym decision checkiem diagnostycznym,
- rekordy 151+ są forward / out-of-sample,
- do N200 obowiązuje zamrożenie po korekcie N150.

### N200
Checkpoint automatyczny.

Zakres audytu:
- N1–150 vs N151–200,
- P(model) vs P(cal),
- Brier,
- log loss,
- kalibracja,
- PLAY / LEARN / CONTROL,
- ligi i rynki,
- wkład 35/35/30,
- Market Signal,
- Data Quality,
- Lineup Risk.

Korekty wyłącznie przy stabilnym sygnale. Po korekcie zapis do Parametry i read-after-write.

## Markets DEV

### DEV N150
Automatyczny audyt diagnostyczny osobno dla:
- GOLE / BTTS / TEAM TOTALS,
- ROŻNE,
- KARTKI,
- FAULE.

### DEV N250
Pełny audyt i możliwa korekta rodzin / parametrów / statusów tylko przy powtarzalnych danych.

### DEV N400
Ocena awansu każdej rodziny osobno do głównego KB.

Awans nie jest automatyczny. Wymaga odpowiedniej próbki, stabilnej kalibracji, dobrego Brier/log loss, wysokiej jakości danych i braku regresji.

## Zasada między checkpointami
Nie dostrajamy modelu po pojedynczych wynikach. Zbieramy czysty forward.
