#!/usr/bin/env python3
"""
CLI Etapu 1 — generuje DXF (model space) z plików wejściowych.

Użycie:
    python generuj.py współrzędne.xlsx wt.xls [wyjscie.dxf]
"""

from __future__ import annotations

import sys

from dxfgen.budowa import zbuduj_projekt
from dxfgen.dxf_model import generuj_model_dxf


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    wspol = argv[1]
    wt = argv[2]
    wyjscie = argv[3] if len(argv) > 3 else "wynik.dxf"

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

    sciezka = generuj_model_dxf(proj, wyjscie)
    print(f"Zapisano DXF: {sciezka}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
