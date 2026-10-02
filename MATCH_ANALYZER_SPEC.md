# KB Match Analyzer — specyfikacja SIM

**Status:** obowiązująca specyfikacja aplikacji towarzyszącej KB Score 2.1  
**Data:** 2026-10-02

## Cel
KB Match Analyzer pozwala wskazać pojedynczy mecz (docelowo także przez Udostępnij z Flashscore), rozpoznać drużyny, datę i rozgrywki, pobrać dane przedmeczowe i wykonać analizę aktualnym KB Score 2.1.

## SIM Isolation Rule — twarda zasada
Match Analyzer jest wyłącznie klientem SIM/read-only modelu. Nie jest źródłem uczenia KB.

Analizy SIM:
- nigdy nie zwiększają głównego N;
- nigdy nie zwiększają DEV N ani N rodzin DEV;
- nie zapisują do Rejestru ani Rynki_DEV;
- nie zmieniają Parametrów ani Kalibracji;
- nie uruchamiają checkpointów N200 / DEV150 / DEV250 / DEV400;
- nie mogą automatycznie dostrajać modelu na podstawie wyników SIM;
- mogą być zapisywane wyłącznie w odrębnej historii SIM_HISTORY.

Nawet 10 000 rozliczonych analiz SIM daje wpływ na oficjalne N równy 0.

## Źródło logiki
Analyzer używa aktualnej wersji KB Score 2.1 zapisanej w repozytorium kb-score-model. Nie tworzy konkurencyjnej wersji modelu.

Obowiązujące elementy:
- Calendar Gate;
- Sport Score 35/35/30;
- surowe P(model);
- P(cal) jako diagnostyczny decision check;
- Accuracy-First;
- Market Signal: CONFIRM / NEUTRAL / CONFLICT;
- Data Quality: A / B / C;
- Lineup Risk: LOW / MED / HIGH;
- decyzje SIM PLAY / LEARN / CONTROL;
- osobna prezentacja Markets DEV bez wpływu na DEV N.

## Przepływ
1. Użytkownik udostępnia link/tekst meczu albo wyszukuje drużyny i datę.
2. Analyzer identyfikuje dokładne spotkanie.
3. Calendar Gate potwierdza mecz, rozgrywki, datę i godzinę.
4. Pobierane są dane sportowe dostępne przed spotkaniem.
5. Liczony jest Sport Score 35/35/30 i P(model).
6. Wyświetlany jest P(cal) jako kontrola diagnostyczna.
7. Dopiero potem oceniany jest Market Signal.
8. Osobno oceniane są Data Quality i Lineup Risk.
9. Bramka Accuracy-First nadaje SIM PLAY / LEARN / CONTROL.
10. Snapshot analizy może zostać zapisany do SIM_HISTORY.
11. Po meczu exact-market może zostać rozliczony WIN / LOSS / PUSH.
12. Statystyki SIM służą użytkownikowi do obserwacji skuteczności, ale nie uczą oficjalnego KB.

## Wynik pojedynczej analizy
Ekran wyniku powinien pokazywać co najmniej:
- drużyny, rozgrywki, datę i godzinę;
- wersję/revision KB;
- status Calendar Gate;
- Sport Score i składowe 35/35/30;
- P(model), P(cal), Confidence;
- Market Signal;
- Data Quality;
- Lineup Risk;
- typ i status SIM;
- fair odds;
- kurs, implied probability, no-vig, Edge i EV tylko przy wiarygodnym exact-market;
- krótkie uzasadnienie;
- ryzyka;
- jasne oznaczenie „SIM — wpływ na N: 0”.

## Historia i skuteczność
SIM_HISTORY może przechowywać snapshot analizy i późniejsze settlementy. Panel skuteczności może liczyć m.in. hit rate, ROI, Brier, log loss, kalibrację, CLV (tylko z wiarygodnym closing snapshotem) oraz segmenty PLAY/LEARN/CONTROL, ligi, rynki, Market/Data/Lineup.

SIM_HISTORY jest analityką użytkową, nie datasetem uczącym główny model.

## Zasada danych
Flashscore ma służyć przede wszystkim jako wygodny sposób wskazania meczu. Analyzer nie powinien uzależniać silnika KB od scrapowania interfejsu Flashscore. Po identyfikacji meczu dane mają pochodzić z jawnych, kontrolowanych źródeł/API i źródeł wymaganych przez KB Score 2.1.

Jeżeli wiarygodnych danych brakuje, Analyzer pokazuje brak danych i obniża Confidence/status zamiast zgadywać lub generować fałszywy PLAY.
