"""
Tabelka rysunkowa (metryka) umieszczana w prawym dolnym rogu arkusza (paper space).

Współrzędne w milimetrach papieru (layout). Pola wypełniane danymi z WT
(Formularz 1K). Jeśli pole jest puste — zostaje pusta komórka.

Dbałość o mieszczenie tekstu: jeśli tekst jest dłuższy niż szerokość komórki,
najpierw zmniejszana jest wysokość tekstu (do minimum), a następnie tekst jest
łamany na wiersze. Dzięki temu metryka nie "wylewa się" poza ramkę.
"""

from __future__ import annotations

from dataclasses import dataclass

from ezdxf.enums import TextEntityAlignment

from .model import DaneProjektu, Projekt

STYL_ARIAL = "Arial"
LAYER = "obramowanie ramek"
LAYER_TEKST = "obramowanie ramek"

# wymiary tabelki [mm]
TAB_W = 180.0
TAB_H = 60.0
PAD = 1.5           # wewnętrzny margines komórki [mm]
H_TEKST = 2.5       # domyślna wysokość tekstu [mm]
H_TEKST_MIN = 1.4   # minimalna wysokość przy zmniejszaniu
H_NAGL = 2.0        # wysokość etykiet (nagłówków pól)


@dataclass
class Pole:
    """Pojedyncza komórka tabelki (we współrzędnych lokalnych tabelki, mm)."""
    x: float
    y: float
    w: float
    h: float
    etykieta: str = ""
    wartosc: str = ""
    h_tekst: float = H_TEKST


def _przytnij_do_szerokosci(tekst: str, szer_mm: float, h: float) -> tuple[str, float]:
    """
    Dobiera wysokość tekstu tak, aby zmieścił się w szerokości komórki.
    Przybliżenie: szerokość znaku Arial ≈ 0,6 * wysokość.
    Zwraca (tekst, dobrana_wysokość). Jeśli i tak za długi — zwraca mniejszą wys.
    """
    if not tekst:
        return tekst, h
    while h > H_TEKST_MIN:
        szer_znaku = 0.62 * h
        if len(tekst) * szer_znaku <= szer_mm:
            return tekst, h
        h -= 0.1
    return tekst, max(h, H_TEKST_MIN)


def _lamanie(tekst: str, szer_mm: float, h: float) -> list[str]:
    """Łamie tekst na wiersze mieszczące się w szerokości komórki."""
    if not tekst:
        return [""]
    szer_znaku = 0.62 * h
    maks_znakow = max(1, int(szer_mm / szer_znaku))
    slowa = tekst.split()
    linie, biez = [], ""
    for w in slowa:
        prob = (biez + " " + w).strip()
        if len(prob) <= maks_znakow:
            biez = prob
        else:
            if biez:
                linie.append(biez)
            biez = w
    if biez:
        linie.append(biez)
    return linie or [""]


def _definicja_pol(d: DaneProjektu, proj: Projekt) -> list[Pole]:
    """
    Układ pól metryki (lokalnie, w mm, origin = lewy-dolny róg tabelki).
    Zbliżony do układu z zab2.dxf (inwestor, obiekt, temat, skala, nr rys...).
    """
    kol = TAB_W
    pola: list[Pole] = []

    # wiersz górny: Inwestor / Projektanci / Nr uprawnień
    pola.append(Pole(0, 48, 70, 12, "Inwestor:", f"{d.operator}\n{d.adres_operatora}"))
    pola.append(Pole(70, 48, 70, 12, "Projektant:", d.projektant))
    pola.append(Pole(140, 48, 40, 12, "Nr uprawnień:", d.nr_uprawnien))

    # Obiekt
    pola.append(Pole(0, 36, 180, 12, "Obiekt:",
                     "TRASA PROJEKTOWANEGO KABLA W DZIERŻAWIONEJ "
                     "KANALIZACJI ORANGE POLSKA S.A."))

    # Temat (adresy zakończeń)
    temat = ""
    if d.zakonczenie_a_adres or d.zakonczenie_b_adres:
        temat = f"{d.zakonczenie_a_adres} - {d.zakonczenie_b_adres}"
    pola.append(Pole(0, 24, 110, 12, "Temat:", temat))
    pola.append(Pole(110, 24, 35, 12, "Skala:", d.skala))
    pola.append(Pole(145, 24, 35, 12, "Data:", d.data_rys or d.data_wt))

    # Branża / Nr rys / Nr kabla
    pola.append(Pole(0, 12, 70, 12, "Branża:", "TELEKOMUNIKACJA"))
    pola.append(Pole(70, 12, 70, 12, "Nr kabla:", d.nr_kabla))
    pola.append(Pole(140, 12, 40, 12, "RYS. NR:", d.rys_nr))

    # dolny pasek: długości
    dl = (f"dł. trasowa: {_fmt(proj.dlugosc_trasowa())} m    "
          f"dł. montażowa: {_fmt(proj.dlugosc_montazowa())} m")
    pola.append(Pole(0, 0, 180, 12, "Długości:", dl))

    return pola


