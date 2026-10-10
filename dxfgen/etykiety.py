"""
Rozmieszczanie etykiet (nazw studni) z unikaniem kolizji.

Zasada (wg pomysłu użytkownika):
  - każdy tekst jest obejmowany PROSTOKĄTEM z marginesem 1 jednostki,
  - utrzymujemy REJESTR zajętych obszarów (prostokątów); nowy tekst nie może
    nachodzić na żaden zajęty obszar,
  - jeśli preferowana pozycja koliduje, PRZESUWAMY ją po trochu — najpierw
    prostopadle do trasy (dalej od linii), potem wzdłuż trasy w obie strony —
    aż znajdziemy wolne miejsce; znalezione miejsce dodajemy do rejestru.

Kolizje liczone są na prostokątach ZORIENTOWANYCH (OBB, obróconych o kąt tekstu)
metodą SAT (separating axis theorem) — dokładnie, bez zgrubnego AABB.

Współrzędne w metrach model space. Szerokość tekstu Arial ≈ 0,62 * wysokość.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MARGINES = 1.0  # odsunięcie ramki wokół tekstu [jednostki] — jak w pomyśle użytkownika


@dataclass
class Prostokat:
    cx: float
    cy: float
    w: float
    h: float
    kat: float = 0.0  # obrót [stopnie]

    def rogi(self) -> list[tuple[float, float]]:
        """4 rogi prostokąta po obrocie (z marginesem już wliczonym w w/h)."""
        rad = math.radians(self.kat)
        c, s = math.cos(rad), math.sin(rad)
        hw, hh = self.w / 2, self.h / 2
        out = []
        for sx, sy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
            out.append((self.cx + sx * c - sy * s, self.cy + sx * s + sy * c))
        return out

    def osie(self) -> list[tuple[float, float]]:
        """Dwie osie prostopadłe prostokąta (do SAT)."""
        rad = math.radians(self.kat)
        c, s = math.cos(rad), math.sin(rad)
        return [(c, s), (-s, c)]


def _rzut(rogi, ax, ay) -> tuple[float, float]:
    vals = [rx * ax + ry * ay for rx, ry in rogi]
    return min(vals), max(vals)


def _koliduja(a: Prostokat, b: Prostokat) -> bool:
    """Kolizja dwóch zorientowanych prostokątów metodą SAT."""
    ra, rb = a.rogi(), b.rogi()
    for ax, ay in a.osie() + b.osie():
        amin, amax = _rzut(ra, ax, ay)
        bmin, bmax = _rzut(rb, ax, ay)
        if amax < bmin or bmax < amin:
            return False  # istnieje oś rozdzielająca -> brak kolizji
    return True


def szerokosc_tekstu(tekst: str, wysokosc: float) -> float:
    # najdłuższa linia (uwzględnia wieloliniowe nazwy)
    linie = str(tekst).split("\n")
    maks = max((len(l) for l in linie), default=1)
    return maks * 0.62 * wysokosc


def ramka_tekstu(tekst, cx, cy, wysokosc, kat) -> Prostokat:
    """Prostokąt obejmujący tekst z marginesem MARGINES ze wszystkich stron."""
    w = szerokosc_tekstu(tekst, wysokosc) + 2 * MARGINES
    linie = str(tekst).count("\n") + 1
    h = wysokosc * 1.35 * linie + 2 * MARGINES
    return Prostokat(cx, cy, w, h, kat)


def rozmiesc_etykiety(studnie, kat_fn, wysokosc: float,
                      zajete: list[Prostokat] | None = None,
                      kierunek_fn=None):
    """
    Zwraca listę krotek (studnia, (x, y), kat, czy_leader) dla etykiet nazw.

    studnie     : lista obiektów z .x, .y, .nazwa
    kat_fn      : funkcja (idx) -> kąt trasy [stopnie]
    zajete      : wstępnie zajęte prostokąty (numery, wymiary) — rejestr startowy
    kierunek_fn : funkcja (idx) -> (ux, uy) jednostkowy wektor PREFEROWANEJ
                  strony etykiety (np. przeciwnej do pomarańczowej linii).
    """
    rejestr: list[Prostokat] = list(zajete or [])
    wynik = []

    for i, s in enumerate(studnie):
        kat = kat_fn(i)
        rad = math.radians(kat)
        # kierunek wzdłuż trasy (styczna) i prostopadły (normalna)
        tx, ty = math.cos(rad), math.sin(rad)         # wzdłuż
        if kierunek_fn is not None:
            nx, ny = kierunek_fn(i)                     # preferowana strona
            strony = (1,)
        else:
            nx, ny = -ty, tx                            # normalna
            strony = (1, -1)

        pozycja, ods = _znajdz_miejsce(
            s, tx, ty, nx, ny, strony, s.nazwa, wysokosc, kat, rejestr
        )
        cx, cy, p = pozycja
        rejestr.append(p)
        czy_leader = ods > 6.0
        wynik.append((s, (cx, cy), kat, czy_leader))

    return wynik


def _znajdz_miejsce(s, tx, ty, nx, ny, strony, tekst, wysokosc, kat, rejestr):
    """
    Iteracyjne przesuwanie ramki:
      - rośnie odsunięcie prostopadłe (dalej od trasy),
      - dla każdego odsunięcia próbujemy przesuwać wzdłuż trasy w obie strony.
    Zwraca ((cx, cy, Prostokat), odsuniecie_prostopadle).
    """
    krok_prost = max(1.5, wysokosc * 0.9)
    krok_wzdluz = max(2.0, wysokosc * 1.2)
    bazowe = 2.5  # minimalny odstęp od punktu studni

    for strona in strony:
        for kp in range(0, 12):               # odsunięcie prostopadłe
            ods = bazowe + kp * krok_prost
            for kw in range(0, 9):            # przesunięcie wzdłuż trasy
                for znak_w in ((0,) if kw == 0 else (1, -1)):
                    dx = nx * ods * strona + tx * (kw * krok_wzdluz * znak_w)
                    dy = ny * ods * strona + ty * (kw * krok_wzdluz * znak_w)
                    cx, cy = s.x + dx, s.y + dy
                    p = ramka_tekstu(tekst, cx, cy, wysokosc, kat)
                    if not any(_koliduja(p, q) for q in rejestr):
                        return (cx, cy, p), ods
    # ostateczność: daleko prostopadle
    ods = bazowe + 12 * krok_prost
    cx, cy = s.x + nx * ods * strony[0], s.y + ny * ods * strony[0]
    return (cx, cy, ramka_tekstu(tekst, cx, cy, wysokosc, kat)), ods
