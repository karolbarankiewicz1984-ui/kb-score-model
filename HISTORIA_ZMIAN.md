# Historia zmian

Ten plik jest trwałym dziennikiem istotnych zmian modelu.

## 2026-10-01 — obowiązkowy Calendar Gate
**Co zmieniono:**  
Dodano obowiązkową kontrolę kompletności kalendarza przed rozpoczęciem dziennego skanu KB Score 2.1. Najpierw trzeba potwierdzić pełną kartę wydarzeń w oficjalnym źródle rozgrywek i co najmniej jednym niezależnym źródle kontrolnym. Kontrola obejmuje nie tylko top-5 i puchary, ale również istotne rozgrywki reprezentacyjne, m.in. Ligę Narodów, eliminacje i turnieje międzynarodowe.

Jeśli kompletności kalendarza nie można potwierdzić, obowiązuje STOP TRANSAKCJI: brak nowych freeze i brak normalnego PDF. Jeżeli pominięcie zostanie wykryte po rozpoczęciu meczów, nie rekonstruuje się retroaktywnie pre-match P(model), kursów ani sygnałów.

**Dlaczego:**  
W przebiegu 01.10.2026 etap wykrywania kalendarza pominął dzisiejsze mecze Ligi Narodów i skan przeszedł głównie na UWCL. Był to błąd kompletności wejścia, a nie świadomy filtr KB. Wymagał wycofania wadliwej dziennej transakcji zamiast rekonstruowania freeze po starcie meczów.

**Dowody / checkpoint:**  
Błąd wykryto przed uznaniem dnia za prawidłowy forward. Calendar Gate nie zmienia Sport Score 35/35/30, P(model), P(cal) ani checkpointów N150/N200 i DEV150/250/400. Jest warunkiem wejścia do skanu.

**Od kiedy obowiązuje:**  
01.10.2026, natychmiast dla każdego kolejnego dziennego przebiegu.

**Poprzednia wersja:**  
Snapshot 2026-09-29 bez osobnego obowiązkowego Calendar Gate.

---

## 2026-09-29 — utworzenie trwałej dokumentacji GitHub
Utworzono pierwszą wersję dokumentacji obecnego KB Score 2.1.

Cel:
- zabezpieczenie modelu przed utratą ustaleń w długich rozmowach,
- możliwość odtworzenia zasad obowiązujących w danym okresie,
- zachowanie historii kolejnych korekt,
- rozdzielenie danych historycznych od logiki modelu.

Nie zmieniono sposobu codziennego działania KB Score ani raportu PDF o 11:30.

## Stan obowiązujący w snapshotcie
- rdzeń Sport Score: **35 / 35 / 30**,
- korekta N150 obowiązuje od **25.09.2026**,
- po N150 główny model zamrożony do checkpointu N200,
- rekordy **151+** traktowane jako forward / out-of-sample,
- od **27.09.2026** Market Signal oraz Data/Lineup zastępują warstwę Reddit/X,
- Reddit i X są usunięte z KB Score 2.1,
- Markets DEV ma własne N i własne checkpointy.

---

## Szablon kolejnej zmiany

### RRRR-MM-DD — nazwa zmiany
**Co zmieniono:**  
...

**Dlaczego:**  
...

**Dowody / checkpoint:**  
...

**Od kiedy obowiązuje:**  
...

**Poprzednia wersja:**  
...
