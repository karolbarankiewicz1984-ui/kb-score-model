# KB Score — odtworzenie oryginalnego LIVE 2.1 z Dysku Google
**Audyt 24.10.2026 | baza oryginalna: Dysk Google | zapis kopii: prywatny GitHub**

## Co rzeczywiście zostało odzyskane

Źródłem danych była historia arkusza Google **„KB Score – Rejestr i Backtest”**,
a nie późniejsze repozytorium GitHub. Do repozytorium trafiła tylko **pochodna
kopia historycznych pól modelu**, nie pełen eksport arkusza ani dane właściciela.

- Plik: [data/kb21_google_restore/original_live_recovered_2026-10-24.json](../data/kb21_google_restore/original_live_recovered_2026-10-24.json).
- **179** historycznych wpisów LIVE z okresu 22.08–06.10.2026, każdy ma:
  oryginalne P(model), Sport Score, Confidence, kurs, EV, dokładnie zapisaną
  historyczną etykietę PLAY / LEARN / CONTROL, wskazanie rynku i meczu.
- Etykiety: **49 PLAY, 42 LEARN, 88 CONTROL**.
- **137 / 179** ma odczytane trzy dokładne składniki STR/35, QUAL/35,
  MATCH/30; każda odzyskana trójka sumuje się do oryginalnego Sport Score.
  **42 / 179** nie mają składników w rozpoznawalnym zapisie.
  Te składowe pozostają **brakujące**, nie wstawiono zer ani szacunków.
- EV przeliczono równaniem P(model) × kurs − 1. Brak rozbieżności
  większych niż 1 punkt procentowy w próbie 179 zapisów.
- Zachowano numer historycznego wpisu oraz ID i czas najwcześniejszej
  **spośród zbadanych** rewizji arkusza, która zawierała dany wpis.

## Granica dowodowa — koniecznie przeczytać

