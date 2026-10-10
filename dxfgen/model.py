"""
Model danych projektu trasy światłowodowej.

Wszystkie współrzędne studni przechowujemy w dwóch układach:
  - lat/lon  (WGS84, EPSG:4326) — tak jak w pliku współrzędne.xlsx
  - x/y      (PL-2000, EPSG:217x) — układ docelowy rysunku DXF
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReserveKind(str, Enum):
    """Rodzaj elementu rysowanego na pomarańczowej kresce przy studni."""
    ZAPAS = "zapas"   # SZ-x  (prostokąt + długość w kółku)
    MUFA = "mufa"     # ZR-x  (trójkąt, tylko symbol)


@dataclass
class Studnia:
    """Pojedyncza studnia / punkt węzłowy trasy."""
    nr: int                       # numer porządkowy wyświetlany na rysunku (od 1)
    nazwa: str                    # np. "SM-ZA-B23"
    lat: float                    # WGS84 szerokość
    lon: float                    # WGS84 długość
    x: float = 0.0                # PL-2000 (po transformacji) — Easting
    y: float = 0.0                # PL-2000 (po transformacji) — Northing

    def __repr__(self) -> str:
        return f"Studnia(nr={self.nr}, nazwa={self.nazwa!r}, x={self.x:.3f}, y={self.y:.3f})"


@dataclass
class Odcinek:
    """Odcinek trasy między dwiema studniami (dane z Zał 3 wt.xls)."""
    lp: int
    studnia_a: str                # oznaczenie studni początkowej
    studnia_b: str                # oznaczenie studni końcowej
    dlugosc_wt: float             # długość [m] WPROST z WT (nie z geometrii!)
    adres_a: str = ""
    adres_b: str = ""

    def __repr__(self) -> str:
        return f"Odcinek({self.lp}: {self.studnia_a}->{self.studnia_b}, {self.dlugosc_wt} m)"


@dataclass
class Zapas:
    """
    Zapas kabla lub mufa umieszczone PRZY studni.
    Rysowane na pomarańczowej kresce odsuniętej od trasy.
    """
    kind: ReserveKind
    studnia: str                  # oznaczenie studni, przy której się znajduje
    dlugosc: float = 0.0          # [m] — istotne tylko dla ReserveKind.ZAPAS
    numer: int = 0                # SZ-numer lub ZR-numer (nadawany automatycznie)

    @property
    def etykieta(self) -> str:
        prefix = "SZ" if self.kind == ReserveKind.ZAPAS else "ZR"
        return f"{prefix}-{self.numer}"


@dataclass
class DaneProjektu:
    """Metadane do tabelki rysunkowej (Formularz 1K z wt.xls)."""
    nr_kabla: str = ""            # np. WTROI/121850000000339/AA
    operator: str = ""            # WAWTEL Sp. z o.o.
    adres_operatora: str = ""     # ul. Szachowa 1, 04-894 Warszawa
    miasto: str = ""              # Ząbki
    data_wt: str = ""             # 15-07-2022
    zakonczenie_a_adres: str = ""
    zakonczenie_b_adres: str = ""
    zakonczenie_a_studnia: str = ""
    zakonczenie_b_studnia: str = ""
    zakonczenie_a_opis: str = ""  # np. "Wyjście rurą HDPE"
    zakonczenie_b_opis: str = ""  # np. "Dowiązanie do projektowanej mufy"
    typ_kabla: str = ""           # Z-XOTKtsd
    srednica_kabla: str = ""      # 7.0
    projektant: str = ""          # mgr inż. Wiktor Ostasiewicz
    nr_uprawnien: str = ""        # 1246/98/U
    rys_nr: str = ""              # 2.1
    skala: str = "1:1000"
    data_rys: str = ""            # VII-2022


@dataclass
class Projekt:
    """Kompletny stan projektu — źródło prawdy dla generatora DXF i GUI."""
    studnie: list[Studnia] = field(default_factory=list)
    odcinki: list[Odcinek] = field(default_factory=list)
    zapasy: list[Zapas] = field(default_factory=list)
    dane: DaneProjektu = field(default_factory=DaneProjektu)
    epsg_2000: Optional[int] = None   # dobrany kod strefy PL-2000 (2176..2179)

    # --- obliczenia długości ---

    def dlugosc_trasowa(self) -> float:
        """Suma długości odcinków WPROST z WT [m]."""
        return round(sum(o.dlugosc_wt for o in self.odcinki), 1)

    def suma_zapasow(self) -> float:
        """Suma długości wszystkich zapasów (SZ) [m]."""
        return round(
            sum(z.dlugosc for z in self.zapasy if z.kind == ReserveKind.ZAPAS), 1
        )

    def dlugosc_montazowa(self, wspolczynnik: float = 1.03) -> float:
        """montażowa = trasowa * 1,03 + suma zapasów  (zaokr. do 0,1 m)."""
        return round(self.dlugosc_trasowa() * wspolczynnik + self.suma_zapasow(), 1)

    def studnia_po_nazwie(self, nazwa: str) -> Optional[Studnia]:
        for s in self.studnie:
            if s.nazwa == nazwa:
                return s
        return None

    def przelicz_numery_zapasow(self) -> None:
        """
        Nadaje numery SZ-x (zapasy) oraz ZR-x (mufy), każdy typ niezależnie,
        od 1, w kolejności wystąpienia studni wzdłuż trasy.
        """
        kolejnosc = {s.nazwa: i for i, s in enumerate(self.studnie)}
        zapasy = sorted(
            [z for z in self.zapasy if z.kind == ReserveKind.ZAPAS],
            key=lambda z: kolejnosc.get(z.studnia, 10**9),
        )
        mufy = sorted(
            [z for z in self.zapasy if z.kind == ReserveKind.MUFA],
            key=lambda z: kolejnosc.get(z.studnia, 10**9),
        )
        for i, z in enumerate(zapasy, start=1):
            z.numer = i
        for i, z in enumerate(mufy, start=1):
            z.numer = i