def _fmt(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def rysuj_tabelke(psp, proj: Projekt, origin_x: float, origin_y: float) -> None:
    """
    Rysuje tabelkę w paper space.
    origin_x, origin_y = lewy-dolny róg tabelki (mm na papierze).
    """
    pola = _definicja_pol(proj.dane, proj)

    # ramka zewnętrzna
    psp.add_lwpolyline(
        [(origin_x, origin_y),
         (origin_x + TAB_W, origin_y),
         (origin_x + TAB_W, origin_y + TAB_H),
         (origin_x, origin_y + TAB_H)],
        close=True,
        dxfattribs={"layer": LAYER},
    )

    for p in pola:
        bx, by = origin_x + p.x, origin_y + p.y
        # ramka komórki
        psp.add_lwpolyline(
            [(bx, by), (bx + p.w, by), (bx + p.w, by + p.h), (bx, by + p.h)],
            close=True,
            dxfattribs={"layer": LAYER},
        )
        # etykieta (u góry komórki)
        if p.etykieta:
            psp.add_text(
                p.etykieta,
                dxfattribs={"layer": LAYER_TEKST, "style": STYL_ARIAL, "height": H_NAGL},
            ).set_placement((bx + PAD, by + p.h - PAD), align=TextEntityAlignment.TOP_LEFT)

        # wartość (poniżej etykiety, z kontrolą mieszczenia)
        if p.wartosc:
            _wpisz_wartosc(psp, p, bx, by)


def _wpisz_wartosc(psp, p: Pole, bx: float, by: float) -> None:
    szer = p.w - 2 * PAD
    gora_wartosci = by + p.h - PAD - (H_NAGL + 0.8 if p.etykieta else 0)

    # najpierw spróbuj dobrać wysokość, by cała wartość zmieściła się w 1 linii
    linie_wejsc = p.wartosc.split("\n")
    h = p.h_tekst
    wszystkie_linie: list[str] = []
    for lw in linie_wejsc:
        _, h_dob = _przytnij_do_szerokosci(lw, szer, h)
        h = min(h, h_dob)
    # po dobraniu wysokości — połam gdzie trzeba
    for lw in linie_wejsc:
        wszystkie_linie.extend(_lamanie(lw, szer, h))

    # jeśli liczba linii nie mieści się w wysokości komórki — zmniejsz jeszcze
    dost_wys = (p.h - 2 * PAD) - (H_NAGL + 0.8 if p.etykieta else 0)
    while len(wszystkie_linie) * (h * 1.3) > dost_wys and h > H_TEKST_MIN:
        h -= 0.1
        wszystkie_linie = []
        for lw in linie_wejsc:
            wszystkie_linie.extend(_lamanie(lw, szer, h))

    y = gora_wartosci
    for linia in wszystkie_linie:
        psp.add_text(
            linia,
            dxfattribs={"layer": LAYER_TEKST, "style": STYL_ARIAL, "height": h},
        ).set_placement((bx + PAD, y), align=TextEntityAlignment.TOP_LEFT)
        y -= h * 1.3
