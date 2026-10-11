"""
Generator OPISU TECHNICZNEGO (Projekt Wykonawczy) w formacie .docx — Etap 6.

Opis powstaje na bazie wzorca `OT 339.docx` i jest wypełniany danymi z:
  - WT (`wt.xls` -> DaneProjektu / Odcinki): nr warunków, operator/inwestor,
    adresy zakończeń (lokalizacja/temat), typ i średnica kabla, długość trasowa,
  - RYSUNKU / PROJEKTU (`Projekt`): numery porządkowe studni z zapasami (SZ),
    mufami (ZR) i zakończeniami (wyjście HDPE / dowiązanie do mufy), liczba muf
    i stelaży zapasu, długość montażowa.

MAPA POWIĄZAŃ (OT 339.docx  <->  źródło danych)
  „Nr warunków: WTROI/..."                 <- d.nr_kabla (WT Formularz 1K)
  „Temat: ... w miejscowości <miasto>"     <- d.miasto (WT)
  „Lokalizacja: <adres A> - <adres B>"     <- d.zakonczenie_a/b_adres (WT 1.1/1.2)
  „INWESTOR: <operator> / <adres>"         <- d.operator, d.adres_operatora (WT)
  „Kabel <typ> - <nr> dł. trasowa X m"     <- d.typ_kabla, d.nr_kabla, proj.dlugosc_trasowa()
  „(długość montażowa Y m)"                <- proj.dlugosc_montazowa()
  „W studniach nr A, B, C ... mufę i ..."  <- numery porządkowe studni z proj.zapasy (RYSUNEK)
  „W studniach nr N wyjście rurą HDPE"     <- studnia zakończenia 'Wyjście rurą HDPE'
  „Mufa - K szt / Stelaż zapasu - M szt"   <- liczność proj.zapasy (RYSUNEK)
  „Projektant: <imię> / <nr uprawnień>"    <- d.projektant, d.nr_uprawnien
  Rys. 1/2/3                               <- stałe (mapa poglądowa / trasa / przywieszki)
"""

from __future__ import annotations

from .model import Projekt, ReserveKind

try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    _DOCX = True
except Exception:  # pragma: no cover - brak python-docx
    _DOCX = False


# --------------------------------------------------------------------------- #
#  Dane wyliczane z RYSUNKU/PROJEKTU (powiązanie opisu z DXF)
# --------------------------------------------------------------------------- #

def _numery_studni_z_elementami(proj: Projekt, kind=None) -> list[int]:
    """
    Numery PORZĄDKOWE studni (jak na rysunku) posiadających element danego
    rodzaju (ReserveKind) lub dowolny element gdy kind=None. Posortowane rosnąco.
    """
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
    """'1, 22, 40' z listy numerów (po polsku, przecinkami)."""
    return ", ".join(str(n) for n in nry)


