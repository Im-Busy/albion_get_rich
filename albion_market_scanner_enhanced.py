"""
Enhanced Albion Market Scanner — Real-Time Arbitrage Detection

Integrates:
- 11,000+ item database from albion-arbitrage-tracker
- Smart filters: stale data, outliers, fake order detection
- Premium vs non-premium profit calculation
- Black Market as a trade destination
- NATS real-time subscription for instant updates
- REST API fallback with caching
"""

import json
import sys
import time
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime, timezone

import httpx

# Force UTF-8 output on Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

API_BASE = "https://west.albion-online-data.com/api/v2/stats"

NATS_SERVER = "nats://www.albion-online-data.com:4222"
NATS_USER = "public"
NATS_PASS = "thenewalbiondata"
NATS_TOPIC = "marketorders.deduped.bulk"

# Premium players get 4% tax reduction on sells
PREMIUM_SELL_TAX = 0.025  # 2.5% with premium
NON_PREMIUM_SELL_TAX = 0.045  # 4.5% without premium

# Location mapping
LOCATION_MAP: dict[int, str] = {
    1: "Caerleon Bank",
    1002: "Fort Sterling",
    1003: "Lymhurst",
    1004: "Thetford",
    1005: "Bridgewatch",
    1006: "Martlock",
    2001: "Black Market",
    2131: "Caerleon",
}

# Reverse mapping: name → ID
LOCATION_ID_MAP = {v: k for k, v in LOCATION_MAP.items()}

# Royal cities + Black Market for scanning
ALL_TRADE_HUBS = [
    "Martlock",
    "Lymhurst",
    "Thetford",
    "Bridgewatch",
    "Fort Sterling",
    "Caerleon",
    "Black Market",
]

ROYAL_CITIES = [
    "Martlock",
    "Lymhurst",
    "Thetford",
    "Bridgewatch",
    "Fort Sterling",
    "Caerleon",
]


# ─── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class ItemInfo:
    """Item metadata from the 11K item database."""

    item_id: str
    name: str


@dataclass
class MarketOrder:
    """Real-time market order from NATS stream."""

    order_id: int
    item_id: str
    location_id: int
    location: str
    quality: int
    enchantment: int
    price: int
    amount: int
    auction_type: str  # "offer" (sell) or "request" (buy)
    expires: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class PricePoint:
    """Aggregated price for an item at a location."""

    item_id: str
    city: str
    quality: int
    enchantment: int
    sell_price_min: int  # Best sell order (lowest ask)
    sell_price_min_date: str
    sell_amount: int
    buy_price_max: int  # Best buy order (highest bid)
    buy_price_max_date: str
    buy_amount: int
    source: str = ""


@dataclass
class FlipOpportunity:
    """A profitable arbitrage opportunity."""

    item_id: str
    item_name: str
    quality: int
    enchantment: int
    buy_city: str
    buy_price: int
    buy_date: str
    sell_city: str
    sell_price: int
    sell_date: str

    # Profit calculations
    gross_profit: int
    profit_premium: int  # After tax with premium
    profit_no_premium: int  # After tax without premium
    margin_premium: float  # ROI % with premium
    margin_no_premium: float  # ROI % without premium

    # Metadata
    is_black_market: bool
    data_age_seconds: float
    source: str


# ─── Item Database Loader ─────────────────────────────────────────────────────


class ItemDatabase:
    """Loads and caches the 11,000+ item database."""

    _instance = None
    _items: dict[str, ItemInfo] = {}
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, path: Optional[Path] = None) -> dict[str, ItemInfo]:
        if self._loaded:
            return self._items

        if path is None:
            path = Path(__file__).parent / "data" / "items.json"

        if not path.exists():
            log.warning(f"Item database not found at {path}")
            return {}

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)

            for item in raw_items:
                item_id = item.get("value", "")
                name = item.get("label", item_id)
                self._items[item_id] = ItemInfo(item_id=item_id, name=name)

            self._loaded = True
            log.info(f"Loaded {len(self._items)} items from database")
            return self._items
        except Exception as e:
            log.error(f"Failed to load item database: {e}")
            return {}

    def get_name(self, item_id: str) -> str:
        if not self._loaded:
            self.load()
        return self._items.get(item_id, ItemInfo(item_id, item_id)).name

    def get_all_ids(self) -> list[str]:
        if not self._loaded:
            self.load()
        return list(self._items.keys())

    def search(self, query: str, limit: int = 20) -> list[ItemInfo]:
        if not self._loaded:
            self.load()
        query = query.lower()
        results = []
        for item in self._items.values():
            if query in item.name.lower() or query in item.item_id.lower():
                results.append(item)
                if len(results) >= limit:
                    break
        return results


