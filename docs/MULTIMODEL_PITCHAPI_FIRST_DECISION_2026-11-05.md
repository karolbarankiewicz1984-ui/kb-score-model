# MULTIMODEL — przejście na PitchAPI (2026-11-05)

Decyzja operatora: tymczasowo odstawić API-Football jako źródło nowych danych. Aktywne źródło nowego pobierania: PitchAPI. Zachować archiwa API-Football i wszystkie historyczne freeze, TOP, N, rozliczenia oraz niezmienione modele. Nie uruchamiać nowych zapytań API-Football dla MULTIMODEL.

PitchAPI dostarcza kontekst statystyczny i terminarz; nie wolno uznawać go automatycznie za źródło kursów exact-market ani gotowych ocen API Market. Do czasu niezależnej weryfikacji kursów nowe raporty mają status analizy obserwacyjnej, bez wymyślonych typów i ROI. KB Score 2.1 oraz Konsensus pozostają źródłami historycznymi, nie blokują analizy PitchAPI-only. FAULE UNDER jest zwykłym rynkiem ogólnym, bez osobnej sekcji i priorytetu.

Wykonano: aktualizacja harmonogramowanej automatyzacji MULTIMODEL 3 PDF i audyt, ID 6ad4abe025748191811addea223a01d3; godzina 11:30 Europe/Warsaw bez zmian. Do wykonania: implementacja rzeczywistego generatora PitchAPI-first, testy danych, trzy PDF E2E i wyłączenie niepotrzebnych workflow API-Football po osobnym przeglądzie zależności. Nie deklarować wdrożenia generatora produkcyjnego przed testami.
