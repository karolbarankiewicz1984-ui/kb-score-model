# MULTIMODEL — audyt end-to-end, 2026-11-02

Status: AUDYT CZĘŚCIOWY / OPEN; bez zmian produkcyjnych.

## Zweryfikowane fakty (GitHub API)
- Workflow `.github/workflows/api-market-multiday-experiment.yml` ma dwa harmonogramy UTC ze świadomym pomijaniem jednego slotu DST. Dla `workflow_dispatch` domyślne `days=2`; skrypt `args=(--days "${DAYS:-2}")` oznacza, że bez jawnego parametru nie ma gwarancji D+2. Nie przesądza to, że każda konkretna automatyczna sesja miała tylko dwa dni.
- Run 41317765320: conclusion=success, lecz brak artefaktów; w krokach checkout, scan i upload mają status skipped. To zamierzone pominięcie drugiego slotu DST, a NIE dowód awarii samego skanu. Nie kwalifikować jako poprawnego źródła.
- Run 41323529393: conclusion=success, artefakt api-market-multiday-experiment istnieje, size=99314 B, expired=false; kroki checkout, scan, upload zakończone sukcesem. Wciąż wymagane sprawdzenie dat wewnątrz i freeze.
- Run 41350611997 PitchAPI prematch: success, artefakt pitchapi-prematch-context size=274692 B. Weryfikacja pokrycia dat/fixture wymaga inspekcji zawartości.
- 2026-11-02: API Market Scan runs 41443035592 i 41486556120 success, ale to inny workflow; nie zastępują multiday.
- Raport etapu 6 Codex z 2026-11-01 jest migawką starszych źródeł i nie może służyć jako aktualny werdykt dla runów z późniejszego 1–2 listopada.
- Zgłoszone w raporcie etapu 6: KB Rejestr ostatni 2026-10-06, Konsensus Selections 2026-10-14, brak strukturalnych fixture ID, exact market, timestamp freeze; pełny shadow SOURCE_BLOCKED. Nie weryfikowano ponownie arkuszy w tym audycie.

## Wnioski i priorytety
P1: Kontrakt kwalifikacji runu: poprawny slot wykonania + conclusion success + artefakt istnieje + daty D/D+1/D+2 + statusy per data + poprawny przedmeczowy freeze. Zamierzony skip DST oznaczyć SKIPPED, nie FAILURE ani SUCCESS_WITH_DATA.
P1: Różnica trzech dat raportu vs domyślne dwa dni workflow; sprawdzić faktyczny plan w automatycznych i manualnych wywołaniach przed zmianą konfiguracji.
P1: Brak potwierdzenia świeżych formalnych prognoz KB21/Konsensus, więc nie nazywać zestawu API pełnym MULTIMODEL TOP.
P1: Udokumentować lineage quote: exact market, bookmaker, timestamp, kickoff, źródło i identyfikator oryginalnej publikacji; brak nie może być zastąpiony późniejszą ceną.
P2: Full candidate pool dla fauli under <67, bez wpływu na TOP/N.
P2: Rozliczenia i ROI osobno dla TOP/API/fauli; brak dowodów -> AUDYT NIEPEŁNY.
P2: Kontrola PDF i dostarczenia trzech rzeczywiście istniejących plików niezależna od zielonego workflow.

## Niewykonane testy i ograniczenia
Nie pobrano i nie rozpakowano binarnych artefaktów 41323529393 i 41350611997; nie potwierdzono dat i pełnych wierszy. Nie sprawdzono ponownie arkuszy. Nie odtworzono ani nie uruchomiono wszystkich testów lokalnie. Nie wykonano porównania matematyki modelu ani backtestu. Żadnych zmian produkcyjnych, merge, płatnych wywołań API.

## Rejestr
2026-11-02 | E2E-001 | Rozróżnić DST skip od poprawnego skanu | OPEN.
2026-11-02 | E2E-002 | Zweryfikować pokrycie trzech dat i manifest per-date | OPEN.
2026-11-02 | E2E-003 | Zweryfikować aktualne freeze KB/Konsensus | OPEN.
2026-11-02 | E2E-004 | Zweryfikować rzeczywiste artefakty API/PitchAPI | OPEN.
2026-11-02 | E2E-005 | Audyt audytów ROI i PDF delivery | OPEN.
