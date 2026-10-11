"""
Plan orientacyjny (mapa poglądowa) — Etap 7.

Rysunek A3 w tym samym układzie co przebieg trasy (ta sama tabelka, drukarka
DWG To PDF, format A3), ale:
  - skala 1:10 000 lub 1:25 000 (dobierana tak, by cała trasa zmieściła się
    w rzutni A3),
  - KOLOROWY podkład OSM (nie szary),
  - trasa jako gruba CZERWONA linia (odwzorowanie trasy na podkładzie),
  - tabelka: Skala = „1:10 000"/„1:25 000", opis = „MAPA POGLĄDOWA", RYS. NR = „1".

Zapis obok DXF przebiegu: `<wynik>_orientacja.dxf` + `<...>_orientacja_podklad.jpg`.
"""

from __future__ import annotations

import os

import ezdxf

from . import dxf_model
from .model import Projekt
from .szablon import (
    _wybierz_layout_wzorzec, _wyczysc_modelspace, _znajdz_wzorzec,
)

# viewport mapy na papierze [mm] (jak w zab2.dxf)
_VP_W_MM = 394.0
_VP_H_MM = 285.0
# dostępne skale planu orientacyjnego
_SKALE = (10000, 25000)
# margines terenu wokół trasy przy doborze skali [ułamek okna]
_MARG_FRAK = 0.12


def _dobierz_skale(proj: Projekt) -> tuple[int, float, float, float, float]:
    """
    Dobiera skalę (1:10 000 lub 1:25 000) tak, by cała trasa + margines zmieściły
    się w rzutni A3. Zwraca (skala, cx, cy, okno_w_m, okno_h_m).
    """
    xs = [s.x for s in proj.studnie]
    ys = [s.y for s in proj.studnie]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    rozp_x = maxx - minx
    rozp_y = maxy - miny

    for skala in _SKALE:
        okno_w = _VP_W_MM / 1000.0 * skala       # szerokość terenu [m] w rzutni
        okno_h = _VP_H_MM / 1000.0 * skala
        if (rozp_x <= okno_w * (1 - 2 * _MARG_FRAK) and
                rozp_y <= okno_h * (1 - 2 * _MARG_FRAK)):
            return skala, cx, cy, okno_w, okno_h
    # jeśli nie mieści się nawet w 1:25 000 — i tak użyj największej skali
    skala = _SKALE[-1]
    okno_w = _VP_W_MM / 1000.0 * skala
    okno_h = _VP_H_MM / 1000.0 * skala
    return skala, cx, cy, okno_w, okno_h


def _fmt_skala(skala: int) -> str:
    """1:10 000 / 1:25 000 (ze spacją jako separatorem tysięcy)."""
    return "1:" + f"{skala:,}".replace(",", " ")


def generuj_plan_orientacyjny(
    proj: Projekt,
    sciezka_wyjscia: str,
    sciezka_wzorca: str | None = None,
) -> tuple[str, int, str]:
    """
    Generuje DXF planu orientacyjnego (A3, 1 arkusz) na bazie wzorca zab2.dxf.
    Zwraca (ścieżka_dxf, skala, etykieta_skali).
    """
    if not proj.studnie:
        raise ValueError("Brak studni — nie można zbudować planu orientacyjnego.")

    wzorzec = _znajdz_wzorzec(sciezka_wzorca)
    doc = ezdxf.readfile(wzorzec)
    _wyczysc_modelspace(doc)
    dxf_model._utworz_warstwy(doc)
    dxf_model._utworz_styl_arial(doc)

    # warstwa trasy orientacyjnej: CZERWONA (ACI 1), gruba
    if "trasa orientacyjna" not in doc.layers:
        lay = doc.layers.add("trasa orientacyjna")
    else:
        lay = doc.layers.get("trasa orientacyjna")
    lay.dxf.color = 1          # czerwony
    lay.dxf.lineweight = 70    # 0,70 mm — gruba linia

    msp = doc.modelspace()

    skala, cx, cy, okno_w, okno_h = _dobierz_skale(proj)

    # --- KOLOROWY podkład OSM dla okna planu orientacyjnego ---
    baza = os.path.splitext(sciezka_wyjscia)[0]
    sciezka_jpg = f"{baza}_podklad.jpg"
    try:
        from . import podklad
        osad = podklad.generuj_podklad_jpg(
            proj, sciezka_jpg, grayscale=False,
            okno_m=(okno_w, okno_h), srodek=(cx, cy),
        )
    except Exception:
        osad = None
    if osad:
        try:
            dxf_model.wstaw_podklad(doc, msp, osad)
        except Exception:
            pass

    # --- TRASA jako gruba czerwona polilinia (odwzorowanie na podkładzie) ---
    pkty = [(s.x, s.y) for s in proj.studnie]
    if len(pkty) >= 2:
        pl = msp.add_lwpolyline(
            pkty, dxfattribs={"layer": "trasa orientacyjna", "lineweight": 70},
        )
        pl.dxf.const_width = 0.0

    # --- arkusz A3: klon wzorcowego layoutu, viewport na całą trasę ---
    nazwa_wzorca = _wybierz_layout_wzorzec(doc)
    bazowy = doc.layouts.get(nazwa_wzorca)
    for n in [x for x in doc.layouts.names() if x not in ("Model", nazwa_wzorca)]:
        try:
            doc.layouts.delete(n)
        except Exception:
            pass
    try:
        doc.layouts.rename(nazwa_wzorca, "Plan orientacyjny")
    except Exception:
        pass
    layout = doc.layouts.get("Plan orientacyjny")

    # ustaw rzutnię: środek = środek trasy, wysokość widoku = okno_h (skala)
    _ustaw_rzutnie_orient(layout, cx, cy, okno_h)

    # tabelka: skala planu, opis „MAPA POGLĄDOWA", nr rysunku „1"
    _wypelnij_tabelke_orient(layout, proj, _fmt_skala(skala))

    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, skala, _fmt_skala(skala)


