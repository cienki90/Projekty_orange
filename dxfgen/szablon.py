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


# --- obszary PAPIERU zasłonięte przez tabelki (mm); trasa nie może pod nie
#     wchodzić, bo po wydruku byłaby niewidoczna ---
#   tabelka główna (prawy-dolny róg):  x 256..394, y 0..40
#   opis kabla      (prawy-górny róg): x 302..394, y 269..285
_ZASLONIETE = [
    (256.0, 0.0, 394.0, 40.0),      # (x0, y0, x1, y1) — tabelka główna
    (288.0, 268.0, 394.0, 285.0),   # opis kabla (prawy-górny róg)
]
# obszar widoczny rzutni mapy na papierze [mm]
_VP_OBSZAR = (0.0, 0.0, 394.0, 285.0)


def _ustaw_rzutnie(layout, ark: Arkusz, proj: "Projekt | None" = None) -> None:
    """
    Ustawia aktywną rzutnię (viewport mapy). Domyślnie na środek fragmentu
    trasy; jeśli przy tym środku jakikolwiek punkt trasy wypadłby POD tabelką
    (prawy-dolny / prawy-górny róg), środek jest przesuwany tak, aby cała
    widoczna trasa znalazła się w obszarze NIEzasłoniętym (kontrola widoczności
    wydruku).
    """
    vps = [v for v in layout.query("VIEWPORT")]
    mapowe = [v for v in vps if getattr(v.dxf, "id", 1) != 1]
    if not mapowe:
        mapowe = vps
    glowny = max(mapowe, key=lambda v: getattr(v.dxf, "width", 0) * getattr(v.dxf, "height", 0))

    cx, cy = ark.center_x, ark.center_y
    if proj is not None and ark.studnie_idx:
        cx, cy = _dopasuj_srodek_bez_zaslon(proj, ark)
        ark.center_x, ark.center_y = cx, cy  # by strzałki zakończeń liczyły się spójnie
    glowny.dxf.view_center_point = (cx, cy, 0)


