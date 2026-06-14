"""HTTP fetcher with Cloudflare bypass, retries and exponential backoff."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

import cloudscraper

from .config import CLAN_URLS, MAX_RETRIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Shared thread pool for blocking cloudscraper calls
_executor = ThreadPoolExecutor(max_workers=4)


def _fetch_sync(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    """Fetch a URL using cloudscraper (bypasses Cloudflare)."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


async def _fetch_one(
    clan_name: str,
    url: str,
    loop: asyncio.AbstractEventLoop,
) -> tuple[str, str | None]:
    """Fetch a single clan page with exponential backoff retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d): %s", clan_name, attempt, MAX_RETRIES, url)
            html = await loop.run_in_executor(_executor, _fetch_sync, url)
            logger.info("Successfully fetched %s (%d bytes)", clan_name, len(html))
            return clan_name, html
        except Exception as exc:
            wait = 2 ** (attempt - 1)
            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %ds...",
                attempt,
                MAX_RETRIES,
                clan_name,
                exc,
                wait,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(wait)

    logger.error("All %d attempts failed for clan %s — skipping.", MAX_RETRIES, clan_name)
    return clan_name, None


async def fetch_all_clans(clan_urls: Dict[str, str] | None = None) -> Dict[str, str]:
    """Fetch HTML for all clans concurrently using cloudscraper.

    Uses a thread pool to run blocking cloudscraper calls in parallel
    (4 at a time to avoid rate limiting).
    """
    if clan_urls is None:
        clan_urls = CLAN_URLS

    loop = asyncio.get_running_loop()
    results: Dict[str, str] = {}

    tasks = [
        _fetch_one(name, url, loop)
        for name, url in clan_urls.items()
    ]
    completed = await asyncio.gather(*tasks)

    for clan_name, html in completed:
        if html is not None:
            results[clan_name] = html
        else:
            logger.warning("No data for clan %s", clan_name)

    logger.info("Fetched %d / %d clans successfully.", len(results), len(clan_urls))
    return results
