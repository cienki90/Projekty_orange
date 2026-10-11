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

# --- stałe wyglądu (w metrach model space) — WARTOŚCI WZIĘTE Z zab2.dxf ---
ACI_POMARANCZ = 30          # kolor odbitej kreski / zapasów / muf
ACI_CZARNY = 7              # trasa, opisy, numery (7 = czarny na białym tle)
ACI_BIALY = 7
STUDNIA_BOK = 1.2           # bok kwadratu studni [m]  (wzorzec: 1,2)
NUMER_PROMIEN = 1.6         # promień kółka numeru porządkowego [m]  (wzorzec: ~1,6)
TRASA_ODSUNIECIE = 15.0     # długość odbitej kreski (wzorzec: 15 jednostek)
ZAPAS_BOK = 3.0             # bok prostokąta zapasu [m]
MUFA_BOK = 3.0              # bok trójkąta mufy [m]
NAZWA_WYS = 1.6             # wysokość tekstu nazwy studni [m]  (wzorzec: 1,6)
NUMER_WYS = 1.6             # wysokość tekstu numeru [m]        (wzorzec: 1,6)
WYMIAR_WYS = 1.5            # wysokość tekstu wymiaru [m]       (zmniejszone na życzenie: 1,5)
KANALY_WYS = 1.5           # wysokość cyfry liczby kanałów pod wymiarem

# lineweight w setnych mm (DXF): 50 = 0,50 mm
LW_TRASA = 50               # trasa czarna 0,50 mm
LW_OPIS = 20                # opisy 0,20 mm

LTYPE_PRZERYWANA = "DASHED"  # przerywana linia odbitej kreski (standardowy DASHED)

WARSTWY = [
    # (nazwa, kolor ACI, typ_linii, lineweight)
    ("Światłowód", ACI_CZARNY, "Continuous", LW_TRASA),         # TRASA: czarna, ciągła, 0,5 mm
    ("kabel projektowany", ACI_POMARANCZ, LTYPE_PRZERYWANA, 50),# odbita kreska: pomarańcz, przerywana
    ("kanalizacja instniejaca", ACI_BIALY, "Continuous", 40),
    ("Nazwa studni", ACI_BIALY, "Continuous", LW_OPIS),
    ("l. porządkowa studni", ACI_BIALY, "Continuous", LW_OPIS),
    ("_liczba", ACI_BIALY, "Continuous", LW_OPIS),
    ("_liczba kanałów", ACI_BIALY, "Continuous", LW_OPIS),
    ("wymiary", ACI_BIALY, "Continuous", LW_OPIS),
    ("wymiarowanie", ACI_POMARANCZ, "Continuous", 18),
    ("Otworówka", ACI_BIALY, "Continuous", LW_OPIS),
    ("obramowanie ramek", ACI_BIALY, "Continuous", LW_OPIS),
    ("Defpoints", ACI_BIALY, "Continuous", -3),
    ("podkład OSM", ACI_BIALY, "Continuous", LW_OPIS),   # raster tła (najniżej)
]

STYL_ARIAL = "Arial"


def _utworz_warstwy(doc) -> None:
    # upewnij się, że typ linii przerywanej istnieje (DASHED)
    if LTYPE_PRZERYWANA not in doc.linetypes:
        try:
            doc.linetypes.add(
                LTYPE_PRZERYWANA,
                pattern="A,3.0,-1.5",  # kreska 3 / spacja 1,5 (metry) — widoczna w skali
                description="Dashed __ __ __ __",
            )
        except Exception:
            pass
    for nazwa, kolor, ltype, lw in WARSTWY:
        if nazwa in doc.layers:
            lay = doc.layers.get(nazwa)
        else:
            lay = doc.layers.add(nazwa)
        lay.dxf.color = kolor
        try:
            lay.dxf.linetype = ltype if ltype in doc.linetypes else "Continuous"
            lay.dxf.lineweight = lw
        except Exception:
            pass


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


def _tekst_z_maska(msp, tekst, pozycja, wysokosc, warstwa, kat=0.0,
                   align=TextEntityAlignment.MIDDLE_CENTER):
    """
    Dodaje MTEXT z MASKĄ TŁA (background fill), obrócony o `kat` stopni.
    Maska tła przesłania obiekty pod tekstem (trasa, kreski) — czytelność.
    """
    mt = msp.add_mtext(tekst, dxfattribs={"layer": warstwa, "style": STYL_ARIAL})
    mt.dxf.char_height = wysokosc
    mt.dxf.rotation = kat
    mt.set_location(pozycja, attachment_point=5)  # 5 = MIDDLE_CENTER
    # MASKA TŁA: użyj koloru tła rysunku (canvas), margines 1.2 wokół tekstu.
    # bg_fill=1 => fill z koloru tła; współczynnik 1.2 ustawia ramkę maski.
    try:
        mt.set_bg_color("canvas", scale=1.0)
    except Exception:
        # fallback: ustaw atrybuty wprost
        mt.dxf.bg_fill = 1
        mt.dxf.box_fill_scale = 1.0
        mt.dxf.bg_fill_color = 0
    return mt