def _dopasuj_srodek_bez_zaslon(proj: "Projekt", ark: Arkusz) -> tuple[float, float]:
    """
    Dobiera środek widoku (view_center) tak, aby footprint trasy na papierze w
    miarę możliwości NIE wchodził w rogi zasłonięte tabelkami
    (prawy-dolny / prawy-górny). Przesuwa środek MINIMALNIE względem środka
    bbox fragmentu — trasa „ucieka" z rogu w lewo i/lub w pionie, o ile się
    mieści w obszarze rzutni. Transformacja papieru:
        px = 197 + (mx - cx),  py = 142.5 + (my - cy).
    """
    s = proj.studnie
    idxs = ark.studnie_idx
    xs = [s[i].x for i in idxs]
    ys = [s[i].y for i in idxs]
    # mały zapas (połowa odsunięcia pomarańczowej linii) — kontrola zasłon
    # obejmuje głównie czarną trasę + węzły; pełne 15 m powiększałoby footprint
    # ponad obszar czysty i psuło dobór środka, więc stosujemy łagodny bufor.
    OFF = dxf_model.TRASA_ODSUNIECIE * 0.4
    minx, maxx = min(xs) - OFF, max(xs) + OFF
    miny, maxy = min(ys) - OFF, max(ys) + OFF
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0

    PX, PY = _VP_CENTER_PAPER
    VX0, VY0, VX1, VY1 = _VP_OBSZAR
    MARG = 5.0  # trzymaj trasę kawałek od krawędzi rzutni

    w = maxx - minx   # szerokość footprintu trasy [m == mm na papierze]
    h = maxy - miny   # wysokość

    def bbox_paper(cx, cy):
        return (PX + (minx - cx), PY + (miny - cy),
                PX + (maxx - cx), PY + (maxy - cy))

    def koliduje(bb):
        bx0, by0, bx1, by1 = bb
        for zx0, zy0, zx1, zy1 in _ZASLONIETE:
            if not (bx1 <= zx0 or bx0 >= zx1 or by1 <= zy0 or by0 >= zy1):
                return True
        return False

    # Zbuduj listę docelowych PRZEDZIAŁÓW papieru dla lewej krawędzi footprintu
    # (bx0) i dolnej (by0), preferując:
    #   1) całą trasę na LEWO od tabelek (prawa krawędź px <= 254),
    #   2) jeśli za szeroka — w PIONOWYM pasie między tabelkami (y 45..266).
    # Dla każdej opcji wyznaczamy (cx,cy) i sprawdzamy brak kolizji + mieszczenie.
    kandydaci = []

    # opcja 1: wyśrodkuj w pionie, dosuń w lewo tak, by px(max) <= 254
    #   px(max) = PX + (maxx - cx) <= 254  =>  cx >= maxx - (254 - PX)
    cx1 = maxx - (254.0 - PX)
    cy1 = cy                      # pion jak natura
    kandydaci.append((cx1, cy1))

    # opcja 2: zostaw poziomo jak natura, ale wepchnij w pas pionowy 45..266:
    #   chcemy by0 >= 45 i by1 <= 266
    #   by0 = PY + (miny - cy) ; by1 = PY + (maxy - cy)
    cy2 = PY + maxy - 266.0 + MARG      # by1 = 266-MARG
    kandydaci.append((cx, cy2))
    cy2b = PY + miny - 45.0 - MARG      # by0 = 45+MARG
    kandydaci.append((cx, cy2b))

    # opcja 3: kombinacja — lewo + pas pionowy
    kandydaci.append((cx1, cy2))
    kandydaci.append((cx1, cy2b))

    # opcja 0: natura (gdy nic nie zasłania)
    kandydaci.insert(0, (cx, cy))

    def dociag_do_vp(cx, cy):
        bx0, by0, bx1, by1 = bbox_paper(cx, cy)
        if bx0 < VX0 + MARG:
            cx += (bx0 - (VX0 + MARG))
        if bx1 > VX1 - MARG:
            cx += (bx1 - (VX1 - MARG))
        if by0 < VY0 + MARG:
            cy += (by0 - (VY0 + MARG))
        if by1 > VY1 - MARG:
            cy += (by1 - (VY1 - MARG))
        return cx, cy

    # kara liczona na RZECZYWISTEJ trasie (czarna polilinia), nie na buforze —
    # bufor służy tylko do preferencji, a o jakości decyduje realne zasłonięcie.
    # Uwzględniamy CAŁĄ trasę (nie tylko węzły tego arkusza) — w oknie rzutni
    # widać też sąsiednie odcinki (zakład), które też nie mogą wpaść pod tabelkę.
    tp_model = [(ss.x, ss.y) for ss in s]

    def kara_trasy(kx, ky):
        """Liczba „zasłoniętych" próbek trasy WIDOCZNYCH w oknie przy (kx,ky)."""
        import math
        n = 0
        for a in range(len(tp_model) - 1):
            (ax, ay), (bx, by) = tp_model[a], tp_model[a + 1]
            d = math.hypot(bx - ax, by - ay)
            steps = max(1, int(d / 3.0))
            for k in range(steps + 1):
                t = k / steps
                mx = ax + (bx - ax) * t
                my = ay + (by - ay) * t
                px = PX + (mx - kx)
                py = PY + (my - ky)
                # tylko to, co faktycznie widać w oknie rzutni
                if not (VX0 <= px <= VX1 and VY0 <= py <= VY1):
                    continue
                for zx0, zy0, zx1, zy1 in _ZASLONIETE:
                    if zx0 <= px <= zx1 and zy0 <= py <= zy1:
                        n += 1
                        break
        return n

    # wybierz pierwszego kandydata, dla którego trasa jest całkowicie odsłonięta;
    # jeśli żaden — ten z NAJMNIEJSZĄ liczbą zasłoniętych próbek trasy
    najlepszy = (cx, cy)
    najlepszy_kara = kara_trasy(cx, cy)   # natura jako baseline
    if najlepszy_kara == 0:
        # sprawdź, czy natura mieści footprint w VP; i tak zwróć
        return dociag_do_vp(cx, cy) if koliduje(bbox_paper(cx, cy)) else (cx, cy)
    for kx, ky in kandydaci:
        kx, ky = dociag_do_vp(kx, ky)
        k = kara_trasy(kx, ky)
        if k == 0:
            return (kx, ky)
        if k < najlepszy_kara:
            najlepszy_kara, najlepszy = k, (kx, ky)
    return najlepszy


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
    # numer rysunku: 2.1, 2.2, 2.3 ... (bazowy człon "2" + numer arkusza)
    nr_rys = _numer_rysunku(ark.numer)
    dl_tras = _fmt_pl(proj.dlugosc_trasowa())
    dl_mont = _fmt_pl(proj.dlugosc_montazowa())

    off_do_usuniecia = []
    for e in layout.query("MTEXT"):
        txt = e.text

        # --- usuń duplikaty pól tabelki/opisów leżące POZA papierem A3
        #     (wzorzec ma po 3 kopie "2.1"/"1:1000"/"PRZEBIEG..."/opis kabla —
        #      zostawiamy tylko tę na arkuszu, resztę kasujemy jako śmieci) ---
        if _poza_papierem(e):
            off_do_usuniecia.append(e)
            continue

        # --- górny-prawy opis kabla (Proj. kabel + dł. trasowa + montażowa) ---
        if "Proj." in txt and "dł. trasowa" in txt.lower():
            e.text = _zbuduj_opis_kabla(txt, d, dl_tras, dl_mont)
            _dopasuj_opis_kabla(layout, e, d, dl_tras, dl_mont)
            continue

        # UWAGA: numeru rysunku NIE ustawiamy tu — jest rysowany od zera w
        # _zapewnij_pola_rysunku (jedno źródło prawdy, bez duplikatów).

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

    # skasuj duplikaty leżące poza papierem (śmieci wzorca)
    for e in off_do_usuniecia:
        try:
            layout.delete_entity(e)
        except Exception:
            pass

    # GWARANCJA: Skala / opis rysunku / nr rysunku na KAŻDYM arkuszu
    # (klonowane arkusze potrafią „zgubić" te pola — rysujemy je pewnie od zera)
    _zapewnij_pola_rysunku(layout, nr_rys)

    # usuń pozostałe (nietekstowe) śmieci wzorca leżące poza papierem A3
    for e in list(layout):
        if e.dxftype() == "MTEXT":
            continue
        if _poza_papierem(e):
            try:
                layout.delete_entity(e)
            except Exception:
                pass


