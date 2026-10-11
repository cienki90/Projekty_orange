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
- [x] **Etap 3** — podkład OSM (raster w odcieniach szarości, georeferowany,
      zapisywany jako JPG obok DXF i osadzany jako IMAGE pod trasą).
- [x] **Etap 4** — GUI (PySide6): wczytywanie plików, lista studni +
      wskazywanie zapasów (SZ) / muf (ZR), metryka na żywo, generowanie w tle.
- [x] **Etap 5** — antykolizja opisów: WSZYSTKIE opisy model space (nazwy
      studni, numery, wymiary, cyfry kanałów oraz symbole i ramki opisowe
      zapasów/muf) współdzielą jeden rejestr OBB; kolidujące opisy są
      przesuwane, a przy większym odsunięciu rysowany jest **leader** (linia
      odniesienia). Ramki zakończeń dodatkowo omijają opisy SZ/ZR.

### Opisy zakończeń A/B (ramki)

Ramki „Zakończenie A/B" są rysowane **od zera** (nie kopiowane ze wzorca):
- prostokąt + tekst w środku + **strzałka wskazująca skrajną studnię** (A =
  pierwsza, B = ostatnia), zgodnie z `opis zakonczenia a/b.png`;
- rozmiar ramki jest **dynamicznie dopasowywany do tekstu** (realny pomiar
  czcionką Arial + zapas), więc żadna linia — także prawy górny róg — nie
  wychodzi poza obramowanie;
- „Zakończenie A" pojawia się tylko na pierwszym arkuszu, „Zakończenie B" tylko
  na ostatnim; na pozostałych arkuszach ramek nie ma;
- położenie ramki jest **dobierane dynamicznie** tak, aby nie zasłaniała trasy,
  opisów ani tabelek (strzałka trafia w skrajną studnię);
- przy czyszczeniu arkusza usuwane są wszystkie **śmieci** ze wzorca (puste
  ramki, osierocone strzałki MULTILEADER, duplikaty pól leżące poza papierem).

### Opis kabla (prawy-górny róg) — „tabelka górny róg.png"

Ramka w prawym-górnym rogu zawiera 3 wiersze:
1. `Proj. kabel <typ z WT pkt 1.4> - <numer warunków/nr kabla>`
2. `dł. trasowa w kanalizacji Orange Polska S.A.: <X> m`
3. `dł. montażowa w kanalizacji Orange Polska S.A.: <Y> m`
Ramka jest dopasowywana do szerokości tekstu (bez zawijania).

### Tabelka (prawy-dolny róg) na KAŻDYM arkuszu

Skala (`1:1000`), opis rysunku (`PRZEBIEG PROJEKTOWANEJ TRASY`) oraz numer
rysunku są **gwarantowane na każdym arkuszu** (rysowane od zera — klonowane
arkusze potrafiły je gubić). Numer rysunku: **2.1, 2.2, 2.3, …** (kolejno).

### Podkład OSM (Etap 3)

Program pobiera kafle OpenStreetMap, skleja je, przelicza (resampling) do układu
rysunku **PL-2000** i zapisuje jako **JPG w odcieniach szarości**:

- plik podkładu powstaje OBOK DXF pod nazwą `<wynik>_podklad.jpg`
  (**trzeba go trzymać razem z plikiem DXF** — DXF odwołuje się do niego
  względną ścieżką przez encję `IMAGE`/`IMAGEDEF`),
- raster jest **georeferowany** (siatka wyjściowa w PL-2000, każdy piksel
  próbkowany z mozaiki Web Mercator), więc idealnie pokrywa się z wektorową
  trasą; wstawiany jest NAJNIŻEJ (warstwa `podkład OSM`), pod trasą i opisami,
- podkład jest **wysokiej rozdzielczości** (zoom auto-dobierany, do ~z19) i tylko
  **lekko rozjaśniony** (jasna szarość jak w `zab3.pdf`), tak aby **nazwy ulic i
  numery domów pozostały czytelne**,
- bufor zasięgu wokół trasy: ok. **120 m** z każdej strony (więcej kontekstu);
  liczba kafli jest ograniczana budżetem (auto-zejście o poziom zoom przy dużym
  obszarze), by nie przeciążać serwera kafli,
