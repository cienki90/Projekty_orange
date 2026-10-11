#!/usr/bin/env python3
"""
CLI / GUI — generuje DXF (model space + arkusze A3 1:1000).

Użycie:
    python generuj.py                       (okno wyboru plików)
    python generuj.py --auto                (auto-wykrycie plików, bez okna)
    python generuj.py współrzędne.xlsx wt.xls [wyjscie.dxf]
"""

from __future__ import annotations

import glob
import os
import sys

from dxfgen.budowa import zbuduj_projekt
from dxfgen.generator import generuj_pelny_dxf


def _znajdz_pliki() -> tuple[str | None, str | None]:
    """Auto-wykrycie plików wejściowych w bieżącym katalogu (jako podpowiedź)."""
    wszystkie = glob.glob("*.xlsx") + glob.glob("*.xls")
    wspol = None
    wt = None
    for p in wszystkie:
        low = p.lower()
        if any(k in low for k in ("wspol", "współ", "wspó", "coord", "xy")):
            wspol = wspol or p
        elif low.startswith("wt") or low == "wt.xls" or "warunk" in low:
            wt = wt or p
    if (wspol is None or wt is None) and len(wszystkie) == 2:
        a, b = wszystkie
        if a.lower().endswith(".xlsx"):
            wspol, wt = wspol or a, wt or b
        else:
            wspol, wt = wspol or b, wt or a
    return wspol, wt


def _generuj(wspol: str, wt: str, wyjscie: str, podklad: bool = True) -> int:
    if not os.path.exists(wspol):
        print(f"[BŁĄD] Brak pliku współrzędnych: {wspol}")
        return 2
    if not os.path.exists(wt):
        print(f"[BŁĄD] Brak pliku warunków technicznych: {wt}")
        return 2

    print(f"Wczytuję: {wspol} + {wt}")
    proj = zbuduj_projekt(wspol, wt)

    print(f"  Studnie:           {len(proj.studnie)}")
    print(f"  Odcinki (WT):      {len(proj.odcinki)}")
    print(f"  Strefa PL-2000:    EPSG:{proj.epsg_2000}")
    print(f"  Dł. trasowa (WT):  {proj.dlugosc_trasowa()} m")
    print(f"  Dł. montażowa:     {proj.dlugosc_montazowa()} m")
    if proj.studnie:
        s0 = proj.studnie[0]
        print(f"  1. studnia:        {s0.nazwa}  -> X={s0.x:.3f}  Y={s0.y:.3f}")

    if podklad:
        print("  Podkład OSM:       pobieram kafle i buduję JPG...")
    sciezka, n_ark = generuj_pelny_dxf(proj, wyjscie, podklad=podklad)
    print(f"  Arkusze A3 1:1000: {n_ark}")
    jpg = os.path.splitext(wyjscie)[0] + "_podklad.jpg"
    if podklad and os.path.exists(jpg):
        print(f"  Podkład (JPG):     {jpg}  (trzymaj obok DXF!)")
    elif podklad:
        print("  Podkład OSM:       pominięto (brak sieci lub błąd pobierania)")
    print(f"Zapisano DXF: {sciezka}")
    return 0


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flagi = {a for a in argv[1:] if a.startswith("--")}

    # --bez-podkladu / --no-osm : wyłącza pobieranie podkładu OSM
    podklad = not ({"--bez-podkladu", "--no-osm"} & flagi)

    # tryb jawny: podano oba pliki w argumentach
    if len(args) >= 2:
        wspol, wt = args[0], args[1]
        wyjscie = args[2] if len(args) > 2 else "wynik.dxf"
        return _generuj(wspol, wt, wyjscie, podklad)

    # podpowiedzi z auto-wykrycia
    auto_wspol, auto_wt = _znajdz_pliki()

    # tryb --auto: bez okna, użyj auto-wykrytych plików
    if "--auto" in flagi:
        if not auto_wspol or not auto_wt:
            print("[BŁĄD] Nie udało się automatycznie znaleźć plików wejściowych.")
            print(f"       Pliki .xls/.xlsx w katalogu: {glob.glob('*.xls*')}")
            return 2
        wyjscie = args[0] if len(args) == 1 else "wynik.dxf"
        print("Auto-wykryto pliki wejściowe.")
        return _generuj(auto_wspol, auto_wt, wyjscie, podklad)

    # tryb domyślny: pełne GUI (PySide6). Gdy brak PySide6 — proste okno Tkinter.
    if "--okno" not in flagi:  # --okno wymusza stary, lekki wybór plików
        try:
            from dxfgen.gui import uruchom_gui
            return uruchom_gui(".")
        except Exception as e:
            print(f"[UWAGA] GUI PySide6 niedostępne ({e}). Używam prostego okna.")

    try:
        from dxfgen.okno_wyboru import wybierz_pliki
        wybor = wybierz_pliki(auto_wspol, auto_wt, "wynik.dxf")
    except Exception as e:
        print(f"[UWAGA] Nie udało się otworzyć okna wyboru ({e}).")
        print("        Użyj: python generuj.py <współrzędne.xlsx> <wt.xls> [wyjscie.dxf]")
        print("        lub:  python generuj.py --auto")
        return 2

    if wybor is None:
        print("Anulowano.")
        return 1
    return _generuj(*wybor, podklad=podklad)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
