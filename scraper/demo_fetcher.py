"""Crawler for downloading .PRdemo files from PR server websites."""

import asyncio
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import cloudscraper
from bs4 import BeautifulSoup

from .config import DEMO_SERVERS, HFS_DOWNLOAD_BASE, OUTPUT_DIR, MAX_RETRIES, REQUEST_TIMEOUT
from .server_discovery import load_discovered_servers

logger = logging.getLogger(__name__)

PROCESSED_FILE = os.path.join(OUTPUT_DIR, "demos", "processed.json")

_executor = ThreadPoolExecutor(max_workers=2)

# Match tracker .PRdemo files, skip .incomplete
_DEMO_RE = re.compile(r"tracker_\d{4}_\d{2}_\d{2}_.*\.PRdemo$")

BATCH_SIZE = 5  # Download and parse N demos at a time to limit memory


def _load_processed() -> Set[str]:
    """Load set of already-processed demo filenames."""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    return set()


def _save_processed(processed: Set[str]) -> None:
    """Persist the set of processed demo filenames."""
    os.makedirs(os.path.dirname(PROCESSED_FILE), exist_ok=True)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(sorted(processed), f)


def _fetch_sync(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes:
    """Fetch raw bytes from a URL using cloudscraper."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def _fetch_text_sync(url: str, timeout: int = REQUEST_TIMEOUT) -> str:
    """Fetch text from a URL using cloudscraper."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False},
    )
    resp = scraper.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _list_demos_from_directory(html: str, base_url: str) -> List[str]:
    """Parse a directory listing page and return full URLs to .PRdemo files.

    Handles three formats:
    1. Direct links to .PRdemo files (standard directory listing)
    2. Viewer links (realitytracker) with ?demo=REAL_URL parameter
    3. HFS JSON API responses ({"list": [{"n": "file.PRdemo", ...}]})
    """
    # Try parsing as HFS JSON API response first
    urls = _try_parse_hfs_json(html, base_url)
    if urls:
        return urls

    # Fall back to HTML parsing
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "incomplete" in href.lower():
            continue
        if not _DEMO_RE.search(href):
            continue

        # Check if this is a viewer URL with ?demo= parameter
        parsed = urlparse(href)
        demo_param = parse_qs(parsed.query).get("demo", [None])[0]
        if demo_param and _DEMO_RE.search(demo_param):
            real_url = demo_param
        else:
            real_url = urljoin(base_url, href)

        if real_url not in seen:
            seen.add(real_url)
            urls.append(real_url)
    return urls


def _try_parse_hfs_json(text: str, base_url: str) -> List[str]:
    """Try to parse an HFS JSON API response for demo file listings.

    HFS 3.x returns: {"list": [{"n": "filename.PRdemo", "s": 12345, ...}]}
    Returns list of download URLs, or empty list if not HFS JSON.
    """
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []

    if not isinstance(data, dict) or "list" not in data:
        return []

    # Strip HFS API query params to get the directory URL for downloads
    clean_base = base_url.split("?")[0]
    if not clean_base.endswith("/"):
        clean_base += "/"

    urls = []
    seen = set()
    for entry in data["list"]:
        name = entry.get("n", "")
        if not name or "incomplete" in name.lower():
            continue
        # Skip subdirectories (end with /)
        if name.endswith("/"):
            continue
        if not _DEMO_RE.search(name):
            continue
        url = clean_base + name
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _is_transient(exc: Exception) -> bool:
    """True para errores recuperables: 429/5xx o timeouts/cortes de conexión.

    Servidores de demos caseros (HFS, IP pelada) devuelven 503 al recibir varias
    descargas a la vez; reintentar con backoff recupera la mayoría."""
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) in (429, 500, 502, 503, 504):
        return True
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


async def _fetch_one_demo(
    url: str,
    loop: asyncio.AbstractEventLoop,
) -> Tuple[str, Optional[bytes]]:
    """Download a single demo file with backoff retries on transient errors.

    Failed demos are not marked as processed and will be retried next run.
    """
    filename = url.rsplit("/", 1)[-1]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            suffix = "" if attempt == 1 else f" (intento {attempt}/{MAX_RETRIES})"
            logger.info("Downloading %s%s", filename, suffix)
            data = await loop.run_in_executor(_executor, _fetch_sync, url)
            logger.info("Downloaded %s (%d bytes)", filename, len(data))
            return filename, data
        except Exception as exc:
            if _is_transient(exc) and attempt < MAX_RETRIES:
                await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s, …
                continue
            logger.warning("Failed to download %s: %s — skipping.", filename, exc)
            return filename, None
    return filename, None