def zbierz_dane_opisu(proj: Projekt) -> dict:
    """
    Zwraca słownik gotowych pól do wstawienia w opis — łączy WT (DaneProjektu)
    z danymi z rysunku (zapasy/mufy/zakończenia). To jest centralny punkt
    POWIĄZANIA opisu z WT i DXF.
    """
    d = proj.dane
    typ = d.typ_kabla or "Z-XOTKtsd"
    srednica = d.srednica_kabla or "7"
    nrw = d.nr_kabla or ""
    dl_tras = _fmt(proj.dlugosc_trasowa())
    dl_mont = _fmt(proj.dlugosc_montazowa())
    adr_a = d.zakonczenie_a_adres or ""
    adr_b = d.zakonczenie_b_adres or ""

    # z RYSUNKU: numery studni z mufami/zapasami oraz zakończeniami
    nry_muf = _numery_studni_z_elementami(proj, ReserveKind.MUFA)
    nry_zap = _numery_studni_z_elementami(proj, ReserveKind.ZAPAS)
    nry_mufa_lub_zapas = sorted(set(nry_muf) | set(nry_zap))

    n_muf = sum(1 for z in proj.zapasy if z.kind == ReserveKind.MUFA)
    n_zap = sum(1 for z in proj.zapasy if z.kind == ReserveKind.ZAPAS)

    # zakończenia: która studnia ma wyjście HDPE / dowiązanie do mufy
    nr_a = _numer_studni(proj, d.zakonczenie_a_studnia)
    nr_b = _numer_studni(proj, d.zakonczenie_b_studnia)
    wyjscie_hdpe_nry = []
    for strona, nr, opis in (("A", nr_a, d.zakonczenie_a_opis),
                             ("B", nr_b, d.zakonczenie_b_opis)):
        if nr and opis and "hdpe" in opis.lower():
            wyjscie_hdpe_nry.append(nr)

    relacja = f"{adr_a} - {adr_b}".strip(" -")
    return {
        "nr_warunkow": nrw,
        "miasto": d.miasto or "",
        "relacja": relacja,
        "adr_a": adr_a,
        "adr_b": adr_b,
        "operator": d.operator or "",
        "adres_operatora": d.adres_operatora or "",
        "typ_kabla": typ,
        "srednica": srednica,
        "dl_trasowa": dl_tras,
        "dl_montazowa": dl_mont,
        "nry_mufa_zapas": nry_mufa_lub_zapas,
        "nry_hdpe": wyjscie_hdpe_nry,
        "liczba_muf": n_muf,
        "liczba_zapasow": n_zap,
        "projektant": d.projektant or "inż. Tomasz Waśko",
        "nr_uprawnien": d.nr_uprawnien or "PDL/0137/PWOT/16",
        "nr_archiwalny": d.nr_archiwalny or "",
        "data_opisu": d.data_opisu or "",
        "miesiac_rozpoczecia": d.miesiac_rozpoczecia or "",
    }


def _fmt(v: float) -> str:
    return f"{v:.1f}".replace(".", ",")


def _fmt_mont(v: float) -> str:
    """Montażowa często podawana bez miejsc po przecinku (np. '1290 m')."""
    return str(int(round(v)))


# --------------------------------------------------------------------------- #
#  Budowa dokumentu .docx
# --------------------------------------------------------------------------- #

