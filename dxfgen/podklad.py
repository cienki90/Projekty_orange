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

# dobór poziomu zoom — wyższy = ostrzej (więcej szczegółów: nazwy ulic, numery).
# z=19 daje bardzo czytelne etykiety na skali 1:1000.
ZOOM_DOMYSLNY = 19
MARGINES_M = 120.0          # ZAPAS terenu wokół trasy [m] (zwiększony bufor)
# Delikatne rozjaśnienie szarości — tak, by podkład był jasny jak w zab3.pdf,
# ale NAZWY ULIC i NUMERY pozostały czytelne (bez „prania" obrazu).
JASNOSC = 1.06
KONTRAST = 1.08             # lekki kontrast, by etykiety były wyraźne
MAKS_PX = 8000             # wyższy limit rozdzielczości wyjścia (ostrość)


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
    grayscale: bool = True,
    okno_m: tuple[float, float] | None = None,
    srodek: tuple[float, float] | None = None,
) -> dict | None:
    """
    Tworzy georeferowany podkład JPG pokrywający trasę.

    grayscale : True = odcienie szarości (podkład przebiegu trasy, jak zab3.pdf);
                False = kolorowy OSM (plan orientacyjny).
    okno_m    : (szer_m, wys_m) — jeśli podane, obszar ma DOKŁADNIE taki rozmiar
                terenu (np. dla stałej skali 1:10000/1:25000); gdy None — obszar
                dobierany ciasno do trasy + margines_m.
    srodek    : (cx, cy) środek obszaru w PL-2000 (domyślnie środek bbox trasy).

    Zwraca słownik osadzenia:
        {"sciezka", "insert"(lewy-dolny), "szer_m", "wys_m", "px_w", "px_h"}
    lub None przy braku sieci/biblioteki.
    """
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except Exception:
        return None

    s = proj.studnie
    if not s:
        return None
    epsg = proj.epsg_2000

    xs = [p.x for p in s]
    ys = [p.y for p in s]
    if okno_m is not None:
        # stały rozmiar okna (dla zadanej skali) wokół środka trasy
        cxr = srodek[0] if srodek else (min(xs) + max(xs)) / 2.0
        cyr = srodek[1] if srodek else (min(ys) + max(ys)) / 2.0
        szer_m, wys_m = okno_m
        minx, maxx = cxr - szer_m / 2.0, cxr + szer_m / 2.0
        miny, maxy = cyr - wys_m / 2.0, cyr + wys_m / 2.0
    else:
        minx, maxx = min(xs) - margines_m, max(xs) + margines_m
        miny, maxy = min(ys) - margines_m, max(ys) + margines_m
        szer_m = maxx - minx
        wys_m = maxy - miny

    # transformer PL-2000 -> WGS84 (do próbkowania mozaiki Mercatora)
    from pyproj import Transformer
    do_wgs = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

    # --- auto-dobór zoomu: najwyższy (najostrzejszy), który mieści się w
    #     budżecie kafli; przy dużym buforze schodzimy o poziom niżej, żeby nie
    #     ściągać setek kafli (polityka OSM) i nie przeciążać pamięci ---
    def _liczba_kafli(z):
        rogi = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
        ll = [do_wgs.transform(x, y) for x, y in rogi]
        xs_t = [_lonlat_do_kafla(lo, la, z)[0] for lo, la in ll]
        ys_t = [_lonlat_do_kafla(lo, la, z)[1] for lo, la in ll]
        nx = int(math.ceil(max(xs_t))) - int(math.floor(min(xs_t)))
        ny = int(math.ceil(max(ys_t))) - int(math.floor(min(ys_t)))
        return nx * ny

    BUDZET_KAFLI = 240
    while zoom > 14 and _liczba_kafli(zoom) > BUDZET_KAFLI:
        zoom -= 1

    # rozdzielczość wyjściowa: ~ dopasowana do zoomu w centrum obszaru
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    clon, clat = do_wgs.transform(cx, cy)
    # metry na piksel w Web Mercator na danym zoomie i szerokości geogr.
    m_na_px = 156543.03392 * math.cos(math.radians(clat)) / (2 ** zoom)
    px_w = max(256, int(szer_m / m_na_px))
    px_h = max(256, int(wys_m / m_na_px))
    # ogranicz rozmiar wyjścia (bezpieczeństwo), ale pozwól na większą ostrość
    if px_w > MAKS_PX or px_h > MAKS_PX:
        skala = MAKS_PX / max(px_w, px_h)
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
    if kafli <= 0 or kafli > BUDZET_KAFLI + 40:
        # zbyt duży obszar na ten zoom — odpuść (zabezpieczenie)
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

    if grayscale:
        # odcienie szarości: lekko rozjaśnione + kontrast (podkład przebiegu)
        wyj = ImageOps.grayscale(obraz)
        wyj = ImageEnhance.Contrast(wyj).enhance(KONTRAST)
        wyj = ImageEnhance.Brightness(wyj).enhance(JASNOSC)
        wyj = wyj.convert("RGB")
    else:
        # kolorowy OSM (plan orientacyjny) — bez odbarwiania
        wyj = obraz

    os.makedirs(os.path.dirname(os.path.abspath(sciezka_jpg)) or ".", exist_ok=True)
    wyj.save(sciezka_jpg, "JPEG", quality=92)

    return {
        "sciezka": sciezka_jpg,
        "insert": (minx, miny),   # lewy-dolny róg w PL-2000
        "szer_m": szer_m,
        "wys_m": wys_m,
        "px_w": px_w,
        "px_h": px_h,
    }
