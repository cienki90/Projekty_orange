"""
Podkład rastrowy OSM (Etap 3).

Pobiera kafle OpenStreetMap (Web Mercator / EPSG:3857), skleja je, przelicza
(resampling) do układu rysunku PL-2000 i zapisuje jako JPG w ODCIENIACH SZAROŚCI.
Zwraca ścieżkę JPG oraz jego osadzenie w PL-2000 (punkt wstawienia + rozmiar w
metrach), aby można było wstawić go jako encję IMAGE pod trasą (najniższa warstwa).

Założenia:
  - źródło: standardowe kafle OSM (z nagłówkiem User-Agent + cache na dysku);
    źródło łatwo podmienić (stała SZABLON_URL),
  - obraz jest georeferowany: siatka wyjściowa jest w PL-2000, każdy piksel
    próbkowany z mozaiki Web Mercator przez pyproj -> IDEALNE dopasowanie do
    wektorowej trasy (bez przesunięć),
  - podkład = odcienie szarości (jak w wymaganiach), lekko rozjaśniony, by nie
    dominował nad rysunkiem.

Uwaga licencyjna: dane © OpenStreetMap contributors (ODbL). Do użytku zgodnie
z polityką tile usage OSM; w razie potrzeby podmień źródło na własny serwer WMTS.
"""

from __future__ import annotations

import math
import os
import time
import urllib.request

from . import crs

# szablon URL kafli OSM (z, x, y). Łatwo podmienić na inny serwer WMTS.
SZABLON_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "generator-dxf-orange/1.0 (projekt techniczny; kontakt: lokalny)"
ROZMIAR_KAFLA = 256  # px
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache_osm")

# dobór poziomu zoom tak, aby 1 m terenu ~ odpowiadał rozsądnej rozdzielczości
# (na 1:1000 wystarcza z=18..19; wyżej = ostrzej, ale więcej kafli)
ZOOM_DOMYSLNY = 18
MARGINES_M = 40.0           # zapas terenu wokół trasy [m]
JASNOSC = 1.35              # rozjaśnienie szarości (1.0 = bez zmian)


# --------------------------------------------------------------------------- #
#  Web Mercator <-> lon/lat <-> kafle
# --------------------------------------------------------------------------- #

def _lonlat_do_kafla(lon: float, lat: float, z: int) -> tuple[float, float]:
    """Zwraca (x, y) kafla (ułamkowo) dla danego lon/lat i zoomu."""
    lat_r = math.radians(lat)
    n = 2.0 ** z
    xt = (lon + 180.0) / 360.0 * n
    yt = (1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n
    return xt, yt


def _kafel_do_lonlat(xt: float, yt: float, z: int) -> tuple[float, float]:
    """Odwrotność: (x, y) kafla -> (lon, lat) lewego-górnego rogu."""
    n = 2.0 ** z
    lon = xt / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yt / n))))
    return lon, lat


def _pobierz_kafel(z: int, x: int, y: int) -> "PIL.Image.Image":
    """Pobiera (z cache) pojedynczy kafel OSM jako obraz PIL (RGB)."""
    from PIL import Image
    os.makedirs(CACHE_DIR, exist_ok=True)
    sciezka = os.path.join(CACHE_DIR, f"{z}_{x}_{y}.png")
    if not os.path.exists(sciezka):
        url = SZABLON_URL.format(z=z, x=x, y=y)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=20) as resp:
            dane = resp.read()
        with open(sciezka, "wb") as f:
            f.write(dane)
        time.sleep(0.1)  # delikatność wobec serwera OSM
    return Image.open(sciezka).convert("RGB")


# --------------------------------------------------------------------------- #
#  Budowa podkładu
# --------------------------------------------------------------------------- #

