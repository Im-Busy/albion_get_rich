"""
Scrapling-based Cloudflare bypass source — replaces 4-tier bypass engine with
a single StealthyFetcher that handles CF natively (curl_cffi TLS impersonation
+ headless Chromium + built-in Turnstile solving).

Advantages over CloudflareBypass:
- Single call instead of 4-tier escalation
- Adaptive element tracking survives albiononline2d.com redesigns
- 12-784x faster parsing than BeautifulSoup
- Built-in session management with cookie persistence

Usage:
    source = ScraplingSource()
    html = await source.fetch("https://albiononline2d.com/en/map")
    zones = source.parse_zones(html)  # adaptive CSS selects
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

try:
    from scrapling.fetchers import StealthyFetcher

    HAS_SCRAPLING = True
except ImportError:
    HAS_SCRAPLING = False
    StealthyFetcher = None

logger = logging.getLogger("albion.scrapling_source")

CACHE_DIR = Path(__file__).parent.parent / ".cf_cache"
CACHE_DIR.mkdir(exist_ok=True)


class ScraplingSource:
    """
    Drop-in alternative to CloudflareBypass using Scrapling's StealthyFetcher.

    Handles Cloudflare Turnstile, browser fingerprinting, and TLS impersonation
    in a single call — no tiered escalation needed.

    Adaptive mode (default on): when albiononline2d.com changes HTML structure,
    CSS selectors automatically relocate to similar elements.
    """

    def __init__(self, adaptive: bool = True):
        if not HAS_SCRAPLING:
            raise ImportError(
                "Scrapling not installed. Run: uv add scrapling"
            )
        self._adaptive = adaptive
        if adaptive:
            StealthyFetcher.adaptive = True
        self._session = None

    async def fetch(
        self,
        url: str,
        headless: bool = True,
        network_idle: bool = True,
        timeout: int = 30000,
    ) -> dict:
        """
        Fetch a URL through Cloudflare with anti-bot stealth.

        Returns dict with keys: status_code, html, source, cookies
        """
        try:
            resp = await StealthyFetcher.async_fetch(
                url,
                headless=headless,
                network_idle=network_idle,
                solve_cloudflare=True,
                timeout=timeout,
            )
            return {
                "status_code": resp.status,
                "html": resp.html_content,
                "source": "scrapling",
                "cookies": resp.cookies,
            }
        except Exception as e:
            logger.error("Scrapling fetch failed for %s: %s", url, e)
            return {
                "status_code": 403,
                "html": "",
                "source": "scrapling_failed",
                "error": str(e),
            }

    def fetch_sync(self, url: str, **kwargs) -> dict:
        """Synchronous wrapper for non-async contexts."""
        return asyncio.run(self.fetch(url, **kwargs))

    def parse_zones(self, html: str) -> list[dict]:
        """
        Parse zone data from albiononline2d.com HTML.
        Uses adaptive selectors that survive site redesigns.
        """
        from scrapling.engines.toolbelt.custom import Response  # noqa: F811

        resp = Response(html)
        zones = []
        for row in resp.css(".zone-row", adaptive=self._adaptive):
            try:
                zone = {
                    "name": row.css(".zone-name", adaptive=self._adaptive).text,
                    "connections": self._parse_connections(row),
                }
                zones.append(zone)
            except Exception:
                continue
        return zones

    def _parse_connections(self, row) -> list[str]:
        """Extract connected zone names from a zone row."""
        connected = row.css(".zone-connection", adaptive=self._adaptive)
        return [c.text for c in connected]

    def extract_links(self, html: str, selector: str = "a") -> list[dict]:
        """Extract all links with text and href from HTML."""
        from scrapling.engines.toolbelt.custom import Response

        resp = Response(html)
        links = []
        for el in resp.css(selector):
            href = el.attrib.get("href", "")
            if href:
                links.append({"text": el.text, "href": href})
        return links


def has_scrapling() -> bool:
    return HAS_SCRAPLING
