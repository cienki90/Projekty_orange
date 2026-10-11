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

## Zapasy (SZ) i mufy (ZR) — wygląd (wzorce: zapas.png / mufa.png / zapas i mufa.png)
- Symbole rysowane NA pomarańczowej linii offsetu (15 j), BEZ kreski łączącej
  z trasą; wszystko OBRÓCONE zgodnie z kierunkiem tej linii.
- Zapas (SZ): pomarańczowy KWADRAT 10×10 (obrys) + kółko z długością zapasu
  BEZ miejsc po przecinku (np. „15"). Przy SZ+ZR na jednej studni: dwa kółka.
- Mufa (ZR): pomarańczowy TRÓJKĄT (wypełniony), WIERZCHOŁEK skierowany wzdłuż
  trasy (lokalny +X). SZ+ZR razem = kwadrat + trójkąt w środku.
- Oznaczenia (kwadrat, kółko, ramka opisowa) rysujemy LINIĄ CIĄGŁĄ
  (`linetype="Continuous"`), bo warstwa 'kabel projektowany' jest przerywana
  tylko dla linii offsetu.
- Ramka opisowa (obrys + czarny tekst) po stronie OD trasy, 2 wiersze:
  „SZ-x"/„ZR-x"/„SZ-x; ZR-x" oraz „st. nr <numer porządkowy studni>" (dowiązanie).
- Pozycje narysowanych symboli zapamiętywane w `Projekt.pozycje_zapasow`
  (nazwa studni -> x, y, kąt, czy SZ, czy ZR) — do użycia w Etapie 5
  (antykolizja opisów / leadery).
