# Raport MULTIMODEL 3D — wymagania v1 (2026-10-15)

## Cel
Codziennie o 11:30 czasu Europe/Warsaw otrzymać **trzy osobne PDF-y**, każdy na jedną lokalną datę: dziś, jutro, pojutrze. Pierwsza strona każdego dokumentu: krótka lista rynków z najlepszym potwierdzonym materiałem dowodowym. Wewnątrz: mecze pogrupowane, najlepsze do 3 rynków w tabeli głównej na mecz, pozostałe w aneksie. Nie generować fikcyjnych typów, kursów ani źródeł.

## Niezależne systemy
1. KB Score 2.1 (Sport Score 35/35/30, P(model), Confidence i decyzja PLAY/LEARN/CONTROL). Źródło zasad: AKTUALNY_MODEL.md. Główny rejestr: Google Sheet „KB Score – Rejestr i Backtest”, zakładki Rejestr i Rynki_DEV. Markets DEV ma osobne N.
2. Konsensus — niezależne modele/analizy, klasy CORE/VALUE/WATCH, rejestr „Konsensus – Rejestr”. Nie mieszać Consensus z punktacją KB. Nie liczyć wspólnego źródła dwa razy.
3. API Market v3 i gałąź experiment/api-market-2-playable-odds — ocena final_assessment_pct (nie jest skalibrowanym P(HIT)), szczegółowo potwierdzony exact market i cena.
4. PitchAPI — dodatkowy **historyczny** pre-match kontekst xG/xGA, bez zmiany punktacji, selekcji i liczników N.

Dane starych rejestrów służą do badania trafności i kalibracji, nie jako świeże prognozy.

## Dopasowanie pozycji między systemami
Dopasowanie bez zgadywania po kombinacji: data lokalna meczu, identyfikator fixture jeśli występuje, drużyny, rynek, strona, exact line, kierunek i reguła settlement (np. asian over 2.0 != over 2.5). Jednoznaczne dopasowanie jest warunkiem stwierdzenia zgodności. Nieobecna prognoza KB/Konsensusu: `brak aktualnej prognozy`; własna doraźna analiza: `analiza pomocnicza (nie freeze)`.

## Zasada kwalifikacji i priorytetu
- API: final_assessment_pct >= 67, realnie potwierdzony kurs >= 1.20 dla dokładnej linii/strony, zapis bukmachera i czasu snapshotu. Bez kursu jedynie OBSERWUJ, nie „graj”.
- Weryfikuj jakość źródeł: A oficjalne lub bezpośrednio potwierdzone; B kilka niezależnych wiarygodnych; C niepełne/niepewne.
- Priorytety: PRIORYTET (wysoka jakość i kompletność danych, uzasadniona prognoza oraz cena, bez poważnych czerwonych flag), WARUNKOWO (brak rozstrzygającego warunku), OBSERWUJ (brak kursu, składu lub danych), ODRZUĆ (wyraźna sprzeczność, słaba jakość lub cena nieuzasadniona). Nie nadawaj PRIORYTET automatycznie za 67/100 lub 3 zbieżne opinie.
- Pokazuj rozmiar historycznej próbki, hit-rate i kalibrację per rynek tylko przy rzeczywiście zebranych wynikach i spójnych zasadach rozliczeń. Każdy współczynnik pokazuj z N i okresem. Brak próbki = brak potwierdzenia historycznego.
- Dokładny kurs, data i bukmacher są wymagane. STS/Superbet podawaj tylko, kiedy istnieją wiarygodne notowania dokładnie tego samego rynku.
- Brak sztucznego uśredniania ocen /100 i probability oraz sztucznego podnoszenia confidence przez wspólny kierunek. Powiązane rynki jednego meczu oznacz jako skorelowane.

## Format na każdą datę
1. Data analizy i snapshotów, pokrycie źródeł, ile propozycji spełniło warunki.
2. Tabela TOP: godzina, mecz, liga, rynek, linia, kierunek, kurs+źródło, KB (lub brak), Konsensus (lub brak), API ocena/100 (lub brak), PitchAPI wspiera/ostrzega/mieszane/brak, data quality, ryzyko, status.
3. Analizy szczegółowe per mecz, najmocniejszy argument za i przeciw oraz istotne zależności danych.
4. Aneks innych kwalifikujących rynków.
5. Sekcja braki danych, daty wstępne i ograniczenia w przyszłych dniach.

## Wymogi wykonawcze
- 3 pliki `MULTIMODEL_YYYY-MM-DD.pdf` i indywidualne załączniki w ChatGPT, nie jeden ZIP.
- Każdy PDF wyłącznie wydarzenia danego dnia (Europe/Warsaw), z dokładnymi źródłami.
- Jeśli źródło, przejście modelu lub PDF się nie powiedzie: raportuj awarię, nie udawaj potwierdzenia.
- Cokolwiek wyliczone po rozpoczęciu spotkania nie może wstecznie stać się prognozą prematch.
- Nie dotykać rdzeni KB, modeli API, archiwów, checkpointów ani N.
- PDF nie jest gwarancją trafienia; rekomendacje służą wsparciu decyzji i ocenie ryzyka.

## Obsługa automatyzacji
Zadanie ChatGPT: `3 PDF — wszystkie modele` o 11:30 Europe/Warsaw; GitHub multi-day jest źródłem API, ale sam w sobie nie zapewnia eksportu obu niezależnych analiz z Google Sheets. Brak wyniku modelu trzeba jawnie sygnalizować.
