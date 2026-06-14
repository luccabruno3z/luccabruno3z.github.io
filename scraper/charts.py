"""Plotly chart generation with dark theme and CDN-based plotly.js."""

import logging
import os
from typing import Dict

import pandas as pd
import plotly.express as px

from .config import CLAN_URLS, GITHUB_PAGES_URL, OUTPUT_DIR

logger = logging.getLogger(__name__)

# Back button HTML with Font Awesome icon
HTML_BACK_BUTTON = f'''
<div style="position: absolute; top: 20px; left: 20px;">
    <a href="{GITHUB_PAGES_URL}" style="padding: 10px 20px; background-color: #00FFFF; color: #000; text-decoration: none; border-radius: 5px; font-weight: bold;">
        <i class="fas fa-arrow-left"></i>
    </a>
</div>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
'''


def _apply_dark_theme(fig) -> None:
    """Apply the standard dark theme to a plotly figure."""
    fig.update_layout(
        title_font=dict(size=24, color="#00FFFF", family="Bebas Neue"),
        font=dict(color="#00FFFF", family="Roboto"),
        paper_bgcolor="#121212",
        plot_bgcolor="#121212",
        xaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.1)",
            title_font=dict(size=18, color="#00FFFF", family="Roboto"),
            tickfont=dict(size=12, color="#FFFFFF", family="Roboto"),
        ),
        yaxis=dict(
            gridcolor="rgba(255, 255, 255, 0.1)",
            title_font=dict(size=18, color="#00FFFF", family="Roboto"),
            tickfont=dict(size=12, color="#FFFFFF", family="Roboto"),
        ),
        coloraxis_colorbar=dict(
            title="Performance Score",
            title_font=dict(size=16, color="#00FFFF", family="Roboto"),
            tickfont=dict(size=12, color="#FFFFFF", family="Roboto"),
            bgcolor="#121212",
        ),
    )


def _add_top_annotations(fig, df: pd.DataFrame, n: int = 3) -> None:
    """Annotate the top N players by Performance Score."""
    top = df.nlargest(n, "Performance Score")
    for _, row in top.iterrows():
        fig.add_annotation(
            x=row["K/D Ratio"],
            y=row["Score per Round"],
            text=f"Top Player: {row['Player']}",
            showarrow=True,
            arrowhead=1,
            ax=-10,
            ay=-10,
            font=dict(color="#000000", size=12, family="Roboto"),
            bgcolor="#00FFFF",
        )


def _write_chart(fig, filepath: str) -> None:
    """Write chart HTML using CDN plotly.js and append back button."""
    fig.write_html(filepath, include_plotlyjs="cdn")
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(HTML_BACK_BUTTON)
    logger.info("Chart saved: %s", filepath)


def generate_all_players_chart(df: pd.DataFrame) -> None:
    """Generate the all-players scatter chart."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    fig = px.scatter(
        df,
        x="K/D Ratio",
        y="Score per Round",
        size="Kills per Round",
        hover_name=df.apply(lambda row: f"{row['Player']} ({row['Clan']})", axis=1),
        color="Performance Score",
        title="Desempeño General de Todos los Jugadores (Basado en Performance Score)",
        template="plotly_dark",
        labels={
            "K/D Ratio": "K/D Ratio",
            "Score per Round": "Puntuación por Ronda",
            "Kills per Round": "Asesinatos por Ronda",
            "Performance Score": "Puntuación de Desempeño",
        },
    )

    _apply_dark_theme(fig)
    _add_top_annotations(fig, df)
    _write_chart(fig, os.path.join(OUTPUT_DIR, "all_players_interactive_chart.html"))


def generate_clan_charts(df: pd.DataFrame, clan_names: Dict[str, str] | None = None) -> None:
    """Generate per-clan scatter charts.

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

        fig = px.scatter(
            df_clan,
            x="K/D Ratio",
            y="Score per Round",
            size="Kills per Round",
            hover_name="Player",
            color="Performance Score",
            title=f"Gráfico Interactivo del Clan {clan_name}",
            template="plotly_dark",
            labels={
                "K/D Ratio": "K/D Ratio",
                "Score per Round": "Puntuación por Ronda",
                "Kills per Round": "Asesinatos por Ronda",
                "Performance Score": "Puntuación de Desempeño",
            },
        )

        _apply_dark_theme(fig)
        _add_top_annotations(fig, df_clan)
        _write_chart(fig, os.path.join(OUTPUT_DIR, f"{clan_name}_interactive_chart.html"))
