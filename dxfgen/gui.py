"""
GUI generatora DXF (Etap 4) — PySide6.

Funkcje:
  - wybór plików wejściowych (współrzędne, WT) i miejsca zapisu DXF
    (z auto-wykryciem plików w katalogu),
  - wczytanie projektu i podgląd listy studni,
  - WSKAZYWANIE zapasów (SZ) i muf (ZR) przy wybranych studniach
    (dodawanie/usuwanie, długość zapasu),
  - podgląd metryki (dł. trasowa / montażowa) aktualizowany na żywo,
  - opcja podkładu OSM,
  - generowanie DXF w tle (bez zamrażania okna) z logiem statusu.

UWAGA: importy PySide6 są WEWNĄTRZ funkcji/metod uruchomieniowych, aby ten moduł
dał się zaimportować także bez GUI (np. w testach logiki / na serwerze bez libGL).
"""

from __future__ import annotations

import glob
import os

from .model import Projekt, Zapas, ReserveKind


# --------------------------------------------------------------------------- #
#  Logika niezależna od Qt (testowalna osobno)
# --------------------------------------------------------------------------- #

def auto_wykryj_pliki(katalog: str = ".") -> tuple[str | None, str | None]:
    """Auto-wykrycie plików wejściowych w katalogu (współrzędne, WT)."""
    wszystkie = glob.glob(os.path.join(katalog, "*.xlsx")) + \
        glob.glob(os.path.join(katalog, "*.xls"))
    wspol = wt = None
    for p in wszystkie:
        low = os.path.basename(p).lower()
        if any(k in low for k in ("wspol", "współ", "wspó", "coord", "xy")):
            wspol = wspol or p
        elif low.startswith("wt") or "warunk" in low:
            wt = wt or p
    if (wspol is None or wt is None) and len(wszystkie) == 2:
        a, b = wszystkie
        if a.lower().endswith(".xlsx"):
            wspol, wt = wspol or a, wt or b
        else:
            wspol, wt = wspol or b, wt or a
    return wspol, wt


def dodaj_zapas(proj: Projekt, nazwa_studni: str, dlugosc: float) -> None:
    """Dodaje zapas (SZ) przy studni i przelicza numery."""
    proj.zapasy.append(
        Zapas(kind=ReserveKind.ZAPAS, studnia=nazwa_studni, dlugosc=float(dlugosc))
    )
    proj.przelicz_numery_zapasow()


def dodaj_mufe(proj: Projekt, nazwa_studni: str) -> None:
    """Dodaje mufę (ZR) przy studni i przelicza numery."""
    proj.zapasy.append(Zapas(kind=ReserveKind.MUFA, studnia=nazwa_studni))
    proj.przelicz_numery_zapasow()


def usun_element(proj: Projekt, indeks: int) -> None:
    """Usuwa element (zapas/mufa) o danym indeksie z listy i przelicza numery."""
    if 0 <= indeks < len(proj.zapasy):
        proj.zapasy.pop(indeks)
        proj.przelicz_numery_zapasow()


# --------------------------------------------------------------------------- #
#  GUI (PySide6)
# --------------------------------------------------------------------------- #