def _numer_rysunku(numer_arkusza: int) -> str:
    """Numer rysunku: 2.1, 2.2, 2.3 ... (człon główny „2" + numer arkusza)."""
    return f"2.{numer_arkusza}"


# KOMÓRKI tabelki (prawy-dolny róg) ze wzorca zab2.dxf [mm papieru].
# Pionowe linie siatki: 329 | 359 | 382 | 394 ; poziome: 0 | 8 | 15.2 | 16.
# Każde pole: (środek_x, środek_y, wysokość_tekstu, szer_komórki, wys_komórki)
#   Skala-wartość: komórka x[~346..359] y[8..16]  (po prawej od etykiety „Skala:")
#   Opis rysunku:  komórka x[329..382] y[0..8]    (dolny, szeroki pas)
#   Nr rysunku:    komórka x[382..394] y[0..16]   (wąska, duży numer)
_CELA_SKALA = (352.5, 12.0, 1.8, 12.0, 7.0)
_CELA_OPIS = (355.5, 4.0, 1.5, 52.0, 7.5)
_CELA_NR = (388.0, 7.0, 4.0, 11.5, 14.0)
_OPIS_RYS_TXT = "PRZEBIEG PROJEKTOWANEJ TRASY"
ACI_CZARNY = 7  # czarny (na białym tle) — teksty tabelki muszą być czarne


