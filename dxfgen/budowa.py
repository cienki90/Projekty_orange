"""
Składanie obiektu Projekt z plików wejściowych:
  - wczytuje studnie i odcinki,
  - dobiera strefę PL-2000 i transformuje współrzędne,
  - dopasowuje adresy zakończeń A/B do skrajnych studni,
  - uzupełnia pola tabelki z danych WT.
"""

from __future__ import annotations

from . import crs
from .model import DaneProjektu, Projekt
from .wczytywanie import wczytaj_wspolrzedne, wczytaj_wt


def zbuduj_projekt(sciezka_wspolrzedne: str, sciezka_wt: str) -> Projekt:
    studnie = wczytaj_wspolrzedne(sciezka_wspolrzedne)
    dane, odcinki = wczytaj_wt(sciezka_wt)

    # dobór strefy PL-2000 wspólny dla całej trasy
    nr_strefy, epsg = crs.dobierz_strefe_dla_punktow([s.lon for s in studnie])

    # transformacja współrzędnych
    for s in studnie:
        s.x, s.y = crs.wgs84_do_2000(s.lat, s.lon, epsg)

    # zakończenia A/B — nazwa studni z Zał 3 (początek pierwszego / koniec ostatniego
    # odcinka); jeśli brak odcinków, użyj skrajnych studni z współrzędnych
    if odcinki:
        dane.zakonczenie_a_studnia = odcinki[0].studnia_a
        dane.zakonczenie_b_studnia = odcinki[-1].studnia_b
    elif studnie:
        dane.zakonczenie_a_studnia = studnie[0].nazwa
        dane.zakonczenie_b_studnia = studnie[-1].nazwa

    proj = Projekt(
        studnie=studnie,
        odcinki=odcinki,
        dane=dane,
        epsg_2000=epsg,
    )
    return proj