def _ustaw_rzutnie_orient(layout, cx, cy, view_h_m) -> None:
    """Ustawia główną rzutnię mapy na środek trasy z wysokością widoku view_h_m."""
    vps = [v for v in layout.query("VIEWPORT")]
    mapowe = [v for v in vps if getattr(v.dxf, "id", 1) != 1] or vps
    glowny = max(mapowe, key=lambda v: getattr(v.dxf, "width", 0) * getattr(v.dxf, "height", 0))
    glowny.dxf.view_center_point = (cx, cy, 0)
    try:
        glowny.dxf.view_height = view_h_m    # skala rzutni = view_h/height_mm
    except Exception:
        pass


def _wypelnij_tabelke_orient(layout, proj: Projekt, etykieta_skali: str) -> None:
    """
    Wypełnia tabelkę planu orientacyjnego: te same pola co arkusze trasy, ale
    Skala = plan orientacyjny, opis = „MAPA POGLĄDOWA", nr rysunku = „1”.
    Usuwa też wszelkie ramki zakończeń / śmieci z klonowanego layoutu.
    """
    import re
    from .szablon import _usun_smieci_ramek, _poza_papierem
    d = proj.dane

    # usuń ramki zakończeń i śmieci (plan orientacyjny ich nie ma)
    _usun_smieci_ramek(layout)

    # skasuj duplikaty poza papierem
    for e in list(layout.query("MTEXT")):
        if _poza_papierem(e):
            try:
                layout.delete_entity(e)
            except Exception:
                pass

    # podmień pola tekstowe tabelki (operator/temat/projektant/data/nr kabla)
    from .szablon import (_zbuduj_operator, _zbuduj_temat)
    for e in layout.query("MTEXT"):
        txt = e.text
        if "Wawtel" in txt or "sp. z o" in txt.lower():
            if d.operator:
                e.text = _zbuduj_operator(txt, d)
        elif txt.startswith("\\pxi0,l1;") or ("GÓRNOŚLĄSKA" in txt.upper() and " - " in txt):
            if d.zakonczenie_a_adres or d.zakonczenie_b_adres:
                e.text = _zbuduj_temat(txt, d)
        elif "Ostasiewicz" in txt or ("mgr" in txt.lower() and "inż" in txt.lower()):
            if d.projektant:
                e.text = d.projektant
        elif re.fullmatch(r"\s*\d+/\d+/\w+\s*", txt) or "PWOT" in txt:
            if d.nr_uprawnien:
                e.text = d.nr_uprawnien
        elif "Data:" in txt:
            if d.data_rys or d.data_wt:
                e.text = f" Data: {d.data_rys or d.data_wt}"
        elif re.fullmatch(r"\s*WTROI/\d+/\w+\s*", txt):
            if d.nr_kabla:
                e.text = d.nr_kabla

    # Skala / opis / nr rysunku — od zera (czarne, w komórce), nr = „1”
    _ustaw_pola_orient(layout, etykieta_skali)


def _ustaw_pola_orient(layout, etykieta_skali: str) -> None:
    """Rysuje Skala / „MAPA POGLĄDOWA" / nr „1" w komórkach tabelki (jak w trasie)."""
    from .szablon import (_CELA_SKALA, _CELA_OPIS, _CELA_NR, _dodaj_pole_komorki,
                          _wyglada_jak_nr)
    # usuń istniejące kopie tych pól
    do_usun = []
    for e in layout.query("MTEXT"):
        t = e.text.strip()
        x, y = e.dxf.insert[0], e.dxf.insert[1]
        if not (250 <= x <= 420 and -5 <= y <= 45):
            continue
        if t == "1:1000" or "PRZEBIEG PROJEKTOWANEJ TRASY" in t or "1:" in t:
            do_usun.append(e)
        elif e.dxf.char_height >= 2.5 and _wyglada_jak_nr(t) and x >= 378:
            do_usun.append(e)
    for e in do_usun:
        try:
            layout.delete_entity(e)
        except Exception:
            pass
    _dodaj_pole_komorki(layout, etykieta_skali, _CELA_SKALA)
    _dodaj_pole_komorki(layout, "MAPA POGLĄDOWA", _CELA_OPIS)
    _dodaj_pole_komorki(layout, "1", _CELA_NR)
