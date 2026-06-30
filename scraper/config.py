"""Configuration for the PR Stats scraper."""

import os

CLAN_URLS = {
    "LDH": "https://prstats.realitymod.org/clan/11204/ldh",
    "FI": "https://prstats.realitymod.org/clan/8067/fi",
    "FI-R": "https://prstats.realitymod.org/clan/30397/fi-r",
    "R-LDH": "https://prstats.realitymod.org/clan/37315/r-ldh",
    "WD": "https://prstats.realitymod.org/clan/11052/wd",
    "300": "https://prstats.realitymod.org/clan/36331/300",
    "E-LAM": "https://prstats.realitymod.org/clan/29486/e-lam",
    "RIM:LA": "https://prstats.realitymod.org/clan/9406/rimla",
    "ADG": "https://prstats.realitymod.org/clan/17913/adg",
    "A-LDH": "https://prstats.realitymod.org/clan/44173/a-ldh",
    "FASO": "https://prstats.realitymod.org/clan/46393/faso",
    "PORN": "https://prstats.realitymod.org/clan/47806/porn",
    "E-102": "https://prstats.realitymod.org/clan/188/e-102",
    "ARA": "https://prstats.realitymod.org/clan/20864/ara",
    "TANGO": "https://prstats.realitymod.org/clan/40384/tango",
    "SF": "https://prstats.realitymod.org/clan/215/sf",
    "KKCK": "https://prstats.realitymod.org/clan/180/kkck",
    "SPTS": "https://prstats.realitymod.org/clan/536/spts",
    # Sumados a pedido (algunos europeos)
    "DARE": "https://prstats.realitymod.org/clan/125/dare",
    "FEB": "https://prstats.realitymod.org/clan/1806/feb",
    "EASY": "https://prstats.realitymod.org/clan/193/easy",
    "U777": "https://prstats.realitymod.org/clan/5296/u777",
    "OSO": "https://prstats.realitymod.org/clan/38980/oso",
    "LA-9": "https://prstats.realitymod.org/clan/166/la-9",
    "WK": "https://prstats.realitymod.org/clan/26959/wk",
    "FAL": "https://prstats.realitymod.org/clan/14393/fal",
    "GoSTML": "https://prstats.realitymod.org/clan/25438/gostml",
}

SCORING_VERSION = "v3"

# Kit names for archetype detection (must match demo kit names)
MEDIC_KITS = ["Medico"]
OFFICER_KITS = ["Oficial"]
ARMOR_KITS = ["Tripulante", "Piloto"]
AT_KITS = ["HAT", "LAT", "Anti-Tanque", "Ingeniero", "Ing. Combate"]

# Fixed normalization caps (for stable historical scores)
NORM_CAPS = {
    "kd": 5.0,
    "score_per_round": 500.0,
    "kills_per_round": 10.0,
    "rounds": 1000.0,
}

LOW_ROUNDS_THRESHOLD = 50
MIN_ROUNDS_PENALTY = 10

REQUEST_TIMEOUT = 15
MAX_RETRIES = 3

OUTPUT_DIR = "graphs"
HISTORY_DIR = "graphs/history"
DEMOS_DIR = "graphs/demos"

GITHUB_PAGES_URL = "https://luccabruno3z.github.io"

# prstats server list URL for auto-discovery
PRSTATS_SERVERS_URL = "https://prstats.realitymod.org/servers"
DISCOVERED_SERVERS_FILE = os.path.join(DEMOS_DIR, "discovered_servers.json")

