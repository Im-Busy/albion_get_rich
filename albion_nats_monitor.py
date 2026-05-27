"""
Real-Time NATS Market Monitor — Continuous Flip Detection

Maintains an in-memory price cache updated by NATS stream.
Detects profitable flips as orders arrive (3-5 second latency).

Features:
- Live subscription to marketorders.deduped.bulk
- In-memory price aggregation per (item, location, quality, enchantment)
- Real-time flip detection on every price update
- WebSocket push to frontend for instant alerts
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Callable

try:
    import nats

    HAS_NATS = True
except ImportError:
    HAS_NATS = False
    logging.warning("nats library not installed, real-time mode unavailable")

from albion_market_scanner_enhanced import (
    ItemDatabase,
    FlipCalculator,
    FlipOpportunity,
    SmartFilters,
    PREMIUM_SELL_TAX,
    NON_PREMIUM_SELL_TAX,
    LOCATION_MAP,
    ALL_TRADE_HUBS,
)

log = logging.getLogger("nats_monitor")


@dataclass
class PriceCacheEntry:
    """Cached price data for a specific (item, location, quality, enchantment)."""

    item_id: str
    location_id: int
    location: str
    quality: int
    enchantment: int

    # Best sell order (lowest ask)
    best_sell_price: int = 0
    best_sell_amount: int = 0
    best_sell_order_id: int = 0
    sell_updated: float = 0

    # Best buy order (highest bid)
    best_buy_price: int = 0
    best_buy_amount: int = 0
    best_buy_order_id: int = 0
    buy_updated: float = 0

    def update_from_order(self, order: dict):
        """Update cache entry from a NATS market order."""
        auction_type = order.get("AuctionType", "offer")
        price = order.get("UnitPriceSilver", 0)
        amount = order.get("Amount", 0)
        order_id = order.get("Id", 0)

        if auction_type == "offer":  # Sell order
            # Update if this is a better (lower) price
            if price > 0 and (
                self.best_sell_price == 0 or price < self.best_sell_price
            ):
                self.best_sell_price = price
                self.best_sell_amount = amount
                self.best_sell_order_id = order_id
                self.sell_updated = time.time()
            # Or if same order updated
            elif order_id == self.best_sell_order_id:
                self.best_sell_price = price
                self.best_sell_amount = amount
                self.sell_updated = time.time()

        elif auction_type == "request":  # Buy order
            # Update if this is a better (higher) price
            if price > 0 and (self.best_buy_price == 0 or price > self.best_buy_price):
                self.best_buy_price = price
                self.best_buy_amount = amount
                self.best_buy_order_id = order_id
                self.buy_updated = time.time()
            # Or if same order updated
            elif order_id == self.best_buy_order_id:
                self.best_buy_price = price
                self.best_buy_amount = amount
                self.buy_updated = time.time()


class RealTimePriceCache:
    """
    In-memory cache of all market prices.
    Updated continuously from NATS stream.
    """

    def __init__(self):
        # Key: (item_id, location_id, quality, enchantment)
        self._cache: dict[tuple, PriceCacheEntry] = {}
        self._lock = asyncio.Lock()
        self._item_db = ItemDatabase()
        self._updates_count = 0
        self._last_update_time = 0

    async def process_order(self, order_data: dict):
        """Process a single order from NATS and update cache."""
        item_id = order_data.get("ItemTypeId", "")
        location_id = order_data.get("LocationId", 0)
        quality = order_data.get("QualityLevel", 1)
        enchantment = order_data.get("EnchantmentLevel", 0)

        if not item_id or not location_id:
            return

        key = (item_id, location_id, quality, enchantment)
        location = LOCATION_MAP.get(location_id, str(location_id))

        async with self._lock:
            if key not in self._cache:
                self._cache[key] = PriceCacheEntry(
                    item_id=item_id,
                    location_id=location_id,
                    location=location,
                    quality=quality,
                    enchantment=enchantment,
                )

            self._cache[key].update_from_order(order_data)
            self._updates_count += 1
            self._last_update_time = time.time()

    async def process_batch(self, orders: list[dict]):
        """Process a batch of orders from NATS message."""
        for order in orders:
            await self.process_order(order)

    async def get_all_entries(self) -> list[PriceCacheEntry]:
        """Get all cache entries."""
        async with self._lock:
            return list(self._cache.values())

    async def find_flips(
        self,
        cities: Optional[list[str]] = None,
        min_profit: int = 100,
        min_margin: float = 0.02,
        max_stale_seconds: float = 3600,
        outlier_mult: float = 4.0,
    ) -> list[FlipOpportunity]:
        """
        Find profitable flips from current cache.

        Args:
            cities: Cities to consider (default: all trade hubs)
            min_profit: Minimum profit after tax
            min_margin: Minimum ROI percentage
            max_stale_seconds: Maximum age of price data
            outlier_mult: Outlier detection multiplier
        """
        if cities is None:
            cities = ALL_TRADE_HUBS

        city_set = set(cities)
        now = time.time()

        async with self._lock:
            entries = list(self._cache.values())

        # Group by (item, quality, enchantment)
        groups: dict[tuple, dict[str, PriceCacheEntry]] = {}

        for entry in entries:
            if entry.location not in city_set:
                continue

            # Check staleness
            sell_age = (
                now - entry.sell_updated if entry.best_sell_price > 0 else float("inf")
            )
            buy_age = (
                now - entry.buy_updated if entry.best_buy_price > 0 else float("inf")
            )

            if sell_age > max_stale_seconds:
                entry.best_sell_price = 0
            if buy_age > max_stale_seconds:
                entry.best_buy_price = 0

            # Outlier detection
            if entry.best_sell_price > 0 and entry.best_buy_price > 0:
                if entry.best_sell_price > entry.best_buy_price * outlier_mult:
                    entry.best_sell_price = 0

            # Skip if no valid prices
            if entry.best_sell_price <= 0 and entry.best_buy_price <= 0:
                continue

            key = (entry.item_id, entry.quality, entry.enchantment)
            if key not in groups:
                groups[key] = {}
            groups[key][entry.location] = entry

        # Find flips
        flips: list[FlipOpportunity] = []

        for (item_id, quality, enchantment), city_data in groups.items():
            # Find best buy (lowest sell price)
            best_buy: Optional[PriceCacheEntry] = None
            for entry in city_data.values():
                if entry.best_sell_price > 0:
                    if (
                        best_buy is None
                        or entry.best_sell_price < best_buy.best_sell_price
                    ):
                        best_buy = entry

            # Find best sell (highest buy price)
            best_sell: Optional[PriceCacheEntry] = None
            for entry in city_data.values():
                if entry.best_buy_price > 0:
                    if (
                        best_sell is None
                        or entry.best_buy_price > best_sell.best_buy_price
                    ):
                        best_sell = entry

            if best_buy is None or best_sell is None:
                continue

            if best_buy.location == best_sell.location:
                continue

            buy_price = best_buy.best_sell_price
            sell_price = best_sell.best_buy_price

            if sell_price <= buy_price:
                continue

            # Calculate profit
            gross = sell_price - buy_price
            profit_prem = int(sell_price * (1 - PREMIUM_SELL_TAX)) - buy_price
            margin_prem = profit_prem / buy_price if buy_price > 0 else 0

            if profit_prem < min_profit or margin_prem < min_margin:
                continue

            profit_no_prem = int(sell_price * (1 - NON_PREMIUM_SELL_TAX)) - buy_price
            margin_no_prem = profit_no_prem / buy_price if buy_price > 0 else 0

            flip = FlipOpportunity(
                item_id=item_id,
                item_name=self._item_db.get_name(item_id),
                quality=quality,
                enchantment=enchantment,
                buy_city=best_buy.location,
                buy_price=buy_price,
                buy_date=datetime.fromtimestamp(
                    best_buy.sell_updated, tz=timezone.utc
                ).isoformat(),
                sell_city=best_sell.location,
                sell_price=sell_price,
                sell_date=datetime.fromtimestamp(
                    best_sell.buy_updated, tz=timezone.utc
                ).isoformat(),
                gross_profit=gross,
                profit_premium=profit_prem,
                profit_no_premium=profit_no_prem,
                margin_premium=margin_prem,
                margin_no_premium=margin_no_prem,
                is_black_market=(
                    best_buy.location == "Black Market"
                    or best_sell.location == "Black Market"
                ),
                data_age_seconds=max(
                    now - best_buy.sell_updated, now - best_sell.buy_updated
                ),
                source="nats_realtime",
            )
            flips.append(flip)

        flips.sort(key=lambda f: f.profit_premium, reverse=True)
        return flips

    def stats(self) -> dict:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "updates": self._updates_count,
            "last_update": self._last_update_time,
        }


class NatsMarketMonitor:
    """
    Real-time market monitor using NATS stream.

    Usage:
        monitor = NatsMarketMonitor()
        await monitor.start()

        # Get current flips
        flips = await monitor.get_flips()

        # Subscribe to flip updates
        await monitor.subscribe_flips(callback)

        await monitor.stop()
    """

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
        self._sub = None
        self._cache = RealTimePriceCache()
        self._running = False
        self._flip_callbacks: list[Callable[[list[FlipOpportunity]], None]] = []
        self._last_flip_check = 0
        self._flip_check_interval = 5.0  # Check for flips every 5 seconds

    async def start(self) -> bool:
        """Start the NATS connection and subscription."""
        if not HAS_NATS:
            log.error("NATS library not installed")
            return False

        try:
            self._nc = await nats.connect(
                servers=[self._server],
                user=self._user,
                password=self._password,
                connect_timeout=10,
            )

            log.info(f"Connected to NATS: {self._server}")

            self._sub = await self._nc.subscribe(self._topic)
            self._running = True

            # Start message processing loop
            asyncio.create_task(self._message_loop())
            asyncio.create_task(self._flip_check_loop())

            return True

        except Exception as e:
            log.error(f"NATS connection failed: {e}")
            return False

    async def _message_loop(self):
        """Process incoming NATS messages."""
        while self._running:
            try:
                msg = await self._sub.next_msg(timeout=30)
                data = json.loads(msg.data.decode("utf-8"))

                # Handle batch format
                if isinstance(data, list):
                    await self._cache.process_batch(data)
                else:
                    await self._cache.process_order(data)

                log.debug(
                    f"Processed {len(data) if isinstance(data, list) else 1} orders"
                )

            except Exception as e:
                if not self._running:
                    break
                log.debug(f"Message loop error: {e}")
                await asyncio.sleep(1)

    async def _flip_check_loop(self):
        """Periodically check for flips and notify subscribers."""
        while self._running:
            await asyncio.sleep(self._flip_check_interval)

            if not self._flip_callbacks:
                continue

            try:
                flips = await self._cache.find_flips()
                if flips:
                    for callback in self._flip_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(flips)
                            else:
                                callback(flips)
                        except Exception as e:
                            log.warning(f"Flip callback error: {e}")
            except Exception as e:
                log.warning(f"Flip check error: {e}")

    async def stop(self):
        """Stop the monitor."""
        self._running = False

        if self._sub:
            try:
                await self._sub.unsubscribe()
            except Exception:
                pass

        if self._nc and not self._nc.is_closed:
            try:
                await self._nc.close()
            except Exception:
                pass

        log.info("NATS monitor stopped")

    async def get_flips(
        self,
        cities: Optional[list[str]] = None,
        min_profit: int = 100,
        min_margin: float = 0.02,
        max_stale_seconds: float = 3600,
    ) -> list[FlipOpportunity]:
        """Get current profitable flips from cache."""
        return await self._cache.find_flips(
            cities=cities,
            min_profit=min_profit,
            min_margin=min_margin,
            max_stale_seconds=max_stale_seconds,
        )

    async def subscribe_flips(self, callback: Callable[[list[FlipOpportunity]], None]):
        """Subscribe to periodic flip updates."""
        self._flip_callbacks.append(callback)

    async def unsubscribe_flips(
        self, callback: Callable[[list[FlipOpportunity]], None]
    ):
        """Remove a flip subscription."""
        if callback in self._flip_callbacks:
            self._flip_callbacks.remove(callback)

    def cache_stats(self) -> dict:
        """Get cache statistics."""
        return self._cache.stats()

    def is_connected(self) -> bool:
        """Check if NATS is connected."""
        return self._nc is not None and not self._nc.is_closed


# ─── Standalone Test ─────────────────────────────────────────────────────────


async def test_monitor():
    """Test the real-time monitor."""
    monitor = NatsMarketMonitor()

    connected = await monitor.start()
    if not connected:
        print("Failed to connect to NATS")
        return

    print("Connected! Monitoring for 30 seconds...")

    # Subscribe to flip updates
    def on_flips(flips: list[FlipOpportunity]):
        print(f"\n--- NEW FLIPS DETECTED ({len(flips)}) ---")
        for f in flips[:5]:
            print(
                f"  {f.item_name}: buy in {f.buy_city} @ {f.buy_price}, sell in {f.sell_city} @ {f.sell_price}, profit={f.profit_premium}"
            )

    await monitor.subscribe_flips(on_flips)

    # Run for 30 seconds
    for i in range(30):
        await asyncio.sleep(1)
        stats = monitor.cache_stats()
        print(
            f"[{i + 1}s] Cache: {stats['entries']} entries, {stats['updates']} updates"
        )

    # Final check
    flips = await monitor.get_flips()
    print(f"\nFinal: {len(flips)} flips found")

    await monitor.stop()


if __name__ == "__main__":
    if HAS_NATS:
        asyncio.run(test_monitor())
    else:
        print("Install nats library: uv add nats")
