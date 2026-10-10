"""
Wczytywanie danych wejściowych:
  - współrzędne.xlsx  -> lista studni (nr, nazwa, lat, lon)
  - wt.xls            -> metadane (Formularz 1K) + odcinki (Zał 3 zestawienie)
"""

from __future__ import annotations

import re

from .model import DaneProjektu, Odcinek, Studnia


# --------------------------------------------------------------------------- #
#  współrzędne.xlsx
# --------------------------------------------------------------------------- #

def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _czy_lat(v) -> bool:
    f = _to_float(v)
    return f is not None and 48.0 <= f <= 56.0


def _czy_lon(v) -> bool:
    f = _to_float(v)
    return f is not None and 13.0 <= f <= 25.0


def _wykryj_kolumny(wiersze: list[tuple]) -> dict:
    """
    Automatycznie wykrywa indeksy kolumn lat / lon / nazwa niezależnie od układu.

    Obsługuje m.in.:
      [nr | nazwa | lat | lon]            (zestaw 1)
      [nr | lat | lon | nazwa | długość]  (zestaw 2)

    lat/lon rozpoznawane po zakresie wartości geograficznych Polski,
    nazwa = pierwsza kolumna tekstowa (nie-liczba) różna od kolumn lat/lon.
    """
    # zbierz statystyki po kolumnach na podstawie kilku wierszy danych
    probki = [w for w in wiersze if any(c is not None for c in w)][:10]
    if not probki:
        raise ValueError("Pusty plik współrzędnych.")
    maxc = max(len(w) for w in probki)

    lat_col = lon_col = nazwa_col = None
    # kandydaci lat i lon
    lat_glosy = [0] * maxc
    lon_glosy = [0] * maxc
    for w in probki:
        for c in range(min(len(w), maxc)):
            if _czy_lat(w[c]):
                lat_glosy[c] += 1
            if _czy_lon(w[c]):
                lon_glosy[c] += 1

    # lat ~ 48–56 (węższy zakres), lon ~ 13–25; rozróżniamy po typowej wartości
    # najpewniejsza kolumna lat = najwięcej trafień w 48–56 i wartości > 48
    def _srednia(col):
        vs = [_to_float(w[col]) for w in probki if col < len(w) and _to_float(w[col]) is not None]
        return sum(vs) / len(vs) if vs else None

    kand = [c for c in range(maxc) if lat_glosy[c] or lon_glosy[c]]
    # kolumna o średniej >= 48 to lat, o średniej < 25 to lon
    for c in kand:
        s = _srednia(c)
        if s is None:
            continue
        if s >= 40:          # szerokości PL ~52-53
            lat_col = c if lat_col is None else lat_col
        elif s <= 25:        # długości PL ~14-24
            lon_col = c if lon_col is None else lon_col

    if lat_col is None or lon_col is None:
        raise ValueError("Nie rozpoznano kolumn lat/lon w pliku współrzędnych.")

    # nazwa = kolumna tekstowa (nie-liczba), nie lat/lon; preferuj kolumnę
    # z wartościami zawierającymi litery
    najlepsza, najlepszy_wynik = None, -1
    for c in range(maxc):
        if c in (lat_col, lon_col):
            continue
        wynik = 0
        for w in probki:
            if c < len(w) and w[c] is not None:
                s = str(w[c]).strip()
                if s and _to_float(s) is None and any(ch.isalpha() for ch in s):
                    wynik += 1
        if wynik > najlepszy_wynik:
            najlepsza, najlepszy_wynik = c, wynik
    nazwa_col = najlepsza

    return {"lat": lat_col, "lon": lon_col, "nazwa": nazwa_col}


