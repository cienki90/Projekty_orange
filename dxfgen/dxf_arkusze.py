"""
Tworzenie layoutów A3 (paper space) z viewportami 1:1000 + tabelką.

Każdy arkusz:
  - papier A3 420x297, drukarka "DWG To PDF.pc3", marginesy 20/6/6/6 (z wzorca),
  - viewport mapy pokazujący fragment trasy w skali 1:1000,
  - obramowanie arkusza,
  - tabelka rysunkowa (metryka) w prawym dolnym rogu.
"""

from __future__ import annotations

from ezdxf.enums import TextEntityAlignment

from . import arkusze as A
from .arkusze import Arkusz
from .model import Projekt
from .tabelka import rysuj_tabelke

STYL_ARIAL = "Arial"


def _konfiguruj_wydruk(layout) -> None:
    """Ustawia A3 + DWG To PDF + marginesy jak w wzorcu."""
    try:
        layout.page_setup(
            size=(A.PAPIER_W, A.PAPIER_H),
            margins=(A.MARG_GORA, A.MARG_PRAWO, A.MARG_DOL, A.MARG_LEWO),  # (top, right, bottom, left)
            units="mm",
            offset=(0, 0),
            rotation=0,
        )
    except Exception:
        pass
    try:
        layout.dxf.plot_configuration_file = "DWG To PDF.pc3"
    except Exception:
        pass


def _ramka_arkusza(psp) -> None:
    """Obramowanie w obszarze zadruku (wewnątrz marginesów)."""
    x0 = A.MARG_LEWO
    y0 = A.MARG_DOL
    x1 = A.PAPIER_W - A.MARG_PRAWO
    y1 = A.PAPIER_H - A.MARG_GORA
    psp.add_lwpolyline(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
        close=True,
        dxfattribs={"layer": "obramowanie ramek"},
    )


def _dodaj_viewport(psp, ark: Arkusz) -> None:
    """
    Viewport mapy 1:1000.
    Położenie viewportu na papierze = wyśrodkowany w obszarze zadruku,
    nad miejscem na tabelkę. Pokazuje OKNO_W_M x OKNO_H_M terenu.
    """
    # środek viewportu na papierze (mm)
    cx_paper = (A.MARG_LEWO + (A.PAPIER_W - A.MARG_PRAWO)) / 2.0
    cy_paper = (A.MARG_DOL + (A.PAPIER_H - A.MARG_GORA)) / 2.0 + 6.0  # lekko w górę nad tabelkę

    vp = psp.add_viewport(
        center=(cx_paper, cy_paper),
        size=(A.VP_W_MM, A.VP_H_MM),
        view_center_point=(ark.center_x, ark.center_y),
        view_height=A.OKNO_H_M,   # 285 m -> przy 285 mm okna = 1:1000
    )
    vp.dxf.status = 1
    return vp


def _usun_glowny_viewport(psp) -> None:
    """
    Usuwa automatyczny główny viewport paper space (id=1), który ezdxf tworzy
    dla każdego layoutu — zostawiamy tylko nasz viewport mapy.
    """
    for vp in list(psp.query("VIEWPORT")):
        if getattr(vp.dxf, "id", None) == 1:
            try:
                psp.delete_entity(vp)
            except Exception:
                pass


def utworz_arkusze(doc, proj: Projekt, lista: list[Arkusz]) -> None:
    """Tworzy layouty A3 dla wszystkich arkuszy fragmentów trasy."""
    for ark in lista:
        nazwa = f"Arkusz {ark.numer}"
        if nazwa in doc.layouts.names():
            doc.layouts.delete(nazwa)
        layout = doc.layouts.new(nazwa)
        _konfiguruj_wydruk(layout)
        psp = layout

        _usun_glowny_viewport(psp)
        _ramka_arkusza(psp)
        _dodaj_viewport(psp, ark)

        # tabelka w prawym dolnym rogu obszaru zadruku
        tab_x = A.PAPIER_W - A.MARG_PRAWO - 180.0
        tab_y = A.MARG_DOL + 2.0
        # ustaw nr rysunku per arkusz, jeśli brak
        if not proj.dane.rys_nr:
            proj.dane.rys_nr = f"{ark.numer}"
        rysuj_tabelke(psp, proj, tab_x, tab_y)

    # usuń domyślny pusty Layout1/Layout2 (ezdxf tworzy je przy new())
    for nazwa in list(doc.layouts.names()):
        if nazwa != "Model" and nazwa.lower().startswith("layout"):
            try:
                doc.layouts.delete(nazwa)
            except Exception:
                pass
