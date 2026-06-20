"""Async HTTP client with TTL-based in-memory cache and retry logic."""

import asyncio
import logging
import time

import aiohttp

from bot.config import (
    all_players_url,
    json_url,
    clan_averages_url,
    demo_player_details_url,
    demo_round_history_url,
    demo_leaderboard_url,
    demo_map_stats_url,
    demo_synergy_url,
    tier_config_url,
)

logger = logging.getLogger(__name__)


class DataFetcher:
    """Cached async HTTP client for fetching JSON data from GitHub Pages.

    Attributes:
        ttl: Cache time-to-live in seconds (default 300).
        timeout: Per-request timeout in seconds (default 10).
        max_retries: Maximum retry attempts on failure (default 3).
    """

    def __init__(self, ttl: int = 300, timeout: int = 10, max_retries: int = 3):
        self.ttl = ttl
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._cache: dict[str, tuple[float, object]] = {}
        self._session: aiohttp.ClientSession | None = None

    # ── Session lifecycle ─────────────────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def get_session(self) -> aiohttp.ClientSession:
        """Public access to the underlying aiohttp session."""
        return await self._get_session()

    async def close(self) -> None:
        """Close the underlying aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Core fetch with retry ──────────────────────────────────────────────

    async def fetch_json(self, url: str, *, use_stale_on_error: bool = True):
        """Fetch JSON from *url*, returning cached data when fresh.

        On network failure, retries with exponential backoff.
        If all retries fail and use_stale_on_error is True, returns stale cache.
        """
        now = time.monotonic()
        cached = self._cache.get(url)
        if cached is not None:
            ts, data = cached
            if now - ts < self.ttl:
                return data

        last_error = None
        for attempt in range(self.max_retries):
            try:
                session = await self._get_session()
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)

                self._cache[url] = (now, data)
                return data

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_error = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(
                    "Fetch attempt %d/%d failed for %s: %s. Retrying in %ds...",
                    attempt + 1, self.max_retries, url, e, wait,
                )
                await asyncio.sleep(wait)

        # All retries failed — try stale cache
        if use_stale_on_error and cached is not None:
            logger.warning("All retries failed for %s. Using stale cache.", url)
            return cached[1]

        raise last_error  # type: ignore[misc]

    # ── Pre-cache (for background refresh) ─────────────────────────────────

    async def pre_cache(self) -> None:
        """Pre-fetch common endpoints to warm the cache."""
        urls = [all_players_url(), clan_averages_url()]
        for url in urls:
            try:
                await self.fetch_json(url)
                logger.info("Pre-cached %s", url)
            except Exception as e:
                logger.warning("Failed to pre-cache %s: %s", url, e)

    # ── Convenience methods ───────────────────────────────────────────────

    async def fetch_all_players(self):
        """Fetch the all-players cluster JSON."""
        return await self.fetch_json(all_players_url())

    async def fetch_clan_players(self, clan: str):
        """Fetch the players JSON for a specific clan."""
        return await self.fetch_json(json_url(clan))

    async def fetch_clan_averages(self):
        """Fetch the clan averages JSON."""
        return await self.fetch_json(clan_averages_url())

    # ── Demo-based detailed stats ────────────────────────────────────────

    async def fetch_player_details(self):
        """Fetch the aggregated player details JSON (from demos)."""
        return await self.fetch_json(demo_player_details_url())

    async def fetch_synergy(self):
        """Fetch the duo-synergy JSON (from demos)."""
        return await self.fetch_json(demo_synergy_url())

    async def fetch_round_history(self):
        """Fetch the round history JSON (from demos).

        Deprecated: kept for backward compatibility. Prefer fetch_leaderboard(),
        which returns a tiny precomputed file instead of the full round history.
        """
        return await self.fetch_json(demo_round_history_url())

    async def fetch_leaderboard(self, periodo: str):
        """Fetch a precomputed period leaderboard (dia/semana/mes/todo).

        Returns a dict ``{period, days, generated_at, total_rounds, players}``
        where each player has kills/deaths/score/rounds/revives/teamwork_score.
        """
        return await self.fetch_json(demo_leaderboard_url(periodo))

    async def fetch_map_stats(self):
        """Fetch the map statistics JSON (from demos)."""
        return await self.fetch_json(demo_map_stats_url())

    async def fetch_tier_config(self):
        """Fetch the tier configuration JSON (dynamic thresholds, predictor weights)."""
        return await self.fetch_json(tier_config_url())

    # ── Combined data ─────────────────────────────────────────────────────

    async def fetch_player_combined(self, player_name: str) -> dict:
        """Merge prstats data with demo data for a player.

        Returns a dict with keys from both sources. If one source fails or
        the player is not found in it, returns partial data from the other.
        """
        result: dict = {}
        name_lower = player_name.lower()

        # Try prstats
        try:
            all_players = await self.fetch_all_players()
            if isinstance(all_players, list):
                for p in all_players:
                    if p.get("Player", "").lower() == name_lower:
                        result.update(p)
                        break
                else:
                    # Fallback: partial/contains match
                    for p in all_players:
                        if name_lower in p.get("Player", "").lower():
                            result.update(p)
                            break
        except Exception:
            logger.warning("fetch_player_combined: prstats fetch failed for '%s'", player_name)

        # Try demos — demo data uses "ign" as the player name key
        try:
            demo_data = await self.fetch_player_details()
            if isinstance(demo_data, list):
                matched = None
                for entry in demo_data:
                    ign = entry.get("ign", entry.get("Player", ""))
                    if ign.lower() == name_lower:
                        matched = entry
                        break
                if matched is None:
                    for entry in demo_data:
                        ign = entry.get("ign", entry.get("Player", ""))
                        if name_lower in ign.lower():
                            matched = entry
                            break
                if matched:
                    for k, v in matched.items():
                        result[f"demo_{k}"] = v
        except Exception:
            logger.warning("fetch_player_combined: demo fetch failed for '%s'", player_name)

        return result
