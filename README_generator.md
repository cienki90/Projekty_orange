# Generator DXF tras światłowodowych (kanalizacja Orange Polska)

Program generuje rysunek DXF trasy projektowanego kabla światłowodowego
w dzierżawionej kanalizacji OPL na podstawie:

- `współrzędne.xlsx` — studnie w układzie **WGS84** (`nr | nazwa | lat | lon`),
- `wt.xls` — Warunki Techniczne OPL:
  - *Formularz 1K* → metadane tabelki rysunkowej,
  - *Zał 3 zestawienie* → długości odcinków (**brane wprost z WT, nie z geometrii**).

Rysunek powstaje w układzie **PL-2000** (strefa dobierana automatycznie),
w formacie zgodnym z wzorcem `zab2.dxf`.

## Status (etapami)

- [x] **Etap 1** — rdzeń: wczytanie danych, transformacja WGS84→PL-2000,
      model space (trasa, studnie, numery w kółkach, nazwy, wymiary z WT,
      zapasy/mufy na pomarańczowej kresce).
- [x] **Etap 2** — arkusze A3 1:1000 (DWG To PDF, marginesy 20/6/6/6),
      viewporty z fragmentami trasy, podział na strony z zakładem na ostatnią
      widoczną studnię (lub zadaną odległość), tabelka rysunkowa z WT
      (z kontrolą mieszczenia tekstu).
- [ ] **Etap 3** — podkład OSM (raster, odcienie szarości).
- [ ] **Etap 4** — GUI (PySide6): wczytywanie plików, lista + wskazywanie
      zapasów/muf, podgląd, generowanie.
- [ ] **Etap 5** — antykolizja opisów (przesuwanie + leadery).

### Opisy zakończeń A/B (ramki)

Ramki „Zakończenie A/B" są rysowane **od zera** (nie kopiowane ze wzorca):
- prostokąt + tekst w środku + **strzałka wskazująca skrajną studnię** (A =
  pierwsza, B = ostatnia), zgodnie z `opis zakonczenia a/b.png`;
- rozmiar ramki jest **dynamicznie dopasowywany do tekstu** (realny pomiar
  czcionką Arial + zapas), więc żadna linia — także prawy górny róg — nie
  wychodzi poza obramowanie;
- „Zakończenie A" pojawia się tylko na pierwszym arkuszu, „Zakończenie B" tylko
  na ostatnim; na pozostałych arkuszach ramek nie ma;
- przy czyszczeniu arkusza usuwane są wszystkie **śmieci** ze wzorca (puste
  ramki, osierocone strzałki MULTILEADER, odklejone bloki opisu kabla).

## Uruchamianie w Windows (pliki .bat)

Najprościej — dwuklik kolejno:

1. **`setup.bat`** — jednorazowa instalacja zależności (wykrywa Pythona, instaluje pakiety).
2. **`generuj.bat`** — generuje DXF. Bez argumentów otwiera **okno wyboru plików**
   (wskazujesz współrzędne, WT i miejsce zapisu DXF; pola są wstępnie wypełniane
   auto-wykrytymi plikami z katalogu). Można też pominąć okno:
   ```
   generuj.bat --auto                               (auto-wykrycie, bez okna)
   generuj.bat moje_wspolrzedne.xlsx moje_wt.xls moj_wynik.dxf
   ```
3. **`sprawdz.bat`** — waliduje wygenerowany DXF (wersja, audit, warstwy, arkusze,
   skala viewportów). Bez argumentu sprawdza `wynik.dxf`.

> Wymagany Python 3.10+ (przy instalacji zaznacz „Add Python to PATH").

## Instalacja (ręcznie / Linux / macOS)

```bash
pip install -r requirements.txt
```

## Użycie (CLI)

```bash
python generuj.py współrzędne.xlsx wt.xls wynik.dxf
```

Generuje DXF z model space + arkuszami A3 (1:1000). Wynik:
```
  Studnie:           41
  Odcinki (WT):      40
  Strefa PL-2000:    EPSG:2178
  Dł. trasowa (WT):  1153.4 m
  Dł. montażowa:     1188.0 m
  Arkusze A3 1:1000: 4
```

## Weryfikacja dokładności

Dla danych testowych (Ząbki) transformacja odwzorowuje studnie wzorca
`zab2.dxf` z dokładnością **< 5 cm** (41/41 wspólnych studni), a długość
trasowa (1153,4 m) i strefa (EPSG:2178, strefa 7) zgadzają się z projektem
źródłowym.

## Arkusze i tabelka ze wzorca

Arkusze A3 (1:1000) **i tabelka projektowa są kopiowane wprost z `zab2.dxf`**
(szablon). Program wczytuje wzorzec, czyści jego model space i rysuje nowe dane,
zachowując format arkusza, marginesy, drukarkę „DWG To PDF", rzutnie oraz układ
i treść tabelki. Dlatego **plik `zab2.dxf` musi znajdować się w katalogu** z
danymi. Gdy go brak — program tworzy arkusze zastępcze (fallback).

## Założenia projektowe

- Trasa: **czarna, ciągła, 0,50 mm** (warstwa Światłowód).
- Odbita kreska zapasów/muf: **15 jednostek, kolor 30 (pomarańcz), przerywana**
  (ACAD_ISO03W100).
- Opisy (nazwy studni, numery, wymiary) oraz znaczniki studni — **równoległe do
  trasy**; każdy tekst ma **maskę tła** (nie koliduje z trasą/kreskami).
- Wysokość tekstu wymiarów: **1,5**; pod wymiarem — równolegle cyfra liczby
  kanałów ("1").
- Długość **trasowa** = suma odcinków z WT (Zał 3).
- Długość **montażowa** = `trasowa × 1,03 + Σ(zapasy)`; wynik zaokrąglany do 0,1 m.
- Zapas: `SZ-x` (pomarańczowy prostokąt + długość w kółku), tylko przy studniach.
- Mufa: `ZR-x` (pomarańczowy trójkąt, tylko symbol).
- Numeracja SZ i ZR niezależna, od 1, w kolejności wzdłuż trasy.
- Trasa = odcinki proste studnia→studnia (wg kolejności w `współrzędne.xlsx`).
- Wszystkie teksty: czcionka **Arial**.