# PRDemo server sources — directory listings with .PRdemo files (fallback)
# Supports standard HTML directory listings and HFS 3.x JSON API.
#
# Receta para sumar un server nuevo (auto-discovery solo agarra los que tienen link
# "Battle records" en su página de prstats):
#   1. https://prstats.realitymod.org/servers → sacar dominios.
#   2. GET la home del dominio y buscar links con track|demo|record|battle|prdemo.
#   3. Clasificar el listado y mapearlo:
#        - Apache plano (tracker_*.PRdemo)          → DEMO_SERVERS
#        - Apache por mes (YYYY_MM/)                 → MONTHLY_DEMO_SERVERS
#        - HFS (marcadores /~/frontend/, ?get=basic)→ DEMO_SERVERS (URL ~/api/
#          get_file_list?uri=...) + HFS_DOWNLOAD_BASE
#        - SPA con visor realitytracker (links <a href=...index.html?demo=URL>) →
#          DEMO_SERVERS con la URL de la página; _list_demos_from_directory ya
#          extrae la URL real del parámetro ?demo= (caso Reality Brasil).
#   4. Verificar que un .PRdemo baje (HTTP 200) antes de commitear.
DEMO_SERVERS = {
    # Reality Brasil migró de Apache (Server01/demos/, ahora 302) a una SPA con
    # selector ?srv=N; las demos están en Server01/tracker/ y la página linkea al
    # visor con ?demo=<URL real>. srv=1 es el server público (actual); 2/4 archivo.
    "RealityBrasil-1": "https://files.realitybrasil.org/PRServer/BattleRecorder/?srv=1",
    "RealityBrasil-2": "https://files.realitybrasil.org/PRServer/BattleRecorder/?srv=2",
    "RealityBrasil-4": "https://files.realitybrasil.org/PRServer/BattleRecorder/?srv=4",
    "LATAMSQUAD-SV1": "https://latamsquad.dev/~/api/get_file_list?uri=/Project-Reality-BF2/PRdemos-2D/sv1/",
    # Alliance EU (alliance-community.com): listado Apache plano. El link "Battle
    # records" de prstats apunta al dir padre (/servers/primary/, sin .PRdemo), así
    # que la auto-discovery no lo agarra; los demos están un nivel abajo en prdemos/.
    # Trae links del visor con ?demo=<ruta relativa-desde-raíz> (resuelto por urljoin
    # en _list_demos_from_directory).
    "Alliance-EU": "https://alliance-community.com/servers/primary/prdemos/",
    # Russian Frontier: HFS como latamsquad. uri = "Трекеры (.PRdemo)/" (URL-encoded).
    # DESACTIVADO (2026-06-30): el host da connect timeout (puerto 443 no responde).
    # Reactivar cuando vuelva a estar accesible (descomentar acá y en HFS_DOWNLOAD_BASE).
    # "RussianFrontier": "https://russianfrontier.ru/~/api/get_file_list?uri=/%D0%A2%D1%80%D0%B5%D0%BA%D0%B5%D1%80%D1%8B%20%28.PRdemo%29/",
}

# HFS servers need a base URL mapping for downloads (API URL != download URL)
HFS_DOWNLOAD_BASE = {
    "LATAMSQUAD-SV1": "https://latamsquad.dev/Project-Reality-BF2/PRdemos-2D/sv1/",
    # "RussianFrontier": "https://russianfrontier.ru/%D0%A2%D1%80%D0%B5%D0%BA%D0%B5%D1%80%D1%8B%20%28.PRdemo%29/",  # DESACTIVADO 2026-06-30 (timeout)
}

# Servers cuyo directorio de demos está particionado por mes (YYYY_MM/), p.ej.
# TikTok War (ruttw.ru). Se expanden en runtime a las carpetas del mes actual y el
# anterior (cubre el cambio de mes). Cada carpeta es un listado Apache plano.
MONTHLY_DEMO_SERVERS = {
    "TikTokWar-RU": "https://ruttw.ru/tracker/",
}

# Maximum demos to process per run (across all servers).
# GitHub throttlea los cron sub-horarios (un "*/10" corre cada ~2-3h), así que en
# vez de muchos runs chicos hacemos pocos runs grandes: más demos por corrida.
# HFS baja secuencial (~2s/demo) → 150 ≈ 5 min. Bajar a 25 para el ritmo normal.
MAX_DEMOS_PER_RUN = 150

# Maximum wall-clock seconds for the entire demo phase (download + parse).
# If exceeded between batches, remaining demos are left for the next run.
# Acompaña a MAX_DEMOS_PER_RUN (temporal, catch-up). Normal: 120.
DEMO_TIME_BUDGET = 900

# Gamemodes excluidos de las stats: gungame es un minijuego de ciclar armas (no son
# rondas competitivas y distorsionan kills/kits). Se filtran tanto al descargar
# (no consumen el cupo por-run) como al agregar (se ignoran las rondas históricas
# ya guardadas, sin borrarlas del disco).
EXCLUDED_GAMEMODES = {"gpm_gungame"}
