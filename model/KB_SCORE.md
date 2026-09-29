# KB Score — rdzeń

## Sport Score 0–100
KB Score jest oceną sportową przed sprawdzeniem ceny.

Skład:
- **35 pkt — siła strukturalna**
- **35 pkt — aktualna jakość gry**
- **30 pkt — matchup / kontekst**

## Główne dane
W piłce nożnej model bierze pod uwagę m.in.:
- długoterminową siłę / ELO,
- jakość kadry i ligi,
- xG / xGA i underlying stats,
- strzały i jakość sytuacji,
- formę skorygowaną o poziom rywali,
- home / away,
- matchup stylów,
- kluczowe absencje,
- odpoczynek i istotny kontekst.

H2H, motywacja, trener i terminarz są korektami, jeśli rzeczywiście wnoszą informację.

## Ważna zasada
Nie wolno liczyć tej samej informacji kilka razy.

Na początku sezonu mała próbka bieżącej formy i xG powinna być silnie regresowana do długoterminowej siły.

## Cena
Kurs i rynek są sprawdzane dopiero po zbudowaniu P(model).

- fair odds = 1 / P(model)
- implied probability = 1 / kurs
- no-vig probability — gdy dostępny jest kompletny wiarygodny rynek
- Edge = P(model) - P(no-vig)
- EV = P(model) × kurs - 1