def _zapewnij_pola_rysunku(layout, nr_rys: str) -> None:
    """
    Gwarantuje obecność na arkuszu trzech pól tabelki, które na klonowanych
    arkuszach bywają gubione: Skala (1:1000), opis rysunku (PRZEBIEG
    PROJEKTOWANEJ TRASY) oraz numer rysunku (2.x).

    Wymagania:
      - tekst CZARNY (ACI 7) — niezależnie od koloru warstwy,
      - tekst MIEŚCI SIĘ w swojej komórce (dobór wysokości + ew. zawijanie),
        bez wychodzenia poza obręb pola.
    Najpierw usuwa istniejące kopie tych pól, potem rysuje od zera (Arial).
    """
    # usuń istniejące (na-arkuszowe) kopie tych pól
    do_usun = []
    for e in layout.query("MTEXT"):
        txt = e.text.strip()
        x, y = e.dxf.insert[0], e.dxf.insert[1]
        if not (250 <= x <= 420 and -5 <= y <= 45):
            continue
        if txt == "1:1000" or "PRZEBIEG PROJEKTOWANEJ TRASY" in txt:
            do_usun.append(e)
        # numer rysunku: duży tekst wyglądający jak „2", „2.1", „1", itp.,
        # w okolicy komórki RYS. NR (x>378) — próg wysokości obniżony, bo kopie
        # mogły zostać zmniejszone przy dopasowaniu do komórki
        elif e.dxf.char_height >= 2.5 and _wyglada_jak_nr(txt) and x >= 378:
            do_usun.append(e)
    for e in do_usun:
        try:
            layout.delete_entity(e)
        except Exception:
            pass

    _dodaj_pole_komorki(layout, "1:1000", _CELA_SKALA)
    _dodaj_pole_komorki(layout, _OPIS_RYS_TXT, _CELA_OPIS)
    _dodaj_pole_komorki(layout, nr_rys, _CELA_NR)


def _dodaj_pole_komorki(layout, tekst: str, cela) -> None:
    """
    Rysuje tekst wyśrodkowany w komórce (cx, cy), CZARNY, z wysokością dobraną
    tak, aby zmieścił się w szerokości i wysokości komórki (z marginesem).
    Gdy przy danej wysokości tekst jest szerszy niż komórka — zmniejsza
    wysokość; dopiero gdy minimalna wysokość nie wystarcza — pozwala zawinąć
    (MTEXT.width = szerokość komórki).
    """
    cx, cy, h0, szer_cela, wys_cela = cela
    pad = 1.0
    maks_szer = szer_cela - 2 * pad
    maks_wys = wys_cela - 2 * pad

    # dobierz wysokość tak, by JEDNA linia zmieściła się w szerokości komórki
    h = h0
    for _ in range(12):
        w = _szerokosc_linii(tekst, h) / ZAPAS_SZER  # realna szer. przy tej h
        if w <= maks_szer and h <= maks_wys:
            break
        h *= 0.92
        if h < 1.0:
            h = 1.0
            break

    mt = layout.add_mtext(tekst, dxfattribs={"layer": "0",
                                             "style": dxf_model.STYL_ARIAL,
                                             "color": ACI_CZARNY})
    mt.dxf.char_height = h
    # szerokość kolumny = komórka (gdyby mimo wszystko trzeba było zawinąć)
    mt.dxf.width = maks_szer
    mt.set_location((cx, cy), attachment_point=5)  # MIDDLE_CENTER


def _wyglada_jak_nr(txt: str) -> bool:
    import re
    return bool(re.fullmatch(r"\d+(\.\d+)*", txt))


