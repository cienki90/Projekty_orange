"""
Wysokopoziomowe API generatora — spina model space i arkusze A3.
"""

from __future__ import annotations

from .arkusze import podziel_na_arkusze
from .dxf_arkusze import utworz_arkusze
from .dxf_model import zbuduj_dokument
from .model import Projekt


def generuj_pelny_dxf(
    proj: Projekt,
    sciezka_wyjscia: str,
    zaklad_m: float | None = None,
) -> tuple[str, int]:
    """
    Generuje kompletny DXF: model space + arkusze A3 (1:1000, DWG To PDF).

    zaklad_m:
      None  -> zakład na ostatnią widoczną studnię,
      float -> zakład o zadaną odległość [m].

    Zwraca (ścieżka_pliku, liczba_arkuszy).
    """
    proj.przelicz_numery_zapasow()
    doc = zbuduj_dokument(proj)
    lista = podziel_na_arkusze(proj, zaklad_m=zaklad_m)
    utworz_arkusze(doc, proj, lista)
    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, len(lista)