# ─── Smart Filters (from albion-arbitrage-tracker) ───────────────────────────


class SmartFilters:
    """
    Intelligent price filters ported from albion-arbitrage-tracker.

    Filters:
    - Stale data: ignore prices older than threshold
    - Outliers: detect fake orders (ask >> bid)
    - Zero prices: skip invalid entries
    """

    def __init__(
        self,
        max_stale_hours: float = 2.0,
        outlier_multiplier: float = 4.0,
    ):
        self.max_stale_hours = max_stale_hours
        self.outlier_multiplier = outlier_multiplier

    def is_stale(self, date_str: str) -> bool:
        """Check if a price timestamp is too old."""
        if not date_str:
            return True

        try:
            # Handle both formats: with and without Z suffix
            if not date_str.endswith("Z"):
                date_str += "Z"
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return age > self.max_stale_hours
        except Exception:
            return True

    def is_outlier(self, sell_price: int, buy_price: int) -> bool:
        """
        Detect fake orders: sell price is X times higher than buy price.
        This indicates price manipulation or data errors.
        """
        if sell_price <= 0 or buy_price <= 0:
            return False
        return sell_price > buy_price * self.outlier_multiplier

    def filter_price_data(self, data: PricePoint) -> PricePoint:
        """Apply filters and return cleaned data (zeroes for invalid prices)."""
        # Check for stale sell price
        if self.is_stale(data.sell_price_min_date):
            data.sell_price_min = 0
            data.sell_amount = 0

        # Check for stale buy price
        if self.is_stale(data.buy_price_max_date):
            data.buy_price_max = 0
            data.buy_amount = 0

        # Check for outliers (fake sell orders)
        if self.is_outlier(data.sell_price_min, data.buy_price_max):
            data.sell_price_min = 0
            data.sell_amount = 0

        return data


# ─── Flip Calculator ─────────────────────────────────────────────────────────