- wymaga internetu przy generowaniu. Gdy brak sieci — podkład jest pomijany
  bez błędu (DXF powstaje bez tła),
- aby wygenerować **bez** podkładu: `generuj.bat --bez-podkladu ...`
  (lub `python generuj.py --bez-podkladu ...`),
- kafle są cache'owane w katalogu `.cache_osm/` (przyspiesza ponowne uruchomienia).

> Dane podkładu: © OpenStreetMap contributors (ODbL). Źródło kafli łatwo
> podmienić (stała `SZABLON_URL` w `dxfgen/podklad.py`), np. na własny WMTS.

### Kontrola zasłaniania rzutni przez tabelki

Tabelki (prawy-dolny i prawy-górny róg) nachodzą na rzutnię mapy. Aby po
wydruku nie zginął żaden fragment projektu, środek rzutni jest dobierany tak,
by **żadna studnia ani trasa nie wpadła pod tabelkę** (użyteczne okno jest
pomniejszone o pasy tabelek, a środek dociskany do obszaru widocznego).

### GUI (Etap 4)

Graficzny interfejs (PySide6) uruchamiasz przez **`gui.bat`** (lub `generuj.bat`
bez argumentów, albo `python generuj.py`). Okno pozwala:

- wskazać pliki wejściowe (współrzędne, WT) i miejsce zapisu DXF
  (pola są wstępnie wypełniane auto-wykrytymi plikami z katalogu),
- wczytać projekt i zobaczyć **listę studni**,
- **wskazywać zapasy (SZ)** — z długością — oraz **mufy (ZR)** przy wybranych
  studniach (dodawanie/usuwanie); numeracja SZ/ZR nadawana automatycznie,
- śledzić **metrykę na żywo** (dł. trasowa i montażowa aktualizują się po
  każdej zmianie zapasów),
- włączyć/wyłączyć podkład OSM,
- wygenerować DXF **w tle** (okno nie zawiesza się podczas pobierania podkładu),
- korzystać z **interaktywnego podglądu trasy** — rysunek całej trasy ze
  studniami; **kliknięcie studni** zaznacza ją (synchronicznie z listą), a
  markery pokazują, gdzie są już zapasy (kwadrat) i mufy (trójkąt).
  Podgląd obsługuje **przybliżanie** (kółko myszy), **przesuwanie**
  (przeciąganie) i opcjonalny **podkład OSM** (przycisk „Pokaż podkład OSM",
  pobierany w tle i georeferowany pod trasą).

> Gdy PySide6 nie jest zainstalowane, `generuj.py` bez argumentów użyje
> uproszczonego okna wyboru plików (Tkinter). Flaga `--okno` wymusza to proste
> okno nawet przy dostępnym PySide6.

## Uruchamianie w Windows (pliki .bat)

Najprościej — dwuklik kolejno:

1. **`setup.bat`** — jednorazowa instalacja zależności (wykrywa Pythona, instaluje pakiety).
2. **`gui.bat`** — graficzny interfejs (wczytanie plików, wskazanie zapasów/muf,
   generowanie). Alternatywnie **`generuj.bat`** — generuje DXF. Bez argumentów otwiera **GUI / okno wyboru plików**
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
- Zapas: `SZ-x` — pomarańczowy **kwadrat 10×10** (obrys) + kółko z długością
  **bez miejsc po przecinku**; na pomarańczowej linii offsetu, bez kreski łączącej.
- Mufa: `ZR-x` — pomarańczowy **trójkąt** (wypełniony).
- SZ+ZR przy jednej studni: kwadrat + trójkąt w środku + dwa kółka z długością.
- Symbole są **obrócone zgodnie z kierunkiem** pomarańczowej linii; ramka opisowa
  (obrys + czarny tekst) ma 2 wiersze: `SZ-x`/`ZR-x`/`SZ-x; ZR-x` oraz
  `st. nr <numer studni>` (dowiązanie). Pozycje symboli są zapamiętywane
  (`Projekt.pozycje_zapasow`) na potrzeby Etapu 5.
- Numeracja SZ i ZR niezależna, od 1, w kolejności wzdłuż trasy.
- Trasa = odcinki proste studnia→studnia (wg kolejności w `współrzędne.xlsx`).
- Wszystkie teksty: czcionka **Arial**.
