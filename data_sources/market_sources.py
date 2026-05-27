"""
Market Data Sources — Abstract interface with NATS, REST, and Cache implementations.

Priority-ordered fallback: NATS (real-time, no rate limits) → REST API → Cache (stale but available).
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import httpx

from albion_market_scanner import MarketOrder, LOCATION_MAP, ROYAL_CITIES

log = logging.getLogger("data_sources.market")


@dataclass
class PriceSnapshot:
    item_id: str
    location_id: int
    city: str
    quality: int
    enchantment: int
    sell_price_min: int
    sell_price_min_date: str
    buy_price_max: int
    buy_price_max_date: str
    sell_amount: int = 0
    buy_amount: int = 0
    source: str = ""


class MarketDataSource(ABC):
    """Abstract base for market data sources."""

    @abstractmethod
    async def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[PriceSnapshot]: ...

    @abstractmethod
    async def subscribe(
        self, callback: Callable[[list[MarketOrder]], None]
    ) -> Optional[object]:
        """Subscribe to real-time updates. Returns a subscription handle or None if unsupported."""
        ...

    @abstractmethod
    async def unsubscribe(self, handle: object) -> None: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def is_realtime(self) -> bool:
        return False


class NATSMarketSource(MarketDataSource):
    """Primary source: real-time NATS stream from albion-online-data.com."""

    def __init__(
        self,
        server: str = "nats://www.albion-online-data.com:4222",
        user: str = "public",
        password: str = "thenewalbiondata",
        topic: str = "marketorders.deduped.bulk",
    ):
        self._server = server
        self._user = user
        self._password = password
        self._topic = topic
        self._nc = None
        self._subs: list = []
        self._price_cache: dict[tuple, PriceSnapshot] = {}
        self._cache_lock = asyncio.Lock()
        self._connected = False

    @property
    def name(self) -> str:
        return "nats"

    @property
    def is_realtime(self) -> bool:
        return True

    async def connect(self) -> bool:
        """Establish NATS connection. Returns True on success."""
        try:
            import nats

            self._nc = await nats.connect(
                servers=[self._server],
                user=self._user,
                password=self._password,
                connect_timeout=10,
            )
            self._connected = True
            log.info("NATS connected to %s", self._server)

            sub = await self._nc.subscribe(self._topic)
            self._subs.append(sub)
            asyncio.create_task(self._message_loop(sub))
            return True
        except Exception as e:
            log.warning("NATS connection failed: %s", e)
            self._connected = False
            return False

    async def _message_loop(self, sub):
        """Background task consuming NATS messages into the price cache."""
        try:
            import nats as nats_lib
        except ImportError:
            return

        while True:
            try:
                msg = await sub.next_msg(timeout=30)
                data = json.loads(msg.data.decode("utf-8"))
                if not isinstance(data, list):
                    data = [data]
                for order_data in data:
                    snap = self._parse_nats_order(order_data)
                    if snap:
                        key = (
                            snap.item_id,
                            snap.location_id,
                            snap.quality,
                            snap.enchantment,
                        )
                        async with self._cache_lock:
                            self._price_cache[key] = snap
            except Exception:
                if self._nc and self._nc.is_closed:
                    break
                await asyncio.sleep(1)

    def _parse_nats_order(self, data: dict) -> Optional[PriceSnapshot]:
        """Parse a NATS market order message into a PriceSnapshot."""
        try:
            location_id = data.get("LocationId", 0)
            city = LOCATION_MAP.get(location_id, str(location_id))
            auction_type = data.get("AuctionType", "offer")
            price = data.get("UnitPriceSilver", 0)
            amount = data.get("Amount", 0)
            enchantment = data.get("EnchantmentLevel", 0)

            snap = PriceSnapshot(
                item_id=data.get("ItemTypeId", ""),
                location_id=location_id,
                city=city,
                quality=data.get("QualityLevel", 1),
                enchantment=enchantment,
                sell_price_min=price if auction_type == "offer" else 0,
                sell_price_min_date="",
                buy_price_max=price if auction_type == "request" else 0,
                buy_price_max_date="",
                sell_amount=amount if auction_type == "offer" else 0,
                buy_amount=amount if auction_type == "request" else 0,
                source="nats",
            )
            return snap
        except Exception as e:
            log.debug("Failed to parse NATS order: %s", e)
            return None

    async def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[PriceSnapshot]:
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return []

        location_names = set(locations) if locations else set(ROYAL_CITIES)
        item_set = set(items) if items else None

        async with self._cache_lock:
            results = []
            for snap in self._price_cache.values():
                if snap.city not in location_names:
                    continue
                if item_set and snap.item_id not in item_set:
                    continue
                if quality and snap.quality != quality:
                    continue
                results.append(snap)
            return results

    async def subscribe(
        self, callback: Callable[[list[MarketOrder]], None]
    ) -> Optional[object]:
        if not self._connected:
            connected = await self.connect()
            if not connected:
                return None

        try:
            import nats as nats_lib

            sub = await self._nc.subscribe(self._topic)
            self._subs.append(sub)

            async def _forward():
                while True:
                    try:
                        msg = await sub.next_msg(timeout=30)
                        data = json.loads(msg.data.decode("utf-8"))
                        if not isinstance(data, list):
                            data = [data]
                        orders = []
                        for d in data:
                            order = MarketOrder(
                                item_id=d.get("ItemTypeId", ""),
                                location=LOCATION_MAP.get(d.get("LocationId", 0), ""),
                                quality=d.get("QualityLevel", 1),
                                enchantment=d.get("EnchantmentLevel", 0),
                                price=d.get("UnitPriceSilver", 0),
                                amount=d.get("Amount", 0),
                                auction_type=d.get("AuctionType", "offer"),
                            )
                            orders.append(order)
                        if orders:
                            await callback(orders) if asyncio.iscoroutinefunction(
                                callback
                            ) else callback(orders)
                    except Exception:
                        if self._nc and self._nc.is_closed:
                            break
                        await asyncio.sleep(1)

            task = asyncio.create_task(_forward())
            return task
        except Exception as e:
            log.warning("NATS subscribe failed: %s", e)
            return None

    async def unsubscribe(self, handle: object) -> None:
        if isinstance(handle, asyncio.Task) and not handle.done():
            handle.cancel()
        for sub in self._subs[:]:
            try:
                await sub.unsubscribe()
                self._subs.remove(sub)
            except Exception:
                pass

    async def close(self):
        for sub in self._subs:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        self._subs.clear()
        if self._nc and not self._nc.is_closed:
            await self._nc.close()
        self._connected = False


class RESTAPIMarketSource(MarketDataSource):
    """Fallback source: AO Data REST API (rate limited)."""

    API_BASE = "https://west.albion-online-data.com/api/v2/stats"

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def name(self) -> str:
        return "rest_api"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    async def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[PriceSnapshot]:
        client = await self._get_client()
        item_param = ",".join(items)
        loc_param = ",".join(locations)
        url = f"{self.API_BASE}/prices/{item_param}?locations={loc_param}&qualities={quality}"

        try:
            resp = await client.get(url)
            resp.raise_for_status()
            raw_data = resp.json()
            return self._parse_rest_response(raw_data)
        except Exception as e:
            log.error("REST API request failed: %s", e)
            return []

    def _parse_rest_response(self, data: list[dict]) -> list[PriceSnapshot]:
        results = []
        for entry in data:
            try:
                snap = PriceSnapshot(
                    item_id=entry.get("item_id", ""),
                    location_id=0,
                    city=entry.get("city", ""),
                    quality=entry.get("quality", 1),
                    enchantment=0,
                    sell_price_min=entry.get("sell_price_min", 0),
                    sell_price_min_date=entry.get("sell_price_min_date", ""),
                    buy_price_max=entry.get("buy_price_max", 0),
                    buy_price_max_date=entry.get("buy_price_max_date", ""),
                    source="rest_api",
                )
                results.append(snap)
            except Exception as e:
                log.debug("Failed to parse REST entry: %s", e)
        return results

    async def subscribe(
        self, callback: Callable[[list[MarketOrder]], None]
    ) -> Optional[object]:
        return None

    async def unsubscribe(self, handle: object) -> None:
        pass

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class CachedMarketSource(MarketDataSource):
    """Last resort: reads from persisted price cache on disk."""

    CACHE_DIR = Path(__file__).parent.parent / ".market_cache"
    CACHE_FILE = CACHE_DIR / "prices_cache.json"

    def __init__(self):
        self.CACHE_DIR.mkdir(exist_ok=True)

    @property
    def name(self) -> str:
        return "cache"

    async def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[PriceSnapshot]:
        if not self.CACHE_FILE.exists():
            return []

        try:
            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        age = time.time() - cached.get("timestamp", 0)
        if age > 3600:
            log.warning("Cache is %.0f minutes old", age / 60)

        location_set = set(locations) if locations else None
        item_set = set(items) if items else None

        results = []
        for entry in cached.get("data", []):
            if location_set and entry.get("city") not in location_set:
                continue
            if item_set and entry.get("item_id") not in item_set:
                continue
            if quality and entry.get("quality") != quality:
                continue
            snap = PriceSnapshot(
                item_id=entry.get("item_id", ""),
                location_id=0,
                city=entry.get("city", ""),
                quality=entry.get("quality", 1),
                enchantment=entry.get("enchantment", 0),
                sell_price_min=entry.get("sell_price_min", 0),
                sell_price_min_date=entry.get("sell_price_min_date", ""),
                buy_price_max=entry.get("buy_price_max", 0),
                buy_price_max_date=entry.get("buy_price_max_date", ""),
                source="cache",
            )
            results.append(snap)
        return results

    async def save_prices(self, snapshots: list[PriceSnapshot]):
        """Persist snapshots to disk for future cache reads."""
        data = {
            "timestamp": time.time(),
            "data": [
                {
                    "item_id": s.item_id,
                    "city": s.city,
                    "quality": s.quality,
                    "enchantment": s.enchantment,
                    "sell_price_min": s.sell_price_min,
                    "sell_price_min_date": s.sell_price_min_date,
                    "buy_price_max": s.buy_price_max,
                    "buy_price_max_date": s.buy_price_max_date,
                }
                for s in snapshots
            ],
        }
        try:
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            log.warning("Failed to save cache: %s", e)

    async def subscribe(
        self, callback: Callable[[list[MarketOrder]], None]
    ) -> Optional[object]:
        return None

    async def unsubscribe(self, handle: object) -> None:
        pass


class MarketDataOrchestrator:
    """
    Tries sources in priority order: NATS → REST → Cache.
    Falls back automatically on failure.
    """

    def __init__(
        self,
        sources: Optional[list[MarketDataSource]] = None,
        nats_source: Optional[NATSMarketSource] = None,
        rest_source: Optional[RESTAPIMarketSource] = None,
        cache_source: Optional[CachedMarketSource] = None,
    ):
        self._nats = nats_source or NATSMarketSource()
        self._rest = rest_source or RESTAPIMarketSource()
        self._cache = cache_source or CachedMarketSource()
        self._sources: list[MarketDataSource] = sources or [
            self._nats,
            self._rest,
            self._cache,
        ]

    async def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[PriceSnapshot]:
        """
        Get prices from the best available source, falling back on failure.
        Returns the first non-empty result.
        """
        last_error = None
        for source in self._sources:
            try:
                results = await source.get_prices(items, locations, quality)
                if results:
                    log.info("Got %d prices from %s", len(results), source.name)
                    if source.name != "cache":
                        await self._cache.save_prices(results)
                    return results
                log.debug("%s returned no data", source.name)
            except Exception as e:
                log.warning("%s failed: %s", source.name, e)
                last_error = e

        if last_error:
            raise last_error
        return []

    async def subscribe(
        self, callback: Callable[[list[MarketOrder]], None]
    ) -> Optional[object]:
        """Subscribe via NATS if available, otherwise returns None."""
        handle = await self._nats.subscribe(callback)
        if handle:
            return handle

        log.info("NATS subscribe failed, no real-time data available")
        return None

    async def unsubscribe(self, handle: object) -> None:
        await self._nats.unsubscribe(handle)

    async def close(self):
        for source in self._sources:
            if hasattr(source, "close"):
                try:
                    await source.close()
                except Exception:
                    pass
