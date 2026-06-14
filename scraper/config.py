"""Configuration for the PR Stats scraper."""

import os

CLAN_URLS = {
    "LDH": "https://prstats.realitymod.org/clan/11204/ldh",
    "FI": "https://prstats.realitymod.org/clan/8067/fi",
    "SAE": "https://prstats.realitymod.org/clan/42817/sae",
    "FI-R": "https://prstats.realitymod.org/clan/30397/fi-r",
    "R-LDH": "https://prstats.realitymod.org/clan/37315/r-ldh",
    "141": "https://prstats.realitymod.org/clan/7555/141",
    "WD": "https://prstats.realitymod.org/clan/11052/wd",
    "300": "https://prstats.realitymod.org/clan/36331/300",
    "E-LAM": "https://prstats.realitymod.org/clan/29486/e-lam",
    "RIM:LA": "https://prstats.realitymod.org/clan/9406/rimla",
    "ADG": "https://prstats.realitymod.org/clan/17913/adg",
    "A-LDH": "https://prstats.realitymod.org/clan/44173/a-ldh",
    "FASO": "https://prstats.realitymod.org/clan/46393/faso",
    "PORN": "https://prstats.realitymod.org/clan/47806/porn",
    "E-102": "https://prstats.realitymod.org/clan/188/e-102",
    "PTFS": "https://prstats.realitymod.org/clan/34631/ptfs",
    "ARA": "https://prstats.realitymod.org/clan/20864/ara",
    "TANGO": "https://prstats.realitymod.org/clan/40384/tango",
    "SF": "https://prstats.realitymod.org/clan/215/sf",
    "KKCK": "https://prstats.realitymod.org/clan/180/kkck",
    "SPTS": "https://prstats.realitymod.org/clan/536/spts",
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
MAX_RETRIES = 1

OUTPUT_DIR = "graphs"
HISTORY_DIR = "graphs/history"
DEMOS_DIR = "graphs/demos"

GITHUB_PAGES_URL = "https://luccabruno3z.github.io"

# prstats server list URL for auto-discovery
PRSTATS_SERVERS_URL = "https://prstats.realitymod.org/servers"
DISCOVERED_SERVERS_FILE = os.path.join(DEMOS_DIR, "discovered_servers.json")

# PRDemo server sources — directory listings with .PRdemo files (fallback)
# Supports standard HTML directory listings and HFS 3.x JSON API
DEMO_SERVERS = {
    "RealityBrasil-Foxtrot": "https://files.realitybrasil.org/PRServer/BattleRecorder/Server01/demos/",
    "LATAMSQUAD-SV1": "https://latamsquad.dev/~/api/get_file_list?uri=/Project%20Reality%20BF2/PRdemos%202D/sv1/",
}

# HFS servers need a base URL mapping for downloads (API URL != download URL)
HFS_DOWNLOAD_BASE = {
    "LATAMSQUAD-SV1": "https://latamsquad.dev/Project%20Reality%20BF2/PRdemos%202D/sv1/",
}

# Maximum demos to process per run (across all servers).
# Keeps each Action run under ~5 min. Remaining demos are picked up next run.
# HFS servers download sequentially (~2s/demo), so 25 demos ≈ 50s for HFS.
# With hourly runs, 25/run catches up with ~600 backlog/day.
MAX_DEMOS_PER_RUN = 25

# Maximum wall-clock seconds for the entire demo phase (download + parse).
# If exceeded between batches, remaining demos are left for the next run.
DEMO_TIME_BUDGET = 120
