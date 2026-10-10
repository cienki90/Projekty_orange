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


def wczytaj_wspolrzedne(sciezka: str) -> list[Studnia]:
    """
    Czyta współrzędne.xlsx. Oczekiwany układ kolumn:
        A: nr porządkowy | B: nazwa studni | C: lat (WGS84) | D: lon (WGS84)

    Nagłówki są wykrywane i pomijane automatycznie (wiersz bez poprawnych
    współrzędnych). Numeracja wyświetlana zaczyna się od 1 niezależnie od
    wartości w kolumnie A.
    """
    import openpyxl

    wb = openpyxl.load_workbook(sciezka, data_only=True)
    ws = wb.active
    studnie: list[Studnia] = []
    nr = 0
    for row in ws.iter_rows(values_only=True):
        if row is None or all(c is None for c in row):
            continue
        if len(row) < 4:
            continue
        nazwa = row[1]
        lat = _to_float(row[2])
        lon = _to_float(row[3])
        # pomiń nagłówki / wiersze bez sensownych współrzędnych w zakresie Polski
        if lat is None or lon is None:
            continue
        if not (48.0 <= lat <= 56.0 and 13.0 <= lon <= 25.0):
            continue
        if not nazwa or not str(nazwa).strip():
            continue
        nr += 1
        studnie.append(
            Studnia(nr=nr, nazwa=str(nazwa).strip(), lat=lat, lon=lon)
        )
    if not studnie:
        raise ValueError(
            "Nie znaleziono poprawnych współrzędnych w pliku. "
            "Oczekiwany układ: [nr | nazwa | lat | lon]."
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
