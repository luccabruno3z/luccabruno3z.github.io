"""Robust HTML parsing for PR Stats clan pages."""

import logging
from typing import Any, Dict, List, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Expected minimum column count per row in the stats table
MIN_COLUMNS = 6


def convertir_valor(valor: str) -> int | None:
    """Convert a display value (with M/k suffixes) to an integer.

    Examples:
        "1.2M" -> 1200000
        "3.5k" -> 3500
        "1,234" -> 1234
    """
    try:
        if "M" in valor:
            return int(float(valor.replace("M", "")) * 1_000_000)
        elif "k" in valor:
            return int(float(valor.replace("k", "")) * 1_000)
        else:
            return int(valor.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_clan_html(
    html: str,
    clan_name: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse a clan's HTML page and extract player stats.

    Args:
        html: Raw HTML text of the clan page.
        clan_name: Name/tag of the clan (used in output dicts).

    Returns:
        Tuple of (list of player dicts, list of warning/error messages).
    """
    players: List[Dict[str, Any]] = []
    warnings: List[str] = []

    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.find("table")

    if tabla is None:
        msg = f"[{clan_name}] No table found in HTML."
        logger.error(msg)
        warnings.append(msg)
        return players, warnings

    filas = tabla.find_all("tr")[1:]  # skip header row

    if not filas:
        msg = f"[{clan_name}] Table found but contains no data rows."
        logger.warning(msg)
        warnings.append(msg)
        return players, warnings

    total_rows = len(filas)
    for row_idx, fila in enumerate(filas):
        columnas = fila.find_all("td")

        if len(columnas) < MIN_COLUMNS:
            is_last_row = (row_idx == total_rows - 1)
            msg = f"[{clan_name}] Row {row_idx}: expected >= {MIN_COLUMNS} columns, got {len(columnas)} — skipping."
            if is_last_row:
                logger.debug(msg)  # Last row is typically a totals/summary row
            else:
                logger.warning(msg)
                warnings.append(msg)
            continue

        try:
            player = columnas[1].text.strip()
            total_score = convertir_valor(columnas[2].text.strip())
            total_kills = convertir_valor(columnas[3].text.strip())
            total_deaths = convertir_valor(columnas[4].text.strip())
            rounds = convertir_valor(columnas[5].text.strip())

            # Validate parsed values
            if any(v is None for v in (total_score, total_kills, total_deaths, rounds)):
                msg = f"[{clan_name}] Row {row_idx} ({player}): failed to parse one or more numeric values — skipping."
                logger.warning(msg)
                warnings.append(msg)
                continue

            if rounds <= 0:
                msg = f"[{clan_name}] Row {row_idx} ({player}): rounds={rounds} <= 0 — skipping."
                logger.warning(msg)
                warnings.append(msg)
                continue

            # Handle division by zero: Deaths=0 -> K/D = kills value
            if total_deaths == 0:
                kd_ratio = float(total_kills)
            else:
                kd_ratio = total_kills / total_deaths

            score_per_round = total_score / rounds
            kills_per_round = total_kills / rounds

            players.append({
                "Player": player,
                "Clan": clan_name,
                "Total Score": total_score,
                "Total Kills": total_kills,
                "Total Deaths": total_deaths,
                "Rounds": rounds,
                "K/D Ratio": kd_ratio,
                "Score per Round": score_per_round,
                "Kills per Round": kills_per_round,
            })

        except (IndexError, TypeError) as exc:
            msg = f"[{clan_name}] Row {row_idx}: unexpected error — {exc}"
            logger.error(msg)
            warnings.append(msg)

    logger.info("[%s] Parsed %d players (%d warnings).", clan_name, len(players), len(warnings))
    return players, warnings