def generuj_opis_docx(proj: Projekt, sciezka_wyjscia: str) -> str:
    """
    Tworzy opis techniczny (.docx) na podstawie danych projektu (WT + rysunek).
    Zwraca ścieżkę zapisanego pliku. Wymaga python-docx.
    """
    if not _DOCX:
        raise RuntimeError(
            "Brak biblioteki python-docx. Zainstaluj: pip install python-docx"
        )
    dd = zbierz_dane_opisu(proj)
    doc = Document()

    def h(txt, lvl=1):
        doc.add_heading(txt, level=lvl)

    def p(txt="", bold=False, center=False):
        par = doc.add_paragraph()
        run = par.add_run(txt)
        run.bold = bold
        if center:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return par

    dl_mont_int = _fmt_mont(proj.dlugosc_montazowa())

    # ===== STRONA TYTUŁOWA =====
    p(f"Nr warunków: {dd['nr_warunkow']}", bold=True)
    p("Numer Egzemplarza:      1")
    p()
    p("Projekt Wykonawczy na Dzierżawę Kanalizacji Kablowej", bold=True, center=True)
    p()
    p(f"Temat:\tTrasa projektowanego kabla światłowodowego w kanalizacji OPL "
      f"Orange Polska S.A. w miejscowości {dd['miasto']}.")
    p(f"Lokalizacja: \t{dd['relacja']}")
    p(f"INWESTOR: \t{dd['operator']}")
    if dd["adres_operatora"]:
        p(dd["adres_operatora"])
    if dd["data_opisu"]:
        p(f"{dd['data_opisu']}")
    if dd["nr_archiwalny"]:
        p(f"Nr archiwalny projektu: {dd['nr_archiwalny']}")

    # ===== SPIS RYSUNKÓW =====
    p()
    p("Rys. nr 1 Mapa poglądowa")
    p(f"Rys. nr 2 Przebieg trasowy kabli światłowodowych {dd['typ_kabla']}")
    p(dd["nr_warunkow"])
    p("Rys. nr 3 Przewieszki informacyjne")

    # ===== 1. DANE OGÓLNE =====
    h("Dane ogólne", 1)
    h("Przedmiot opracowania", 2)
    p("Projekt obejmuje budowę kabla teletechnicznego na odcinku:")
    p(dd["relacja"])
    p(f"Kabel {dd['typ_kabla']} – {dd['nr_warunkow']} o długości trasowej "
      f"{dd['dl_trasowa']} m (długość montażowa {dl_mont_int} m).")
    p(f"Łączna projektowana długość trasowa linii w ww. relacji wyniesie: "
      f"{dd['dl_trasowa']} m.")
    p("Projekt będzie załącznikiem do umowy o dzierżawę kanalizacji kablowej "
      "Orange Polska S.A.")

    h("Inwestor i zleceniodawca", 2)
    p(f"Inwestorem i zleceniodawcą jest firma {dd['operator']} z siedzibą przy "
      f"{dd['adres_operatora']}.")

    h("Adres obiektu", 2)
    p(f"Trasa: {dd['relacja']}")

    h("Podstawa opracowania projektu", 2)
    p("Podstawę opracowania projektu stanowią:")
    for pkt in ("umowa z inwestorem,",
                "dane uzyskane od inwestora,",
                "dane zebrane przez projektanta w terenie,",
                "warunki techniczne wydane przez Orange Polska S.A. na dostęp "
                "do kanalizacji kablowej Orange,",
                "materiały z paszportyzacji Orange Polska S.A."):
        doc.add_paragraph(pkt, style="List Bullet")

    h("Wykonawca robót", 2)
    p("Wykonawcą robót powinna być firma wyspecjalizowana w pracach budowy "
      "linii światłowodowych i posiadająca osoby uprawnione do ich wykonywania.")

    # ===== 2. OPIS TECHNICZNY =====
    h("Opis techniczny", 1)
    h("Stan istniejący", 2)
    p("W chwili obecnej pomiędzy punktami końcowymi znajduje się kanalizacja "
      "Orange Polska S.A. (rys. 2), do dzierżawionej kanalizacji mają zostać "
      "wprowadzone kable światłowodowe wzmocnione, bez rury kanalizacji wtórnej.")

    h("Budowa kabla telekomunikacyjnego w dzierżawionej kanalizacji", 2)
    p(f"W oparciu o wydane przez OPL S.A. warunki techniczne zaprojektowano "
      f"budowę sieci transmisyjnej dla Operatora w kanalizacji teletechnicznej "
      f"będącej własnością OPL S.A. Kable światłowodowe typu {dd['typ_kabla']} "
      f"Ø {dd['srednica']} mm należy wciągnąć bezpośrednio do kanalizacji "
      f"teletechnicznej do częściowo zajętych otworów.")
    p("W studniach wskazanych na rys. 2, zaprojektowano mufę i stelaż wraz "
      "z zapasem kabla.")
    p("Szczegóły dotyczące zajmowanego otworu uzgodnione zostaną między "
      "wykonawcą, a przedstawicielem OPL S.A. po sprawdzeniu przez wykonawcę "
      "drożności poszczególnych przęseł kanalizacji. Na kablu zawiesić "
      "przywieszki identyfikacyjne (rys. 3).")

    h("Wciąganie kabla do kanalizacji", 2)
    p("Wciąganie kabla wykonać metodą ręczną z uwagi na zajętość kanalizacji "
      "kablowej.")

    h("Oznaczenia linii kablowej", 2)
    p("Kabel na całym przebiegu w studniach kablowych oznakować w sposób trwały "
      "za pomocą przywieszek z tworzyw sztucznych z trwałym opisem.")

    # ===== 3. CHARAKTERYSTYKA STANU PROJEKTOWANEGO =====
    h("Charakterystyka stanu projektowanego", 1)
    h("Linia światłowodowa", 2)
    p(f"Linię światłowodową w relacji wybudować kablem typu {dd['typ_kabla']}:")
    p(dd["relacja"])
    p(f"Kabel {dd['typ_kabla']} – {dd['nr_warunkow']} o długości trasowej "
      f"{dd['dl_trasowa']} m (długość montażowa {dl_mont_int} m).")
    p(f"Łączna projektowana długość trasowa linii w ww. relacji wyniesie: "
      f"{dd['dl_trasowa']} m.")
    # --- POWIĄZANIE Z RYSUNKIEM: numery studni z mufą/zapasem ---
    if dd["nry_mufa_zapas"]:
        p(f"W studniach nr {_lista_pl(dd['nry_mufa_zapas'])} jest planowany "
          f"montaż mufy, stelażu zapasu wraz z zapasem kabla.")
    if dd["nry_hdpe"]:
        p(f"W studniach nr {_lista_pl(dd['nry_hdpe'])} projektowane wyjście "
          f"rurą HDPE.")

    h("Harmonogram prac", 2)
    if dd["miesiac_rozpoczecia"]:
        p(f"Planuje się, że rozpoczęcie prac związanych z zaciąganiem kabla do "
          f"kanalizacji Orange Polska S.A. nastąpi w {dd['miesiac_rozpoczecia']}.")
    else:
        p("Rozpoczęcie prac związanych z zaciąganiem kabla do kanalizacji "
          "Orange Polska S.A. nastąpi po uzgodnieniu z OPL S.A.")

    # ===== 4. UWAGI KOŃCOWE =====
    h("Uwagi końcowe", 1)
    p("Po zakończeniu budowy sieci światłowodowej sporządzić dokumentację "
      "powykonawczą linii.")
    p("W czasie wykonywania prac ściśle przestrzegać przepisów bezpieczeństwa "
      "i higieny pracy oraz przepisów przeciwpożarowych.")
    p("Prace prowadzić pod nadzorem pracowników Orange Polska S.A.")

    # ===== 5. OŚWIADCZENIE PROJEKTANTA =====
    h("Oświadczenie projektanta", 1)
    p(f"Oświadczam, że projekt wykonawczy linii światłowodowej na odcinku: "
      f"{dd['relacja']}, został sporządzony zgodnie z obowiązującymi przepisami "
      f"oraz zasadami wiedzy technicznej.")
    p()
    p(f"Projektant: {dd['projektant']}")
    p(f"Nr uprawnień: {dd['nr_uprawnien']}")
    p("……………………………………..")
    p("(podpis projektanta)")

    # ===== 6. ZESTAWIENIE PODSTAWOWYCH MATERIAŁÓW (z rysunku) =====
    h("Zestawienie podstawowych materiałów", 1)
    p(f"Kabel światłowodowy {dd['typ_kabla']} – {dl_mont_int} m "
      f"(długość montażowa kabla w kanalizacji Orange Polska S.A.)")
    p(f"Mufa\t\t\t\t\t\t\t- {dd['liczba_muf']} szt.")
    p(f"Stelaż zapasu\t\t\t\t\t\t- {dd['liczba_zapasow']} szt.")

    # ===== TABELA PROJEKTANTA =====
    doc.add_paragraph()
    tab = doc.add_table(rows=2, cols=4)
    tab.style = "Table Grid"
    nag = ["", "Imię i nazwisko", "Uprawnienia", "Pieczątka i podpis"]
    for i, txt in enumerate(nag):
        tab.cell(0, i).text = txt
    tab.cell(1, 0).text = "Projektant"
    tab.cell(1, 1).text = dd["projektant"]
    tab.cell(1, 2).text = dd["nr_uprawnien"]
    tab.cell(1, 3).text = ""

    doc.save(sciezka_wyjscia)
    return sciezka_wyjscia