class FlipCalculator:
    """
    Calculates profitable arbitrage opportunities.

    Features:
    - Premium vs non-premium profit
    - Black Market awareness
    - Smart filtering
    - Quality grouping
    """

    def __init__(
        self,
        filters: Optional[SmartFilters] = None,
        min_profit: int = 100,
        min_margin: float = 0.02,  # 2% minimum
    ):
        self.filters = filters or SmartFilters()
        self.min_profit = min_profit
        self.min_margin = min_margin
        self.item_db = ItemDatabase()

    def calculate_profit(
        self,
        buy_price: int,
        sell_price: int,
    ) -> tuple[int, int, float, float]:
        """
        Calculate profit after taxes.

        Returns: (gross_profit, profit_premium, profit_no_premium, margin_premium, margin_no_premium)
        """
        gross = sell_price - buy_price

        # Premium: 2.5% tax on sell
        profit_premium = int(sell_price * (1 - PREMIUM_SELL_TAX)) - buy_price
        margin_premium = profit_premium / buy_price if buy_price > 0 else 0

        # No premium: 4.5% tax on sell
        profit_no_premium = int(sell_price * (1 - NON_PREMIUM_SELL_TAX)) - buy_price
        margin_no_premium = profit_no_premium / buy_price if buy_price > 0 else 0

        return (
            gross,
            profit_premium,
            profit_no_premium,
            margin_premium,
            margin_no_premium,
        )

    def find_flips(
        self,
        prices: list[PricePoint],
        cities: Optional[list[str]] = None,
        include_black_market: bool = True,
    ) -> list[FlipOpportunity]:
        """
        Find all profitable flips from price data.

        Algorithm:
        1. Group by (item_id, quality, enchantment)
        2. For each group, find best buy price and best sell price
        3. Calculate profit after taxes
        4. Filter by minimum profit and margin
        """
        if cities is None:
            cities = ALL_TRADE_HUBS if include_black_market else ROYAL_CITIES

        city_set = set(cities)

        # Group prices by item/quality/enchantment
        groups: dict[tuple[str, int, int], dict[str, PricePoint]] = {}

        for pp in prices:
            if pp.city not in city_set:
                continue

            # Apply filters
            pp = self.filters.filter_price_data(pp)

            # Skip if no valid prices
            if pp.sell_price_min <= 0 and pp.buy_price_max <= 0:
                continue

            key = (pp.item_id, pp.quality, pp.enchantment)
            if key not in groups:
                groups[key] = {}
            groups[key][pp.city] = pp

        # Find best buy/sell pairs
        flips: list[FlipOpportunity] = []
        now = time.time()

        for (item_id, quality, enchantment), city_data in groups.items():
            # Find cheapest to buy (lowest sell_price_min)
            best_buy: Optional[tuple[str, int, str, float]] = (
                None  # (city, price, date, age)
            )

            # Find best to sell to (highest buy_price_max)
            best_sell: Optional[tuple[str, int, str, float]] = None

            for city, pp in city_data.items():
                # Best place to buy from (lowest ask)
                if pp.sell_price_min > 0:
                    age = now - self._parse_date(pp.sell_price_min_date)
                    if best_buy is None or pp.sell_price_min < best_buy[1]:
                        best_buy = (
                            city,
                            pp.sell_price_min,
                            pp.sell_price_min_date,
                            age,
                        )

                # Best place to sell to (highest bid)
                if pp.buy_price_max > 0:
                    age = now - self._parse_date(pp.buy_price_max_date)
                    if best_sell is None or pp.buy_price_max > best_sell[1]:
                        best_sell = (city, pp.buy_price_max, pp.buy_price_max_date, age)

            # Check if we have a valid flip
            if best_buy is None or best_sell is None:
                continue

            buy_city, buy_price, buy_date, buy_age = best_buy
            sell_city, sell_price, sell_date, sell_age = best_sell

            # Must be different cities
            if buy_city == sell_city:
                continue

            # Must be profitable
            if sell_price <= buy_price:
                continue

            gross, profit_prem, profit_no_prem, margin_prem, margin_no_prem = (
                self.calculate_profit(buy_price, sell_price)
            )

            # Filter by minimum profit
            if profit_prem < self.min_profit:
                continue

            # Filter by minimum margin
            if margin_prem < self.min_margin:
                continue

            flip = FlipOpportunity(
                item_id=item_id,
                item_name=self.item_db.get_name(item_id),
                quality=quality,
                enchantment=enchantment,
                buy_city=buy_city,
                buy_price=buy_price,
                buy_date=buy_date,
                sell_city=sell_city,
                sell_price=sell_price,
                sell_date=sell_date,
                gross_profit=gross,
                profit_premium=profit_prem,
                profit_no_premium=profit_no_prem,
                margin_premium=margin_prem,
                margin_no_premium=margin_no_prem,
                is_black_market=(
                    sell_city == "Black Market" or buy_city == "Black Market"
                ),
                data_age_seconds=max(buy_age, sell_age),
                source="scan",
            )
            flips.append(flip)

        # Sort by profit (premium)
        flips.sort(key=lambda f: f.profit_premium, reverse=True)
        return flips

    def _parse_date(self, date_str: str) -> float:
        """Parse date string to timestamp."""
        if not date_str:
            return 0
        try:
            if not date_str.endswith("Z"):
                date_str += "Z"
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0


# ─── REST API Fetcher ────────────────────────────────────────────────────────


class RestApiFetcher:
    """Fetches market data from AO Data REST API."""

    def __init__(self, api_base: str = API_BASE):
        self.api_base = api_base
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=30)
        return self._client

    def fetch_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: Optional[int] = None,
    ) -> list[PricePoint]:
        """
        Fetch current prices from REST API.

        Batch requests to respect rate limits.
        """
        client = self._get_client()
        results = []

        # Batch items (API allows ~100 items per request)
        BATCH_SIZE = 70

        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            item_param = ",".join(batch)
            loc_param = ",".join(locations)

            url = f"{self.api_base}/prices/{item_param}?locations={loc_param}"
            if quality:
                url += f"&qualities={quality}"

            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

                for entry in data:
                    pp = PricePoint(
                        item_id=entry.get("item_id", ""),
                        city=entry.get("city", ""),
                        quality=entry.get("quality", 1),
                        enchantment=0,  # REST API doesn't separate by enchantment
                        sell_price_min=entry.get("sell_price_min", 0),
                        sell_price_min_date=entry.get("sell_price_min_date", ""),
                        sell_amount=0,
                        buy_price_max=entry.get("buy_price_max", 0),
                        buy_price_max_date=entry.get("buy_price_max_date", ""),
                        buy_amount=0,
                        source="rest_api",
                    )
                    results.append(pp)

                log.info(f"Fetched {len(data)} prices for batch {i // BATCH_SIZE + 1}")

            except Exception as e:
                log.error(f"API request failed for batch: {e}")

        return results

    def close(self):
        if self._client and not self._client.is_closed:
            self._client.close()