def _kat_trasy(proj: Projekt, idx: int) -> float:
    """Kąt stycznej do trasy w studni idx [stopnie], znormalizowany do czytelności."""
    s = proj.studnie
    if len(s) < 2:
        return 0.0
    if idx == 0:
        dx, dy = s[1].x - s[0].x, s[1].y - s[0].y
    elif idx == len(s) - 1:
        dx, dy = s[-1].x - s[-2].x, s[-1].y - s[-2].y
    else:
        dx, dy = s[idx + 1].x - s[idx - 1].x, s[idx + 1].y - s[idx - 1].y
    kat = math.degrees(math.atan2(dy, dx))
    if kat > 90 or kat <= -90:
        kat += 180  # tekst zawsze "do góry nogami" czytelny
    return kat


def _rysuj_trase(msp, proj: Projekt) -> None:
    """Trasa (Światłowód) — czarna, ciągła, 0,50 mm. Odcinki proste studnia->studnia."""
    pkty = [(s.x, s.y) for s in proj.studnie]
    if len(pkty) >= 2:
        msp.add_lwpolyline(
            pkty,
            dxfattribs={"layer": "Światłowód", "lineweight": LW_TRASA},
        )


def _rysuj_studnie(msp, proj: Projekt) -> None:
    """Znacznik studni (blok) obrócony RÓWNOLEGLE do trasy."""
    for i, s in enumerate(proj.studnie):
        kat = _kat_trasy(proj, i)
        msp.add_blockref(
            "studnia", (s.x, s.y),
            dxfattribs={"layer": "kanalizacja instniejaca", "rotation": kat},
        )


def _rysuj_odbite_linie(msp, proj: Projekt) -> None:
    """
    Pomarańczowa linia RÓWNOLEGŁA do CAŁEJ trasy, odsunięta o 15 jednostek
    (offset całej polilinii) — przerywana (DASHED), kolor 30
    (warstwa 'kabel projektowany'). Jedna ciągła linia wzdłuż całej trasy.
    """
    pkty = [(s.x, s.y) for s in proj.studnie]
    if len(pkty) < 2:
        return
    offset = _offset_polilinii(pkty, TRASA_ODSUNIECIE)  # 15 j
    if len(offset) >= 2:
        msp.add_lwpolyline(
            offset,
            dxfattribs={"layer": "kabel projektowany"},
        )


def _offset_polilinii(pkty, dystans: float):
    """
    Oblicza polilinię równoległą (offset) do zadanej, odsuniętą o `dystans`
    po jednej stronie. Dla każdego wierzchołka liczy normalną uśrednioną
    z sąsiednich segmentów (gładkie załamania).
    """
    n = len(pkty)
    out = []
    for i in range(n):
        # kierunki segmentów przyległych do wierzchołka i
        if i == 0:
            dx, dy = pkty[1][0] - pkty[0][0], pkty[1][1] - pkty[0][1]
            nx, ny = _normalna(dx, dy)
        elif i == n - 1:
            dx, dy = pkty[-1][0] - pkty[-2][0], pkty[-1][1] - pkty[-2][1]
            nx, ny = _normalna(dx, dy)
        else:
            # wierzchołek wewnętrzny: wektor dwusiecznej (mitra),
            # długość skorygowana tak, by odstęp PROSTOPADŁY = dystans
            n1 = _normalna(pkty[i][0] - pkty[i - 1][0], pkty[i][1] - pkty[i - 1][1])
            n2 = _normalna(pkty[i + 1][0] - pkty[i][0], pkty[i + 1][1] - pkty[i][1])
            mx, my = n1[0] + n2[0], n1[1] + n2[1]
            d = math.hypot(mx, my)
            if d < 1e-9:
                nx, ny = n1
            else:
                mnx, mny = mx / d, my / d
                # cos kąta między normalną segmentu a dwusieczną
                cos_pol = n1[0] * mnx + n1[1] * mny
                cos_pol = max(0.2, cos_pol)  # ogranicz wydłużenie w ostrych kątach
                skala = 1.0 / cos_pol
                nx, ny = mnx * skala, mny * skala
        out.append((pkty[i][0] + nx * dystans, pkty[i][1] + ny * dystans))
    return out


