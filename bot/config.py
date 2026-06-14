"""Centralized configuration for the PR Stats Discord bot."""

# ── Base URL ──────────────────────────────────────────────────────────────────
BASE_URL = "https://luccabruno3z.github.io"

# ── URL builders ──────────────────────────────────────────────────────────────

def graph_url(clan: str) -> str:
    """Return the interactive chart URL for a given clan."""
    return f"{BASE_URL}/graphs/{clan}_interactive_chart.html"


def json_url(clan: str) -> str:
    """Return the players JSON URL for a given clan."""
    return f"{BASE_URL}/graphs/{clan}_players.json"


def all_players_url() -> str:
    """Return the URL for the combined all-players cluster JSON."""
    return f"{BASE_URL}/graphs/all_players_clusters.json"


def clan_averages_url() -> str:
    """Return the URL for the clan averages JSON."""
    return f"{BASE_URL}/graphs/clan_averages.json"


def history_url(player_name: str) -> str:
    """Return the URL for a player's history JSON (local path pattern)."""
    return f"graphs/history/{player_name}_history.json"


def all_players_graph_url() -> str:
    """Return the interactive chart URL for all players."""
    return f"{BASE_URL}/graphs/all_players_interactive_chart.html"


# ── Demo-based detailed stats URLs ───────────────────────────────────────────

def demo_player_details_url() -> str:
    """Return the URL for the aggregated player details JSON (from demos)."""
    return f"{BASE_URL}/graphs/demos/player_details.json"


def demo_round_history_url() -> str:
    """Return the URL for the round history JSON (from demos).

    Deprecated: the 100 MB monolith was replaced by daily partitions
    (graphs/demos/rounds/) plus precomputed leaderboards. Kept for backward
    compatibility only; use demo_leaderboard_url().
    """
    return f"{BASE_URL}/graphs/demos/round_history.json"


def demo_leaderboard_url(periodo: str) -> str:
    """Return the URL for a precomputed period leaderboard JSON (from demos).

    *periodo* must be one of: ``dia``, ``semana``, ``mes``, ``todo``.
    """
    return f"{BASE_URL}/graphs/demos/leaderboards/{periodo}.json"


def demo_map_stats_url() -> str:
    """Return the URL for the map statistics JSON (from demos)."""
    return f"{BASE_URL}/graphs/demos/map_stats.json"


def tier_config_url() -> str:
    """Return the URL for the tier configuration JSON (dynamic thresholds)."""
    return f"{BASE_URL}/graphs/tier_config.json"


# ── Clan logo URLs ───────────────────────────────────────────────────────────
# Clans that use .gif instead of .png for their logo
_GIF_CLANS = {"ADG"}
_NO_LOGO_CLANS = {"E-102", "PTFS", "ARA", "TANGO", "SF", "KKCK", "SPTS"}

def clan_logo_url(clan: str) -> str:
    """Return the logo URL for a clan, using .gif for known GIF clans."""
    if clan in _NO_LOGO_CLANS:
        return f"{BASE_URL}/logos/Logo_default.png"
    ext = "gif" if clan in _GIF_CLANS else "png"
    return f"{BASE_URL}/logos/Logo_{clan}.{ext}"


# ── Clan list ─────────────────────────────────────────────────────────────────
CLAN_NAMES = [
    "LDH", "SAE", "FI", "FI-R", "141", "R-LDH", "A-LDH",
    "WD", "300", "E-LAM", "RIM:LA", "ADG", "FASO", "PORN",
    "E-102", "PTFS", "ARA", "TANGO", "SF", "KKCK", "SPTS",
]

# ── Clan emojis (Discord custom emoji markup) ────────────────────────────────
CLAN_EMOJIS = {
    "LDH": "<a:Logo_LDH:1331795086169866290>",
    "SAE": "<:Logo_SAE:1330790573061312542>",
    "FI": "<:Logo_FI:1330790559601659924>",
    "FI-R": "<:Logo_FI:1330790559601659924>",
    "141": "",  # se completa via -setup_emojis (Application Emoji)
    "R-LDH": "<:Logo_R_LDH:1331795559291551877>",
    "A-LDH": "<:Logo_R_LDH:1331795559291551877>",
    "WD": "",  # se completa via -setup_emojis (Application Emoji)
    "300": "<:Logo_300:1330790501460213770>",
    "E-LAM": "<:Logo_E_LAM:1330790544263217243>",
    "RIM:LA": "<:Logo_RIM_LA:1330790529214185472>",
    "ADG": "<a:Logo_ADG:1331778693949034516>",
    "FASO": "<:Logo_FASO:1344203061907689482>",
    "PORN": "",
    "E-102": "",
    "PTFS": "",
    "ARA": "",
    "TANGO": "",
    "SF": "",
    "KKCK": "",
    "SPTS": "",
}

# ── Flag emojis for timezone selection ────────────────────────────────────────
FLAG_EMOJIS = {
    "\U0001f1e6\U0001f1f7": "America/Argentina/Buenos_Aires",  # AR
    "\U0001f1f2\U0001f1fd": "America/Mexico_City",             # MX
    "\U0001f1ea\U0001f1f8": "Europe/Madrid",                   # ES
    "\U0001f1e8\U0001f1f1": "America/Santiago",                # CL
    "\U0001f1e8\U0001f1f4": "America/Bogota",                  # CO
    "\U0001f1f5\U0001f1ea": "America/Lima",                    # PE
    "\U0001f1fb\U0001f1ea": "America/Caracas",                 # VE
    "\U0001f1f5\U0001f1fe": "America/Asuncion",                # PY
    "\U0001f1fa\U0001f1fe": "America/Montevideo",              # UY
}