def _poza_papierem(e) -> bool:
    """
    True, gdy encja leży (praktycznie w całości) POZA obszarem papieru A3
    (0..420 × 0..297 mm) — czyli jest „śmieciem" wzorca do skasowania.
    Dla MTEXT bierzemy punkt wstawienia; dla linii/polilinii — wszystkie
    wierzchołki; z marginesem tolerancji.
    """
    MARG = 5.0
    def poza(x, y):
        return x < -MARG or x > 420 + MARG or y < -MARG or y > 297 + MARG
    t = e.dxftype()
    try:
        if t == "MTEXT":
            p = e.dxf.insert
            return poza(p[0], p[1])
        if t == "LWPOLYLINE":
            pts = list(e.get_points("xy"))
            return bool(pts) and all(poza(x, y) for x, y in pts)
        if t == "LINE":
            s, en = e.dxf.start, e.dxf.end
            return poza(s[0], s[1]) and poza(en[0], en[1])
        if t == "MULTILEADER":
            try:
                bp = e.context.base_point
                return poza(bp[0], bp[1])
            except Exception:
                return False
        if t == "SOLID":
            v = e.dxf.vtx0
            return poza(v[0], v[1])
        if t == "HATCH":
            return False  # hatche tabelki zostawiamy
    except Exception:
        return False
    return False


def _zbuduj_opis_kabla(oryg: str, d, dl_tras: str, dl_mont: str) -> str:
    """
    Górny-prawy opis kabla (wg „tabelka górny róg.png"):
      wiersz 1: Proj. kabel <typ z WT 1.4> - <numer warunków/nr kabla>
      wiersz 2: dł. trasowa w kanalizacji Orange Polska S.A.: <X> m
      wiersz 3: dł. montażowa w kanalizacji Orange Polska S.A.: <Y> m
    Zachowuje prefiks akapitu wzorca (\\pxi...) i formatowanie \\T, jeśli były.
    """
    typ = d.typ_kabla or "Z-XOTKtsd"
    nrk = d.nr_kabla or ""
    srednica = f" Ø {d.srednica_kabla} mm" if d.srednica_kabla else ""
    # bez kodu tabulatora \I (renderował się dosłownie jako „\Ikabel");
    # bez skalowania \T, żeby tekst nie był szerszy niż ramka
    return (
        f"Proj. kabel {typ}{srednica} - {nrk}"
        f"\\Pdł. trasowa w kanalizacji Orange Polska S.A.: {dl_tras} m"
        f"\\Pdł. montażowa w kanalizacji Orange Polska S.A.: {dl_mont} m"
    )


