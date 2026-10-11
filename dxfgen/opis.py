"""
Generator OPISU TECHNICZNEGO (Projekt Wykonawczy) w formacie .docx — Etap 6.

STRATEGIA: aby styl był DOKŁADNIE taki sam jak we wzorcu, NIE budujemy dokumentu
od zera — otwieramy wzorzec `OT 339.docx` i podmieniamy w nim tylko DANE
(zachowując wszystkie style, czcionki, sekcje, marginesy i treść stałą).

Dane pochodzą z:
  - WT (`wt.xls` -> DaneProjektu / Odcinki): nr warunków, operator/inwestor,
    adresy zakończeń (lokalizacja/temat), typ i średnica kabla, długość trasowa,
  - RYSUNKU / PROJEKTU (`Projekt`): numery porządkowe studni z zapasami (SZ),
    mufami (ZR) i zakończeniami (wyjście HDPE), liczba muf i stelaży zapasu,
    długość montażowa.

Podmiana działa na poziomie AKAPITU (cały tekst akapitu wpisywany jest w jego
pierwszy run, pozostałe runy czyszczone) — dzięki temu zachowujemy styl akapitu
i czcionkę pierwszego runu, a jednocześnie łapiemy wartości rozbite przez Worda
na wiele runów (np. „WTROI/...339/AA").
"""

from __future__ import annotations

import os

from .model import Projekt, ReserveKind

try:
    from docx import Document
    _DOCX = True
except Exception:  # pragma: no cover
    _DOCX = False

# nazwa wzorca opisu w katalogu z danymi
SZABLON_OPISU = "OT 339.docx"

# --- WARTOŚCI WZORCOWE w OT 339.docx (do podmiany na dane bieżącego projektu) ---
_W = {
    "nr_warunkow": "WTROI/121850000000339/AA",
    "miasto": "Ząbki",
    "relacja": "05-091 Ząbki, ul. Górnośląska 42 - 05-091 Ząbki, ul. 3 Maja 4",
    "operator": "Wawtel sp. z o. o.",
    "adres_ulica": "Szachowa 1",
    "adres_kodmiasto": "04-894 WARSZAWA",
    "adres_miasto_odm": "Warszawie",
    "typ_kabla": "Z-XOTksd",
    "srednica": "7",
    "dl_trasowa": "1153,4",
    "dl_montazowa": "1290",
    "nr_archiwalny": "MM/PW/04/2022",
    "data_opisu": "Warszawa, lipiec 2022 r.",
    "miesiac_rozp": "wrzesień 2022",
    "nry_mufa_zapas": "1, 22, 40",
    "nry_hdpe": "1",
    "liczba_muf": "3",
    "liczba_zapasow": "3",
    "projektant": "Wiktor Ostasiewicz",
    "nr_uprawnien": "1246/98/U",
}


# --------------------------------------------------------------------------- #
#  Dane z WT + RYSUNKU
# --------------------------------------------------------------------------- #

def _numery_z_elementami(proj: Projekt, kind=None) -> list[int]:
    nazwa_do_nr = {s.nazwa: s.nr for s in proj.studnie}
    nry = set()
    for z in proj.zapasy:
        if kind is not None and z.kind != kind:
            continue
        nr = nazwa_do_nr.get(z.studnia)
        if nr:
            nry.add(nr)
    return sorted(nry)


def _numer_studni(proj: Projekt, nazwa: str) -> int | None:
    for s in proj.studnie:
        if s.nazwa == nazwa:
            return s.nr
    return None


def _lista_pl(nry: list[int]) -> str:
    return ", ".join(str(n) for n in nry)


