"""
dxfgen — generator rysunków DXF tras światłowodowych w kanalizacji Orange Polska.

Pipeline:
    współrzędne.xlsx (WGS84)  ->  transformacja  ->  PL-2000
    wt.xls (Zał 3)            ->  długości odcinków, numeracja, relacje
    wt.xls (Formularz 1K)     ->  metadane tabelki rysunkowej
    [zapasy/mufy wskazane w GUI]
    OSM                       ->  podkład rastrowy (szarość)
            |
            v
    DXF: model space + arkusze A3 (1:1000, DWG To PDF)
"""

__version__ = "0.1.0"
