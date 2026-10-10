"""
Budowa DXF na bazie SZABLONU zab2.dxf — arkusze i tabelka kopiowane ze wzorca.

Strategia:
  1. Wczytujemy wzorzec zab2.dxf.
  2. Czyścimy jego model space (usuwamy starą trasę/studnie/opisy), zachowując
     warstwy, typy linii, style, bloki (studnia/mufa) i — co najważniejsze —
     gotowe ARKUSZE A3 z tabelką i rzutniami.
  3. Rysujemy w model space nowe dane z projektu (ta sama logika co dxf_model).
  4. Dla każdego fragmentu trasy klonujemy wzorcowy arkusz, ustawiamy rzutnię
     (view_center) na środek fragmentu i podmieniamy pola tabelki.

Dzięki temu arkusze i tabelka są 1:1 jak w zab2.dxf (format, marginesy,
drukarka, układ pól), a zmienia się tylko zawartość mapy i metryki.
"""

from __future__ import annotations

import os

import ezdxf

from . import dxf_model
from .arkusze import Arkusz, podziel_na_arkusze
from .model import Projekt

SCIEZKA_WZORCA_DOMYSLNA = "zab2.dxf"

# nazwa wzorcowego layoutu-arkusza (A3, z tabelką i rzutnią 1:1000)
LAYOUT_WZORZEC = "2.1 (10)"


def _znajdz_wzorzec(sciezka: str | None) -> str:
    if sciezka and os.path.exists(sciezka):
        return sciezka
    # szukaj w katalogu bieżącym i obok modułu
    for kand in (SCIEZKA_WZORCA_DOMYSLNA,
                 os.path.join(os.path.dirname(__file__), "..", SCIEZKA_WZORCA_DOMYSLNA)):
        if os.path.exists(kand):
            return kand
    raise FileNotFoundError(
        f"Nie znaleziono szablonu {SCIEZKA_WZORCA_DOMYSLNA}. "
        "Umieść go w katalogu z danymi."
    )


def _wyczysc_modelspace(doc) -> None:
    """Usuwa z model space zawartość (trasa/studnie/opisy wzorca)."""
    msp = doc.modelspace()
    do_usuniecia = list(msp)
    for e in do_usuniecia:
        try:
            msp.delete_entity(e)
        except Exception:
            pass


def _wybierz_layout_wzorzec(doc):
    """Zwraca nazwę istniejącego wzorcowego arkusza A3 z tabelką."""
    kandydaci = [n for n in doc.layouts.names() if n != "Model"]
    if LAYOUT_WZORZEC in kandydaci:
        return LAYOUT_WZORZEC
    # wybierz arkusz z największą liczbą encji (najpełniejsza tabelka)
    best, best_n = None, -1
    for n in kandydaci:
        lay = doc.layouts.get(n)
        cnt = sum(1 for _ in lay)
        if cnt > best_n:
            best, best_n = n, cnt
    return best


def _ustaw_rzutnie(layout, ark: Arkusz) -> None:
    """Ustawia aktywną rzutnię (viewport mapy) na środek fragmentu trasy."""
    vps = [v for v in layout.query("VIEWPORT")]
    # pomijamy główny viewport paper space (id==1); bierzemy ten z największym view
    mapowe = [v for v in vps if getattr(v.dxf, "id", 1) != 1]
    if not mapowe:
        mapowe = vps
    # viewport o największej powierzchni = główna rzutnia mapy
    glowny = max(mapowe, key=lambda v: getattr(v.dxf, "width", 0) * getattr(v.dxf, "height", 0))
    glowny.dxf.view_center_point = (ark.center_x, ark.center_y, 0)


