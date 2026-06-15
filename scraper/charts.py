"""Plotly chart generation styled to match the site's dark/cyan esports theme.

Charts are exported as full-bleed dark HTML (CDN-based plotly.js) so they blend
seamlessly into the surrounding dark site with no white flash around the plot.

This is the ACTIVE chart pipeline, used by `scraper/main.py`. The standalone
`graphs/PRstats_multiclans.py` is a legacy duplicate kept consistent with this.
"""

import logging
import os
from typing import Dict

import pandas as pd
import plotly.express as px

from .config import CLAN_URLS, GITHUB_PAGES_URL, OUTPUT_DIR

logger = logging.getLogger(__name__)

# ── Site theme palette ───────────────────────────────────────────────────────
THEME_BG = "#0a0a0f"           # site background
THEME_SURFACE = "#0f0f19"      # surface / panels
THEME_CYAN = "#00FFFF"         # primary accent
THEME_ORANGE = "#FFA500"       # secondary accent
THEME_GREEN = "#00FF88"        # success
THEME_TEXT = "#ffffff"         # text
THEME_MUTED = "#a0a0b0"        # muted text
THEME_GRID = "rgba(255, 255, 255, 0.08)"
THEME_ZERO = "rgba(255, 255, 255, 0.18)"

# Discrete color sequence for categorical marks (cyan / orange / green ...)
COLOR_SEQUENCE = [THEME_CYAN, THEME_ORANGE, THEME_GREEN, "#FF4D6D", "#9D4EDD", "#FFD60A"]

# Continuous colorscale for Performance Score: deep navy -> cyan -> green.
# Reads as "low -> high" on a dark background while staying on-brand.
PERFORMANCE_COLORSCALE = [
    [0.0, "#0b3d4d"],
    [0.45, "#0c93a8"],
    [0.7, THEME_CYAN],
    [1.0, THEME_GREEN],
]

# Back button + body styling injected after Plotly's HTML so the page is
# full-bleed dark (no white margin/flash) and matches the site chrome.
HTML_HEAD_INJECT = f'''
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    height: 100%;
    background-color: {THEME_BG};
    color: {THEME_TEXT};
    font-family: 'Roboto', sans-serif;
    overflow: hidden;
  }}
  .plotly-graph-div {{ background-color: {THEME_BG}; }}
  .pr-back-btn {{
    position: fixed;
    top: 18px;
    left: 18px;
    z-index: 1000;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 42px;
    height: 42px;
    background: {THEME_CYAN};
    color: #000;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 700;
    box-shadow: 0 0 12px rgba(0, 255, 255, 0.45);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }}
  .pr-back-btn:hover {{
    transform: translateY(-2px);
    box-shadow: 0 0 18px rgba(0, 255, 255, 0.7);
  }}
</style>
'''

HTML_BACK_BUTTON = f'''
<a class="pr-back-btn" href="{GITHUB_PAGES_URL}" title="Volver">
    <i class="fas fa-arrow-left"></i>
</a>
'''


def _apply_dark_theme(fig, colorbar_title: str = "Performance Score") -> None:
    """Apply the site's dark/cyan theme on top of the plotly_dark template."""
    fig.update_traces(
        marker=dict(
            line=dict(width=1, color="rgba(0, 0, 0, 0.6)"),
            opacity=0.9,
        ),
    )
    fig.update_layout(
        title=dict(
            font=dict(size=26, color=THEME_CYAN, family="Bebas Neue"),
            x=0.5,
            xanchor="center",
        ),
        font=dict(color=THEME_TEXT, family="Roboto"),
        paper_bgcolor=THEME_BG,
        plot_bgcolor=THEME_BG,
        colorway=COLOR_SEQUENCE,
        margin=dict(l=70, r=40, t=80, b=60),
        hoverlabel=dict(
            bgcolor=THEME_SURFACE,
            bordercolor=THEME_CYAN,
            font=dict(color=THEME_TEXT, family="Roboto", size=13),
        ),
        legend=dict(
            bgcolor="rgba(15, 15, 25, 0.8)",
            bordercolor="rgba(0, 255, 255, 0.3)",
            borderwidth=1,
            font=dict(color=THEME_TEXT, family="Roboto"),
        ),
        xaxis=dict(
            gridcolor=THEME_GRID,
            zerolinecolor=THEME_ZERO,
            linecolor="rgba(255, 255, 255, 0.15)",
            title_font=dict(size=16, color=THEME_CYAN, family="Roboto"),
            tickfont=dict(size=12, color=THEME_MUTED, family="Roboto"),
        ),
        yaxis=dict(
            gridcolor=THEME_GRID,
            zerolinecolor=THEME_ZERO,
            linecolor="rgba(255, 255, 255, 0.15)",
            title_font=dict(size=16, color=THEME_CYAN, family="Roboto"),
            tickfont=dict(size=12, color=THEME_MUTED, family="Roboto"),
        ),
        coloraxis=dict(
            colorscale=PERFORMANCE_COLORSCALE,
            colorbar=dict(
                title=dict(
                    text=colorbar_title,
                    font=dict(size=14, color=THEME_CYAN, family="Roboto"),
                ),
                tickfont=dict(size=11, color=THEME_MUTED, family="Roboto"),
                outlinewidth=0,
                bgcolor="rgba(0,0,0,0)",
            ),
        ),
    )