# ─── Enhanced Scanner ────────────────────────────────────────────────────────


class EnhancedMarketScanner:
    """
    Enhanced market scanner combining all features:
    - 11K+ item database
    - Smart filters (stale, outliers)
    - Premium/non-premium profit calculation
    - Black Market support
    - REST API fetching (NATS integration via data_sources module)
    """

    def __init__(
        self,
        items: Optional[list[str]] = None,
        cities: Optional[list[str]] = None,
        max_stale_hours: float = 2.0,
        outlier_multiplier: float = 4.0,
        min_profit: int = 100,
        min_margin: float = 0.02,
        include_black_market: bool = True,
    ):
        self.item_db = ItemDatabase()
        self.items = items or self.item_db.get_all_ids()
        self.cities = cities or (
            ALL_TRADE_HUBS if include_black_market else ROYAL_CITIES
        )

        self.filters = SmartFilters(
            max_stale_hours=max_stale_hours,
            outlier_multiplier=outlier_multiplier,
        )
        self.calculator = FlipCalculator(
            filters=self.filters,
            min_profit=min_profit,
            min_margin=min_margin,
        )
        self.fetcher = RestApiFetcher()

        self.include_black_market = include_black_market

    def scan(
        self,
        quality: Optional[int] = 1,
        limit: int = 50,
    ) -> list[FlipOpportunity]:
        """Run a scan and return top flip opportunities."""
        log.info(f"Scanning {len(self.items)} items in {len(self.cities)} cities...")

        prices = self.fetcher.fetch_prices(
            items=self.items,
            locations=self.cities,
            quality=quality,
        )

        log.info(f"Received {len(prices)} price points")

        flips = self.calculator.find_flips(
            prices=prices,
            cities=self.cities,
            include_black_market=self.include_black_market,
        )

        log.info(f"Found {len(flips)} profitable flips")
        return flips[:limit]

    def scan_all_items_progress(
        self,
        quality: Optional[int] = 1,
        min_profit: int = 100,
        min_margin: float = 0.02,
        include_black_market: bool = True,
        batch_delay: float = 1.05,
    ):
        """
        Generator that scans all items in batches, yielding progress updates.

        Yields dicts with:
          - type: "progress" | "flips"
          - scanned: number of items scanned so far
          - total: total items to scan
          - flips_found: cumulative flips found
          - flips: list of FlipOpportunity (only on "flips" events)

        This is designed for SSE streaming to the frontend.
        """
        all_items = self.items
        total = len(all_items)
        all_prices: list[PricePoint] = []
        all_flips: list[FlipOpportunity] = []
        scanned = 0
        BATCH_SIZE = 70

        log.info(f"Starting global scan of {total} items...")

        for i in range(0, total, BATCH_SIZE):
            batch = all_items[i : i + BATCH_SIZE]
            batch_prices = self.fetcher.fetch_prices(
                items=batch,
                locations=self.cities,
                quality=quality,
            )
            all_prices.extend(batch_prices)
            scanned += len(batch)

            batch_flips = self.calculator.find_flips(
                prices=batch_prices,
                cities=self.cities,
                include_black_market=include_black_market,
            )

            new_flips = []
            seen_keys = {
                (f.item_id, f.quality, f.enchantment, f.buy_city, f.sell_city)
                for f in all_flips
            }
            for f in batch_flips:
                key = (f.item_id, f.quality, f.enchantment, f.buy_city, f.sell_city)
                if key not in seen_keys:
                    new_flips.append(f)
                    seen_keys.add(key)

            all_flips.extend(new_flips)

            yield {
                "type": "progress",
                "scanned": min(scanned, total),
                "total": total,
                "flips_found": len(all_flips),
                "batch": i // BATCH_SIZE + 1,
                "total_batches": (total + BATCH_SIZE - 1) // BATCH_SIZE,
            }

            if new_flips:
                new_flips.sort(key=lambda f: f.profit_premium, reverse=True)
                yield {
                    "type": "flips",
                    "scanned": min(scanned, total),
                    "total": total,
                    "flips_found": len(all_flips),
                    "flips": new_flips[:50],
                }

            if i + BATCH_SIZE < total:
                time.sleep(batch_delay)

        all_flips.sort(key=lambda f: f.profit_premium, reverse=True)
        filtered = [
            f
            for f in all_flips
            if f.profit_premium >= min_profit and f.margin_premium >= min_margin
        ]

        yield {
            "type": "complete",
            "scanned": total,
            "total": total,
            "flips_found": len(filtered),
            "flips": filtered[:200],
        }

    def scan_item(
        self, item_id: str, quality: Optional[int] = None
    ) -> list[FlipOpportunity]:
        """Scan a specific item across all cities."""
        prices = self.fetcher.fetch_prices(
            items=[item_id],
            locations=self.cities,
            quality=quality,
        )

        return self.calculator.find_flips(
            prices=prices,
            cities=self.cities,
            include_black_market=self.include_black_market,
        )

    def close(self):
        self.fetcher.close()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def print_flips(flips: list[FlipOpportunity], limit: int = 50):
    """Pretty-print flip opportunities."""
    if not flips:
        print("\nNo profitable flips found.")
        return

    print(f"\n{'=' * 120}")
    print(f"  TOP {min(len(flips), limit)} ARBITRAGE OPPORTUNITIES")
    print(f"{'=' * 120}")

    print(
        f"  {'Item':<35} {'Buy From':<14} {'Buy Price':>10} "
        f"{'Sell To':<14} {'Sell Price':>10} {'Profit':>10} {'ROI':>8} {'BM':>3}"
    )
    print(
        f"  {'-' * 35} {'-' * 14} {'-' * 10} {'-' * 14} {'-' * 10} {'-' * 10} {'-' * 8} {'-' * 3}"
    )

    for flip in flips[:limit]:
        name = flip.item_name[:34]
        roi = f"{flip.margin_premium * 100:.1f}%"
        bm = "Y" if flip.is_black_market else " "

        print(
            f"  {name:<35} {flip.buy_city:<14} {flip.buy_price:>10,} "
            f"{flip.sell_city:<14} {flip.sell_price:>10,} "
            f"{flip.profit_premium:>10,} {roi:>8} {bm:>3}"
        )

    print(f"\n{'=' * 120}")
    print(
        f"  Note: Profit calculated with Premium tax (2.5%). BM = Black Market involved."
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Enhanced Albion Market Scanner — Real-Time Arbitrage Detection"
    )
    parser.add_argument(
        "--items", nargs="+", help="Items to scan (default: all 11K+ items)"
    )
    parser.add_argument(
        "--cities", nargs="+", help="Cities to scan (default: all hubs including BM)"
    )
    parser.add_argument(
        "--quality", type=int, default=1, help="Quality level (1-5, default: 1)"
    )
    parser.add_argument(
        "--min-profit", type=int, default=100, help="Minimum profit in silver"
    )
    parser.add_argument(
        "--min-margin", type=float, default=0.02, help="Minimum margin (0.02 = 2%%)"
    )
    parser.add_argument(
        "--max-stale", type=float, default=2.0, help="Max stale hours for price data"
    )
    parser.add_argument(
        "--outlier-mult",
        type=float,
        default=4.0,
        help="Outlier multiplier for fake orders",
    )
    parser.add_argument(
        "--no-black-market", action="store_true", help="Exclude Black Market"
    )
    parser.add_argument("--limit", type=int, default=50, help="Max results to show")
    parser.add_argument("--search", type=str, help="Search for item IDs by name")

    args = parser.parse_args()

    # Item search mode
    if args.search:
        db = ItemDatabase()
        results = db.search(args.search, limit=20)
        print(f"\nItems matching '{args.search}':")
        for item in results:
            print(f"  {item.item_id:<30} {item.name}")
        return

    scanner = EnhancedMarketScanner(
        items=args.items,
        cities=args.cities,
        max_stale_hours=args.max_stale,
        outlier_multiplier=args.outlier_mult,
        min_profit=args.min_profit,
        min_margin=args.min_margin,
        include_black_market=not args.no_black_market,
    )

    try:
        flips = scanner.scan(quality=args.quality, limit=args.limit)
        print_flips(flips, limit=args.limit)
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
