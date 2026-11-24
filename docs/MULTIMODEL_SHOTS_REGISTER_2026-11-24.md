# MultiModel V2 — strzały, start prac badawczych (24.11.2026)

Polecenie użytkownika: dołożyć **strzały ogółem** i **strzały celne**. Poprzedni warunek „dopiero po faulach i kartkach” zostaje zmieniony dla odizolowanych badań; blokady dyscyplinarne #84/#78 nadal obowiązują dla fauli i kartek.

## Rejestr wykonania
- [x] Zadanie #88 z kryteriami odbioru i zakazem fikcyjnych kursów.
- [x] Izolowany moduł `github_models/shots_research.py`: walidacja chronologii, IDs, definicji strzałów i braków; eksperymentalny baseline Poissona przy >=5 obserwacjach; filtr rzeczywistych archiwalnych kursów Superbet >=1,20; łączny mecz tylko z dwóch rzeczywistych stron.
- [x] Testy offline `tests/test_multimodel_shots_research.py` przygotowane. **CI i integracja produkcyjna niepotwierdzone**.
- [ ] Ustalić semantykę i niezależne publikowane źródła (PitchAPI / dane historyczne tylko read-only; żadnego API-Football jako nowego feedu). `stat_definition_verified=True` musi wynikać z dowodu, nie z założenia.
- [ ] Zbudować prawdziwy prematch pipeline snapshotów historycznych i prospektywnych (cutoff), kalibrację dystrybucji i statusy missing.
- [ ] Zmapować realne market IDs OddsPapi Superbet, scope (mecz/drużyna), line, period i wybór; **zero nowych płatnych API calls bez osobnej decyzji**.
- [ ] Użyć odrębnych prognoz strzałów w `SHADOW`, następnie po CI w istniejących **dwóch** PDF, nie dodawać trzeciego raportu.
- [ ] Prospektywne, niezależne rozliczenia i metryki Brier/log-loss na różnych meczach, holdout przed decyzją o promocji typu.

## Stałe ograniczenia
Nie zmieniamy A/B/C, ich wag, wcześniej zamrożonych N, historii prognoz ani filtrów. Poisson dla count jest **baseline badawczym**, nie skalibrowaną rekomendacją: nie wolno wystawiać PLAY, EV, ROI ani wartości kursowej na jego podstawie. Brak pokrycia / sprzeczna semantyka = brak prognozy. Historyczne wydarzenie rozegrane wcześniej, ale opublikowane później niż cutoff, jest niedostępne w przewidywaniu. Strzały celne nie są tożsame z xGOT; strzały ogółem nie są tożsame z golami.