def _add_top_annotations(fig, df: pd.DataFrame, n: int = 3) -> None:
    """Annotate the top N players by Performance Score with on-theme labels."""
    top = df.nlargest(n, "Performance Score")
    for _, row in top.iterrows():
        fig.add_annotation(
            x=row["K/D Ratio"],
            y=row["Score per Round"],
            text=f"⭐ {row['Player']}",
            showarrow=True,
            arrowhead=2,
            arrowcolor=THEME_CYAN,
            arrowwidth=1.5,
            ax=0,
            ay=-32,
            font=dict(color="#000000", size=12, family="Roboto"),
            bgcolor=THEME_CYAN,
            bordercolor=THEME_CYAN,
            borderpad=4,
            opacity=0.95,
        )


def _build_scatter(df: pd.DataFrame, title: str, include_clan: bool):
    """Build the styled performance scatter (Score/Round vs K/D, sized by Rounds).

    Hover shows player (and clan, for the global chart) plus key stats.
    """
    custom_cols = ["Player", "Rounds", "Total Kills", "Total Deaths", "Kills per Round"]
    if include_clan:
        custom_cols.insert(1, "Clan")

    fig = px.scatter(
        df,
        x="K/D Ratio",
        y="Score per Round",
        size="Rounds",
        size_max=42,
        color="Performance Score",
        custom_data=custom_cols,
        title=title,
        template="plotly_dark",
        labels={
            "K/D Ratio": "K/D Ratio",
            "Score per Round": "Puntuación por Ronda",
            "Performance Score": "Performance Score",
        },
    )

    if include_clan:
        hovertemplate = (
            "<b>%{customdata[0]}</b>  <span style='color:#a0a0b0'>[%{customdata[1]}]</span><br>"
            "<br>"
            "K/D Ratio: <b>%{x:.2f}</b><br>"
            "Puntuación/Ronda: <b>%{y:.0f}</b><br>"
            "Performance: <b>%{marker.color:.3f}</b><br>"
            "Rondas: <b>%{customdata[2]:,}</b><br>"
            "Kills / Deaths: <b>%{customdata[3]:,} / %{customdata[4]:,}</b><br>"
            "Kills/Ronda: <b>%{customdata[5]:.2f}</b>"
            "<extra></extra>"
        )
    else:
        hovertemplate = (
            "<b>%{customdata[0]}</b><br>"
            "<br>"
            "K/D Ratio: <b>%{x:.2f}</b><br>"
            "Puntuación/Ronda: <b>%{y:.0f}</b><br>"
            "Performance: <b>%{marker.color:.3f}</b><br>"
            "Rondas: <b>%{customdata[1]:,}</b><br>"
            "Kills / Deaths: <b>%{customdata[2]:,} / %{customdata[3]:,}</b><br>"
            "Kills/Ronda: <b>%{customdata[4]:.2f}</b>"
            "<extra></extra>"
        )

    fig.update_traces(hovertemplate=hovertemplate)
    return fig


def _write_chart(fig, filepath: str) -> None:
    """Write full-bleed dark chart HTML using CDN plotly.js."""
    html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displaylogo": False},
    )
    # Inject fonts + dark body styling into <head>, and the back button into <body>.
    html = html.replace("</head>", HTML_HEAD_INJECT + "</head>", 1)
    html = html.replace("<body>", "<body>" + HTML_BACK_BUTTON, 1)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Chart saved: %s", filepath)


def generate_all_players_chart(df: pd.DataFrame) -> None:
    """Generate the all-players performance scatter chart."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig = _build_scatter(
        df,
        title="Desempeño General · Todos los Jugadores",
        include_clan=True,
    )
    _apply_dark_theme(fig)
    _add_top_annotations(fig, df)
    _write_chart(fig, os.path.join(OUTPUT_DIR, "all_players_interactive_chart.html"))


def generate_clan_charts(df: pd.DataFrame, clan_names: Dict[str, str] | None = None) -> None:
    """Generate per-clan performance scatter charts.

    Args:
        df: Full DataFrame with all players.
        clan_names: Optional dict of clan names; defaults to config CLAN_URLS keys.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if clan_names is None:
        clan_names = CLAN_URLS

    for clan_name in clan_names:
        df_clan = df[df["Clan"] == clan_name]
        if df_clan.empty:
            logger.warning("No data for clan %s — skipping chart.", clan_name)
            continue

        fig = _build_scatter(
            df_clan,
            title=f"Clan {clan_name} · Desempeño de Jugadores",
            include_clan=False,
        )
        _apply_dark_theme(fig)
        _add_top_annotations(fig, df_clan)
        _write_chart(fig, os.path.join(OUTPUT_DIR, f"{clan_name}_interactive_chart.html"))