def _normalna(dx: float, dy: float) -> tuple[float, float]:
    """Jednostkowa normalna (obrót wektora o +90°)."""
    d = math.hypot(dx, dy) or 1.0
    return (-dy / d, dx / d)


def _strona_offsetu(proj: Projekt, idx: int) -> tuple[float, float]:
    """
    Jednostkowy wektor wskazujący stronę POMARAŃCZOWEJ linii offsetu
    w studni idx (ta sama konwencja co _offset_polilinii: normalna +90°).
    """
    s = proj.studnie
    if len(s) < 2:
        return (0.0, 1.0)
    if idx == 0:
        dx, dy = s[1].x - s[0].x, s[1].y - s[0].y
    elif idx == len(s) - 1:
        dx, dy = s[-1].x - s[-2].x, s[-1].y - s[-2].y
    else:
        dx, dy = s[idx + 1].x - s[idx - 1].x, s[idx + 1].y - s[idx - 1].y
    return _normalna(dx, dy)


def _rysuj_wymiary(msp, proj: Projekt, rejestr: list) -> None:
    """
    Wymiar odcinka = długość z WT (wys. 1,5), RÓWNOLEGLE do odcinka, z maską tła.
    Pod wymiarem (równolegle) cyfra "1" = liczba kanałów.
    Pozycje szukane z unikaniem kolizji (wspólny rejestr) — przy ciasnocie
    wymiar/cyfra przesuwają się wzdłuż odcinka lub dalej od trasy.
    """
    from .etykiety import ramka_tekstu, _koliduja
    nazwa_do_idx = {s.nazwa: i for i, s in enumerate(proj.studnie)}

    def umiesc(tekst, mx, my, nx, ny, tx, ty, baza, h, warstwa):
        """Znajdź wolne miejsce: rośnie odsunięcie prostopadłe + wzdłuż odcinka."""
        for kp in range(0, 8):
            ods = baza + kp * (h * 0.9)
            for kw in range(0, 5):
                for zw in ((0,) if kw == 0 else (1, -1)):
                    cx = mx + nx * ods + tx * (kw * h * 1.1 * zw)
                    cy = my + ny * ods + ty * (kw * h * 1.1 * zw)
                    r = ramka_tekstu(tekst, cx, cy, h, 0)  # bbox niezal. od obrotu dla testu
                    if not any(_koliduja(r, q) for q in rejestr):
                        _tekst_z_maska(msp, tekst, (cx, cy), h, warstwa, kat=katg)
                        rejestr.append(ramka_tekstu(tekst, cx, cy, h,
                                                    math.degrees(math.atan2(ty, tx))))
                        return
        # ostateczność
        cx, cy = mx + nx * baza, my + ny * baza
        _tekst_z_maska(msp, tekst, (cx, cy), h, warstwa, kat=katg)
        rejestr.append(ramka_tekstu(tekst, cx, cy, h, 0))

    for o in proj.odcinki:
        ia = nazwa_do_idx.get(o.studnia_a)
        ib = nazwa_do_idx.get(o.studnia_b)
        if ia is None or ib is None:
            continue
        a = proj.studnie[ia]
        b = proj.studnie[ib]
        mx, my = (a.x + b.x) / 2.0, (a.y + b.y) / 2.0
        katg = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        if katg > 90 or katg < -90:
            katg += 180
        rad = math.radians(katg)
        tx, ty = math.cos(rad), math.sin(rad)   # wzdłuż odcinka
        nx, ny = math.sin(rad), -math.cos(rad)  # normalna
        odsun = WYMIAR_WYS * 1.4
        # wymiar nad linią, cyfra kanałów pod linią (przeciwna normalna)
        umiesc(_fmt(o.dlugosc_wt), mx, my, -nx, -ny, tx, ty, odsun, WYMIAR_WYS, "wymiary")
        umiesc("1", mx, my, nx, ny, tx, ty, odsun, KANALY_WYS, "_liczba kanałów")