# ── Command prefix ────────────────────────────────────────────────────────────
COMMAND_PREFIX = "-"

# ── Performance score color thresholds ────────────────────────────────────────
# Fallback thresholds — dynamic thresholds come from tier_config.json.
PERFORMANCE_THRESHOLDS = [
    (0.70, "gold"),
    (0.55, "green"),
    (0.40, "blue"),
    (0.25, "orange"),
]
# Anything below 0.25 -> red


def performance_color(score: float, thresholds: dict | None = None):
    """Return a discord.Color based on the performance score.

    If *thresholds* is provided (from tier_config.json), it maps tier names
    to score boundaries and overrides the static PERFORMANCE_THRESHOLDS.
    """
    import discord
    if thresholds:
        ordered = [
            (thresholds.get("elite", 0.70), "gold"),
            (thresholds.get("veterano", 0.55), "green"),
            (thresholds.get("experimentado", 0.40), "blue"),
            (thresholds.get("soldado", 0.25), "orange"),
        ]
        for threshold, color_name in ordered:
            if score >= threshold:
                return getattr(discord.Color, color_name)()
        return discord.Color.red()
    for threshold, color_name in PERFORMANCE_THRESHOLDS:
        if score >= threshold:
            return getattr(discord.Color, color_name)()
    return discord.Color.red()


# ── Static page URLs ─────────────────────────────────────────────────────────
GITHUB_INDEX = BASE_URL
GITHUB_GUIDES = f"{BASE_URL}/#guias"
GITHUB_VISUALIZER_2D = f"{BASE_URL}/realitytracker.github.io/"

# ── Thumbnail ─────────────────────────────────────────────────────────────────
BOT_THUMBNAIL = f"{BASE_URL}/LDH_BOY2.png"

# ── Metric key mapping (user-facing name -> JSON key) ─────────────────────────
METRIC_KEY_MAP = {
    "performance": "Performance Score",
    "kd": "K/D Ratio",
    "kills": "Total Kills",
    "deaths": "Total Deaths",
    "rounds": "Rounds",
    "score": "Total Score",
}

# ── Valid categories for the top command (lowercase -> clan name) ──────────────
TOP_CATEGORIES = {
    "general": None,  # uses all_players_url()
    "ldh": "LDH",
    "sae": "SAE",
    "fi": "FI",
    "141": "141",
    "fi-r": "FI-R",
    "r-ldh": "R-LDH",
    "a-ldh": "A-LDH",
    "e-lam": "E-LAM",
    "300": "300",
    "rim-la": "RIM:LA",
    "adg": "ADG",
    "faso": "FASO",
    "porn": "PORN",
    "wd": "WD",
    "e-102": "E-102",
    "ptfs": "PTFS",
    "ara": "ARA",
    "tango": "TANGO",
    "sf": "SF",
    "kkck": "KKCK",
    "spts": "SPTS",
}

# ── Clan JSON URL map (uppercase) for sugerir_equipo ──────────────────────────
CLAN_JSON_MAP = {
    "LDH": json_url("LDH"),
    "SAE": json_url("SAE"),
    "FI": json_url("FI"),
    "FI-R": json_url("FI-R"),
    "141": json_url("141"),
    "R-LDH": json_url("R-LDH"),
    "A-LDH": json_url("A-LDH"),
    "WD": json_url("WD"),
    "300": json_url("300"),
    "E-LAM": json_url("E-LAM"),
    "RIM:LA": json_url("RIM:LA"),
    "ADG": json_url("ADG"),
    "FASO": json_url("FASO"),
    "PORN": json_url("PORN"),
    "E-102": json_url("E-102"),
    "PTFS": json_url("PTFS"),
    "ARA": json_url("ARA"),
    "TANGO": json_url("TANGO"),
    "SF": json_url("SF"),
    "KKCK": json_url("KKCK"),
    "SPTS": json_url("SPTS"),
}

# ── Graph alias mapping (command alias -> clan name) ──────────────────────────
# Used to register backward-compatible graficoldh, graficosae, etc.
GRAPH_ALIASES = {
    "graficoldh": "LDH",
    "graficosae": "SAE",
    "graficofi": "FI",
    "graficofi_r": "FI-R",
    "grafico141": "141",
    "graficor_ldh": "R-LDH",
    "graficoa_ldh": "A-LDH",
    "graficowd": "WD",
    "grafico300": "300",
    "graficoe_lam": "E-LAM",
    "graficorim_la": "RIM:LA",
    "graficoadg": "ADG",
    "graficofaso": "FASO",
    "graficoporn": "PORN",
    "graficoe_102": "E-102",
    "graficoptfs": "PTFS",
    "graficoara": "ARA",
    "graficotango": "TANGO",
    "graficosf": "SF",
    "graficokkck": "KKCK",
    "graficospts": "SPTS",
}
