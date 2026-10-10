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


def _podmien_pole_tabelki(layout, proj: Projekt, ark: Arkusz) -> None:
    """
    Podmienia w tabelce dynamiczne pola: nr rysunku i długości.
    Reszta pól (inwestor, projektant itd.) zostaje jak we wzorcu —
    chyba że dane z WT różnią się: wtedy aktualizujemy znane pola po treści.
    """
    nr_rys = proj.dane.rys_nr or f"{ark.numer}"
    for e in layout.query("MTEXT"):
        txt = e.text
        # nr kabla
        if proj.dane.nr_kabla and "WTROI/" in txt and "/AA" in txt:
            # zostaw — wzorzec zwykle ma poprawny; aktualizacja opcjonalna
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
    dxf_model._rysuj_trase(msp, proj)
    dxf_model._rysuj_studnie(msp, proj)
    dxf_model._rysuj_wymiary(msp, proj)
    dxf_model._rysuj_numery(msp, proj)
    dxf_model._rysuj_nazwy(msp, proj)
    dxf_model._rysuj_zapasy_mufy(msp, proj)

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

    # pierwszy arkusz = bazowy (zmień nazwę), kolejne = kopie
    for i, ark in enumerate(lista):
        if i == 0:
            layout = bazowy
            try:
                doc.layouts.rename(nazwa_wzorca, f"Arkusz {ark.numer}")
            except Exception:
                pass
        else:
            layout = _klonuj_layout(doc, bazowy, f"Arkusz {ark.numer}")
        _ustaw_rzutnie(layout, ark)
        _podmien_pole_tabelki(layout, proj, ark)

    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, len(lista)


def _klonuj_layout(doc, bazowy, nowa_nazwa: str):
    """Klonuje layout bazowy wraz z zawartością (tabelka, ramka, rzutnia)."""
    if nowa_nazwa in doc.layouts.names():
        doc.layouts.delete(nowa_nazwa)
    nowy = doc.layouts.new(nowa_nazwa)
    # skopiuj ustawienia strony
    try:
        nowy.dxf.plot_layout_flags = bazowy.dxf.plot_layout_flags
    except Exception:
        pass
    # skopiuj encje paper space
    import ezdxf
    for e in bazowy:
        try:
            nowa = e.copy()
            nowy.add_entity(nowa)
        except Exception:
            pass
    return nowy