def _fmt(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _fmt_mont(v: float) -> str:
    return str(int(round(v)))


def zbierz_dane_opisu(proj: Projekt) -> dict:
    """Buduje słownik wartości BIEŻĄCYCH (powiązanie WT + rysunek)."""
    d = proj.dane
    adr_a = d.zakonczenie_a_adres or ""
    adr_b = d.zakonczenie_b_adres or ""
    relacja = f"{adr_a} - {adr_b}".strip(" -")

    nry_muf = _numery_z_elementami(proj, ReserveKind.MUFA)
    nry_zap = _numery_z_elementami(proj, ReserveKind.ZAPAS)
    nry_mz = sorted(set(nry_muf) | set(nry_zap))

    nr_a = _numer_studni(proj, d.zakonczenie_a_studnia)
    nr_b = _numer_studni(proj, d.zakonczenie_b_studnia)
    hdpe = []
    for nr, opis in ((nr_a, d.zakonczenie_a_opis), (nr_b, d.zakonczenie_b_opis)):
        if nr and opis and "hdpe" in opis.lower():
            hdpe.append(nr)

    return {
        "nr_warunkow": d.nr_kabla or _W["nr_warunkow"],
        "miasto": d.miasto or _W["miasto"],
        "relacja": relacja or _W["relacja"],
        "operator": d.operator or _W["operator"],
        "adres_ulica": _czesc_adresu(d.adres_operatora, "ulica") or _W["adres_ulica"],
        "adres_kodmiasto": _czesc_adresu(d.adres_operatora, "kod") or _W["adres_kodmiasto"],
        "adres_miasto_odm": _W["adres_miasto_odm"],
        "typ_kabla": d.typ_kabla or _W["typ_kabla"],
        "srednica": d.srednica_kabla or _W["srednica"],
        "dl_trasowa": _fmt(proj.dlugosc_trasowa()),
        "dl_montazowa": _fmt_mont(proj.dlugosc_montazowa()),
        "nr_archiwalny": d.nr_archiwalny or _W["nr_archiwalny"],
        "data_opisu": d.data_opisu or _W["data_opisu"],
        "miesiac_rozp": d.miesiac_rozpoczecia or _W["miesiac_rozp"],
        "nry_mufa_zapas": _lista_pl(nry_mz) if nry_mz else _W["nry_mufa_zapas"],
        "nry_hdpe": _lista_pl(hdpe) if hdpe else _W["nry_hdpe"],
        "liczba_muf": str(sum(1 for z in proj.zapasy if z.kind == ReserveKind.MUFA)
                          or _W["liczba_muf"]),
        "liczba_zapasow": str(sum(1 for z in proj.zapasy if z.kind == ReserveKind.ZAPAS)
                              or _W["liczba_zapasow"]),
        "projektant": d.projektant or _W["projektant"],
        "nr_uprawnien": d.nr_uprawnien or _W["nr_uprawnien"],
    }


def _czesc_adresu(adres: str, co: str) -> str:
    """Rozbija 'ul. Szachowa 1, 04-894 Warszawa' na ulicę / kod+miasto."""
    if not adres:
        return ""
    czesci = [c.strip() for c in adres.split(",")]
    if co == "ulica":
        s = czesci[0] if czesci else ""
        return s[3:].strip() if s.lower().startswith("ul.") else s
    if co == "kod":
        return czesci[1].upper() if len(czesci) > 1 else ""
    return ""


# --------------------------------------------------------------------------- #
#  Podmiana w szablonie (zachowanie stylu 1:1)
# --------------------------------------------------------------------------- #

def _ustaw_tekst_akapitu(par, nowy_tekst: str) -> None:
    """
    Wpisuje `nowy_tekst` do akapitu, zachowując jego styl i czcionkę pierwszego
    runu. Pozostałe runy są czyszczone (ale nie usuwane — kolejność/anchory ok).
    """
    runs = par.runs
    if not runs:
        par.add_run(nowy_tekst)
        return
    runs[0].text = nowy_tekst
    for r in runs[1:]:
        r.text = ""


def _podmien(par_text: str, w: dict, b: dict) -> str | None:
    """
    Zwraca nowy tekst akapitu, jeśli zawiera którąś wartość wzorcową; inaczej
    None (akapit pozostaje bez zmian). Podmienia WSZYSTKIE wystąpienia wartości
    wzorcowych na bieżące (najdłuższe najpierw, by uniknąć kolizji podciągów).
    """
    pary = [
        (w["nr_warunkow"], b["nr_warunkow"]),
        (w["relacja"], b["relacja"]),
        (w["nr_archiwalny"], b["nr_archiwalny"]),
        (w["data_opisu"], b["data_opisu"]),
        # typ kabla w kilku wariantach zapisu
        (w["typ_kabla"], b["typ_kabla"]),
        # liczby/długości
        (f"{w['dl_trasowa']}", b["dl_trasowa"]),
        (f"{w['dl_montazowa']}m", f"{b['dl_montazowa']}m"),
        (f"{w['dl_montazowa']} m", f"{b['dl_montazowa']} m"),
        (f"–{w['dl_montazowa']} ", f"–{b['dl_montazowa']} "),
        (w["operator"], b["operator"]),
        (w["adres_ulica"], b["adres_ulica"]),
        (w["adres_kodmiasto"], b["adres_kodmiasto"]),
        (w["miasto"], b["miasto"]),
        (w["projektant"], b["projektant"]),
        (w["nr_uprawnien"], b["nr_uprawnien"]),
        (w["miesiac_rozp"], b["miesiac_rozp"]),
        # frazy zależne od rysunku
        (f"studniach nr {w['nry_mufa_zapas']}",
         f"studniach nr {b['nry_mufa_zapas']}"),
        (f"studniach nr {w['nry_hdpe']} projektowane",
         f"studniach nr {b['nry_hdpe']} projektowane"),
        (f"- {w['liczba_muf']} szt", f"- {b['liczba_muf']} szt"),
        (f"-{w['liczba_zapasow']} m", f"-{b['liczba_zapasow']} m"),
    ]
    # najpierw najdłuższe wzorce
    pary.sort(key=lambda p: len(p[0]), reverse=True)
    nowy = par_text
    zmieniono = False
    for stare, nowe in pary:
        if stare and stare != nowe and stare in nowy:
            nowy = nowy.replace(stare, nowe)
            zmieniono = True
    return nowy if zmieniono else None


def _znajdz_szablon(katalog: str) -> str | None:
    for kand in (os.path.join(katalog, SZABLON_OPISU),
                 os.path.join(os.path.dirname(__file__), "..", SZABLON_OPISU),
                 SZABLON_OPISU):
        if os.path.exists(kand):
            return kand
    return None


def generuj_opis_docx(proj: Projekt, sciezka_wyjscia: str,
                      szablon: str | None = None) -> str:
    """
    Tworzy opis techniczny (.docx) o stylu IDENTYCZNYM jak wzorzec OT 339.docx
    (otwiera wzorzec i podmienia tylko dane). Zwraca ścieżkę pliku.
    """
    if not _DOCX:
        raise RuntimeError("Brak python-docx. Zainstaluj: pip install python-docx")

    katalog = os.path.dirname(os.path.abspath(sciezka_wyjscia)) or "."
    wzor = szablon or _znajdz_szablon(katalog) or _znajdz_szablon(".")
    if not wzor:
        raise FileNotFoundError(
            "Nie znaleziono wzorca opisu '" + SZABLON_OPISU
            + "' - umiesc go w katalogu z danymi (obok wt.xls)."
        )

    b = zbierz_dane_opisu(proj)
    doc = Document(wzor)

    # 1) akapity w treści
    for par in doc.paragraphs:
        nowy = _podmien(par.text, _W, b)
        if nowy is not None:
            _ustaw_tekst_akapitu(par, nowy)

    # 2) akapity w komórkach tabel (również nagłówki/stopki używają tabel)
    for tab in doc.tables:
        for row in tab.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    nowy = _podmien(par.text, _W, b)
                    if nowy is not None:
                        _ustaw_tekst_akapitu(par, nowy)

    # 3) nagłówki i stopki sekcji (mogą zawierać nr warunków / dane)
    for sec in doc.sections:
        for cont in (sec.header, sec.footer, sec.first_page_header,
                     sec.first_page_footer):
            try:
                for par in cont.paragraphs:
                    nowy = _podmien(par.text, _W, b)
                    if nowy is not None:
                        _ustaw_tekst_akapitu(par, nowy)
                for tab in cont.tables:
                    for row in tab.rows:
                        for cell in row.cells:
                            for par in cell.paragraphs:
                                nowy = _podmien(par.text, _W, b)
                                if nowy is not None:
                                    _ustaw_tekst_akapitu(par, nowy)
            except Exception:
                pass

    doc.save(sciezka_wyjscia)
    return sciezka_wyjscia
