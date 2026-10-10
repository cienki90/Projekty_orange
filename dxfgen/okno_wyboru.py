"""
Proste okno wyboru plików (Tkinter — wbudowany w Pythona, bez instalacji).

Pozwala wskazać:
  - plik współrzędnych (.xlsx/.xls),
  - plik Warunków Technicznych (.xls/.xlsx),
  - plik wyjściowy DXF.

Pola są wstępnie wypełniane auto-wykrytymi plikami z katalogu (jeśli są).
Zwraca krotkę (wspolrzedne, wt, wyjscie) lub None, gdy użytkownik anuluje.
"""

from __future__ import annotations

import os


def wybierz_pliki(
    domyslne_wspol: str | None = None,
    domyslne_wt: str | None = None,
    domyslne_wyjscie: str = "wynik.dxf",
) -> tuple[str, str, str] | None:
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("Generator DXF — wybór plików")
    root.geometry("640x240")
    root.resizable(False, False)

    v_wspol = tk.StringVar(value=domyslne_wspol or "")
    v_wt = tk.StringVar(value=domyslne_wt or "")
    v_out = tk.StringVar(value=domyslne_wyjscie)

    wynik: dict[str, tuple[str, str, str] | None] = {"val": None}

    def _wybierz(var, title, filetypes, save=False):
        if save:
            p = filedialog.asksaveasfilename(
                title=title, defaultextension=".dxf", filetypes=filetypes,
                initialfile=os.path.basename(var.get()) or "wynik.dxf",
            )
        else:
            p = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if p:
            var.get()
            var.set(p)

    def _wiersz(rij, etykieta, var, cmd):
        tk.Label(root, text=etykieta, anchor="w", width=22).grid(
            row=rij, column=0, padx=8, pady=10, sticky="w"
        )
        tk.Entry(root, textvariable=var, width=52).grid(row=rij, column=1, padx=4)
        tk.Button(root, text="Przeglądaj…", command=cmd).grid(row=rij, column=2, padx=8)

    xlsx_ft = [("Arkusze Excel", "*.xlsx *.xls"), ("Wszystkie pliki", "*.*")]
    dxf_ft = [("Pliki DXF", "*.dxf"), ("Wszystkie pliki", "*.*")]

    _wiersz(0, "Plik współrzędnych:", v_wspol,
            lambda: _wybierz(v_wspol, "Wybierz plik współrzędnych", xlsx_ft))
    _wiersz(1, "Plik Warunków Tech. (WT):", v_wt,
            lambda: _wybierz(v_wt, "Wybierz plik WT", xlsx_ft))
    _wiersz(2, "Zapisz DXF jako:", v_out,
            lambda: _wybierz(v_out, "Zapisz DXF jako", dxf_ft, save=True))

    def _ok():
        if not v_wspol.get() or not os.path.exists(v_wspol.get()):
            messagebox.showerror("Błąd", "Wskaż istniejący plik współrzędnych.")
            return
        if not v_wt.get() or not os.path.exists(v_wt.get()):
            messagebox.showerror("Błąd", "Wskaż istniejący plik WT.")
            return
        if not v_out.get():
            messagebox.showerror("Błąd", "Podaj nazwę pliku wyjściowego DXF.")
            return
        wynik["val"] = (v_wspol.get(), v_wt.get(), v_out.get())
        root.destroy()

    def _anuluj():
        wynik["val"] = None
        root.destroy()

    ramka = tk.Frame(root)
    ramka.grid(row=3, column=0, columnspan=3, pady=20)
    tk.Button(ramka, text="Generuj DXF", command=_ok, width=16,
              default="active").pack(side="left", padx=10)
    tk.Button(ramka, text="Anuluj", command=_anuluj, width=12).pack(side="left", padx=10)

    root.bind("<Return>", lambda e: _ok())
    root.bind("<Escape>", lambda e: _anuluj())

    # wyśrodkuj okno
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() - w) // 2
    y = (root.winfo_screenheight() - h) // 3
    root.geometry(f"+{x}+{y}")

    root.mainloop()
    return wynik["val"]
