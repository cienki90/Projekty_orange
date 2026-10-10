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
    Dynamicznie aktualizuje pola tabelki i ramek opisowych danymi z WT.

    Ramki zakończeń:
      - "Zakończenie A" (początek trasy) tylko na PIERWSZYM arkuszu,
      - "Zakończenie B" (koniec trasy) tylko na OSTATNIM arkuszu,
      - na pozostałych arkuszach ramki zakończeń są usuwane.
    Zachowujemy formatowanie MTEXT (kody \\P, \\T, \\px...).
    """
    import re
    d = proj.dane
    nr_rys = d.rys_nr or f"{ark.numer}"
    dl_tras = _fmt_pl(proj.dlugosc_trasowa())
    dl_mont = _fmt_pl(proj.dlugosc_montazowa())

    do_usuniecia = []
    for e in layout.query("MTEXT"):
        txt = e.text

        # === NAJPIERW ramki zakończeń (zawierają adres, więc muszą być
        #     sprawdzane PRZED polem "Temat") ===
        if "Zakończenie A" in txt or "Zakonczenie A" in txt:
            if jest_pierwszy:
                e.text = _zbuduj_zakonczenie(txt, "A", d)
            else:
                do_usuniecia.append(e)
            continue
        if "Zakończenie B" in txt or "Zakonczenie B" in txt:
            if jest_ostatni:
                e.text = _zbuduj_zakonczenie(txt, "B", d)
            else:
                do_usuniecia.append(e)
            continue

        # --- ramka opisowa: Proj. kabel ... + długości ---
        if "Proj." in txt and ("kabel" in txt or "XOTK" in txt.upper()):
            e.text = _zbuduj_ramke_kabel(txt, d, dl_tras, dl_mont)
            continue

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

    # usuń ramki zakończeń nienależące do tego arkusza
    for e in do_usuniecia:
        try:
            layout.delete_entity(e)
        except Exception:
            pass


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


def _zbuduj_ramke_kabel(oryg: str, d, dl_tras: str, dl_mont: str) -> str:
    """
    Buduje treść ramki:
      Proj. kabel <typ> - <nr kabla>
      dł. trasowa w kanalizacji Orange Polska S.A.: <X> m
      dł. montażowa w kanalizacji Orange Polska S.A.: <Y> m
    Zachowuje prefiks akapitu (\\pxi...) jeśli był.
    """
    pref = ""
    if oryg.startswith("\\px"):
        pref = oryg[: oryg.find(";") + 1]
    typ = d.typ_kabla or "Z-XOTKtsd"
    nrk = d.nr_kabla or ""
    srednica = f" Ø {d.srednica_kabla} mm" if d.srednica_kabla else ""
    return (
        f"{pref}{{\\T0.95;Proj.\\Ikabel {typ}{srednica} - {nrk}"
        f"\\P\\pi0,l0;dł. trasowa w kanalizacji Orange Polska S.A.: {dl_tras} m"
        f"\\Pdł. montażowa w kanalizacji Orange Polska S.A.: {dl_mont} m}}"
    )


def _zbuduj_zakonczenie(oryg: str, strona: str, d) -> str:
    pref = ""
    if oryg.startswith("\\px"):
        pref = oryg[: oryg.find(";") + 1]
    if strona == "A":
        adres = d.zakonczenie_a_adres
        studnia = d.zakonczenie_a_studnia
        opis = d.zakonczenie_a_opis or "Wyjście rurą HDPE"
    else:
        adres = d.zakonczenie_b_adres
        studnia = d.zakonczenie_b_studnia
        opis = d.zakonczenie_b_opis or "Dowiązanie do projektowanej mufy"
    typ = d.typ_kabla or "Z-XOTKtsd"
    srednica = f" %%C {d.srednica_kabla} mm" if d.srednica_kabla else ""
    return (
        f"{pref}Zakończenie {strona}:\\P{adres}\\P\\pq*;Studnia OPL S.A.: {studnia}"
        f"\\P\\pql;{{\\C30;Proj. kabel {typ}{srednica}\\P{opis}}}"
    )


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

    # zapamiętaj parametry wzorcowej ramki "Zakończenie B" (dane, nie encję —
    # encja zostałaby osierocona po usunięciu swojego layoutu)
    szablon_zak_b = _parametry_wzorcowej_ramki_b(doc)

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

        # na ostatnim arkuszu dołóż ramkę "Zakończenie B", jeśli jej brak w szablonie
        if jest_ostatni and szablon_zak_b is not None:
            ma_b = any("Zakończenie B" in e.text for e in layout.query("MTEXT"))
            if not ma_b:
                mt = layout.add_mtext(
                    szablon_zak_b["text"],
                    dxfattribs={"layer": szablon_zak_b["layer"],
                                "style": szablon_zak_b.get("style", "Standard")},
                )
                mt.dxf.char_height = szablon_zak_b["h"]
                mt.set_location(szablon_zak_b["insert"],
                                attachment_point=szablon_zak_b["attach"])

        _ustaw_rzutnie(layout, ark)
        _podmien_pole_tabelki(layout, proj, ark, jest_pierwszy, jest_ostatni)

    doc.saveas(sciezka_wyjscia)
    return sciezka_wyjscia, len(lista)


def _parametry_wzorcowej_ramki_b(doc):
    """
    Zwraca parametry (dane) wzorcowej ramki 'Zakończenie B' — treść, pozycję,
    wysokość, warstwę, styl. Dane, bo sama encja zostanie usunięta z layoutem.
    """
    for n in doc.layouts.names():
        if n == "Model":
            continue
        for e in doc.layouts.get(n).query("MTEXT"):
            if "Zakończenie B" in e.text:
                return {
                    "text": e.text,
                    "insert": (e.dxf.insert.x, e.dxf.insert.y),
                    "h": e.dxf.char_height,
                    "layer": e.dxf.layer,
                    "style": getattr(e.dxf, "style", "Standard"),
                    "attach": getattr(e.dxf, "attachment_point", 1),
                }
    return None


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