def get_new_demo_urls() -> List[str]:
    """Discover new demo URLs that haven't been processed yet.

    Returns list of direct download URLs for new demos.
    """
    processed = _load_processed()

    servers = load_discovered_servers()
    if servers:
        logger.info("Using %d discovered servers.", len(servers))
    else:
        servers = {}

    # Merge in fallback/static servers (skip if same URL already discovered)
    discovered_urls = set(servers.values())
    for name, url in DEMO_SERVERS.items():
        if name not in servers and url not in discovered_urls:
            servers[name] = url
    logger.info("Total servers to scan: %d", len(servers))

    all_new_urls = []
    deferred_urls = []  # hosts flaky/rate-limited → al final, no acaparan el cupo/run

    for server_name, base_url in servers.items():
        logger.info("Scanning %s: %s", server_name, base_url)

        try:
            # HFS servers may respond slowly with large file lists; use longer timeout
            timeout = 60 if server_name in HFS_DOWNLOAD_BASE else REQUEST_TIMEOUT
            html = _fetch_text_sync(base_url, timeout=timeout)
        except Exception as exc:
            logger.error("Failed to list demos for %s: %s", server_name, exc)
            continue

        # For HFS servers, use the download base URL instead of the API URL
        download_base = HFS_DOWNLOAD_BASE.get(server_name, base_url)
        demo_urls = _list_demos_from_directory(html, download_base)
        logger.info("Found %d demo files on %s", len(demo_urls), server_name)

        new_urls = [u for u in demo_urls if u.rsplit("/", 1)[-1] not in processed]
        logger.info("%d new demos from %s", len(new_urls), server_name)
        host = urlparse(base_url).hostname or ""
        (deferred_urls if host in _LOW_PRIORITY_HOSTS else all_new_urls).extend(new_urls)

    # Servidores confiables primero; los flaky (p.ej. ARES, que rate-limitea con
    # 503) al final, así no consumen el límite por-run con demos que mayormente
    # fallan y bloquean el backlog valioso (AAS de LATAMSQUAD).
    return all_new_urls + deferred_urls


# Hosts que se atragantan con descargas concurrentes (devuelven 503/timeout) y
# deben bajarse de a una. ARES Brasil (IP pelada, HTTP) fue agregado tras ver 503
# en masa al pedirle 5 demos a la vez.
_SEQUENTIAL_HOSTS = {"latamsquad.dev", "82.38.28.159"}

# Hosts que rate-limitean fuerte (503 incluso secuencial + reintentos). Se difieren
# al final de la cola para que no acaparen el límite por-run; sus demos (en su
# mayoría gungame, bajo valor) se intentan solo si sobra cupo.
_LOW_PRIORITY_HOSTS = {"82.38.28.159"}


async def fetch_demo_batch(urls: List[str]) -> List[Tuple[str, bytes]]:
    """Download a batch of demos. Returns list of (filename, bytes) for successes.

    URLs from throttle-prone hosts are downloaded sequentially (one at a time)
    to avoid connection timeouts. Other URLs are downloaded in parallel.
    """
    loop = asyncio.get_running_loop()

    sequential = [u for u in urls if urlparse(u).hostname in _SEQUENTIAL_HOSTS]
    parallel = [u for u in urls if urlparse(u).hostname not in _SEQUENTIAL_HOSTS]

    results = []

    # Parallel downloads for standard servers
    if parallel:
        tasks = [_fetch_one_demo(url, loop) for url in parallel]
        results.extend(await asyncio.gather(*tasks))

    # Sequential downloads for throttle-prone servers
    for url in sequential:
        result = await _fetch_one_demo(url, loop)
        results.append(result)

    return [(fname, data) for fname, data in results if data is not None]


def mark_processed(filenames: List[str]) -> None:
    """Add filenames to the processed set and save."""
    processed = _load_processed()
    processed.update(filenames)
    _save_processed(processed)
