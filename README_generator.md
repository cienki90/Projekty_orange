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
- [ ] **Etap 2** — arkusze A3 1:1000 (DWG To PDF), tabelka, podział na strony.
- [ ] **Etap 3** — podkład OSM (raster, odcienie szarości).
- [ ] **Etap 4** — GUI (PySide6): wczytywanie plików, lista + wskazywanie
      zapasów/muf, podgląd, generowanie.
- [ ] **Etap 5** — antykolizja opisów (przesuwanie + leadery).

## Instalacja

```bash
pip install -r requirements.txt
```

## Użycie (CLI, Etap 1)

```bash
python generuj.py współrzędne.xlsx wt.xls wynik.dxf
```

## Weryfikacja dokładności

Dla danych testowych (Ząbki) transformacja odwzorowuje studnie wzorca
`zab2.dxf` z dokładnością **< 5 cm** (41/41 wspólnych studni), a długość
trasowa (1153,4 m) i strefa (EPSG:2178, strefa 7) zgadzają się z projektem
źródłowym.

## Założenia projektowe

- Długość **trasowa** = suma odcinków z WT (Zał 3).
- Długość **montażowa** = `trasowa × 1,03 + Σ(zapasy)`; wynik zaokrąglany do 0,1 m.
- Zapas: `SZ-x` (pomarańczowy prostokąt + długość w kółku), tylko przy studniach.
- Mufa: `ZR-x` (pomarańczowy trójkąt, tylko symbol).
- Numeracja SZ i ZR niezależna, od 1, w kolejności wzdłuż trasy.
- Trasa = odcinki proste studnia→studnia (wg kolejności w `współrzędne.xlsx`).
- Wszystkie teksty: czcionka **Arial**.