def generuj_podklad_jpg(
    proj,
    sciezka_jpg: str,
    zoom: int = ZOOM_DOMYSLNY,
    margines_m: float = MARGINES_M,
) -> dict | None:
    """
    Tworzy georeferowany podkład JPG (grayscale) pokrywający trasę + margines.

    Zwraca słownik osadzenia:
        {"sciezka": <jpg>, "insert": (x_pl2000, y_pl2000_dolny_lewy),
         "szer_m": <szerokość w metrach>, "wys_m": <wysokość w metrach>,
         "px_w": <piksele>, "px_h": <piksele>}
    lub None, gdy nie udało się pobrać podkładu (brak sieci) — generator
    kontynuuje wtedy bez tła.
    """
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except Exception:
        return None

    s = proj.studnie
    if not s:
        return None
    epsg = proj.epsg_2000

    # zasięg trasy w PL-2000 + margines
    xs = [p.x for p in s]
    ys = [p.y for p in s]
    minx, maxx = min(xs) - margines_m, max(xs) + margines_m
    miny, maxy = min(ys) - margines_m, max(ys) + margines_m
    szer_m = maxx - minx
    wys_m = maxy - miny

    # transformer PL-2000 -> WGS84 (do próbkowania mozaiki Mercatora)
    from pyproj import Transformer
    do_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    # rozdzielczość wyjściowa: ~ dopasowana do zoomu w centrum obszaru
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    clon, clat = do_wgs.transform(cx, cy)
    # metry na piksel w Web Mercator na danym zoomie i szerokości geogr.
    m_na_px = 156543.03392 * math.cos(math.radians(clat)) / (2 ** zoom)
    px_w = max(256, int(szer_m / m_na_px))
    px_h = max(256, int(wys_m / m_na_px))
    # ogranicz rozmiar wyjścia (bezpieczeństwo)
    MAKS = 4000
    if px_w > MAKS or px_h > MAKS:
        skala = MAKS / max(px_w, px_h)
        px_w = int(px_w * skala)
        px_h = int(px_h * skala)

    # --- zbuduj mozaikę Mercatora pokrywającą obszar (w kaflach) ---
    # rogi obszaru -> lon/lat -> kafle
    naroza_pl = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
    lonlat = [do_wgs.transform(x, y) for x, y in naroza_pl]
    xts = [_lonlat_do_kafla(lon, lat, zoom)[0] for lon, lat in lonlat]
    yts = [_lonlat_do_kafla(lon, lat, zoom)[1] for lon, lat in lonlat]
    x0t, x1t = int(math.floor(min(xts))), int(math.ceil(max(xts)))
    y0t, y1t = int(math.floor(min(yts))), int(math.ceil(max(yts)))

    kafli = (x1t - x0t) * (y1t - y0t)
    if kafli <= 0 or kafli > 400:
        # zbyt duży obszar na ten zoom — odpuść (albo zmień zoom)
        return None

    mozaika = Image.new("RGB", ((x1t - x0t) * ROZMIAR_KAFLA,
                                (y1t - y0t) * ROZMIAR_KAFLA), (240, 240, 240))
    try:
        for xt in range(x0t, x1t):
            for yt in range(y0t, y1t):
                kafel = _pobierz_kafel(zoom, xt, yt)
                mozaika.paste(kafel, ((xt - x0t) * ROZMIAR_KAFLA,
                                      (yt - y0t) * ROZMIAR_KAFLA))
    except Exception:
        return None  # brak sieci / błąd pobierania — bez tła

    # --- resampling: siatka wyjściowa w PL-2000 -> próbka z mozaiki Mercatora ---
    # dla każdego piksela wyjścia liczymy PL-2000 -> lon/lat -> piksel mozaiki
    import numpy as np

    moz = np.asarray(mozaika)
    moz_h, moz_w = moz.shape[0], moz.shape[1]

    # siatka PL-2000 (wektor) — oś X rośnie w prawo, Y rośnie w górę (DXF),
    # obraz ma Y w dół, więc wiersz 0 = góra (maxy)
    gx = np.linspace(minx, maxx, px_w)
    gy = np.linspace(maxy, miny, px_h)  # od góry do dołu
    GX, GY = np.meshgrid(gx, gy)
    flon, flat = do_wgs.transform(GX.ravel(), GY.ravel())
    flon = np.asarray(flon); flat = np.asarray(flat)

    # lon/lat -> piksel mozaiki
    n = 2.0 ** zoom
    xt = (flon + 180.0) / 360.0 * n
    lat_r = np.radians(flat)
    yt = (1.0 - np.arcsinh(np.tan(lat_r)) / np.pi) / 2.0 * n
    px = ((xt - x0t) * ROZMIAR_KAFLA).astype(int)
    py = ((yt - y0t) * ROZMIAR_KAFLA).astype(int)
    np.clip(px, 0, moz_w - 1, out=px)
    np.clip(py, 0, moz_h - 1, out=py)

    out = moz[py, px].reshape(px_h, px_w, 3)
    obraz = Image.fromarray(out, "RGB")

    # --- odcienie szarości + rozjaśnienie ---
    szary = ImageOps.grayscale(obraz)
    szary = ImageEnhance.Brightness(szary).enhance(JASNOSC)
    szary = szary.convert("RGB")  # JPG lubi RGB

    os.makedirs(os.path.dirname(os.path.abspath(sciezka_jpg)) or ".", exist_ok=True)
    szary.save(sciezka_jpg, "JPEG", quality=85)

    return {
        "sciezka": sciezka_jpg,
        "insert": (minx, miny),   # lewy-dolny róg w PL-2000
        "szer_m": szer_m,
        "wys_m": wys_m,
        "px_w": px_w,
        "px_h": px_h,
    }