def _rysuj_numery(msp, proj: Projekt, rejestr: list) -> None:
    """
    Numer porządkowy w kółku po STRONIE POMARAŃCZOWEJ linii, umieszczany tak,
    by NIE kolidował z żadnym zajętym obszarem (wspólny rejestr).
    """
    from .etykiety import Prostokat, _koliduja, ramka_tekstu
    bok = NUMER_PROMIEN * 2 + 2 * 1.0  # kółko + margines 1 j
    for i, s in enumerate(proj.studnie):
        kat = _kat_trasy(proj, i)
        sx, sy = _strona_offsetu(proj, i)   # strona pomarańczowej linii
        tx, ty = math.cos(math.radians(kat)), math.sin(math.radians(kat))
        umieszczono = None
        for kp in range(0, 10):
            ods = 3.0 + kp * (NUMER_PROMIEN * 1.4)
            for kw in range(0, 7):
                for zw in ((0,) if kw == 0 else (1, -1)):
                    cx = s.x + sx * ods + tx * (kw * (NUMER_PROMIEN * 1.6) * zw)
                    cy = s.y + sy * ods + ty * (kw * (NUMER_PROMIEN * 1.6) * zw)
                    p = Prostokat(cx, cy, bok, bok, 0.0)
                    if not any(_koliduja(p, q) for q in rejestr):
                        umieszczono = (cx, cy, p)
                        break
                if umieszczono:
                    break
            if umieszczono:
                break
        if umieszczono is None:
            cx, cy = s.x + sx * 3.0, s.y + sy * 3.0
            p = Prostokat(cx, cy, bok, bok, 0.0)
        else:
            cx, cy, p = umieszczono
        rejestr.append(p)
        msp.add_circle((cx, cy), NUMER_PROMIEN, dxfattribs={"layer": "_liczba"})
        _tekst_z_maska(msp, str(s.nr), (cx, cy), NUMER_WYS, "_liczba", kat=kat)


def _rysuj_nazwy(msp, proj: Projekt, rejestr: list) -> None:
    """
    Nazwy studni RÓWNOLEGLE do trasy, PO STRONIE PRZECIWNEJ niż pomarańczowa
    linia offsetu. Rozmieszczane z unikaniem kolizji (wspólny rejestr) i
    leaderami, gdy etykieta musi być odsunięta dalej.
    """
    from .etykiety import Prostokat, rozmiesc_etykiety

    # punkty studni jako małe przeszkody (żeby nazwa nie siadała na znaczniku)
    for s in proj.studnie:
        rejestr.append(Prostokat(s.x, s.y, STUDNIA_BOK + 1.0, STUDNIA_BOK + 1.0))

    def strona(i):
        sx, sy = _strona_offsetu(proj, i)
        return (-sx, -sy)  # przeciwna do offsetu

    rozmieszczenie = rozmiesc_etykiety(
        proj.studnie, lambda i: _kat_trasy(proj, i), NAZWA_WYS,
        rejestr, kierunek_fn=strona,
    )
    for s, (tx, ty), kat, czy_leader in rozmieszczenie:
        if czy_leader:
            msp.add_line((s.x, s.y), (tx, ty),
                         dxfattribs={"layer": "Nazwa studni"})
        _tekst_z_maska(msp, s.nazwa, (tx, ty), NAZWA_WYS, "Nazwa studni", kat=kat)


def _rysuj_zapasy_mufy(msp, proj: Projekt) -> None:
    """
    Zapasy (SZ) i mufy (ZR) na ODBITEJ KRESCE 15 j — pomarańczowej, przerywanej
    (warstwa 'kabel projektowany'). Symbol na końcu kreski, etykieta z maską tła.
    """
    proj.przelicz_numery_zapasow()
    for z in proj.zapasy:
        s = proj.studnia_po_nazwie(z.studnia)
        if s is None:
            continue
        idx = next((i for i, ss in enumerate(proj.studnie) if ss.nazwa == z.studnia), 0)
        off = _wektor_normalny(proj, idx, dystans=TRASA_ODSUNIECIE)  # 15 j
        bx, by = s.x + off[0], s.y + off[1]
        kat = _kat_trasy(proj, idx)

        # odbita kreska 15 j — pomarańczowa przerywana (ltype/kolor z warstwy)
        msp.add_lwpolyline(
            [(s.x, s.y), (bx, by)],
            dxfattribs={"layer": "kabel projektowany"},
        )

        if z.kind == ReserveKind.ZAPAS:
            _symbol_zapas(msp, bx, by, z, kat)
        else:
            _symbol_mufa(msp, bx, by, z, kat)


