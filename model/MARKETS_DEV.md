# Markets DEV 0.2

Markets DEV jest niezależną warstwą badawczą od głównego KB.

## Rodziny
- GOLE / BTTS / TEAM TOTALS
- ROŻNE
- KARTKI
- FAULE

## Dane
Każda obserwacja DEV ma mieć:
- datę analizy i wydarzenia,
- ligę,
- wydarzenie,
- rodzinę,
- dokładny rynek i typ,
- P(model),
- fair odds,
- Confidence,
- jakość danych,
- status,
- uzasadnienie,
- źródła.

Kurs, implied, Edge i EV tylko wtedy, gdy dokładny kurs jest wiarygodny.

## Liczenie
DEV ma własne ID i własne N. Nie zwiększa głównego N.

Jedna obserwacja = jedna niezależna teza.

## Checkpointy
- DEV N150 — audyt diagnostyczny,
- DEV N250 — pełny audyt + możliwa korekta,
- DEV N400 — ocena awansu każdej rodziny osobno.

Między checkpointami DEV jest zamrożony i zbiera czysty forward.

Cel 10–20 nowych jakościowych obserwacji dziennie jest orientacyjny. Nie nabijamy N na siłę.