Google Drive zwrócił **9** historycznych rewizji arkusza (m.in. 60, 64,
71, 81, 94, 103, 116, 132, 248). Próby odczytu rewizji 147, 173 i 202
zostały ograniczone przez Google (HTTP 429), dlatego **nie** jest to pełny
przegląd 93 rewizji. W archiwum pole \`earliest_sampled_revision\` oznacza
**pierwszą ze skutecznie sprawdzonych**, a nie absolutnie pierwszą
wersję zawierającą ocenę.

- **12** ocen po raz pierwszy widzimy w tym zbiorze rewizji **w dniu**
  zapisanego meczu. Ponieważ arkusz nie przechowuje dokładnego kickoff,
  ta data nie dowodzi, że ocena została zapisana przed rozpoczęciem.
- **167** ocen w naszej rzadkiej próbce rewizji po raz pierwszy widzimy
  **po dacie meczu**. To **nie dowodzi**, że pierwotne oceny powstały
  po meczu — mogły istnieć we wcześniejszych, niepobranych wersjach.
- **0** ocen ma w tej próbce rewizję sprzed daty meczu.
- W żadnej nie udowodniono niezależnie, że P(model) zamrożono **przed
  poznaniem kursu**. Sam oryginalny arkusz zawiera w tym samym wierszu kurs
  i P(model). Nie wolno wstecz dopisywać potwierdzenia kolejności.

**Żaden wpis archiwalny nie zwiększa obecnego N i nie jest nową
rekomendacją PLAY.** Oryginalny arkusz pozostał bez zmian.

## Historia modelu — co należy odtworzyć, a czego NIE mieszać

### Pierwsza wersja (12.08)
Wersja pierwsza miała 10 czynników: Forma 15; ELO 15; xG 15; dom/wyjazd 10;
absencje 10; motywacja 10; H2H 5; ruch kursów 10; Value 5;
ryzyko/dane 5. Ówczesne progi: PLAY 80, LEARN 74–79, CONTROL 68–73.
To **nie jest** układ LIVE 2.1.

### Wersja 2.0 (rewizja 50, 22.08.2026 08:26 UTC)
STR 30, QUAL 30, MATCH 20, rynek/cena 20 — czyli cztery bloki.
Orientacyjne decyzje z progami; brak limitu liczby PLAY.

### Wersja 2.1 (rewizja 58, 22.08.2026 09:25 UTC)
**STR 35 + QUAL 35 + MATCH 30.** Sport Score jest bezkursowy. Rynek,
Consensus i Confidence są osobnymi warstwami. Oryginalna polityka:
- wyznacz kierunek i P(model) **przed kursem**;
- osobno oceniając dane, formę, xG, absencje, siłę przeciwników;
- później sprawdź no-vig, fair odds, EV, contrarian, jakościowe blokery;
- PLAY / LEARN / CONTROL **nie mają twardego progu punktów**;
- robocze minimum EV: Conf 8–10: 2%; Conf 6–7: 3,5%; Conf 5: 5%;
  Conf poniżej 5: bez PLAY — wyjątki wymagają osobnego wyjaśnienia;
- LEARN/CONTROL bez realnego budżetu gry; służą do diagnostyki;
- przy 50 rozliczonych pierwsza kalibracja; zmiana po 100+
  obserwacjach i powtarzalnym sygnale.

Rewizja 60 z 22.08.2026 o 12:07 UTC zawiera pierwsze odnalezione
oryginalne oceny 2.1 (jeszcze przed późniejszymi aktualizacjami
settlementów), np. Everton – Crystal Palace: STR 27, QUAL 25,
MATCH 27, Sport Score 79, P(model) 48%, historyczna etykieta PLAY.
To konkretne **dane archiwalne**, nie dzisiejszy typ.

## Co odzyskaliśmy w sensie wykonawczym

1. [tools/kb21_google_original_restore.py](../tools/kb21_google_original_restore.py)
   to odtwarzalny, testowalny parser archiwalnego eksportu Google revisions.
2. Parser wybiera najwcześniej **obserwowany** wpis, nawet jeśli później
   zmieniono wynik lub etykietę; takie modyfikacje raportuje jako drift.
3. Weryfikuje sumę trzech składników, zakresy P i punktów oraz EV.
4. Klasyfikuje datę pierwszego potwierdzonego odczytu jako wcześniejszą
   od daty meczu, tę samą (godzina nieznana) lub późniejszą.
5. Odmawia domyślnego uznania historii za nowy przedmeczowy freeze,
   automatyczny typ lub wyznaczenie oryginalnego P(model).

Przykład użycia na *własnych, prawdziwych* eksportach rewizji:

```bash
python -m tools.kb21_google_original_restore manifest.json --output restored.json
```

Manifest: \`{"revisions":[{"revision_id":"60","modified_at":"2026-08-22T12:07:04.883Z","path":"rev60.txt"}]}\`.
Daty i ID muszą pochodzić z Google, nie wolno ich wymyślać.

## Czego nadal brak do oryginalnego, samodzielnego KB21 LIVE

1. **Algorytmu** przeliczania statystyk na STR/QUAL/MATCH;
   dysponujemy wartościami, zakresami i słownymi kryteriami, lecz nie pełnymi
   tabelami przeliczeniowymi/subwagami.
2. **Formuły P(model)** z przedmeczowego profilu meczu i rynku.
   P(model) w oryginalnym \`Rejestr\` jest wpisaną liczbą, nie formułą;
   zastąpienie jej samym Poissonem przeczy wcześniejszemu porównaniu.
3. Pełnej, deterministycznej **reguły PLAY/LEARN/CONTROL**, ponieważ
   analizator uwzględniał także trudne do skwantyfikowania kontrargumenty
   i uzasadnione wyjątki.
4. Brakujących **42 zestawów trzech składowych** — jedynie w dostępnych
   dziewięciu rewizjach; przy dalszych przeglądach trzeba sprawdzić wcześniejsze.
5. **Pewnej chronologii przed kickoff** i kolejności freeze-P przed ceną,
   zwłaszcza dla rewizji wykonanych w dniu lub po dniu wydarzenia.
6. Nowych, wiarygodnych danych/prognoz z przyszłego, niezależnego
   testu, pozwalających na prawdziwą kalibrację.

**Decyzja bezpieczeństwa:** zachowaj oryginalny arkusz Google jako
pierwotne źródło. Archiwum z repozytorium jest kopią badawczą, nie nowym
programem bukmacherskim i nie należy uruchamiać na jego podstawie
automatycznych PLAY. Nie przywracaj w miejsce LIVE 2.1 dawnych wag
rynkowych 2.0 lub klasyfikatora CORE v1R.