def _podmien_pole_tabelki(layout, proj: Projekt, ark: Arkusz,
                          jest_pierwszy: bool = True,
                          jest_ostatni: bool = True) -> None:
    """
    Dynamicznie aktualizuje pola tabelki danymi z WT.

    UWAGA: ramki zakończeń (prostokąt + tekst + strzałka) NIE są obsługiwane
    tutaj — są najpierw w całości usuwane ze wzorca (razem ze „śmieciami"),
    a następnie rysowane od zera przez `_rysuj_ramke_zakonczenia`
    (patrz `generuj_z_szablonu`). Dzięki temu ramka zawsze mieści tekst,
    a strzałka wskazuje właściwą skrajną studnię.
    Zachowujemy formatowanie MTEXT (kody \\P, \\T, \\px...).
    """
    import re
    d = proj.dane
    nr_rys = d.rys_nr or f"{ark.numer}"

    for e in layout.query("MTEXT"):
        txt = e.text

        # --- nr rysunku (duży tekst "2.1") ---
        if re.fullmatch(r"\d+(\.\d+)*", txt.strip()) and e.dxf.char_height >= 3.5:
            e.text = nr_rys
            continue

        # --- operator / adres (Wykonawca, Inwestor) ---
        if "Wawtel" in txt or "sp. z o" in txt.lower():
            if d.operator:
                e.text = _zbuduj_operator(txt, d)
            continue

        # --- pole TEMAT w tabelce: rozpoznane po kodzie "\pxi0,l1;" (dwuwierszowy
        #     adres A - B w metryce), NIE mylić z ramkami zakończeń ---
        if txt.startswith("\\pxi0,l1;") or ("GÓRNOŚLĄSKA" in txt.upper() and " - " in txt):
            if d.zakonczenie_a_adres or d.zakonczenie_b_adres:
                e.text = _zbuduj_temat(txt, d)
            continue

        # --- projektant ---
        if "Ostasiewicz" in txt or ("mgr" in txt.lower() and "inż" in txt.lower()):
            if d.projektant:
                e.text = d.projektant
            continue

        # --- nr uprawnień ---
        if re.fullmatch(r"\s*\d+/\d+/\w+\s*", txt):
            if d.nr_uprawnien:
                e.text = d.nr_uprawnien
            continue

        # --- data ---
        if "Data:" in txt:
            if d.data_rys or d.data_wt:
                e.text = f" Data: {d.data_rys or d.data_wt}"
            continue

        # --- nr kabla samodzielny (Wykonawca WTROI) ---
        if re.fullmatch(r"\s*WTROI/\d+/\w+\s*", txt):
            if d.nr_kabla:
                e.text = d.nr_kabla
            continue


def _fmt_pl(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _zbuduj_operator(oryg: str, d) -> str:
    """Odtwarza blok 'nazwa + adres' zachowując kod formatowania \\T jeśli był."""
    pref = ""
    if oryg.startswith("{\\T"):
        pref = oryg[: oryg.find(";") + 1]  # np. {\T0.9;
        suf = "}"
    else:
        suf = ""
    linie = d.operator
    if d.adres_operatora:
        linie += "\\P" + d.adres_operatora
    return f"{pref}{linie}{suf}"


def _zbuduj_temat(oryg: str, d) -> str:
    pref = ""
    if oryg.startswith("\\px"):
        pref = oryg[: oryg.find(";") + 1]
    a = d.zakonczenie_a_adres
    b = d.zakonczenie_b_adres
    return f"{pref}{a} - \\P{b}"


# ====================================================================
#  RAMKI ZAKOŃCZEŃ A / B  — rysowane OD ZERA (prostokąt + tekst + strzałka)
# ====================================================================
#
# Wzorzec (opis zakonczenia a/b.png): prostokąt, w środku tekst, a od ramki
# odchodzi strzałka wskazująca skrajną studnię (zakończenie trasy).
#
# Założenia (jednostki = mm na papierze A3; 1 mm papieru = 1 m terenu w 1:1000):
#   - wysokość tekstu ramki: ~2.0 mm (jak wzorzec zab2.dxf: 1.944),
#   - ramka jest DYNAMICZNIE dopasowywana do tekstu (szer. i wys.), z marginesem
#     wewnętrznym, tak aby żadna linia (zwł. prawy górny róg) nie wychodziła poza
#     obramowanie,
#   - strzałka: linia łamana od krawędzi ramki do punktu skrajnej studni, z
#     grotem (SOLID), na warstwie 'obramowanie ramek'.

WYS_TEKST_ZAK = 1.944          # wysokość tekstu w ramce [mm] (ze wzorca)
PAD_RAMKI = 2.5                # margines wewnętrzny ramki wokół tekstu [mm]
# Zapas na szerokość znaku Arial. Wartość CELOWO zawyżona (0,68 zamiast ~0,55
# realnej średniej), by ramka ZAWSZE mieściła tekst — także wiersze pisane
# wersalikami (np. „GÓRNOŚLĄSKA"), które są szersze. Lepiej ramka minimalnie
# za szeroka niż tekst wychodzący poza prawą krawędź (wymóg użytkownika).
SZER_ZNAKU = 0.68              # przybliżona szerokość znaku Arial (× wysokość)
INTERLINIA = 1.55              # odstęp między wierszami (× wysokość)
GROT = 2.0                     # długość grota strzałki [mm] (ze wzorca)
ZAPAS_SZER = 1.08              # dodatkowy zapas szerokości ramki (×) — bufor

# środek i rozmiar głównej rzutni mapy na papierze (z arkuszy.py / zab2.dxf)
_VP_CENTER_PAPER = (197.0, 142.5)

# jednorazowo wczytana czcionka Arial do pomiaru szerokości tekstu (realny
# rozmiar, nie zgadywany). Gdy niedostępna — używamy współczynnika SZER_ZNAKU.
_FONT_CACHE = {}


def _font_arial(h: float):
    """Zwraca obiekt czcionki ezdxf o wysokości h (z cache) albo None."""
    if h in _FONT_CACHE:
        return _FONT_CACHE[h]
    font = None
    try:
        from ezdxf.fonts.fonts import make_font
        font = make_font("arial.ttf", h)
        # sanity-check: zmierz literę; gdy brak czcionek, text_width zwróci 0/rzuci
        if not font.text_width("W") > 0:
            font = None
    except Exception:
        font = None
    _FONT_CACHE[h] = font
    return font


def _szerokosc_linii(tekst: str, h: float) -> float:
    """
    Rzeczywista szerokość pojedynczej linii tekstu [mm]. Preferuje pomiar
    czcionką (ezdxf), z buforem; w razie braku czcionki — oszacowanie przez
    współczynnik SZER_ZNAKU (celowo zawyżony).
    """
    font = _font_arial(h)
    if font is not None:
        try:
            return font.text_width(tekst) * ZAPAS_SZER
        except Exception:
            pass
    return len(tekst) * SZER_ZNAKU * h * ZAPAS_SZER


def _dane_zakonczenia(strona: str, d):
    """Zwraca listę (tekst, czy_pomaranczowy) wierszy ramki zakończenia."""
    if strona == "A":
        adres = d.zakonczenie_a_adres
        studnia = d.zakonczenie_a_studnia
        opis = d.zakonczenie_a_opis or "Wyjście rurą HDPE"
    else:
        adres = d.zakonczenie_b_adres
        studnia = d.zakonczenie_b_studnia
        opis = d.zakonczenie_b_opis or "Dowiązanie do projektowanej mufy"
    typ = d.typ_kabla or "Z-XOTKtsd"
    srednica = f"  Ø {d.srednica_kabla} mm" if d.srednica_kabla else ""
    linie = [
        (f"Zakończenie {strona}:", False),
        (adres, False),
        (f"Studnia OPL S.A.: {studnia}", False),
        (f"Proj. kabel {typ}{srednica}", True),   # pomarańczowy
        (opis, True),                              # pomarańczowy
    ]
    return [(t, kol) for (t, kol) in linie if t]


def _studnia_terminala_papier(proj: Projekt, ark: Arkusz, strona: str):
    """
    Punkt skrajnej studni (A = pierwsza, B = ostatnia) w układzie PAPIERU
    danego arkusza [mm]. Transformacja 1:1000: 1 m terenu = 1 mm papieru,
    px = 197 + (x - center_x),  py = 142.5 + (y - center_y).
    Zwraca (px, py) lub None, gdy brak studni.
    """
    if not proj.studnie:
        return None
    s = proj.studnie[0] if strona == "A" else proj.studnie[-1]
    px = _VP_CENTER_PAPER[0] + (s.x - ark.center_x)
    py = _VP_CENTER_PAPER[1] + (s.y - ark.center_y)
    return (px, py)


def _rysuj_ramke_zakonczenia(layout, proj: Projekt, ark: Arkusz, strona: str,
                             kotwica=None) -> None:
    """
    Rysuje ramkę zakończenia OD ZERA: prostokąt dopasowany do tekstu, tekst
    wewnątrz (lewy górny róg + padding) oraz strzałkę do skrajnej studni.

    kotwica: (x, y) lewego-górnego rogu ramki [mm papieru]. Gdy None —
             używamy pozycji ze wzorca (lewy-górny obszar arkusza).
    """
    d = proj.dane
    linie = _dane_zakonczenia(strona, d)
    if not linie:
        return

    h = WYS_TEKST_ZAK
    # --- rozmiar ramki dopasowany do NAJSZERSZEJ linii (realny pomiar czcionką,
    #     kontrola prawego górnego rogu) ---
    szer_tekstu = max(_szerokosc_linii(t, h) for t, _ in linie)
    wys_tekstu = (len(linie) - 1) * INTERLINIA * h + h
    szer_ramki = szer_tekstu + 2 * PAD_RAMKI
    wys_ramki = wys_tekstu + 2 * PAD_RAMKI

    # lewy-górny róg ramki
    if kotwica is None:
        lx, gy = (38.1, 223.9) if strona == "A" else (31.0, 60.3)
    else:
        lx, gy = kotwica
    # prawy-dolny róg
    px = lx + szer_ramki
    dy = gy - wys_ramki

    # --- prostokąt ramki (obramowanie) ---
    layout.add_lwpolyline(
        [(lx, dy), (px, dy), (px, gy), (lx, gy)],
        close=True,
        dxfattribs={"layer": "obramowanie ramek"},
    )

    # --- tekst wewnątrz: MTEXT z lewym-górnym punktem (attach=1), wiersze \P,
    #     linie kabla/opisu w kolorze pomarańczowym (ACI 30) ---
    czesci = []
    for t, pomarancz in linie:
        bezp = t.replace("\\", "\\\\")
        if pomarancz:
            czesci.append(f"{{\\C30;{bezp}}}")
        else:
            czesci.append(bezp)
    tresc = "\\P".join(czesci)
    mt = layout.add_mtext(tresc, dxfattribs={"layer": "obramowanie ramek",
                                             "style": dxf_model.STYL_ARIAL})
    mt.dxf.char_height = h
    # szerokość kolumny MTEXT = zmierzona szerokość najszerszej linii (z buforem
    # ZAPAS_SZER wliczonym już w szer_tekstu) + mały epsilon, aby CAD NIE zawijał
    # wiersza do kolejnej linii (zawijanie psuło wysokość i wychodziło poza ramkę)
    mt.dxf.width = szer_tekstu + 0.5
    # punkt wstawienia = lewy-górny róg obszaru tekstu (po paddingu)
    mt.set_location((lx + PAD_RAMKI, gy - PAD_RAMKI), attachment_point=1)  # TOP_LEFT

    # --- strzałka do skrajnej studni ---
    cel = _studnia_terminala_papier(proj, ark, strona)
    if cel is not None:
        _rysuj_strzalke(layout, (lx, dy, px, gy), cel)


def _rysuj_strzalke(layout, ramka_box, cel) -> None:
    """
    Łamana strzałka od ramki do punktu `cel` (skrajna studnia) z grotem (SOLID).
    ramka_box = (lx, dy, px, gy). Start = róg ramki najbliższy celu;
    strzałka wychodzi lekko „na zewnątrz" (jak we wzorcu).
    """
    lx, dy, px, gy = ramka_box
    cx = (lx + px) / 2.0
    cy = (dy + gy) / 2.0
    tx, ty = cel

    # jeśli skrajna studnia wypada POZA obszarem mapy na papierze
    # (x:[0,394], y:[0,285]) — przytnij grot do krawędzi widoku, by strzałka
    # nie uciekała poza arkusz
    tx = min(max(tx, 1.0), 393.0)
    ty = min(max(ty, 1.0), 284.0)

    # punkt startu na krawędzi ramki — róg po stronie celu
    sx = lx if tx < cx else px
    sy = dy if ty < cy else gy
    # mały „ząb" wychodzący z rogu w kierunku celu
    dx, dyv = tx - sx, ty - sy
    dlug = (dx * dx + dyv * dyv) ** 0.5 or 1.0
    ux, uy = dx / dlug, dyv / dlug
    kolano = (sx + ux * 3.0, sy + uy * 3.0)

    layout.add_lwpolyline(
        [(sx, sy), kolano, (tx, ty)],
        dxfattribs={"layer": "obramowanie ramek"},
    )
    # grot strzałki (trójkąt SOLID) przy celu
    perp = (-uy, ux)
    g = GROT
    p1 = (tx, ty)
    p2 = (tx - ux * g + perp[0] * g * 0.35, ty - uy * g + perp[1] * g * 0.35)
    p3 = (tx - ux * g - perp[0] * g * 0.35, ty - uy * g - perp[1] * g * 0.35)
    layout.add_solid([p1, p2, p3, p3],
                     dxfattribs={"layer": "obramowanie ramek"})


def _usun_smieci_ramek(layout) -> None:
    """
    Usuwa z arkusza WSZYSTKIE pozostałości wzorca po ramkach zakończeń oraz
    „śmieci" (smiec.png): puste prostokąty, osierocone strzałki (MULTILEADER),
    bloki opisu kabla przyklejone poza papierem itd.

    Zachowujemy wyłącznie elementy TABELKI (layer 0 z realnymi polami, rzutnie,
    wymiarowanie/Otworówka tabelki). Czyszczone są:
      - MTEXT zawierające 'Zakończenie' (stare ramki tekstowe),
      - MTEXT z blokiem 'Proj.\\Ikabel ... dł. trasowa ...' (osierocony opis),
      - WSZYSTKIE encje na warstwie 'obramowanie ramek'
        (prostokąty ramek + MULTILEADER-strzałki wzorca),
      - MULTILEADER (strzałki) na dowolnej warstwie.
    """
    do_usuniecia = []
    for e in layout:
        t = e.dxftype()
        warstwa = e.dxf.layer
        if warstwa == "obramowanie ramek":
            do_usuniecia.append(e)
            continue
        if t == "MULTILEADER":
            do_usuniecia.append(e)
            continue
        if t == "MTEXT":
            txt = e.text
            if "Zakończenie" in txt or "Zakonczenie" in txt:
                do_usuniecia.append(e)
                continue
            # osierocony opis kabla wzorca (blok 'Proj.\Ikabel ... dł. trasowa')
            if "Proj." in txt and "dł. trasowa" in txt:
                do_usuniecia.append(e)
                continue
    for e in do_usuniecia:
        try:
            layout.delete_entity(e)
        except Exception:
            pass


def generuj_z_szablonu(
    proj: Projekt,
    sciezka_wyjscia: str,
    sciezka_wzorca: str | None = None,
    zaklad_m: float | None = None,
) -> tuple[str, int]:
    """
    Generuje DXF używając zab2.dxf jako szablonu arkuszy i tabelki.
    Zwraca (ścieżka, liczba_arkuszy).
    """
    wzorzec = _znajdz_wzorzec(sciezka_wzorca)
    doc = ezdxf.readfile(wzorzec)

    # 1) wyczyść model space, zachowaj warstwy/style/bloki/arkusze
    _wyczysc_modelspace(doc)

    # 2) upewnij się, że mamy styl Arial + poprawione warstwy (trasa czarna itd.)
    dxf_model._utworz_warstwy(doc)
    dxf_model._utworz_styl_arial(doc)
    if "studnia" not in doc.blocks:
        dxf_model._utworz_blok_studni(doc)

    # 3) narysuj nowe dane w model space
    proj.przelicz_numery_zapasow()
    msp = doc.modelspace()
    dxf_model.rysuj_zawartosc(msp, proj)

    # 4) arkusze: klonuj wzorcowy layout dla każdego fragmentu trasy
    lista = podziel_na_arkusze(proj, zaklad_m=zaklad_m)
    nazwa_wzorca = _wybierz_layout_wzorzec(doc)

    # usuń pozostałe wzorcowe arkusze (zostaw tylko jeden jako bazę do klonowania)
    bazowy = doc.layouts.get(nazwa_wzorca)
    for n in [x for x in doc.layouts.names() if x not in ("Model", nazwa_wzorca)]:
        try:
            doc.layouts.delete(n)
        except Exception:
            pass

    n_ark = len(lista)
    for i, ark in enumerate(lista):
        jest_pierwszy = (i == 0)
        jest_ostatni = (i == n_ark - 1)
        if i == 0:
            layout = bazowy
            try:
                doc.layouts.rename(nazwa_wzorca, f"Arkusz {ark.numer}")
            except Exception:
                pass
        else:
            layout = _klonuj_layout(doc, bazowy, f"Arkusz {ark.numer}")

        _ustaw_rzutnie(layout, ark)
        _podmien_pole_tabelki(layout, proj, ark, jest_pierwszy, jest_ostatni)

        # najpierw USUŃ wszystkie wzorcowe ramki zakończeń + śmieci,
        # potem narysuj czyste ramki OD ZERA tylko tam, gdzie trzeba:
        #   - "Zakończenie A" tylko na PIERWSZYM arkuszu,
        #   - "Zakończenie B" tylko na OSTATNIM arkuszu.
        _usun_smieci_ramek(layout)
        if jest_pierwszy:
            _rysuj_ramke_zakonczenia(layout, proj, ark, "A")
        if jest_ostatni:
            _rysuj_ramke_zakonczenia(layout, proj, ark, "B")

    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, len(lista)


# atrybuty plot settings do skopiowania 1:1 z layoutu bazowego
_PLOT_ATRYBUTY = (
    "plot_configuration_file", "paper_size", "plot_paper_units", "plot_rotation",
    "plot_type", "paper_width", "paper_height", "plot_origin_x_offset",
    "plot_origin_y_offset", "left_margin", "bottom_margin", "right_margin",
    "top_margin", "scale_numerator", "scale_denominator", "standard_scale_type",
    "plot_layout_flags", "unit_factor", "plot_view_name", "current_style_sheet",
)


def _klonuj_layout(doc, bazowy, nowa_nazwa: str):
    """
    Klonuje layout bazowy wraz z zawartością (tabelka, ramka, rzutnia)
    ORAZ dokładnymi ustawieniami wydruku skopiowanymi z bazowego
    (ten sam profil 'DWG To PDF', rozmiar User69634, marginesy wzorca).
    """
    if nowa_nazwa in doc.layouts.names():
        doc.layouts.delete(nowa_nazwa)
    nowy = doc.layouts.new(nowa_nazwa)

    # 1) skopiuj WSZYSTKIE atrybuty plot settings wprost z bazowego layoutu
    #    (kluczowe — bez tego kopie dostają generyczny profil ezdxf i "zły format")
    for a in _PLOT_ATRYBUTY:
        try:
            val = getattr(bazowy.dxf, a)
            setattr(nowy.dxf, a, val)
        except Exception:
            pass

    # 2) skopiuj encje paper space (tabelka, ramki, rzutnie, opisy)
    for e in bazowy:
        try:
            nowa = e.copy()
            nowy.add_entity(nowa)
        except Exception:
            pass
    return nowy