def _symbol_zapas(msp, cx, cy, z, kat) -> None:
    """Pomarańczowy prostokąt (zapas) + długość w kółku + etykieta SZ-x z maską."""
    h = ZAPAS_BOK / 2.0
    msp.add_lwpolyline(
        [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)],
        close=True,
        dxfattribs={"layer": "kabel projektowany"},
    )
    # kółko z długością zapasu
    kx, ky = cx + ZAPAS_BOK, cy + ZAPAS_BOK
    msp.add_circle((kx, ky), NUMER_PROMIEN, dxfattribs={"layer": "wymiarowanie"})
    _tekst_z_maska(msp, _fmt(z.dlugosc), (kx, ky), NUMER_WYS, "wymiarowanie", kat=kat)
    # etykieta SZ-x
    _tekst_z_maska(msp, z.etykieta, (cx, cy - ZAPAS_BOK - 1.0),
                   NUMER_WYS, "wymiarowanie", kat=kat)


def _symbol_mufa(msp, cx, cy, z, kat) -> None:
    """Pomarańczowy trójkąt (mufa) + etykieta ZR-x z maską."""
    h = MUFA_BOK / 2.0
    pkty = [(cx, cy + h), (cx - h, cy - h), (cx + h, cy - h)]
    msp.add_solid(
        [pkty[0], pkty[1], pkty[2], pkty[2]],
        dxfattribs={"layer": "kabel projektowany"},
    )
    _tekst_z_maska(msp, z.etykieta, (cx, cy - MUFA_BOK - 1.0),
                   NUMER_WYS, "wymiarowanie", kat=kat)


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

def zbuduj_dokument(proj: Projekt):
    """
    Tworzy dokument DXF (R2010) i rysuje całą zawartość model space.
    Zwraca obiekt ezdxf.Drawing (bez zapisu) — do dalszej obróbki (arkusze).
    """
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # metry

    _utworz_warstwy(doc)
    _utworz_styl_arial(doc)
    _utworz_blok_studni(doc)

    msp = doc.modelspace()
    rysuj_zawartosc(msp, proj)
    return doc


def rysuj_zawartosc(msp, proj: Projekt) -> None:
    """
    Rysuje całą zawartość model space w poprawnej kolejności, z unikaniem kolizji:
    trasa -> studnie -> offset 15j -> wymiary -> numery (omijają wymiary)
    -> nazwy (przeciwna strona offsetu) -> zapasy/mufy.
    """
    _rysuj_trase(msp, proj)
    _rysuj_studnie(msp, proj)
    _rysuj_odbite_linie(msp, proj)
    # wspólny rejestr zajętych obszarów — wszystkie opisy go współdzielą,
    # dzięki czemu nic nie nachodzi na nic (wg pomysłu: ramka + rejestr + przesuwanie)
    rejestr = []
    _rysuj_wymiary(msp, proj, rejestr)
    _rysuj_numery(msp, proj, rejestr)
    _rysuj_nazwy(msp, proj, rejestr)
    _rysuj_zapasy_mufy(msp, proj)


def wstaw_podklad(doc, msp, osadzenie: dict) -> None:
    """
    Wstawia georeferowany raster (JPG) jako encję IMAGE w model space,
    na warstwie 'podkład OSM'. Obraz jest umieszczany najniżej (rysowany jako
    pierwszy), tak by trasa/opisy były NAD nim.

    osadzenie: słownik z podklad.generuj_podklad_jpg (insert = lewy-dolny róg
    w PL-2000, szer_m/wys_m = rozmiar w metrach, px_w/px_h = piksele).
    """
    import os

    sciezka = osadzenie["sciezka"]
    insert = osadzenie["insert"]            # (x, y) lewy-dolny róg [PL-2000]
    szer_m = osadzenie["szer_m"]
    wys_m = osadzenie["wys_m"]
    px_w = osadzenie["px_w"]
    px_h = osadzenie["px_h"]

    # IMAGEDEF odwołuje się do pliku WZGLĘDEM DXF (ten sam katalog), aby po
    # przeniesieniu pary .dxf + .jpg obraz nadal się odnajdywał
    sciezka_wzgl = os.path.basename(sciezka)
    image_def = doc.add_image_def(filename=sciezka_wzgl, size_in_pixel=(px_w, px_h))

    # insert = lewy-DOLNY róg w PL-2000; size_in_units = rozmiar w metrach.
    # ezdxf sam policzy u/v-pixel; obraz rośnie w górę (standard georeferencji).
    msp.add_image(
        image_def=image_def,
        insert=(insert[0], insert[1]),
        size_in_units=(szer_m, wys_m),
        dxfattribs={"layer": "podkład OSM"},
    )


def generuj_model_dxf(proj: Projekt, sciezka_wyjscia: str) -> str:
    """Tworzy DXF tylko z model space (Etap 1). Zwraca ścieżkę pliku."""
    doc = zbuduj_dokument(proj)
    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia
