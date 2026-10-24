# KB Score 2.1 — odzyskiwanie z dawnych rozmów, Google Drive i biblioteki ChatGPT

Data przeglądu: **24 października 2026 r.**  
Tryb: **tylko odczyt danych pierwotnych, tylko dokumentacja**. Oryginalny arkusz Google niezmieniony; historyczne `N`, oznaczenia LIVE i SHADOW bez zmian.

## Co zostało sprawdzone

1. Dostępne pliki na Dysku Google (wyszukiwanie po nazwach i szerokie przeglądanie):
   - **KB Score – Rejestr i Backtest**: `https://docs.google.com/spreadsheets/d/1Raay44yu5OUefV4czv4TN4Xa_SQ5K5txUUPf1WHvXUI/edit` — arkusz pierwotny.
   - **Konsensus – Rejestr** — **osobny model**, nie używać go do wyliczania KB.
   - Nie znaleziono **oddzielnego, nazwanego pliku z algorytmem P(model)**. To nie wyklucza innych nieindeksowanych/deleted źródeł.
2. Dawne rozmowy ChatGPT odnalezione semantycznie — szczególnie 7–22.08, 3–10.09, 19–29.09. **To wybór odzyskanych ustaleń, a nie kompletny eksport wszystkich wątków.**
3. Historyczne pliki Biblioteki ChatGPT, m.in.:
   - `KB_Score_Rejestr.xlsx` (7.08.2026) — najwcześniejszy odnaleziony w bibliotece szablon.
   - `KB_Score_Rejestr_v2.xlsx` i `KB_Score_Rejestr_Backtest.xlsx` (11.08.2026) — dokumentacja PLAY/LEARN/CONTROL i odrębnego backtestu.
   - `SPEC.md` (4.09.2026) — **KB Sports Center**, architektura SANDBOX/SHADOW, zakaz nadpisywania LIVE, potrzeba trwałego model/version log.
   - `KB_Score_2_1_2026-09-17_Reddit_Signal.pdf`, `KB_Score_2_1_2026-09-19.pdf`, `KB_Score_2_1_2026-09-28.pdf`, `KB_Score_2_1_2026-10-02.pdf` — przykłady bramki PLAY i kontrolnych pól, nie dowód autentycznego pregame freeze.
4. Oryginalny rejestr i zakładki `Parametry`, `Kalibracja` — ponownie sprawdzone bez zapisu.

## Odkrycie zasadnicze: dawne rozmowy nie zawierają kompletnego wzoru P(model)

W rozmowie z **22 sierpnia 2026, ok. 10:35 czasu Warszawy** sam ówczesny opis wskazywał brak jednej jawnej powtarzalnej funkcji wyliczającej `P(model)`.
Proponowana metodologia była **analityczna**, z bazową szansą `P_base` wynikającą z siły drużyn, xG, przewagi własnego boiska i formy, oraz niewielkimi poprawkami za absencje/matchup.
Nie odnaleziono w dawnych rozmowach potwierdzonego zestawu współczynników, logitu ani kompletnego deterministycznego kodu `P(model)`.

**Konsekwencja:** nie przypisywać modelowi fikcyjnej starej formuły; nowy silnik statystyczny wymaga osobnego identyfikatora wersji, walidacji i N.

## Nowe istotne znalezisko: rzeczywiste wartości P(cal) po N150

W rozmowach z **25.09.2026** zatwierdzono:
- surowe `P(model)` **bez zmiany**;
- `P(cal)` jako aktywny **diagnostyczny decision check**, nie nowa liczba podstawiana do historycznego EV;
- wyniki od N151 = forward/out-of-sample, parametry zamrożone do N200;
- na podstawie N150 przybliżona korekta słabo skalibrowanych zakresów 55–80%;
- **schodkowe przybliżenia**, a nie zatwierdzona interpolacja. Wprowadzenie interpolacji padło jako propozycja, lecz nie zostało zatwierdzone.

W aktualnym oryginalnym `Rejestr!A151:AJ205` odnaleziono **23 notatki** zawierające jawnie parę `P(model)→P(cal)`; zgodne wartości obserwowane, nie uogólniony algorytm:

| Surowe P(model) | Zapisane P(cal) | Uwagi |
| ---: | ---: | --- |
| 52–54% | 54% | Rejestr: 52/53/54 → 54 |
| 57% | 65% | 1 zapis |
| 60–64% | 70% | 60/61/64 → 70 |
| 65–74% | 75% | 65/66/68/70/72/74 → 75 |
| 76–78% | 83% | 76/78 → 83 |

**UWAGA:** tabela to **przykłady**, nie dowód pełnych progów; brak punktów granicznych 55/56%, 59%, 75%, 79–80%, >80% i nie ma odtworzonych reguł interpolacji ani podstaw kalibracji poza próbką. Nie generować P(cal) dla brakujących przedziałów przez domysły.

Niezależny raport z **2.10.2026** również pokazuje `P(model) 68%→P(cal) 75%`, `61→70`, `72→75`, `64→70`; P(cal) **nie tworzy** PLAY.

### Wynik kalibracji arkusza = niekoniecznie formuła zastosowania

Zakładka `Kalibracja` ma biny `P(model)`, liczbę zdarzeń, średnią przewidywaną skuteczność, faktyczny HIT, Brier i log loss. Są to historyczne **statystyki**, nie wzór zamieniający punktowy `P(model)` na `P(cal)`. Wysoka próbka/trafność w binie nie uzasadnia automatycznego przypisywania `P(cal)=HIT` bez walidacji.

## Odtworzony oryginalny proces — potwierdzone na wielu źródłach

1. **Terminarz/Calendar Gate** i źródła faktów przed meczem; oryginalna zasada kontrolnego niezależnego źródła; późniejsza decyzja użytkownika o jednym głównym API-Football terminarzu należy do nowego pipeline'u, nie przepisywać historii.
2. **Sport Score**, wyłącznie sportowy: `STR/35` długofalowa siła/ELO; `QUAL/35` xG/xGA + skorygowana forma (gdy xG brak, nie oznacza automatycznego zera); `MATCH/30` dom/wyjazd, ryzyko kadry, styl, odpoczynek. Unikać podwójnego liczenia tego samego czynnika.
3. **P(model)** i konkretna linia rynku przed kursem. Niezależne `P(HIT)` to ranking dokładnego prawdopodobieństwa trafienia, a nie Value.
4. Po **N100** model był zamrożony do N150 i P(cal) tylko SHADOW; po **N150, 25.09** P(cal) aktywny jako diagnostic decision check. Nie dodawać P(cal) do Sport Score.
5. **Kontrola ceny** po freeze: uczciwy kurs = 1/P, raw implied = 1/odds, no-vig przy pełnym rynku, EV = P(model)×odds−1, niezależne Confidence i data-risk.
6. **Decyzja**: PLAY/LEARN/CONTROL, bramka Accuracy-First i realne kontrargumenty. Od 19.09 przywrócono bramkę sprzed 13.09 (nie odrzucać wszystkich plus-value tylko z powodu późniejszego surowszego filtru).
7. Od **27.09** `Market Signal CONFIRM/NEUTRAL/CONFLICT`, `Data Quality A/B/C`, `Lineup Risk LOW/MED/HIGH` zastępują Reddit/X w podstawowej kwalifikacji; w żadnym przypadku nie zmieniają wstecz P(model).
8. **Write → read-after-write → N → PDF**. W rozmowach z 20.09 i starszych dokumentach wymagano rzeczywistego zapisu/odczytu arkusza, brak danych nie może podnosić N. Oryginalny arkusz nie jest tylko raportem, lecz historycznym rejestrem LIVE.

## Zasady niezmienności i pytania do dalszego odzyskania

- Nie kopiuj modelu `Konsensus` do KB Score. Nie kopiuj `CORE v1R` ani `Markets DEV` do oryginalnego P(model).
- Wczesna specyfikacja **KB Sports Center** deklarowała SANDBOX/SHADOW i odrębną bazę. W rozmowie 17.09 użytkownik wycofał Base44 z głównego procesu. **Nie przywracać Base44 jako wymaganego komponentu.**
- Stare raporty (PDF) są śladem wyliczeń i decyzji, **nie automatycznym potwierdzeniem**, że prawdopodobieństwo lub kurs faktycznie zamrożono przed startem.
- Przy odtwarzaniu pełnego silnika pozostaje niewiadoma **surowa funkcja `P(model)`** oraz **subwagi** STR/QUAL/MATCH.
- Aby opracować nowy automatyczny następca: osobny candidate/SHADOW, archiwalne porównania bez post-hoc lookahead, datowany przedmeczowy freeze na nowych meczach, późniejsze rozliczenie i kalibracja; nie zmieniać oryginalnych 179 prognoz ani N.

## Co wnosi ponowna kontrola względem dokumentu z wcześniejszego dnia

**Nowe, nieobecne w samym przeglądzie GitHuba:** 
1. ślad z rozmowy 22.08 przyznający brak jednego deterministycznego P(model);
2. ustalenie N150 z 25.09: schodkowe przykłady P(cal), interpolacja niezatwierdzona;
3. 23 zapisane pary P(model)/P(cal) w Google, przy zachowaniu braku pełnej funkcji;
4. pliki z **7 i 11 sierpnia** i PDF-y w bibliotece ChatGPT, istniejące przed GitHubem;
5. specyfikacja KB Sports Center z 4.09 wskazująca dodatkowe wcześniejsze próby migracji, niepotwierdzająca jednak oryginalnego silnika LIVE.

Nie nastąpiła żadna zmiana ustawień modelu, publikacji PLAY, oryginalnego `N` ani źródłowego Google Sheets.
