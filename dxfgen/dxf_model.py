"""
Generator model space DXF (Etap 1).

Odtwarza elementy zgodne z wzorcem zab2.dxf:
  - warstwy (z kolorami: trasa/kabel = pomarańczowy ACI 30),
  - styl tekstu Arial,
  - blok "studnia" (kwadrat 1,2 m) wstawiany w punktach PL-2000,
  - polilinia trasy (Światłowód) łącząca studnie wg kolejności,
  - numer porządkowy w kółku przy studni,
  - nazwa studni,
  - wymiary odcinków = długości z WT (nie z geometrii),
  - zapasy (pomarańczowy prostokąt + długość w kółku) i mufy (pomarańczowy trójkąt)
    na odsuniętej pomarańczowej kresce.

Jednostki rysunku = metry w PL-2000 (1:1 w model space; skala 1:1000 realizowana
na arkuszu przez viewport — Etap 2).
"""

from __future__ import annotations

import math

import ezdxf
from ezdxf.enums import TextEntityAlignment

from .model import Projekt, ReserveKind

# --- stałe wyglądu (w metrach model space) ---
ACI_POMARANCZ = 30          # kolor trasy/kabla/zapasów/muf
ACI_BIALY = 7               # opisy, numery, obramowania
STUDNIA_BOK = 1.2           # bok kwadratu studni [m]
NUMER_PROMIEN = 1.6         # promień kółka numeru porządkowego [m]
TRASA_ODSUNIECIE = 4.0      # odsunięcie pomarańczowej kreski zapasów od trasy [m]
ZAPAS_BOK = 3.0             # bok prostokąta zapasu [m]
MUFA_BOK = 3.0              # bok trójkąta mufy [m]
NAZWA_WYS = 2.2             # wysokość tekstu nazwy studni [m]
NUMER_WYS = 2.0             # wysokość tekstu numeru [m]
WYMIAR_WYS = 2.0            # wysokość tekstu wymiaru [m]

WARSTWY = [
    # (nazwa, kolor ACI)
    ("Światłowód", ACI_POMARANCZ),
    ("kabel projektowany", ACI_POMARANCZ),
    ("kanalizacja instniejaca", ACI_BIALY),
    ("Nazwa studni", ACI_BIALY),
    ("l. porządkowa studni", ACI_BIALY),
    ("_liczba", ACI_BIALY),
    ("wymiary", ACI_BIALY),
    ("wymiarowanie", ACI_POMARANCZ),
    ("Otworówka", ACI_BIALY),
    ("obramowanie ramek", ACI_BIALY),
    ("Defpoints", ACI_BIALY),
]

STYL_ARIAL = "Arial"


def _utworz_warstwy(doc) -> None:
    for nazwa, kolor in WARSTWY:
        if nazwa not in doc.layers:
            doc.layers.add(nazwa, color=kolor)


def _utworz_styl_arial(doc) -> None:
    if STYL_ARIAL not in doc.styles:
        doc.styles.add(STYL_ARIAL, font="arial.ttf")


def _utworz_blok_studni(doc) -> None:
    """Blok 'studnia' — kwadrat 1,2 m wyśrodkowany w (0,0), warstwa kanalizacji."""
    if "studnia" in doc.blocks:
        return
    blk = doc.blocks.new(name="studnia")
    h = STUDNIA_BOK / 2.0
    blk.add_lwpolyline(
        [(-h, -h), (h, -h), (h, h), (-h, h)],
        close=True,
        dxfattribs={"layer": "kanalizacja instniejaca"},
    )


def _rysuj_trase(msp, proj: Projekt) -> None:
    """Polilinia trasy (Światłowód) — odcinki proste studnia->studnia."""
    pkty = [(s.x, s.y) for s in proj.studnie]
    if len(pkty) >= 2:
        msp.add_lwpolyline(pkty, dxfattribs={"layer": "Światłowód"})


def _rysuj_studnie(msp, proj: Projekt) -> None:
    for s in proj.studnie:
        msp.add_blockref("studnia", (s.x, s.y), dxfattribs={"layer": "kanalizacja instniejaca"})


def _rysuj_numery(msp, proj: Projekt) -> None:
    """Numer porządkowy w kółku, odsunięty prostopadle od trasy, by nie zasłaniać."""
    for i, s in enumerate(proj.studnie):
        # kierunek odsunięcia numeru = prostopadły do trasy w tym punkcie
        off = _wektor_normalny(proj, i, dystans=3.0)
        cx, cy = s.x + off[0], s.y + off[1]
        msp.add_circle((cx, cy), NUMER_PROMIEN, dxfattribs={"layer": "_liczba"})
        msp.add_text(
            str(s.nr),
            dxfattribs={"layer": "_liczba", "style": STYL_ARIAL, "height": NUMER_WYS},
        ).set_placement((cx, cy), align=TextEntityAlignment.MIDDLE_CENTER)


def _rysuj_nazwy(msp, proj: Projekt) -> None:
    """Nazwa studni odsunięta po przeciwnej stronie niż numer."""
    for i, s in enumerate(proj.studnie):
        off = _wektor_normalny(proj, i, dystans=-3.5)
        tx, ty = s.x + off[0], s.y + off[1]
        msp.add_text(
            s.nazwa,
            dxfattribs={"layer": "Nazwa studni", "style": STYL_ARIAL, "height": NAZWA_WYS},
        ).set_placement((tx, ty), align=TextEntityAlignment.MIDDLE_CENTER)


