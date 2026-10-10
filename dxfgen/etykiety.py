"""
Rozmieszczanie etykiet (nazw studni) z unikaniem kolizji.

Strategia:
  - Dla każdej studni próbujemy kolejnych pozycji etykiety: prostopadle do
    trasy, naprzemiennie po obu stronach, z rosnącym odsunięciem.
  - Pozycję akceptujemy, gdy prostokąt etykiety (bounding box) nie nachodzi
    na już umieszczone etykiety ani na kółka numerów.
  - Gdy etykieta jest odsunięta dalej niż próg — rysujemy LEADER (linię
    odniesienia) od studni do etykiety.

Współrzędne w metrach model space. Szerokość tekstu Arial ≈ 0,62 * wysokość.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Prostokat:
    cx: float
    cy: float
    w: float
    h: float
    kat: float = 0.0  # obrót [stopnie] — kolizje liczymy na AABB (uproszczenie)

    def aabb(self) -> tuple[float, float, float, float]:
        """Osiowo-wyrównany bounding box uwzględniający obrót (zgrubnie)."""
        rad = math.radians(self.kat)
        hw, hh = self.w / 2, self.h / 2
        # rogi po obrocie
        rogi = []
        for sx, sy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            rx = sx * math.cos(rad) - sy * math.sin(rad)
            ry = sx * math.sin(rad) + sy * math.cos(rad)
            rogi.append((self.cx + rx, self.cy + ry))
        xs = [p[0] for p in rogi]
        ys = [p[1] for p in rogi]
        return min(xs), min(ys), max(xs), max(ys)


def _koliduja(a: Prostokat, b: Prostokat, luz: float = 0.5) -> bool:
    ax0, ay0, ax1, ay1 = a.aabb()
    bx0, by0, bx1, by1 = b.aabb()
    return not (ax1 + luz < bx0 or bx1 + luz < ax0 or
                ay1 + luz < by0 or by1 + luz < ay0)


def szerokosc_tekstu(tekst: str, wysokosc: float) -> float:
    return len(tekst) * 0.62 * wysokosc


def rozmiesc_etykiety(studnie, kat_fn, wysokosc: float,
                      zajete: list[Prostokat] | None = None):
    """
    Zwraca listę krotek (studnia, (x, y), kat, czy_leader) dla etykiet nazw.

    studnie  : lista obiektów z .x, .y, .nazwa
    kat_fn   : funkcja (idx) -> kąt trasy [stopnie]
    zajete   : wstępnie zajęte prostokąty (np. kółka numerów) do omijania
    """
    rozmieszczone: list[Prostokat] = list(zajete or [])
    wynik = []

    for i, s in enumerate(studnie):
        kat = kat_fn(i)
        w = szerokosc_tekstu(s.nazwa, wysokosc)
        h = wysokosc * 1.4

        # kierunek prostopadły do trasy
        rad = math.radians(kat)
        nx, ny = -math.sin(rad), math.cos(rad)

        najlepsza = None
        # próbuj: strona +, strona -, rosnące odsunięcie
        for mult in (1, -1):
            for krok in range(1, 9):
                ods = 3.0 + krok * (h * 0.9)
                cx = s.x + nx * ods * mult
                cy = s.y + ny * ods * mult
                p = Prostokat(cx, cy, w, h, kat)
                if not any(_koliduja(p, q) for q in rozmieszczone):
                    najlepsza = (p, ods, mult)
                    break
            if najlepsza:
                break

        if najlepsza is None:
            # ostateczność: daleko w górę
            cx = s.x + nx * 12.0
            cy = s.y + ny * 12.0
            najlepsza = (Prostokat(cx, cy, w, h, kat), 12.0, 1)

        p, ods, mult = najlepsza
        rozmieszczone.append(p)
        czy_leader = ods > 6.0  # jeśli odsunięte dalej — rysuj linię odniesienia
        wynik.append((s, (p.cx, p.cy), kat, czy_leader))

    return wynik