def _dopasuj_opis_kabla(layout, mt, d, dl_tras: str, dl_mont: str) -> None:
    """
    Dopasowuje ramkę (prostokąt) górnego-prawego opisu kabla do tekstu i ustawia
    szerokość kolumny MTEXT, aby tekst się mieścił i nie zawijał poza ramkę.
    Ramka jest przyklejona do GÓRNEJ i PRAWEJ krawędzi rzutni (y=285, x=394).
    """
    h = 2.5
    typ = d.typ_kabla or "Z-XOTKtsd"
    nrk = d.nr_kabla or ""
    srednica = f" Ø {d.srednica_kabla} mm" if d.srednica_kabla else ""
    linie = [
        f"Proj. kabel {typ}{srednica} - {nrk}",
        f"dł. trasowa w kanalizacji Orange Polska S.A.: {dl_tras} m",
        f"dł. montażowa w kanalizacji Orange Polska S.A.: {dl_mont} m",
    ]
    szer_txt = max(_szerokosc_linii(t, h) for t in linie)
    pad = 2.0
    szer_ramki = szer_txt + 2 * pad
    wys_ramki = (len(linie) - 1) * INTERLINIA * h + h + 2 * pad

    # prawy-górny róg ramki = (394, 285) (krawędź rzutni)
    px, gy = 394.0, 285.0
    lx = px - szer_ramki
    dy = gy - wys_ramki

    # ustaw MTEXT: lewy-górny róg + padding, kolumna = szer_txt (bez zawijania)
    mt.dxf.char_height = h
    mt.dxf.width = szer_txt + 0.5
    mt.set_location((lx + pad, gy - pad), attachment_point=1)  # TOP_LEFT

    # znajdź i przeskaluj prostokąt ramki (LWPOLYLINE layer 0 obejmujący stary box)
    for e in list(layout.query("LWPOLYLINE")):
        if not e.closed:
            continue
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # stary górny-prawy box: przy prawej-górnej krawędzi
        if max(xs) >= 390 and max(ys) >= 283 and min(ys) >= 260:
            e.set_points([(lx, dy), (px, dy), (px, gy), (lx, gy)], format="xy")
            break


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

    cel = _studnia_terminala_papier(proj, ark, strona)

    # --- DOBÓR POŁOŻENIA ramki: nie może zasłaniać trasy/opisów ani tabelek;
    #     wybieramy pozycję najbliższą „ładnej" domyślnej, z której strzałka
    #     dobrze trafia w skrajną studnię ---
    if kotwica is not None:
        lx, gy = kotwica
    else:
        lx, gy = _dobierz_pozycje_ramki(layout, proj, ark, strona,
                                        szer_ramki, wys_ramki, cel)
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
    # MASKA TŁA — przesłania podkład/obiekty pod ramką (czytelność opisu)
    try:
        mt.set_bg_color("canvas", scale=1.0)
    except Exception:
        mt.dxf.bg_fill = 1
        mt.dxf.box_fill_scale = 1.0
        mt.dxf.bg_fill_color = 0

    # --- strzałka do skrajnej studni ---
    if cel is not None:
        _rysuj_strzalke(layout, (lx, dy, px, gy), cel)


def _trasa_papier(proj: Projekt, ark: Arkusz):
    """
    Punkty CAŁEJ trasy (nie tylko węzłów tego arkusza) w układzie papieru [mm],
    ograniczone do tych widocznych w oknie rzutni. Dzięki temu ramka zakończenia
    omija też sąsiednie odcinki trasy wpadające w okno (zakład).
    """
    PX, PY = _VP_CENTER_PAPER
    VX0, VY0, VX1, VY1 = _VP_OBSZAR
    pts = []
    for s in proj.studnie:
        px = PX + (s.x - ark.center_x)
        py = PY + (s.y - ark.center_y)
        if VX0 - 20 <= px <= VX1 + 20 and VY0 - 20 <= py <= VY1 + 20:
            pts.append((px, py))
    return pts


def _offset_papier(proj: Projekt, ark: Arkusz):
    """
    Punkty POMARAŃCZOWEJ linii „kabel projektowany" (offset trasy o 15 m) w
    układzie papieru [mm] — żeby ramka zakończenia jej też nie zasłaniała.
    """
    PX, PY = _VP_CENTER_PAPER
    VX0, VY0, VX1, VY1 = _VP_OBSZAR
    pkty = [(s.x, s.y) for s in proj.studnie]
    if len(pkty) < 2:
        return []
    off = dxf_model._offset_polilinii(pkty, dxf_model.TRASA_ODSUNIECIE)
    out = []
    for ox, oy in off:
        px = PX + (ox - ark.center_x)
        py = PY + (oy - ark.center_y)
        if VX0 - 20 <= px <= VX1 + 20 and VY0 - 20 <= py <= VY1 + 20:
            out.append((px, py))
    return out