def _rysuj_wymiary(msp, proj: Projekt) -> None:
    """
    Wymiar odcinka = długość z WT, pisany w połowie odcinka trasy.
    Dopasowanie odcinków WT do par studni po nazwach.
    """
    nazwa_do_idx = {s.nazwa: i for i, s in enumerate(proj.studnie)}
    for o in proj.odcinki:
        ia = nazwa_do_idx.get(o.studnia_a)
        ib = nazwa_do_idx.get(o.studnia_b)
        if ia is None or ib is None:
            continue
        a = proj.studnie[ia]
        b = proj.studnie[ib]
        mx, my = (a.x + b.x) / 2.0, (a.y + b.y) / 2.0
        kat = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        if kat > 90 or kat < -90:
            kat += 180  # tekst zawsze czytelny
        tekst = _fmt(o.dlugosc_wt)
        msp.add_text(
            tekst,
            dxfattribs={
                "layer": "wymiary",
                "style": STYL_ARIAL,
                "height": WYMIAR_WYS,
                "rotation": kat,
            },
        ).set_placement((mx, my), align=TextEntityAlignment.MIDDLE_CENTER)


def _rysuj_zapasy_mufy(msp, proj: Projekt) -> None:
    """Zapasy (prostokąt) i mufy (trójkąt) na pomarańczowej kresce przy studni."""
    proj.przelicz_numery_zapasow()
    for z in proj.zapasy:
        s = proj.studnia_po_nazwie(z.studnia)
        if s is None:
            continue
        idx = next((i for i, ss in enumerate(proj.studnie) if ss.nazwa == z.studnia), 0)
        off = _wektor_normalny(proj, idx, dystans=TRASA_ODSUNIECIE)
        bx, by = s.x + off[0], s.y + off[1]

        # pomarańczowa kreska odbijająca od trasy do symbolu
        msp.add_line((s.x, s.y), (bx, by), dxfattribs={"layer": "kabel projektowany"})

        if z.kind == ReserveKind.ZAPAS:
            _symbol_zapas(msp, bx, by, z)
        else:
            _symbol_mufa(msp, bx, by, z)


def _symbol_zapas(msp, cx, cy, z) -> None:
    h = ZAPAS_BOK / 2.0
    msp.add_lwpolyline(
        [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)],
        close=True,
        dxfattribs={"layer": "kabel projektowany"},
    )
    # kółko z długością zapasu
    kx, ky = cx + ZAPAS_BOK, cy + ZAPAS_BOK
    msp.add_circle((kx, ky), NUMER_PROMIEN, dxfattribs={"layer": "wymiarowanie"})
    msp.add_text(
        _fmt(z.dlugosc),
        dxfattribs={"layer": "wymiarowanie", "style": STYL_ARIAL, "height": NUMER_WYS},
    ).set_placement((kx, ky), align=TextEntityAlignment.MIDDLE_CENTER)
    # etykieta SZ-x
    msp.add_text(
        z.etykieta,
        dxfattribs={"layer": "wymiarowanie", "style": STYL_ARIAL, "height": NUMER_WYS},
    ).set_placement((cx, cy - ZAPAS_BOK), align=TextEntityAlignment.MIDDLE_CENTER)


def _symbol_mufa(msp, cx, cy, z) -> None:
    h = MUFA_BOK / 2.0
    pkty = [(cx, cy + h), (cx - h, cy - h), (cx + h, cy - h)]
    # wypełniony trójkąt (SOLID) w pomarańczu
    msp.add_solid(
        [pkty[0], pkty[1], pkty[2], pkty[2]],
        dxfattribs={"layer": "kabel projektowany"},
    )
    msp.add_text(
        z.etykieta,
        dxfattribs={"layer": "wymiarowanie", "style": STYL_ARIAL, "height": NUMER_WYS},
    ).set_placement((cx, cy - MUFA_BOK), align=TextEntityAlignment.MIDDLE_CENTER)


# --- geometria pomocnicza ---

def _wektor_normalny(proj: Projekt, idx: int, dystans: float) -> tuple[float, float]:
    """
    Wektor prostopadły do trasy w studni idx, o długości |dystans|.
    Znak dystansu wybiera stronę. Dla końców trasy używa jedynego sąsiada.
    """
    s = proj.studnie
    if len(s) < 2:
        return (0.0, dystans)
    if idx == 0:
        dx, dy = s[1].x - s[0].x, s[1].y - s[0].y
    elif idx == len(s) - 1:
        dx, dy = s[-1].x - s[-2].x, s[-1].y - s[-2].y
    else:
        dx, dy = s[idx + 1].x - s[idx - 1].x, s[idx + 1].y - s[idx - 1].y
    d = math.hypot(dx, dy) or 1.0
    # normalna (obrót o 90°)
    nx, ny = -dy / d, dx / d
    return (nx * dystans, ny * dystans)


def _fmt(v: float) -> str:
    """Format długości: 1 miejsce po przecinku, przecinek dziesiętny (PL)."""
    return f"{v:.1f}".replace(".", ",")


# --- API ---

def generuj_model_dxf(proj: Projekt, sciezka_wyjscia: str) -> str:
    """
    Tworzy DXF (AutoCAD 2010) z zawartością model space.
    Zwraca ścieżkę zapisanego pliku.
    """
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metry

    _utworz_warstwy(doc)
    _utworz_styl_arial(doc)
    _utworz_blok_studni(doc)

    msp = doc.modelspace()
    _rysuj_trase(msp, proj)
    _rysuj_studnie(msp, proj)
    _rysuj_wymiary(msp, proj)
    _rysuj_numery(msp, proj)
    _rysuj_nazwy(msp, proj)
    _rysuj_zapasy_mufy(msp, proj)

    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia
