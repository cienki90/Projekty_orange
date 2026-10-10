"""
Transformacja współrzędnych WGS84 (EPSG:4326) -> PL-2000 (EPSG:2176..2179).

Układ PL-2000 (GK) dzieli Polskę na 4 pasy 3-stopniowe:
    strefa 5: południk osiowy 15°E  ->  EPSG:2176  (False Easting 5 500 000)
    strefa 6: południk osiowy 18°E  ->  EPSG:2177  (False Easting 6 500 000)
    strefa 7: południk osiowy 21°E  ->  EPSG:2178  (False Easting 7 500 000)
    strefa 8: południk osiowy 24°E  ->  EPSG:2179  (False Easting 8 500 000)

UWAGA dot. EPSG a kolejność osi:
    W bazie EPSG układy 2176..2179 mają urzędową kolejność osi (North, East).
    W rysunku DXF potrzebujemy klasycznego (X=Easting w poziomie, Y=Northing w pionie),
    dlatego wymuszamy kolejność east/north przez pyproj (always_xy=True).

Pierwsza cyfra Eastingu w PL-2000 koduje numer strefy (np. 7xxxxxx -> strefa 7),
co zgadza się z danymi z zab2.dxf ($EXTMIN X ≈ 7 507 000 -> strefa 7).
"""

from __future__ import annotations

from functools import lru_cache

# longitude -> (numer strefy, kod EPSG)
_STREFY = [
    (5, 2176, 13.5, 16.5),   # pas wokół 15°E
    (6, 2177, 16.5, 19.5),   # pas wokół 18°E
    (7, 2178, 19.5, 22.5),   # pas wokół 21°E
    (8, 2179, 22.5, 25.5),   # pas wokół 24°E
]


def dobierz_strefe(lon: float) -> tuple[int, int]:
    """
    Dobiera strefę PL-2000 na podstawie długości geograficznej.
    Zwraca (numer_strefy, epsg).
    """
    for nr, epsg, lo, hi in _STREFY:
        if lo <= lon < hi:
            return nr, epsg
    # poza zakresem Polski — wybierz najbliższy południk osiowy
    poludniki = {5: 15, 6: 18, 7: 21, 8: 24}
    nr = min(poludniki, key=lambda s: abs(poludniki[s] - lon))
    epsg = {5: 2176, 6: 2177, 7: 2178, 8: 2179}[nr]
    return nr, epsg


def dobierz_strefe_dla_punktow(lony: list[float]) -> tuple[int, int]:
    """Dobiera jedną strefę dla całej trasy na podstawie średniej długości."""
    if not lony:
        raise ValueError("Brak współrzędnych do określenia strefy PL-2000.")
    srednia = sum(lony) / len(lony)
    return dobierz_strefe(srednia)


@lru_cache(maxsize=8)
def _transformer(epsg: int):
    from pyproj import Transformer
    # always_xy=True => wejście (lon, lat), wyjście (easting, northing)
    return Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)


def wgs84_do_2000(lat: float, lon: float, epsg: int) -> tuple[float, float]:
    """
    Przelicza pojedynczy punkt WGS84 -> PL-2000.
    Zwraca (x, y) = (Easting, Northing) gotowe do rysunku DXF.
    """
    t = _transformer(epsg)
    x, y = t.transform(lon, lat)
    return x, y
