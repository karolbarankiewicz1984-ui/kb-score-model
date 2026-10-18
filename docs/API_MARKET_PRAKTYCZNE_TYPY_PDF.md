# API Market — krótki PDF z konkretnymi rynkami do sprawdzenia

## Cel

Dotychczasowe pliki `KB21_FORM_*.pdf` oraz `KB21_XG_V_GOALS_SHADOW_*.pdf`
przedstawiają **badania sportowe**, a nie wybór zakładu. Zostają bez zmian.

Właściwe rynki (np. poniżej 2,5 gola drużyny, powyżej 3,5 rożnych)
liczy odrębny silnik **API Market**. Istniejący wielostronicowy
`API_MARKET_SCAN_YYYY-MM-DD.pdf` zawiera pełne zestawienie.

Nowy raport `API_MARKET_PRAKTYCZNE_TYPY_YYYY-MM-DD.pdf` ma umożliwić
szybkie znalezienie konkretnego rynku bez przeszukiwania setek pozycji.

## Jakie dane pokazujemy

- Najwyżej **6 rynków bramkowych i 6 innych** (kartki, rożne, faule itp.)
  na jedno bieżące przedmeczowe wydanie.
- Maksymalnie **jeden wariant na mecz** w całym krótkim raporcie.
  Kilka wariantów jednego meczu to powiązane, nie niezależne typy.
- Obowiązują ustalone zasady API Market: ocena końcowa co najmniej
  **67/100**, oferta API dla dokładnego wariantu z kursem **co najmniej 1,20**,
  brak linii już rozpoczętych spotkań.
- Przy każdym wariancie: mecz, **godzina rozpoczęcia w Polsce**,
  **dokładna linia i kierunek**, ocena, najwyższy kwalifikujący się
  **kurs źródłowego API i dostawca tego kursu**.
- Pochodzenie prognozy jest zachowane; renderer nie wprowadza
  nowych danych ani nie modyfikuje historii, P(model), ocen,
  liczników N ani niezależnego modelu xG.

## Granice

- `ocena 80/100` nie jest matematycznie udowodnionym
  prawdopodobieństwem 80% trafienia, a `API PURE` jest oddzielnym
  wskaźnikiem historycznego pokrycia.
- **Dane API nie potwierdzają oferty STS ani Superbet.** Należy sprawdzić
  dokładną linię, zasady rozliczenia, wysokość kursu i godzinę
  rozpoczęcia we własnej aplikacji bukmacherskiej.
- Kursy nie są odświeżane w samym PDF; na nagłówku jest UTC
  ostatniego pobrania notowań. Po rozpoczęciu meczu PDF
  staje się archiwalnym świadectwem przedmeczowego rankingu.
- Nie należy traktować krótkiej listy jako pewnych zakładów,
  gwarancji ROI czy sygnału do zwiększania stawki.

## Automatyzacja

Zmiana dotyczy wyłącznie prezentacji istniejącego API Market.
Workflow `.github/workflows/api-market-scan.yml` generuje nowy,
niedługi PDF razem z pełnym raportem, a następnie publikuje
oba w `reports/api_market_scan/`. Nie wpływa na
`KB21 SINGLE SOURCE`, na analizy xG ani na originalny N.

Komenda:
`python tools/api_market_practical_pdf.py 2026-10-18`

Regresja:
`python -m unittest tests.test_api_market_practical_pdf -v`.
