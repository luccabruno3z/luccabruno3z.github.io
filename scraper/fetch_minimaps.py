"""Descarga y stitchea los minimapas de Project Reality para los heatmaps de la web.

Fuente: el Map Gallery oficial (https://mapgallery.realitymod.org), que sirve cada
mapa como una pirámide de tiles Leaflet en
  /images/maps/<cleanName(Name)>/tiles/{z}/{x}/{y}.jpg
donde cleanName(Name) = Name sin espacios/underscores, en minúsculas.

Para cada nivel de `json/levels.json` arma una imagen única a zoom 3 (8×8 tiles =
2048×2048) y la guarda como `web/img/maps/<Key>.jpg` — `Key` es el nombre interno
del mapa, que coincide con `map_name` de nuestras rondas, así que el heatmap la
encuentra por el manifest sin recalibrar (misma normalización centrada al mapa).

Uso:  python -m scraper.fetch_minimaps [--zoom 3] [--quality 82] [--force]
Idempotente: salta los mapas ya descargados salvo --force.
"""

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

GALLERY = "https://mapgallery.realitymod.org"
LEVELS_URL = f"{GALLERY}/json/levels.json"
OUT_DIR = os.path.join("web", "img", "maps")
UA = {"User-Agent": "Mozilla/5.0 (compatible; LDH-StatsTracker/1.0)"}


def clean_name(name: str) -> str:
    """Reproduce el cleanName del gallery: sin espacios/underscores, minúsculas."""
    return re.sub(r"[\s_]", "", name).lower()


def _get(url: str, timeout: int = 30, retries: int = 3) -> bytes:
    """GET con reintentos exponenciales para 5xx/timeout; relanza 404 enseguida."""
    for attempt in range(retries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def _tile(img_name: str, z: int, x: int, y: int):
    from PIL import Image
    url = f"{GALLERY}/images/maps/{img_name}/tiles/{z}/{x}/{y}.jpg"
    return (x, y, Image.open(io.BytesIO(_get(url))))


def stitch(img_name: str, zoom: int):
    """Descarga los tiles del zoom dado (en paralelo) y los compone en una imagen."""
    from PIL import Image
    n = 2 ** zoom
    full = Image.new("RGB", (n * 256, n * 256))
    coords = [(x, y) for x in range(n) for y in range(n)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for x, y, tile in ex.map(lambda c: _tile(img_name, zoom, c[0], c[1]), coords):
            full.paste(tile, (x * 256, y * 256))
    return full


def stitch_best(img_name: str, max_zoom: int):
    """Intenta max_zoom y baja (z-1, z-2…) si ese nivel no existe (404)."""
    last = None
    for z in range(max_zoom, 1, -1):
        try:
            return stitch(img_name, z), z
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            last = e
    raise last or RuntimeError("sin tiles")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=int, default=3, help="nivel de zoom (3 = 2048px)")
    ap.add_argument("--quality", type=int, default=82, help="calidad JPEG")
    ap.add_argument("--force", action="store_true", help="re-descargar los ya existentes")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    levels = json.loads(_get(LEVELS_URL).decode("utf-8"))
    manifest = {}
    ok = skipped = failed = 0

    for lvl in levels:
        key = lvl.get("Key")
        name = lvl.get("Name", "")
        if not key or not name:
            continue
        out = os.path.join(OUT_DIR, f"{key}.jpg")
        if os.path.exists(out) and not args.force:
            manifest[key] = "jpg"
            skipped += 1
            continue
        img_name = clean_name(name)
        try:
            img, z = stitch_best(img_name, args.zoom)
            img.save(out, "JPEG", quality=args.quality, optimize=True)
            manifest[key] = "jpg"
            ok += 1
            note = "" if z == args.zoom else f" (z{z} fallback)"
            print(f"  ✓ {key:24s} ({name}) {img.size[0]}px {os.path.getsize(out)//1024} KB{note}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  ✗ {key:24s} ({name}): {exc}")

    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=0, sort_keys=True)

    total = sum(os.path.getsize(os.path.join(OUT_DIR, f"{k}.jpg")) for k in manifest) / 1e6
    print(f"\nlistos {ok}, saltados {skipped}, fallidos {failed} · manifest {len(manifest)} mapas · {total:.1f} MB")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