def wczytaj_wspolrzedne(sciezka: str) -> list[Studnia]:
    """
    Czyta plik współrzędnych (.xlsx). Automatycznie wykrywa układ kolumn —
    obsługuje zarówno [nr | nazwa | lat | lon] jak i [nr | lat | lon | nazwa | ...].

    Nagłówki i wiersze podsumowań (np. "Całkowita długość...") są pomijane
    (brak poprawnych współrzędnych). Numeracja wyświetlana zaczyna się od 1.
    """
    import openpyxl

    wb = openpyxl.load_workbook(sciezka, data_only=True)
    ws = wb.active
    wiersze = [row for row in ws.iter_rows(values_only=True)]
    kol = _wykryj_kolumny(wiersze)
    lat_c, lon_c, nazwa_c = kol["lat"], kol["lon"], kol["nazwa"]

    studnie: list[Studnia] = []
    nr = 0
    for row in wiersze:
        if row is None or all(c is None for c in row):
            continue
        if max(lat_c, lon_c) >= len(row):
            continue
        lat = _to_float(row[lat_c])
        lon = _to_float(row[lon_c])
        if lat is None or lon is None:
            continue
        if not (48.0 <= lat <= 56.0 and 13.0 <= lon <= 25.0):
            continue
        nazwa = ""
        if nazwa_c is not None and nazwa_c < len(row) and row[nazwa_c] is not None:
            nazwa = str(row[nazwa_c]).strip()
        if not nazwa:
            nazwa = f"St-{nr + 1}"
        nr += 1
        studnie.append(Studnia(nr=nr, nazwa=nazwa, lat=lat, lon=lon))

    if not studnie:
        raise ValueError(
            "Nie znaleziono poprawnych współrzędnych w pliku "
            "(oczekiwano kolumn lat 48–56 i lon 13–25)."
        )
    return studnie


# --------------------------------------------------------------------------- #
#  wt.xls — Formularz 1K + Zał 3 zestawienie
# --------------------------------------------------------------------------- #

def _komorka(sheet, r: int, c: int) -> str:
    if r < 0 or r >= sheet.nrows or c < 0 or c >= sheet.ncols:
        return ""
    v = sheet.cell_value(r, c)
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _znajdz_wartosc(sheet, etykieta_fragment: str, max_rows: int | None = None):
    """
    Szuka wiersza, którego kolumna 0 zawiera dany fragment etykiety,
    i zwraca pierwszą niepustą komórkę po prawej stronie.
    """
    rows = sheet.nrows if max_rows is None else min(sheet.nrows, max_rows)
    for r in range(rows):
        label = _komorka(sheet, r, 0)
        if etykieta_fragment.lower() in label.lower():
            for c in range(1, sheet.ncols):
                val = _komorka(sheet, r, c)
                if val:
                    return val
    return ""


def _znajdz_wartosc_dowolna_kol(sheet, etykieta_fragment: str):
    """
    Jak _znajdz_wartosc, ale etykieta może być w DOWOLNEJ kolumnie wiersza;
    zwraca pierwszą niepustą komórkę na prawo od etykiety.
    """
    for r in range(sheet.nrows):
        for c in range(sheet.ncols):
            if etykieta_fragment.lower() in _komorka(sheet, r, c).lower():
                for cc in range(c + 1, sheet.ncols):
                    val = _komorka(sheet, r, cc)
                    if val:
                        return val
    return ""


def _znajdz_po_wzorcu(sheet, wzorzec: str):
    """Szuka pierwszej komórki pasującej do wyrażenia regularnego."""
    rx = re.compile(wzorzec)
    for r in range(sheet.nrows):
        for c in range(sheet.ncols):
            v = _komorka(sheet, r, c)
            m = rx.search(v)
            if m:
                return m.group(0)
    return ""


def wczytaj_wt(sciezka: str) -> tuple[DaneProjektu, list[Odcinek]]:
    """Czyta wt.xls — zwraca (metadane Formularz 1K, lista odcinków z Zał 3)."""
    import xlrd

    wb = xlrd.open_workbook(sciezka)
    dane = _czytaj_formularz_1k(wb)
    odcinki = _czytaj_zal3(wb)
    return dane, odcinki


