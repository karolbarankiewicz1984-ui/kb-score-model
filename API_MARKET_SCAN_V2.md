# API Market Scan v2 — trwała specyfikacja

## 1. Izolacja od KB Score CORE

API Market Scan jest osobnym modułem projektu.

- KB Score 2.1 CORE działa według wcześniejszych zasad.
- API Market Scan nie zmienia parametrów CORE.
- `KB N += 0`.
- `DEV N += 0`.
- Żadna korekta rynku nie może nadpisać wartości `API PURE`.

## 2. Dwie widoczne oceny

Każda pozycja posiada dwie osobne wartości:

1. **API PURE** — wyłącznie statystyka historyczna z API-Football.
2. **MARKET ADJUSTED** — API PURE po konserwatywnej korekcie aktualnego rynku.

W raporcie użytkowym pokazujemy przede wszystkim:

- pozycję i mecz,
- `API PURE`,
- `Po analizie rynku`,
- zmianę w punktach procentowych i kierunek,
- opisowy sygnał rynku,
- krótki komentarz słowny.

L5/L10/L15, surowe kursy, liczba bukmacherów i dane pomocnicze pozostają w JSON do audytu.

## 3. API PURE

API PURE powstaje z historycznych danych meczowych i nie korzysta z kursów.

Warstwy historyczne:

- L5 / L10 / L15,
- własna częstość pokrycia drużyny,
- częstość dopuszczania danego zdarzenia przez przeciwnika,
- dom / wyjazd,
- odpowiedni kontekst rozgrywek: domestic / international club / national team.

Minimalne warunki v2:

- końcowe historyczne pokrycie co najmniej 72%,
- własne L10 co najmniej 60%,
- profil rywala L10 co najmniej 50%,
- co najmniej 7 użytecznych meczów po obu stronach.

## 4. MARKET OVERLAY

Rynek nie zastępuje API PURE. Jest warstwą korekcyjną.

Źródło bieżącego rynku: pre-match odds API-Football `/odds`.

Dla dokładnej linii system zbiera notowania wielu bukmacherów, zestawia Over z Under i usuwa marżę bukmachera. Następnie liczy medianę prawdopodobieństwa rynku.

Jeżeli rynek jest zbyt wąski lub dokładna linia nie występuje, `MARKET ADJUSTED = API PURE` i raport wyjaśnia brak korekty.

## 5. Siła korekty

Rynek wpływa na ocenę konserwatywnie:

- mocny, spójny konsensus wielu bukmacherów: większa waga,
- średni konsensus: umiarkowana waga,
- mało źródeł lub duży rozrzut: mała waga,
- mniej niż dwa pełne zestawy Over/Under: brak korekty.

Pojedynczy przebieg nie może zmienić API PURE o więcej niż 10 punktów procentowych.

## 6. Ruch rynku

System zapisuje własne snapshoty rynku kilka razy przed głównym skanem.

Porównanie bieżącego odczytu z wcześniejszym pozwala określić, czy rynek:

- przesuwa się w stronę Over,
- pozostaje stabilny,
- przesuwa się przeciwko Over.

Ruch rynku jest tylko dodatkową częścią korekty i nie może samodzielnie zmienić oceny o więcej niż 2 punkty procentowe.

## 7. Obsługiwane rynki v2

Warstwa PURE i MARKET OVERLAY są mapowane dla:

- goli drużyny,
- żółtych kartek drużyny,
- rożnych drużyny,
- fauli drużyny,
- strzałów drużyny,
- strzałów celnych drużyny,
- spalonych drużyny,
- interwencji bramkarza.

Używane są wyłącznie linie połówkowe, żeby uniknąć niejednoznaczności push.

## 8. Statusy rynku

Każda pozycja może dostać opisowy status:

- `mocne potwierdzenie`,
- `potwierdzenie`,
- `neutralny`,
- `ostrzeżenie`,
- `mocne ostrzeżenie`,
- `zbyt mało danych rynkowych`,
- `brak dokładnej linii rynkowej`.

## 9. Harmonogram

Przed głównym skanem zapisywane są wcześniejsze snapshoty rynku. Ostatni zaplanowany przebieg jest celowany w okolice 11:05 czasu Europe/Warsaw, przed dotychczasową rutyną KB Score 2.1 o 11:30.

Zmiana czasu letni/zimowy jest obsługiwana przez sprawdzanie lokalnej godziny Europe/Warsaw w workflow.

## 10. Zasada dalszego rozwoju

Najpierw zbieramy historię:

`API PURE -> MARKET ADJUSTED -> wynik zdarzenia`

Dopiero po uzyskaniu odpowiedniej próbki wolno kalibrować wagi MARKET OVERLAY na podstawie faktycznej skuteczności. Nie przenosimy tych wag ani sygnałów do KB Score CORE bez osobnej, jawnej decyzji użytkownika.
