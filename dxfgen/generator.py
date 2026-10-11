"""
Wysokopoziomowe API generatora.

Domyślnie buduje DXF na bazie SZABLONU zab2.dxf (arkusze + tabelka ze wzorca).
Jeśli szablon jest niedostępny, tworzy arkusze od zera (fallback).
"""

from __future__ import annotations

import os

from .arkusze import podziel_na_arkusze
from .dxf_arkusze import utworz_arkusze
from .dxf_model import zbuduj_dokument
from .model import Projekt
from .szablon import generuj_z_szablonu


def generuj_pelny_dxf(
    proj: Projekt,
    sciezka_wyjscia: str,
    zaklad_m: float | None = None,
    sciezka_wzorca: str | None = None,
    uzyj_szablonu: bool = True,
    podklad: bool = True,
) -> tuple[str, int]:
    """
    Generuje kompletny DXF: model space + arkusze A3 (1:1000, DWG To PDF).

    uzyj_szablonu=True -> arkusze i tabelka kopiowane z zab2.dxf (zalecane).
    podklad=True       -> dołącza georeferowany raster OSM (grayscale JPG) pod trasą.
    Zwraca (ścieżka_pliku, liczba_arkuszy).
    """
    if uzyj_szablonu:
        try:
            return generuj_z_szablonu(
                proj, sciezka_wyjscia,
                sciezka_wzorca=sciezka_wzorca, zaklad_m=zaklad_m,
                podklad=podklad,
            )
        except FileNotFoundError:
            # brak wzorca — fallback do generowania od zera
            pass

    proj.przelicz_numery_zapasow()
    doc = zbuduj_dokument(proj)
    lista = podziel_na_arkusze(proj, zaklad_m=zaklad_m)
    utworz_arkusze(doc, proj, lista)
    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, len(lista)
