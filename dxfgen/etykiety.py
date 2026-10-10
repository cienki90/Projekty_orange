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
                      zajete: list[Prostokat] | None = None,
                      kierunek_fn=None):
    """
    Zwraca listę krotek (studnia, (x, y), kat, czy_leader) dla etykiet nazw.

    studnie     : lista obiektów z .x, .y, .nazwa
    kat_fn      : funkcja (idx) -> kąt trasy [stopnie]
    zajete      : wstępnie zajęte prostokąty (numery, wymiary) do omijania
    kierunek_fn : funkcja (idx) -> (ux, uy) jednostkowy wektor PREFEROWANEJ
                  strony etykiety (np. przeciwnej do pomarańczowej linii).
                  Gdy None — kierunek prostopadły do trasy.
    """
    rozmieszczone: list[Prostokat] = list(zajete or [])
    wynik = []

    for i, s in enumerate(studnie):
        kat = kat_fn(i)
        w = szerokosc_tekstu(s.nazwa, wysokosc)
        h = wysokosc * 1.4

        if kierunek_fn is not None:
            nx, ny = kierunek_fn(i)
            kolejnosc = (1,)        # tylko preferowana strona
        else:
            rad = math.radians(kat)
            nx, ny = -math.sin(rad), math.cos(rad)
            kolejnosc = (1, -1)

        najlepsza = None
        for mult in kolejnosc:
            for krok in range(1, 10):
                ods = 3.0 + krok * (h * 0.9)
                cx = s.x + nx * ods * mult
                cy = s.y + ny * ods * mult
                p = Prostokat(cx, cy, w, h, kat)
                if not any(_koliduja(p, q) for q in rozmieszczone):
                    najlepsza = (p, ods)
                    break
            if najlepsza:
                break

        if najlepsza is None:
            cx = s.x + nx * 14.0
            cy = s.y + ny * 14.0
            najlepsza = (Prostokat(cx, cy, w, h, kat), 14.0)

        p, ods = najlepsza
        rozmieszczone.append(p)
        czy_leader = ods > 6.0  # odsunięte dalej -> linia odniesienia
        wynik.append((s, (p.cx, p.cy), kat, czy_leader))

    return wynik
