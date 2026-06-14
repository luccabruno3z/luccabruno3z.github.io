"""Auto-discover PR servers that host .PRdemo files for download.

Scrapes the prstats.realitymod.org server list, visits each server page
to find "Battle records" links, and verifies they point to directory
listings containing .PRdemo files.
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from urllib.parse import urljoin

import cloudscraper
from bs4 import BeautifulSoup

from .config import (
    DISCOVERED_SERVERS_FILE,
    PRSTATS_SERVERS_URL,
    REQUEST_TIMEOUT,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)

# Pattern for server page URLs on prstats
_SERVER_PAGE_RE = re.compile(r"/server/\d+/")

# Pattern for .PRdemo files in a directory listing
_DEMO_FILE_RE = re.compile(r"tracker_\d{4}_\d{2}_\d{2}_.*\.PRdemo")


def _create_scraper() -> cloudscraper.CloudScraper:
    """Create a cloudscraper instance matching the project convention."""
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )


def _fetch_text(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    """Fetch text content from a URL using cloudscraper."""
    scraper = _create_scraper()
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _discover_server_pages(html: str, base_url: str) -> list[dict]:
    """Parse the prstats servers page and return server info dicts.

    Each dict has keys: name, prstats_url.
    """
    soup = BeautifulSoup(html, "html.parser")
    servers = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if _SERVER_PAGE_RE.search(href):
            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)
            name = a.get_text(strip=True) or full_url
            servers.append({"name": name, "prstats_url": full_url})

    logger.info("Discovered %d server pages on prstats.", len(servers))
    return servers


def _find_battle_records_url(html: str, base_url: str) -> Optional[str]:
    """Find the 'Battle records' link on a server page.

    Returns the URL if found, None otherwise.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Look for links containing "battle record" text (case-insensitive)
    for a in soup.find_all("a", href=True):
        link_text = a.get_text(strip=True).lower()
        if "battle record" in link_text or "battlerecord" in link_text:
            return urljoin(base_url, a["href"])

    # Also check for links near labels or elements mentioning battle records
    for el in soup.find_all(string=re.compile(r"battle\s*record", re.IGNORECASE)):
        parent = el.find_parent()
        if parent:
            a = parent.find("a", href=True)
            if a:
                return urljoin(base_url, a["href"])

    return None


def _has_demo_files(html: str) -> bool:
    """Check whether an HTML directory listing contains .PRdemo files."""
    return bool(_DEMO_FILE_RE.search(html))


def _probe_server(server: dict) -> Optional[dict]:
    """Visit a server page, find its battle records URL, and verify demos.

    Returns a result dict with name, prstats_url, demo_url on success,
    or None if no valid demo directory is found.
    """
    name = server["name"]
    prstats_url = server["prstats_url"]

    try:
        page_html = _fetch_text(prstats_url)
    except Exception as exc:
        logger.debug("Failed to fetch server page %s: %s", name, exc)
        return None

    demo_url = _find_battle_records_url(page_html, prstats_url)
    if not demo_url:
        logger.debug("No battle records link found for %s", name)
        return None

    # Verify the URL points to a directory listing with .PRdemo files
    try:
        listing_html = _fetch_text(demo_url)
    except Exception as exc:
        logger.debug("Failed to fetch battle records for %s (%s): %s", name, demo_url, exc)
        return None

    if not _has_demo_files(listing_html):
        logger.debug("No .PRdemo files found at %s for %s", demo_url, name)
        return None

    logger.info("Found demo source: %s -> %s", name, demo_url)
    return {"name": name, "prstats_url": prstats_url, "demo_url": demo_url}


def discover_servers() -> Dict[str, dict]:
    """Discover PR servers with available .PRdemo files.

    Scrapes prstats, probes each server concurrently, and saves results
    to discovered_servers.json.

    Returns:
        Dict mapping server name to {prstats_url, demo_url}.
    """
    logger.info("Starting server discovery from %s", PRSTATS_SERVERS_URL)

    try:
        servers_html = _fetch_text(PRSTATS_SERVERS_URL)
    except Exception as exc:
        logger.error("Failed to fetch prstats servers page: %s", exc)
        return {}

    server_pages = _discover_server_pages(servers_html, PRSTATS_SERVERS_URL)
    if not server_pages:
        logger.warning("No server pages found on prstats.")
        return {}

    # Probe servers concurrently
    results: Dict[str, dict] = {}
    futures = []
    for server in server_pages:
        futures.append(_executor.submit(_probe_server, server))

    for future in futures:
        try:
            result = future.result(timeout=REQUEST_TIMEOUT * 2)
        except Exception as exc:
            logger.debug("Server probe timed out or failed: %s", exc)
            continue
        if result:
            results[result["name"]] = {
                "prstats_url": result["prstats_url"],
                "demo_url": result["demo_url"],
            }

    logger.info("Discovery complete: %d servers with demo files.", len(results))

    # Save to JSON
    _save_discovered(results)
    return results


def _save_discovered(servers: Dict[str, dict]) -> None:
    """Persist discovered servers to JSON file."""
    timestamp = datetime.now(
        timezone(timedelta(hours=-3))
    ).strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "servers": servers,
        "last_updated": timestamp,
    }

    os.makedirs(os.path.dirname(DISCOVERED_SERVERS_FILE), exist_ok=True)
    with open(DISCOVERED_SERVERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

    logger.info("Saved discovered servers to %s", DISCOVERED_SERVERS_FILE)


def load_discovered_servers() -> Optional[Dict[str, str]]:
    """Load discovered servers from JSON, returning {name: demo_url} or None.

    Returns None if the file doesn't exist or is invalid.
    """
    if not os.path.exists(DISCOVERED_SERVERS_FILE):
        return None

    try:
        with open(DISCOVERED_SERVERS_FILE) as f:
            data = json.load(f)
        servers = data.get("servers", {})
        if not servers:
            return None
        # Return {name: demo_url} for compatibility with DEMO_SERVERS format
        return {name: info["demo_url"] for name, info in servers.items()}
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to load discovered servers: %s", exc)
        return None
