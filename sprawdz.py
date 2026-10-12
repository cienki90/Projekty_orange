#!/usr/bin/env python3
"""
Walidacja wygenerowanego pliku DXF.

Sprawdza:
  - czy plik otwiera się poprawnie (wersja DXF),
  - audit ezdxf (błędy struktury),
  - obecność warstw, stylu Arial i bloku studni,
  - listę arkuszy A3 wraz ze skalą viewportów,
  - statystyki encji w model space.

Użycie:
    python sprawdz.py [wynik.dxf]
"""

from __future__ import annotations

import sys
from collections import Counter


def main(argv: list[str]) -> int:
    sciezka = argv[1] if len(argv) > 1 else "wynik.dxf"

    try:
        import ezdxf
    except ImportError:
        print("[BŁĄD] Brak biblioteki ezdxf. Uruchom setup.bat")
        return 1

    try:
        doc = ezdxf.readfile(sciezka)
    except IOError:
        print(f"[BŁĄD] Nie można otworzyć pliku: {sciezka}")
        return 1
    except ezdxf.DXFStructureError:
        print(f"[BŁĄD] Nieprawidłowa struktura DXF: {sciezka}")
        return 1

    print(f"=== Sprawdzenie: {sciezka} ===\n")
    print(f"Wersja DXF: {doc.dxfversion} (AC1024 = AutoCAD 2010)")

    # audit
    auditor = doc.audit()
    n_err = len(auditor.errors)
    print(f"Audit — błędy struktury: {n_err}  {'OK' if n_err == 0 else '!!!'}")

    # warstwy / styl / blok
    warstwy = sorted(l.dxf.name for l in doc.layers)
    print(f"\nWarstwy ({len(warstwy)}): {', '.join(warstwy)}")
    print(f"Styl 'Arial': {'TAK' if 'Arial' in doc.styles else 'NIE'}")
    print(f"Blok 'studnia': {'TAK' if 'studnia' in doc.blocks else 'NIE'}")

    # model space
    msp = doc.modelspace()
    c = Counter(e.dxftype() for e in msp)
    print(f"\nEncje model space:")
    for typ, n in sorted(c.items(), key=lambda x: -x[1]):
        print(f"   {typ:14s} {n}")

    # podkład OSM (IMAGE) — przypomnienie o pliku JPG obok DXF
    import os
    obrazy = list(msp.query("IMAGE"))
    if obrazy:
        for im in obrazy:
            try:
                nazwa = im.image_def.dxf.filename
            except Exception:
                nazwa = "?"
            jest = os.path.exists(os.path.join(os.path.dirname(sciezka), nazwa))
            print(f"\nPodkład OSM (IMAGE): {nazwa}  "
                  f"[plik {'JEST' if jest else 'BRAK — skopiuj JPG obok DXF!'}]")
    else:
        print("\nPodkład OSM (IMAGE): brak (wygenerowano bez tła)")

    # arkusze
    arkusze = [n for n in doc.layouts.names() if n != "Model"]
    print(f"\nArkusze ({len(arkusze)}):")
    for nazwa in arkusze:
        layout = doc.layouts.get(nazwa)
        vps = list(layout.query("VIEWPORT"))
        skala_txt = ""
        for vp in vps:
            vh = getattr(vp.dxf, "view_height", None)
            h = getattr(vp.dxf, "height", None)
            if vh and h:
                skala = vh / (h / 1000.0) / 1000.0
                skala_txt = f"viewport {h:.0f}mm -> 1:{skala*1000:.0f}"
        n_txt = len(list(layout.query("TEXT")))
        print(f"   {nazwa:12s} viewportów={len(vps)}  {skala_txt}  (TEXT={n_txt})")

    print("\n=== " + ("WYNIK OK" if n_err == 0 else "SĄ BŁĘDY — sprawdź powyżej") + " ===")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