def _czytaj_formularz_1k(wb) -> DaneProjektu:
    dane = DaneProjektu()
    try:
        sh = wb.sheet_by_name("Formularz 1K")
    except Exception:
        sh = wb.sheet_by_index(0)

    def czysc(s: str) -> str:
        return re.sub(r"\s*\n\s*\(\s*\)\s*$", "", s).strip()

    dane.nr_kabla = czysc(
        _znajdz_wartosc_dowolna_kol(sh, "nr kabla")
        or _znajdz_wartosc_dowolna_kol(sh, "Zapytanie nr")
        or _znajdz_po_wzorcu(sh, r"WTROI/\d+/\w+")
    )
    dane.operator = _znajdz_wartosc(sh, "NAZWA OPERATORA")
    dane.adres_operatora = _znajdz_wartosc(sh, "ADRES OPERATORA")
    dane.miasto = _znajdz_wartosc(sh, "DOSTĘP DO KANALIZACJI")
    dane.data_wt = _znajdz_wartosc(sh, "WARUNKI TECHNICZNE WYDANE")

    # zakończenia A/B — adres jest w wierszu poniżej etykiety "Adres zakończenia"
    adresy = []
    for r in range(sh.nrows):
        if "adres zakończenia" in _komorka(sh, r, 0).lower():
            # adres zwykle w kolejnym wierszu (dowolna kolumna)
            for rr in range(r + 1, min(r + 3, sh.nrows)):
                for c in range(sh.ncols):
                    v = _komorka(sh, rr, c)
                    if v and ("ząbki" in v.lower() or re.match(r"\d{2}-\d{3}", v)):
                        adresy.append(v)
                        break
                if len(adresy) and adresy[-1]:
                    break
    if len(adresy) >= 1:
        dane.zakonczenie_a_adres = adresy[0]
    if len(adresy) >= 2:
        dane.zakonczenie_b_adres = adresy[1]

    # pole 1.3 — opisy zakończeń A i B ("Pole opisowe A: ...; Pole opisowe B: ...")
    opis_13 = ""
    for r in range(sh.nrows):
        if "1.3" in _komorka(sh, r, 0):
            for c in range(1, sh.ncols):
                v = _komorka(sh, r, c)
                if v:
                    opis_13 = v
                    break
            break
    if opis_13:
        ma = re.search(r"Pole opisowe A:\s*(.*?)(?:;|\n|Pole opisowe B:|$)", opis_13, re.S)
        mb = re.search(r"Pole opisowe B:\s*(.*?)(?:;|\n|$)", opis_13, re.S)
        if ma:
            dane.zakonczenie_a_opis = ma.group(1).strip()
        if mb:
            dane.zakonczenie_b_opis = mb.group(1).strip()

    # typ / średnica kabla — wiersz "Typ kabla/rury"
    for r in range(sh.nrows):
        if "typ kabla" in _komorka(sh, r, 0).lower():
            for c in range(1, sh.ncols):
                v = _komorka(sh, r, c)
                if "Z-" in v or "XOTK" in v.upper():
                    dane.typ_kabla = v
                m = re.match(r"^\d+(\.\d+)?$", v)
                if m and not dane.srednica_kabla and float(v) < 100:
                    dane.srednica_kabla = v
            break

    return dane


def _czytaj_zal3(wb) -> list[Odcinek]:
    """
    Zał 3 zestawienie — tabela odcinków.
    Kolumny (wg analizy): 0=Lp | 1=adres A | 2=studnia A | 3=adres B | 4=studnia B | 5=długość
    """
    try:
        sh = wb.sheet_by_name("Zał 3 zestawienie")
    except Exception:
        return []

    odcinki: list[Odcinek] = []
    for r in range(sh.nrows):
        lp_raw = _komorka(sh, r, 0)
        # wiersz danych: Lp. to liczba
        m = re.match(r"^\d+(\.\d+)?$", lp_raw)
        if not m:
            continue
        studnia_a = _komorka(sh, r, 2)
        studnia_b = _komorka(sh, r, 4)
        dl_raw = _komorka(sh, r, 5).replace(",", ".")
        if not studnia_a or not studnia_b:
            continue
        try:
            dlugosc = round(float(dl_raw), 1)
        except ValueError:
            continue
        odcinki.append(
            Odcinek(
                lp=int(float(lp_raw)),
                studnia_a=studnia_a,
                studnia_b=studnia_b,
                dlugosc_wt=dlugosc,
                adres_a=_komorka(sh, r, 1),
                adres_b=_komorka(sh, r, 3),
            )
        )
    return odcinki
