"""
Podział trasy na arkusze A3 (skala 1:1000) i tworzenie layoutów z viewportami.

Wzorzec zab2.dxf:
  - papier A3: 420 x 297 mm, drukarka "DWG To PDF.pc3",
    marginesy: góra 20 / dół 6 / lewo 6 / prawo 6 mm,
  - aktywny viewport mapy: ~394 x 285 mm na papierze,
    pokazuje 394 x 285 METRÓW terenu => skala 1:1000.

Logika podziału:
  Trasa jest ciągiem studni. Każdy arkusz obejmuje maksymalny fragment trasy,
  który mieści się w oknie viewportu (szer. x wys. w metrach / zapas marginesu).
  Zakład kolejnego arkusza = na OSTATNIĄ widoczną studnię poprzedniego arkusza
  (lub zadana odległość zakładu w metrach).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .model import Projekt, Studnia

# --- geometria arkusza A3 (mm) — z wzorca ---
PAPIER_W = 420.0
PAPIER_H = 297.0
MARG_GORA = 20.0
MARG_DOL = 6.0
MARG_LEWO = 6.0
MARG_PRAWO = 6.0

# viewport mapy (mm na papierze) — jak w zab2.dxf (~394 x 285)
VP_W_MM = 394.0
VP_H_MM = 285.0
SKALA = 1000.0  # 1:1000

# obszar terenu widoczny w viewporcie [m]
OKNO_W_M = VP_W_MM / 1000.0 * SKALA   # 394 m
OKNO_H_M = VP_H_MM / 1000.0 * SKALA   # 285 m

# margines bezpieczeństwa wewnątrz okna (żeby opisy nie wychodziły poza ramkę)
MARGINES_TERENU = 20.0  # m z każdej strony


@dataclass
class Arkusz:
    """Jeden arkusz A3 obejmujący fragment trasy."""
    numer: int
    studnie_idx: list[int] = field(default_factory=list)  # indeksy studni na tym arkuszu
    center_x: float = 0.0   # środek okna mapy w PL-2000
    center_y: float = 0.0
    kat: float = 0.0        # obrót widoku [stopnie] — 0 = bez obrotu (Etap 2a: bez obrotu)


def _bbox(studnie: list[Studnia], idxs: list[int]) -> tuple[float, float, float, float]:
    xs = [studnie[i].x for i in idxs]
    ys = [studnie[i].y for i in idxs]
    return min(xs), min(ys), max(xs), max(ys)


def podziel_na_arkusze(
    proj: Projekt,
    zaklad_m: float | None = None,
) -> list[Arkusz]:
    """
    Dzieli trasę na arkusze A3 1:1000.

    zaklad_m:
      None  -> zakład na ostatnią widoczną studnię poprzedniego arkusza
               (kolejny arkusz zaczyna się od tej samej studni),
      float -> dodatkowy zakład w metrach (kolejny arkusz cofa się o tę odległość).

    Zwraca listę arkuszy z przypisanymi studniami i środkiem okna mapy.
    """
    s = proj.studnie
    if not s:
        return []

    okno_w = OKNO_W_M - 2 * MARGINES_TERENU
    okno_h = OKNO_H_M - 2 * MARGINES_TERENU
    # promień okna jako koło wpisane (konserwatywnie — niezależnie od kierunku trasy)
    maks_rozpietosc = min(okno_w, okno_h)

    arkusze: list[Arkusz] = []
    start = 0
    nr = 1
    n = len(s)

    while start < n:
        idxs = [start]
        for j in range(start + 1, n):
            kandydat = idxs + [j]
            minx, miny, maxx, maxy = _bbox(s, kandydat)
            if (maxx - minx) <= okno_w and (maxy - miny) <= okno_h:
                idxs.append(j)
            else:
                break

        minx, miny, maxx, maxy = _bbox(s, idxs)
        ark = Arkusz(
            numer=nr,
            studnie_idx=list(idxs),
            center_x=(minx + maxx) / 2.0,
            center_y=(miny + maxy) / 2.0,
        )
        arkusze.append(ark)
        nr += 1

        ostatnia = idxs[-1]
        if ostatnia >= n - 1:
            break

        # wyznacz początek kolejnego arkusza
        if zaklad_m is None:
            # zakład na ostatnią widoczną studnię
            start = ostatnia
        else:
            # cofnij się o zadaną odległość wzdłuż trasy
            start = _cofnij_o_dystans(s, ostatnia, zaklad_m)
        # zabezpieczenie przed pętlą
        if start <= idxs[0]:
            start = ostatnia if ostatnia > idxs[0] else idxs[0] + 1

    return arkusze


def _cofnij_o_dystans(s: list[Studnia], idx: int, dystans: float) -> int:
    """Zwraca indeks studni cofniętej o ~dystans metrów względem idx (wzdłuż trasy)."""
    d = 0.0
    i = idx
    while i > 0 and d < dystans:
        d += math.hypot(s[i].x - s[i - 1].x, s[i].y - s[i - 1].y)
        i -= 1
    return i