def _opisy_papier(layout, ark: Arkusz):
    """
    Prostokąty (AABB na papierze) obejmujące OPISY model space widoczne w oknie:
    nazwy studni, numery porządkowe, wymiary, cyfry kanałów, etykiety SZ/ZR.
    Każdy obrócony tekst otaczamy prostokątem osiowym (konserwatywnie), aby
    ramka zakończenia go nie zasłoniła.
    """
    import math
    PX, PY = _VP_CENTER_PAPER
    VX0, VY0, VX1, VY1 = _VP_OBSZAR
    try:
        msp = layout.doc.modelspace()
    except Exception:
        return []
    # warstwy opisów + ramki/etykiety zapasów-muf ('obramowanie ramek'),
    # by ramka zakończenia omijała także opisy SZ/ZR (Etap 5)
    warstwy = {"Nazwa studni", "_liczba", "_liczba kanałów", "wymiary",
               "wymiarowanie", "obramowanie ramek"}
    out = []
    for e in msp.query("MTEXT"):
        if e.dxf.layer not in warstwy:
            continue
        txt = (e.text or "").replace("\\P", " ")
        txt = txt.split(";")[-1] if "\\" in txt else txt  # odrzuć kody formatu
        if not txt.strip():
            continue
        h = e.dxf.char_height or 1.6
        w = _szerokosc_linii(txt.strip(), h) / ZAPAS_SZER
        # środek etykiety w papierze
        ins = e.dxf.insert
        cx = PX + (ins[0] - ark.center_x)
        cy = PY + (ins[1] - ark.center_y)
        if not (VX0 - 20 <= cx <= VX1 + 20 and VY0 - 20 <= cy <= VY1 + 20):
            continue
        # obrócony tekst -> AABB obejmujący prostokąt w×h obrócony o rotację
        rot = math.radians(e.dxf.rotation or 0.0)
        hw, hh = w / 2.0, h / 2.0
        ex = abs(hw * math.cos(rot)) + abs(hh * math.sin(rot))
        ey = abs(hw * math.sin(rot)) + abs(hh * math.cos(rot))
        out.append((cx - ex, cy - ey, cx + ex, cy + ey))
    return out


def _koliduje_prost(box, other, margines=1.0) -> bool:
    """Kolizja dwóch prostokątów AABB (x0,y0,x1,y1) z marginesem."""
    ax0, ay0, ax1, ay1 = box
    bx0, by0, bx1, by1 = other
    return not (ax1 + margines <= bx0 or ax0 - margines >= bx1 or
                ay1 + margines <= by0 or ay0 - margines >= by1)


def _odcinek_prostokat(p, q, bok=2.0):
    """Przybliża odcinek p-q siatką małych prostokątów (do testu kolizji)."""
    import math
    (x0, y0), (x1, y1) = p, q
    d = math.hypot(x1 - x0, y1 - y0)
    n = max(1, int(d / bok))
    out = []
    for k in range(n + 1):
        t = k / n
        cx = x0 + (x1 - x0) * t
        cy = y0 + (y1 - y0) * t
        out.append((cx - bok, cy - bok, cx + bok, cy + bok))
    return out


