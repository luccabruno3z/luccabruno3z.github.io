"""HTTP fetcher with Cloudflare bypass, retries and exponential backoff."""

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import cloudscraper
from bs4 import BeautifulSoup

from .config import CLAN_URLS, MAX_RETRIES, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

# Shared thread pool for blocking cloudscraper calls
_executor = ThreadPoolExecutor(max_workers=4)

# prstats clan rosters paginate at 50 members/page and expose the rest via a
# `?page=N` pagination block (`<ul class="pagination">`). We must follow it or we
# only ever see the top 50.
_PAGE_RE = re.compile(r"[?&]page=(\d+)")
_MAX_PAGES = 50  # safety cap against malformed pagination


def _max_page(html: str) -> int:
    """Highest page number from the roster's pagination control (>=1).

    Scoped to the `<ul class="pagination">` block on purpose: scanning the whole
    document for `?page=N` would pick up unrelated links and request out-of-range
    pages (prstats returns HTTP 500 for those, now retried, so the waste matters).
    """
    soup = BeautifulSoup(html, "html.parser")
    pager = soup.select_one("ul.pagination") or soup.select_one(".pagination")
    if pager is None:
        return 1
    pages = [int(m) for a in pager.find_all("a")
             for m in _PAGE_RE.findall(a.get("href", ""))]
    return min(max(pages, default=1), _MAX_PAGES)


def _page_url(url: str, page: int) -> str:
    """Append `page=N`, respecting any query string already on the base URL."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}page={page}"


def _fetch_sync(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    """Fetch a URL using cloudscraper (bypasses Cloudflare)."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


async def _fetch_page(
    label: str,
    url: str,
    loop: asyncio.AbstractEventLoop,
) -> str | None:
    """Fetch one URL with exponential backoff retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d): %s", label, attempt, MAX_RETRIES, url)
            html = await loop.run_in_executor(_executor, _fetch_sync, url)
            logger.info("Successfully fetched %s (%d bytes)", label, len(html))
            return html
        except Exception as exc:
            wait = 2 ** (attempt - 1)
            logger.warning(
                "Attempt %d/%d failed for %s: %s. Retrying in %ds...",
                attempt, MAX_RETRIES, label, exc, wait,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(wait)

    logger.error("All %d attempts failed for %s — skipping.", MAX_RETRIES, label)
    return None


async def _fetch_one(
    clan_name: str,
    url: str,
    loop: asyncio.AbstractEventLoop,
) -> tuple[str, List[str] | None]:
    """Fetch all paginated pages of a clan roster. Returns (clan, [html, ...])."""
    first = await _fetch_page(clan_name, url, loop)
    if first is None:
        return clan_name, None

    pages = [first]
    total = _max_page(first)
    missing = 0
    for pg in range(2, total + 1):
        html = await _fetch_page(f"{clan_name} p{pg}", _page_url(url, pg), loop)
        if html:
            pages.append(html)
        else:
            missing += 1

    if total > 1:
        if missing:
            # A dropped page silently truncates the roster (~50 members). Surface
            # it loudly rather than reporting an incomplete roster as complete.
            logger.error(
                "[%s] INCOMPLETE roster: fetched %d/%d pages (%d failed).",
                clan_name, len(pages), total, missing,
            )
        else:
            logger.info("[%s] fetched %d/%d pages.", clan_name, len(pages), total)
    return clan_name, pages


async def fetch_all_clans(clan_urls: Dict[str, str] | None = None) -> Dict[str, List[str]]:
    """Fetch every clan's full (paginated) roster concurrently.

    Returns a mapping of clan name -> list of page HTMLs. Uses a thread pool to
    run blocking cloudscraper calls in parallel (4 at a time to avoid rate limiting).
    """
    if clan_urls is None:
        clan_urls = CLAN_URLS

    loop = asyncio.get_running_loop()
    results: Dict[str, List[str]] = {}

    tasks = [
        _fetch_one(name, url, loop)
        for name, url in clan_urls.items()
    ]
    completed = await asyncio.gather(*tasks)

    for clan_name, pages in completed:
        if pages:
            results[clan_name] = pages
        else:
            logger.warning("No data for clan %s", clan_name)

    logger.info("Fetched %d / %d clans successfully.", len(results), len(clan_urls))
    return results
