# Konwencje projektu — generator DXF tras Orange

## Workflow etapowy
- Projekt budowany jest etapami (Etap 1..5), każdy etap kończy się commitem na
  gałęzi `feature/dxf-generator` i aktualizacją PR.
- **Po każdym etapie generuj/aktualizuj pliki `.bat`** do uruchamiania i
  sprawdzania programu pod Windows:
  - `setup.bat` — instalacja zależności,
  - `generuj.bat` — uruchomienie generatora,
  - `sprawdz.bat` — walidacja wygenerowanego DXF.
  Pliki `.bat` muszą obsługiwać polskie znaki (`chcp 65001`) i wykrywać Pythona
  (`py -3` lub `python`).

## Zasady merytoryczne (ustalenia z użytkownikiem)
- Współrzędne wejściowe: WGS84 (stopnie), rysunek docelowy: PL-2000
  (strefa dobierana automatycznie z długości geograficznej).
- Długość trasowa = suma odcinków z WT (Zał 3), NIE z geometrii.
- Długość montażowa = trasowa × 1,03 + Σ(zapasy); zaokrąglenie do 0,1 m.
- Zapasy tylko przy studniach: SZ-x (pomarańczowy prostokąt + długość w kółku).
- Mufy: ZR-x (pomarańczowy trójkąt, tylko symbol). Numeracja SZ i ZR niezależna.
- Wszystkie teksty: czcionka **Arial**.
- Wymiary symboli/tekstów brane z wzorca `zab2.dxf`.
- Arkusze: zawsze A3, skala 1:1000, drukarka DWG To PDF, marginesy 20/6/6/6.
- Zakład arkuszy: na ostatnią widoczną studnię lub o zadaną odległość.
- Opisy nie mogą kolidować — wolno przesuwać i rysować leadery; nazwa studni
  zawsze widoczna.
- Podkład: raster OSM w odcieniach szarości (program pobiera z internetu).
- Kolor pomarańczowy = ACI 30 (warstwy Światłowód / kabel projektowany).
