"""
Zone Data Sources — Abstract interface with live CF bypass and static JSON fallback.

Priority: Live Albion2D (CF bypass) → Static extracted JSON.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("data_sources.zone")


@dataclass
class Zone:
    id: int
    name: str
    file: str
    zone_type: int
    layer: int
    x: float
    y: float
    connections: list[int]
    source: str = ""


class ZoneDataSource(ABC):
    """Abstract base for zone/map data sources."""

    @abstractmethod
    async def get_zones(self) -> list[Zone]: ...

    @abstractmethod
    async def get_connections(self) -> dict[int, list[int]]:
        """Return zone ID → list of connected zone IDs."""
        ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def is_live(self) -> bool:
        return False


class Albion2DZoneSource(ZoneDataSource):
    """
    Live source: fetches zone data from albiononline2d.com via Cloudflare bypass.
    """

    def __init__(self, cf_bypass=None):
        self._bypass = cf_bypass
        self._zones: Optional[list[Zone]] = None
        self._connections: Optional[dict[int, list[int]]] = None
        self._last_fetch = 0
        self._cache_ttl = 3600

    @property
    def name(self) -> str:
        return "albion2d"

    @property
    def is_live(self) -> bool:
        return True

    def _ensure_bypass(self):
        if self._bypass is None:
            from albion_cloudflare_bypass import CloudflareBypass

            self._bypass = CloudflareBypass()
        return self._bypass

    async def get_zones(self) -> list[Zone]:
        """Fetch zone data from albiononline2d.com."""
        now = time.time()
        if self._zones and (now - self._last_fetch) < self._cache_ttl:
            return self._zones

        bypass = self._ensure_bypass()
        url = "https://albiononline2d.com/en/map"

        try:
            result = await self._fetch_async(bypass, url)
            if result and result["status_code"] == 200:
                zones = self._parse_albion2d_html(result["html"])
                if zones:
                    self._zones = zones
                    self._last_fetch = now
                    log.info("Fetched %d zones from albiononline2d.com", len(zones))
                    return zones
        except Exception as e:
            log.warning("Albion2D fetch failed: %s", e)

        return []

    async def _fetch_async(self, bypass, url: str) -> dict:
        """Run CF bypass in async context."""
        loop = time.time()
        import asyncio

        def _sync_fetch():
            return bypass.get(url)

        return await asyncio.get_event_loop().run_in_executor(None, _sync_fetch)

    def _parse_albion2d_html(self, html: str) -> list[Zone]:
        """
        Parse zone data from Albion2D HTML page.
        The site embeds zone data in a JavaScript config or JSON blob.
        """
        import re

        zones = []

        try:
            pattern = r'"name":"([^"]+)"[^}]*"id":\s*(\d+)[^}]*"x":\s*(-?\d+\.?\d*)[^}]*"y":\s*(-?\d+\.?\d*)[^}]*"connections":\s*\[(\d+(?:,\s*\d+)*)\]'
            matches = re.findall(pattern, html, re.IGNORECASE)
            for name, zone_id, x, y, conns in matches:
                conn_ids = [
                    int(c.strip()) for c in conns.split(",") if c.strip().isdigit()
                ]
                zone = Zone(
                    id=int(zone_id),
                    name=name.replace("_", " "),
                    file=name,
                    zone_type=1,
                    layer=0,
                    x=float(x),
                    y=float(y),
                    connections=conn_ids,
                    source="albion2d",
                )
                zones.append(zone)
        except Exception as e:
            log.debug("HTML parsing failed: %s", e)

        if not zones:
            try:
                pattern = r"var\s+mapConfig\s*=\s*(\{.+?\});"
                m = re.search(pattern, html, re.DOTALL)
                if m:
                    config_str = m.group(1)
                    config = json.loads(config_str)
                    for zdata in config.get("zones", []):
                        zone = Zone(
                            id=zdata.get("id", 0),
                            name=zdata.get("name", ""),
                            file=zdata.get("file", ""),
                            zone_type=zdata.get("zone_type", 1),
                            layer=zdata.get("layer", 0),
                            x=zdata.get("x", 0.0),
                            y=zdata.get("y", 0.0),
                            connections=zdata.get("connections", []),
                            source="albion2d",
                        )
                        zones.append(zone)
            except Exception as e:
                log.debug("mapConfig parsing failed: %s", e)

        return zones

    async def get_connections(self) -> dict[int, list[int]]:
        if self._connections is None:
            zones = await self.get_zones()
            self._connections = {z.id: z.connections for z in zones}
        return self._connections


class StaticFileZoneSource(ZoneDataSource):
    """
    Fallback source: reads zone data from static JSON file.
    """

    DEFAULT_PATH = Path(__file__).parent.parent / "extracted_maps" / "albion_zones.json"

    def __init__(self, file_path: Optional[Path] = None):
        self._path = file_path or self.DEFAULT_PATH
        self._zones: Optional[list[Zone]] = None
        self._connections: Optional[dict[int, list[int]]] = None

    @property
    def name(self) -> str:
        return "static_file"

    async def get_zones(self) -> list[Zone]:
        if self._zones is not None:
            return self._zones

        if not self._path.exists():
            log.warning("Static zone file not found: %s", self._path)
            return []

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw_zones = json.load(f)

            self._zones = []
            for zdata in raw_zones:
                zone = Zone(
                    id=zdata.get("id", 0),
                    name=zdata.get("name", ""),
                    file=zdata.get("file", ""),
                    zone_type=zdata.get("zone_type", 1),
                    layer=zdata.get("layer", 0),
                    x=zdata.get("x", 0.0),
                    y=zdata.get("y", 0.0),
                    connections=zdata.get("connections", []),
                    source="static_file",
                )
                self._zones.append(zone)

            log.info("Loaded %d zones from static file", len(self._zones))
            return self._zones
        except (json.JSONDecodeError, OSError) as e:
            log.error("Failed to load static zone file: %s", e)
            return []

    async def get_connections(self) -> dict[int, list[int]]:
        if self._connections is None:
            zones = await self.get_zones()
            self._connections = {z.id: z.connections for z in zones}
        return self._connections


class ZoneDataOrchestrator:
    """
    Tries sources in priority order: Live Albion2D → Static File.
    Falls back automatically on failure.
    """

    def __init__(
        self,
        sources: Optional[list[ZoneDataSource]] = None,
        live_source: Optional[Albion2DZoneSource] = None,
        static_source: Optional[StaticFileZoneSource] = None,
    ):
        self._live = live_source or Albion2DZoneSource()
        self._static = static_source or StaticFileZoneSource()
        self._sources: list[ZoneDataSource] = sources or [self._live, self._static]

    async def get_zones(self) -> list[Zone]:
        """
        Get zones from the best available source, falling back on failure.
        Returns the first non-empty result.
        """
        for source in self._sources:
            try:
                zones = await source.get_zones()
                if zones:
                    log.info("Got %d zones from %s", len(zones), source.name)
                    return zones
                log.debug("%s returned no zones", source.name)
            except Exception as e:
                log.warning("%s failed: %s", source.name, e)

        return []

    async def get_connections(self) -> dict[int, list[int]]:
        for source in self._sources:
            try:
                conns = await source.get_connections()
                if conns:
                    return conns
            except Exception as e:
                log.warning("%s failed: %s", source.name, e)
        return {}

    async def find_zone_by_name(self, name: str) -> Optional[Zone]:
        zones = await self.get_zones()
        for z in zones:
            if z.name.lower() == name.lower() or z.file.lower() == name.lower().replace(
                " ", "_"
            ):
                return z
        return None

    async def find_zone_by_id(self, zone_id: int) -> Optional[Zone]:
        zones = await self.get_zones()
        for z in zones:
            if z.id == zone_id:
                return z
        return None