def _dobierz_pozycje_ramki(layout, proj: Projekt, ark: Arkusz, strona: str,
                           szer: float, wys: float, cel) -> tuple[float, float]:
    """
    Dobiera lewy-górny róg ramki zakończenia tak, aby prostokąt ramki:
      - mieścił się na papierze (z marginesem),
      - NIE nachodził na ŻADEN element projektu: trasę, pomarańczową linię
        offsetu, OPISY (nazwy studni, numery, wymiary, zapasy/mufy) ani tabelki,
      - leżał możliwie blisko skrajnej studni (ładny, krótki leader).
    Zwraca (lx, gy). Gdy nic nie pasuje — pozycja najmniej kolidująca.
    """
    VX0, VY0, VX1, VY1 = _VP_OBSZAR
    MARG = 6.0

    # przeszkody: tabelki + odcinki trasy + pomarańczowa linia offsetu + OPISY
    # (ramka zakończenia nie może zasłaniać ŻADNEGO elementu projektowanego)
    przeszkody = list(_ZASLONIETE)
    tp = _trasa_papier(proj, ark)
    for i in range(len(tp)):
        przeszkody.append((tp[i][0] - 2, tp[i][1] - 2, tp[i][0] + 2, tp[i][1] + 2))
        if i + 1 < len(tp):
            przeszkody.extend(_odcinek_prostokat(tp[i], tp[i + 1]))
    op = _offset_papier(proj, ark)
    for i in range(len(op) - 1):
        przeszkody.extend(_odcinek_prostokat(op[i], op[i + 1]))
    # opisy z model space (nazwy studni, numery, wymiary, SZ/ZR) jako przeszkody
    przeszkody.extend(_opisy_papier(layout, ark))

    # punkt docelowy (skrajna studnia) — chcemy ramkę blisko niego, ale nie na trasie
    tx, ty = cel if cel else (_VP_CENTER_PAPER)

    # kandydaci: siatka lewych-górnych rogów po całym obszarze rzutni
    kand = []
    x = VX0 + MARG
    while x + szer <= VX1 - MARG:
        y = VY1 - MARG
        while y - wys >= VY0 + MARG:
            kand.append((x, y))
            y -= 8.0
        x += 10.0

    najlepszy = None
    najlepszy_koszt = None
    for lx, gy in kand:
        box = (lx, gy - wys, lx + szer, gy)
        if any(_koliduje_prost(box, o) for o in przeszkody):
            continue
        # koszt = odległość środka ramki od celu (krótki, czytelny leader)
        cxb = lx + szer / 2.0
        cyb = gy - wys / 2.0
        koszt = (cxb - tx) ** 2 + (cyb - ty) ** 2
        if najlepszy_koszt is None or koszt < najlepszy_koszt:
            najlepszy_koszt, najlepszy = koszt, (lx, gy)

    if najlepszy is not None:
        return najlepszy
    # fallback: domyślny róg (lewy-górny / lewy-dolny), byle na papierze
    return (38.1, 223.9) if strona == "A" else (31.0, 60.3)


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
            # UWAGA: górny-prawy opis kabla ('Proj. ... dł. trasowa ...') na
            # arkuszu ZOSTAJE — jest potrzebny (uzupełniany w _podmien_pole_tabelki).
            # Jego duplikaty poza papierem skasowano już wcześniej (_poza_papierem).
    for e in do_usuniecia:
        try:
            layout.delete_entity(e)
        except Exception:
            pass


def _dolacz_podklad(doc, msp, proj, sciezka_wyjscia: str) -> None:
    """
    Generuje georeferowany podkład OSM (grayscale JPG obok DXF) i wstawia go
    jako IMAGE pod trasą. Przy braku sieci/biblioteki — pomija bez błędu.
    Nazwa JPG = <nazwa_dxf bez rozszerzenia>_podklad.jpg.
    """
    import os
    try:
        from . import podklad as _podklad_mod
    except Exception:
        return
    baza = os.path.splitext(sciezka_wyjscia)[0]
    sciezka_jpg = f"{baza}_podklad.jpg"
    try:
        osadzenie = _podklad_mod.generuj_podklad_jpg(proj, sciezka_jpg)
    except Exception:
        osadzenie = None
    if osadzenie:
        try:
            dxf_model.wstaw_podklad(doc, msp, osadzenie)
        except Exception:
            pass


def generuj_z_szablonu(
    proj: Projekt,
    sciezka_wyjscia: str,
    sciezka_wzorca: str | None = None,
    zaklad_m: float | None = None,
    podklad: bool = True,
) -> tuple[str, int]:
    """
    Generuje DXF używając zab2.dxf jako szablonu arkuszy i tabelki.
    Zwraca (ścieżka, liczba_arkuszy).

    podklad=True -> dołącza georeferowany raster OSM (grayscale JPG) pod trasą.
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

    # 3a) PODKŁAD OSM — wstawiamy NAJPIERW (najniżej), żeby trasa była nad nim
    if podklad:
        _dolacz_podklad(doc, msp, proj, sciezka_wyjscia)

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

        _ustaw_rzutnie(layout, ark, proj)
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