def uruchom_gui(domyslny_katalog: str = ".") -> int:
    """
    Uruchamia aplikację GUI. Zwraca kod wyjścia Qt.
    Importy PySide6 są tutaj, aby moduł był importowalny bez GUI.
    """
    import sys

    from PySide6 import QtCore, QtGui, QtWidgets

    from .budowa import zbuduj_projekt
    from .generator import generuj_pelny_dxf

    class Watek(QtCore.QThread):
        """Wątek generowania DXF (żeby okno się nie zawieszało)."""
        postep = QtCore.Signal(str)
        skonczone = QtCore.Signal(bool, str)

        def __init__(self, proj, wyjscie, podklad):
            super().__init__()
            self.proj = proj
            self.wyjscie = wyjscie
            self.podklad = podklad

        def run(self):
            try:
                if self.podklad:
                    self.postep.emit("Pobieram podkład OSM i buduję JPG…")
                sciezka, n = generuj_pelny_dxf(
                    self.proj, self.wyjscie, podklad=self.podklad
                )
                self.skonczone.emit(True, f"OK: {sciezka} ({n} ark.)")
            except Exception as e:  # noqa: BLE001
                self.skonczone.emit(False, f"Błąd: {e}")

    class PodgladTrasy(QtWidgets.QWidget):
        """
        Interaktywny podgląd trasy: rysuje studnie i odcinki dopasowane do
        rozmiaru widżetu, zaznacza studnie z zapasami (SZ=kwadrat) i mufami
        (ZR=trójkąt). Kliknięcie studni emituje sygnał `wybrano(indeks)`.
        """
        wybrano = QtCore.Signal(int)

        def __init__(self):
            super().__init__()
            self.proj = None
            self.wybrany = -1
            self._pkty = []     # [(sx, sy, idx)] ekranowe pozycje studni
            self.setMinimumHeight(260)
            self.setToolTip("Kliknij studnię, aby ją zaznaczyć; potem dodaj SZ/ZR.")

        def ustaw_projekt(self, proj):
            self.proj = proj
            self.update()

        def ustaw_wybrany(self, idx):
            self.wybrany = idx
            self.update()

        def _przelicz(self):
            self._pkty = []
            if not self.proj or not self.proj.studnie:
                return None
            xs = [s.x for s in self.proj.studnie]
            ys = [s.y for s in self.proj.studnie]
            minx, maxx = min(xs), max(xs)
            miny, maxy = min(ys), max(ys)
            szer = max(maxx - minx, 1.0)
            wys = max(maxy - miny, 1.0)
            m = 30  # margines px
            W = max(self.width() - 2 * m, 10)
            H = max(self.height() - 2 * m, 10)
            skala = min(W / szer, H / wys)
            # wyśrodkowanie
            ox = m + (W - szer * skala) / 2.0
            oy = m + (H - wys * skala) / 2.0

            def na_ekran(x, y):
                sx = ox + (x - minx) * skala
                sy = self.height() - (oy + (y - miny) * skala)  # odwróć Y
                return sx, sy
            return na_ekran

        def paintEvent(self, event):  # noqa: N802
            from PySide6 import QtGui, QtCore as _C
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)
            p.fillRect(self.rect(), QtGui.QColor("#ffffff"))
            na_ekran = self._przelicz()
            if na_ekran is None:
                p.setPen(QtGui.QColor("#888"))
                p.drawText(self.rect(), _C.Qt.AlignCenter,
                           "Wczytaj projekt, aby zobaczyć podgląd trasy")
                p.end()
                return
            s = self.proj.studnie
            # odcinki trasy (czarne)
            p.setPen(QtGui.QPen(QtGui.QColor("#111111"), 2))
            for i in range(len(s) - 1):
                x1, y1 = na_ekran(s[i].x, s[i].y)
                x2, y2 = na_ekran(s[i + 1].x, s[i + 1].y)
                p.drawLine(int(x1), int(y1), int(x2), int(y2))
            # studnie + markery zapasów/muf
            poz = {z.studnia for z in self.proj.zapasy}
            sz_set = {z.studnia for z in self.proj.zapasy
                      if z.kind == ReserveKind.ZAPAS}
            zr_set = {z.studnia for z in self.proj.zapasy
                      if z.kind == ReserveKind.MUFA}
            self._pkty = []
            for i, st in enumerate(s):
                sx, sy = na_ekran(st.x, st.y)
                self._pkty.append((sx, sy, i))
                zazn = (i == self.wybrany)
                # węzeł
                p.setPen(QtGui.QPen(QtGui.QColor("#111"), 1))
                p.setBrush(QtGui.QColor("#1565c0") if zazn else QtGui.QColor("#333"))
                r = 6 if zazn else 4
                p.drawEllipse(int(sx - r), int(sy - r), 2 * r, 2 * r)
                # marker SZ (pomarańczowy kwadrat) / ZR (pomarańczowy trójkąt)
                orange = QtGui.QColor("#ff7f0e")
                p.setBrush(orange)
                p.setPen(QtGui.QPen(orange, 1))
                if st.nazwa in sz_set:
                    p.drawRect(int(sx + 6), int(sy - 16), 10, 10)
                if st.nazwa in zr_set:
                    tri = QtGui.QPolygon([
                        _C.QPoint(int(sx + 6), int(sy + 6)),
                        _C.QPoint(int(sx + 18), int(sy + 6)),
                        _C.QPoint(int(sx + 12), int(sy - 4)),
                    ])
                    p.drawPolygon(tri)
                # numer studni przy zaznaczonej
                if zazn:
                    p.setPen(QtGui.QColor("#1565c0"))
                    p.drawText(int(sx + 8), int(sy + 18), f"{st.nr}. {st.nazwa}")
            p.end()

        def mousePressEvent(self, event):  # noqa: N802
            if not self._pkty:
                return
            mx, my = event.position().x(), event.position().y()
            najbl, dmin = -1, 1e9
            for sx, sy, idx in self._pkty:
                d = (sx - mx) ** 2 + (sy - my) ** 2
                if d < dmin:
                    dmin, najbl = d, idx
            if najbl >= 0 and dmin <= 20 ** 2:  # tolerancja kliknięcia
                self.wybrany = najbl
                self.update()
                self.wybrano.emit(najbl)

    class Okno(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Generator DXF tras — Orange Polska")
            self.resize(1000, 820)
            self.proj: Projekt | None = None
            self.watek: Watek | None = None

            centrala = QtWidgets.QWidget()
            self.setCentralWidget(centrala)
            root = QtWidgets.QVBoxLayout(centrala)

            # --- sekcja plików ---
            gb_pliki = QtWidgets.QGroupBox("1. Pliki wejściowe")
            fp = QtWidgets.QGridLayout(gb_pliki)
            awsp, awt = auto_wykryj_pliki(domyslny_katalog)
            self.e_wspol = QtWidgets.QLineEdit(awsp or "")
            self.e_wt = QtWidgets.QLineEdit(awt or "")
            self.e_out = QtWidgets.QLineEdit(
                os.path.join(domyslny_katalog, "wynik.dxf")
            )
            fp.addWidget(QtWidgets.QLabel("Współrzędne (.xlsx):"), 0, 0)
            fp.addWidget(self.e_wspol, 0, 1)
            fp.addWidget(self._btn("…", self._wybierz_wspol), 0, 2)
            fp.addWidget(QtWidgets.QLabel("Warunki Techniczne (.xls):"), 1, 0)
            fp.addWidget(self.e_wt, 1, 1)
            fp.addWidget(self._btn("…", self._wybierz_wt), 1, 2)
            fp.addWidget(QtWidgets.QLabel("Zapisz DXF jako:"), 2, 0)
            fp.addWidget(self.e_out, 2, 1)
            fp.addWidget(self._btn("…", self._wybierz_out), 2, 2)
            btn_wczytaj = QtWidgets.QPushButton("Wczytaj projekt")
            btn_wczytaj.clicked.connect(self._wczytaj)
            fp.addWidget(btn_wczytaj, 3, 1)
            root.addWidget(gb_pliki)

            # --- sekcja studni + zapasy/mufy ---
            gb = QtWidgets.QGroupBox("2. Studnie oraz zapasy (SZ) / mufy (ZR)")
            h = QtWidgets.QHBoxLayout(gb)

            # lista studni
            lewa = QtWidgets.QVBoxLayout()
            lewa.addWidget(QtWidgets.QLabel("Studnie (zaznacz, aby dodać SZ/ZR):"))
            self.lista_studni = QtWidgets.QListWidget()
            lewa.addWidget(self.lista_studni)
            sterowanie = QtWidgets.QHBoxLayout()
            self.sb_dl = QtWidgets.QDoubleSpinBox()
            self.sb_dl.setRange(0.0, 999.0)
            self.sb_dl.setValue(15.0)
            self.sb_dl.setSuffix(" m")
            self.sb_dl.setDecimals(1)
            b_sz = QtWidgets.QPushButton("+ Zapas (SZ)")
            b_sz.clicked.connect(self._dodaj_zapas)
            b_zr = QtWidgets.QPushButton("+ Mufa (ZR)")
            b_zr.clicked.connect(self._dodaj_mufe)
            sterowanie.addWidget(QtWidgets.QLabel("dł. zapasu:"))
            sterowanie.addWidget(self.sb_dl)
            sterowanie.addWidget(b_sz)
            sterowanie.addWidget(b_zr)
            lewa.addLayout(sterowanie)
            h.addLayout(lewa, 2)

            # lista dodanych elementów
            prawa = QtWidgets.QVBoxLayout()
            prawa.addWidget(QtWidgets.QLabel("Dodane elementy:"))
            self.lista_elem = QtWidgets.QListWidget()
            prawa.addWidget(self.lista_elem)
            b_usun = QtWidgets.QPushButton("Usuń zaznaczony")
            b_usun.clicked.connect(self._usun_elem)
            prawa.addWidget(b_usun)
            h.addLayout(prawa, 2)
            root.addWidget(gb)

            # synchronizacja: lista studni <-> podgląd
            self.lista_studni.currentRowChanged.connect(self._studnia_zmieniona)

            # --- PODGLĄD TRASY (klikalny: wskazywanie studni do SZ/ZR) ---
            gb_pod = QtWidgets.QGroupBox(
                "Podgląd trasy — kliknij studnię, potem dodaj SZ/ZR powyżej"
            )
            vp = QtWidgets.QVBoxLayout(gb_pod)
            self.podglad = PodgladTrasy()
            self.podglad.wybrano.connect(self._podglad_klik)
            vp.addWidget(self.podglad)
            root.addWidget(gb_pod, 1)

            # --- metryka + opcje ---
            gb3 = QtWidgets.QGroupBox("3. Metryka i opcje")
            g3 = QtWidgets.QGridLayout(gb3)
            self.lbl_metryka = QtWidgets.QLabel("—")
            g3.addWidget(self.lbl_metryka, 0, 0, 1, 2)
            self.cb_podklad = QtWidgets.QCheckBox(
                "Dołącz podkład OSM (wymaga internetu)"
            )
            self.cb_podklad.setChecked(True)
            g3.addWidget(self.cb_podklad, 1, 0, 1, 2)
            root.addWidget(gb3)

            # --- generowanie + log ---
            dol = QtWidgets.QHBoxLayout()
            self.btn_generuj = QtWidgets.QPushButton("Generuj DXF")
            self.btn_generuj.clicked.connect(self._generuj)
            self.btn_generuj.setEnabled(False)
            dol.addStretch(1)
            dol.addWidget(self.btn_generuj)
            root.addLayout(dol)
            self.log = QtWidgets.QPlainTextEdit()
            self.log.setReadOnly(True)
            self.log.setMaximumBlockCount(500)
            self.log.setFixedHeight(120)
            root.addWidget(self.log)

        # --- pomocnicze ---
        def _btn(self, txt, cb):
            b = QtWidgets.QPushButton(txt)
            b.setFixedWidth(36)
            b.clicked.connect(cb)
            return b

        def _wpis(self, s):
            self.log.appendPlainText(s)

        def _wybierz_wspol(self):
            p, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Plik współrzędnych", self.e_wspol.text() or ".",
                "Excel (*.xlsx *.xls);;Wszystkie (*.*)")
            if p:
                self.e_wspol.setText(p)

        def _wybierz_wt(self):
            p, _ = QtWidgets.QFileDialog.getOpenFileName(
                self, "Plik WT", self.e_wt.text() or ".",
                "Excel (*.xls *.xlsx);;Wszystkie (*.*)")
            if p:
                self.e_wt.setText(p)

        def _wybierz_out(self):
            p, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Zapisz DXF jako", self.e_out.text() or "wynik.dxf",
                "DXF (*.dxf)")
            if p:
                self.e_out.setText(p)

        def _wczytaj(self):
            wsp, wt = self.e_wspol.text(), self.e_wt.text()
            if not os.path.exists(wsp) or not os.path.exists(wt):
                self._wpis("[BŁĄD] Wskaż istniejące pliki współrzędnych i WT.")
                return
            try:
                self.proj = zbuduj_projekt(wsp, wt)
            except Exception as e:  # noqa: BLE001
                self._wpis(f"[BŁĄD] Wczytywanie: {e}")
                return
            self.lista_studni.clear()
            for s in self.proj.studnie:
                self.lista_studni.addItem(f"{s.nr}. {s.nazwa}")
            self.podglad.ustaw_projekt(self.proj)
            if self.proj.studnie:
                self.lista_studni.setCurrentRow(0)
            self._odswiez_elementy()
            self._odswiez_metryke()
            self.btn_generuj.setEnabled(True)
            self._wpis(
                f"Wczytano: {len(self.proj.studnie)} studni, "
                f"{len(self.proj.odcinki)} odcinków (WT), "
                f"strefa EPSG:{self.proj.epsg_2000}."
            )

        def _wybrana_studnia(self):
            r = self.lista_studni.currentRow()
            if self.proj and 0 <= r < len(self.proj.studnie):
                return self.proj.studnie[r].nazwa
            return None

        def _dodaj_zapas(self):
            n = self._wybrana_studnia()
            if not n:
                return
            dodaj_zapas(self.proj, n, self.sb_dl.value())
            self._odswiez_elementy()
            self._odswiez_metryke()

        def _dodaj_mufe(self):
            n = self._wybrana_studnia()
            if not n:
                return
            dodaj_mufe(self.proj, n)
            self._odswiez_elementy()
            self._odswiez_metryke()

        def _usun_elem(self):
            r = self.lista_elem.currentRow()
            if self.proj and r >= 0:
                usun_element(self.proj, r)
                self._odswiez_elementy()
                self._odswiez_metryke()

        def _studnia_zmieniona(self, row):
            # synchronizuj podgląd po wyborze na liście
            if hasattr(self, "podglad"):
                self.podglad.ustaw_wybrany(row)

        def _podglad_klik(self, idx):
            # klik na podglądzie -> ustaw wiersz na liście (bez pętli sygnałów)
            if 0 <= idx < self.lista_studni.count():
                self.lista_studni.setCurrentRow(idx)

        def _odswiez_elementy(self):
            self.lista_elem.clear()
            if not self.proj:
                return
            for z in self.proj.zapasy:
                if z.kind == ReserveKind.ZAPAS:
                    self.lista_elem.addItem(
                        f"{z.etykieta}  @ {z.studnia}  ({z.dlugosc:.1f} m)")
                else:
                    self.lista_elem.addItem(f"{z.etykieta}  @ {z.studnia}  (mufa)")
            if hasattr(self, "podglad"):
                self.podglad.update()  # odśwież markery SZ/ZR na podglądzie

        def _odswiez_metryke(self):
            if not self.proj:
                self.lbl_metryka.setText("—")
                return
            t = self.proj.dlugosc_trasowa()
            m = self.proj.dlugosc_montazowa()
            sz = sum(1 for z in self.proj.zapasy if z.kind == ReserveKind.ZAPAS)
            zr = sum(1 for z in self.proj.zapasy if z.kind == ReserveKind.MUFA)
            self.lbl_metryka.setText(
                f"Dł. trasowa: {t:.1f} m    Dł. montażowa: {m:.1f} m    "
                f"Zapasy (SZ): {sz}    Mufy (ZR): {zr}"
            )

        def _generuj(self):
            if not self.proj:
                return
            out = self.e_out.text() or "wynik.dxf"
            self.btn_generuj.setEnabled(False)
            self._wpis(f"Generuję: {out} …")
            self.watek = Watek(self.proj, out, self.cb_podklad.isChecked())
            self.watek.postep.connect(self._wpis)
            self.watek.skonczone.connect(self._po_generowaniu)
            self.watek.start()

        def _po_generowaniu(self, ok, msg):
            self._wpis(msg)
            self.btn_generuj.setEnabled(True)
            if ok:
                QtWidgets.QMessageBox.information(self, "Gotowe", msg)
            else:
                QtWidgets.QMessageBox.critical(self, "Błąd", msg)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    okno = Okno()
    uruchom_gui._okno = okno  # referencja pomocnicza (np. do testów headless)
    okno.show()
    return app.exec()
