"""Baja el atlas de iconos del juego (del realitytracker) para usarlo en la web.

Fuente: github.com/yossizap/realitytracker — `atlas.png` (tira horizontal de sprites,
16384×64) + `data.json` (`atlas`: {icon:[x,w,h]}; `vehicles`: {code:{MiniMapIcon,MenuIcon}}).

Genera:
  web/img/atlas.png            — la tira de sprites
  web/img/atlas.json           — {"icons": {icon:[x,w,h]}, "vehicles": {code: icon}}
donde para cada vehículo se elige el MiniMapIcon (si no es "empty" y está en el atlas),
si no el MenuIcon. La web usa esto como CSS sprite (ver utils.vehicleIconHTML).

Uso:  python -m scraper.fetch_atlas
"""

import json
import os
import urllib.request

RAW = "https://raw.githubusercontent.com/yossizap/realitytracker/master"
OUT_DIR = os.path.join("web", "img")
UA = {"User-Agent": "Mozilla/5.0 (compatible; LDH-StatsTracker/1.0)"}


def _get(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    data = json.loads(_get(f"{RAW}/data.json").decode("utf-8"))
    atlas = data.get("atlas", {})           # icon -> [x, w, h]
    vehicles = data.get("vehicles", {})     # code -> {MiniMapIcon, MenuIcon, ...}

    veh_icon = {}
    for code, info in vehicles.items():
        mini = (info or {}).get("MiniMapIcon", "")
        menu = (info or {}).get("MenuIcon", "")
        icon = mini if (mini and mini != "empty" and mini in atlas) else (menu if menu in atlas else "")
        if icon:
            veh_icon[code] = icon

    with open(os.path.join(OUT_DIR, "atlas.png"), "wb") as f:
        f.write(_get(f"{RAW}/atlas.png"))
    with open(os.path.join(OUT_DIR, "atlas.json"), "w", encoding="utf-8") as f:
        json.dump({"icons": atlas, "vehicles": veh_icon}, f, ensure_ascii=False)

    size = os.path.getsize(os.path.join(OUT_DIR, "atlas.png")) / 1024
    print(f"atlas.png {size:.0f} KB · {len(atlas)} iconos · {len(veh_icon)} vehículos con icono")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
