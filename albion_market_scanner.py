"""
Albion Market Scanner — Smart City Flipping Scanner

Ingests real-time market data from AO Data REST API + NATS stream,
calculates profitable buy-low/sell-high routes between cities.

Usage:
    uv run python -m albion_market_scanner          # CLI mode
    uv run python -m albion_market_scanner --server  # HTTP API mode (integrated with web/)
"""

import json
import sys
import time
import asyncio
import logging

# Force UTF-8 output on Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import httpx

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

API_BASE = "https://west.albion-online-data.com/api/v2/stats"

NATS_SERVER = "nats://www.albion-online-data.com:4222"
NATS_USER = "public"
NATS_PASS = "thenewalbiondata"

# ─── Location Mapping (LocationId → Name) ────────────────────────────────────
# Sourced from AlbionTradeBot notes + AO Data API docs

LOCATION_MAP: dict[int, str] = {
    1: "Caerleon Bank",
    1002: "Fort Sterling",
    1003: "Lymhurst",
    1004: "Thetford",
    1005: "Bridgewatch",
    1006: "Martlock",
    2001: "Black Market (Caerleon)",
    2131: "Caerleon",
    3007: "Blean",  # Outlands
    3008: "Wasteland",  # Outlands
    3009: "Steppe",  # Outlands
    3010: "Fenrock",  # Outlands
    3011: "Highland",  # Outlands
    3012: "Mountain",  # Outlands
    3013: "Longmarsh",  # Outlands
    3014: "Halfmoor",  # Outlands
    3015: "Deadpine",  # Outlands
    3016: "Everwinter",  # Outlands
    3017: "Redroad",  # Outlands
    3018: "Hell's Maw",  # Outlands
    3201: "Learcrest",  # Outlands
    3202: "Bankspring",  # Outlands
    3203: "Timberslope",  # Outlands
    3204: "Flatcliff",  # Outlands
    3205: "Laketown",  # Outlands
    3206: "Sunstrand",  # Outlands
    3207: "Stonehollow",  # Outlands
    3208: "Gibberlands",  # Outlands
    3209: "Deepwood",  # Outlands
    3210: "Murkweald",  # Outlands
    3301: "Inis Mon",  # Avalon Roads
    3302: "Ivory Glade",  # Avalon Roads
    3303: "Glen Astrid",  # Avalon Roads
    3304: "Lynford",  # Avalon Roads
    3305: "Aldan",  # Avalon Roads
    3306: "Merlyn's Rest",  # Avalon Roads
    3307: "Tawny Camp",  # Avalon Roads
    3308: "Arthur's Rest",  # Avalon Roads
    3309: "Camelot Ruins",  # Avalon Roads
}

# Royal cities for the core flipping scanner
ROYAL_CITIES = [
    "Martlock",
    "Lymhurst",
    "Thetford",
    "Bridgewatch",
    "Fort Sterling",
    "Caerleon",
]

# Items to track by default (T4-T8 common trade goods)
DEFAULT_ITEMS = [
    # T4-T8 Basic materials (bulk trade goods)
    "T4_CLOTH",
    "T5_CLOTH",
    "T6_CLOTH",
    "T7_CLOTH",
    "T8_CLOTH",
    "T4_LEATHER",
    "T5_LEATHER",
    "T6_LEATHER",
    "T7_LEATHER",
    "T8_LEATHER",
    "T4_METALBAR",
    "T5_METALBAR",
    "T6_METALBAR",
    "T7_METALBAR",
    "T8_METALBAR",
    "T4_PLANKS",
    "T5_PLANKS",
    "T6_PLANKS",
    "T7_PLANKS",
    "T8_PLANKS",
    "T4_ROCK",
    "T5_ROCK",
    "T6_ROCK",
    "T7_ROCK",
    "T8_ROCK",
    # Food
    "T4_FISH",
    "T5_FISH",
    "T6_FISH",
    "T7_FISH",
    # Equipment
    "T4_BAG",
    "T5_BAG",
    "T4_CAPE",
    "T5_CAPE",
    # Weapons
    "T4_SWORD",
    "T5_SWORD",
    "T6_SWORD",
    "T7_SWORD",
    "T4_AXE",
    "T5_AXE",
    "T6_AXE",
    "T4_MACE",
    "T5_MACE",
    "T6_MACE",
    "T4_BOW",
    "T5_BOW",
    "T6_BOW",
]


# ─── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class MarketOrder:
    """Represents a single market order."""

    item_id: str
    location: str
    quality: int  # 1 (normal) - 4 (masterpiece)
    enchantment: int  # 0-3
    price: int
    amount: int
    auction_type: str  # "offer" (sell) or "request" (buy)


@dataclass
class PricePoint:
    """Aggregated price for an item at a location."""

    item_id: str
    city: str
    quality: int
    enchantment: int
    buy_price: int  # Best buy order (city buys at this price)
    buy_amount: int  # Quantity available at buy price
    sell_price: int  # Best sell order (city sells at this price)
    sell_amount: int  # Quantity available at sell price


@dataclass
class FlipOpportunity:
    """A profitable buy-low, sell-high opportunity between two cities."""

    item_id: str
    from_city: str
    to_city: str
    quality: int
    enchantment: int
    buy_price: int  # Price to buy in from_city
    sell_price: int  # Price to sell in to_city
    raw_profit: int  # sell_price - buy_price
    profit_margin: float  # raw_profit / buy_price * 100
    quantity: int  # Available quantity at the source sell price
    # Route info
    travel_time_minutes: float = 0.0
    profit_per_hour: float = 0.0
    # Travel cost (sell tax ~3% sell price, transport tax varies)
    sell_tax: int = 0
    net_profit: int = 0


# ─── Market Data Fetcher ─────────────────────────────────────────────────────


class MarketDataFetcher:
    """Fetches market data from AO Data REST API."""

    def __init__(self, api_base: str = API_BASE):
        self.api_base = api_base
        self._client = httpx.Client(timeout=30)

    def get_prices(
        self,
        items: list[str],
        locations: list[str],
        quality: int = 1,
    ) -> list[dict]:
        """
        Fetch current prices from AO Data API.

        Args:
            items: List of item type IDs (e.g., ["T4_CLOTH", "T5_CLOTH"])
            locations: List of city names
            quality: Quality level (1-4)

        Returns:
            List of price dicts from the API
        """
        item_param = ",".join(items)
        loc_param = ",".join(locations)

        url = (
            f"{self.api_base}/prices/{item_param}"
            f"?locations={loc_param}"
            f"&qualities={quality}"
        )

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.RequestError as e:
            log.error(f"API request failed: {e}")
            return []

    def close(self):
        self._client.close()


# ─── Flip Calculator ─────────────────────────────────────────────────────────


class FlipCalculator:
    """
    Takes raw market data and identifies profitable flip opportunities.

    Sell tax estimate: ~3% of sell price (standard market sell tax).
    Buy tax: ~1-2% of buy price (standard market buy tax).
    """

    SELL_TAX_RATE = 0.03
    BUY_TAX_RATE = 0.015
    MIN_PROFIT_MARGIN = 0.05  # 5% minimum margin
    MIN_RAW_PROFIT = 100  # 100 silver minimum raw profit

    def __init__(
        self,
        route_finder=None,
    ):
        self.route_finder = route_finder

    def calculate_flips(
        self,
        market_data: list[dict],
        cities: Optional[list[str]] = None,
        min_profit: int = MIN_RAW_PROFIT,
        min_margin: float = MIN_PROFIT_MARGIN,
    ) -> list[FlipOpportunity]:
        """
        Calculate all profitable flip opportunities from market data.

        Args:
            market_data: Raw data from AO Data API
            cities: Cities to consider (default: all in data)
            min_profit: Minimum raw profit in silver
            min_margin: Minimum profit margin

        Returns:
            List of FlipOpportunity, sorted by profit margin descending
        """
        if cities is None:
            cities = ROYAL_CITIES

        # Organize data: (item_id, quality, enchantment) → {city → {sell_price, sell_amount, buy_price, buy_amount}}
        price_map: dict[tuple[str, int, int], dict[str, dict]] = {}

        for entry in market_data:
            item_id = entry.get("item_id", "")
            city = entry.get("city", "")  # API uses 'city' not 'location'
            if city not in cities:
                continue

            quality = entry.get("quality", 1)
            # Enchantment is not included in the stats/prices endpoint aggregation
            enchantment = 0

            sell_price = entry.get("sell_price_min", 0)
            buy_price = entry.get(
                "buy_price_max", 0
            )  # best price to sell *to* (highest buyer)
            # Note: quantity fields are not included in the aggregated stats/prices endpoint
            sell_amount = 0
            buy_amount = 0

            key = (item_id, quality, enchantment)
            if key not in price_map:
                price_map[key] = {}

            price_map[key][city] = {
                "sell_price": sell_price,
                "sell_amount": sell_amount,
                "buy_price": buy_price,
                "buy_amount": buy_amount,
            }

        # Find cross-city flips
        flips: list[FlipOpportunity] = []

        for (item_id, quality, enchantment), city_prices in price_map.items():
            city_list = list(city_prices.keys())

            for i, from_city in enumerate(city_list):
                for to_city in city_list[i + 1 :]:
                    from_data = city_prices[from_city]
                    to_data = city_prices[to_city]

                    # Direction A: Buy in from_city, sell in to_city
                    flip_a = self._check_flip(
                        item_id,
                        from_city,
                        to_city,
                        from_data,
                        to_data,
                        quality,
                        enchantment,
                    )
                    if flip_a:
                        flips.append(flip_a)

                    # Direction B: Buy in to_city, sell in from_city
                    flip_b = self._check_flip(
                        item_id,
                        to_city,
                        from_city,
                        to_data,
                        from_data,
                        quality,
                        enchantment,
                    )
                    if flip_b:
                        flips.append(flip_b)

        # Calculate travel times and per-hour profit
        if self.route_finder:
            self._enrich_with_travel_times(flips)

        # Sort by profitability
        flips.sort(
            key=lambda f: (
                f.profit_per_hour if f.profit_per_hour > 0 else f.profit_margin
            ),
            reverse=True,
        )

        return flips

    def _check_flip(
        self,
        item_id: str,
        from_city: str,
        to_city: str,
        source: dict,
        dest: dict,
        quality: int,
        enchantment: int,
    ) -> Optional[FlipOpportunity]:
        """
        Check if buying in source city and selling in dest city is profitable.

        We buy at source's sell_price_min (what sellers are asking)
        and sell at dest's buy_price_min (what buyers are offering).
        """
        buy_price = source["sell_price"]
        sell_price = dest["buy_price"]
        quantity = source["sell_amount"]

        if buy_price <= 0 or sell_price <= 0:
            return None
        if sell_price <= buy_price:
            return None

        raw_profit = sell_price - buy_price
        margin = raw_profit / buy_price

        if raw_profit < self.MIN_RAW_PROFIT:
            return None
        if margin < self.MIN_PROFIT_MARGIN:
            return None

        sell_tax = int(sell_price * self.SELL_TAX_RATE)
        net_profit = raw_profit - sell_tax

        opportunity = FlipOpportunity(
            item_id=item_id,
            from_city=from_city,
            to_city=to_city,
            quality=quality,
            enchantment=enchantment,
            buy_price=buy_price,
            sell_price=sell_price,
            raw_profit=raw_profit,
            profit_margin=margin,
            quantity=quantity,
            sell_tax=sell_tax,
            net_profit=net_profit,
        )

        return opportunity

    def _enrich_with_travel_times(self, flips: list[FlipOpportunity]):
        """Add travel time and profit-per-hour to each flip."""
        if not self.route_finder:
            return

        for flip in flips:
            route = self.route_finder.find_route(flip.from_city, flip.to_city)
            if route:
                flip.travel_time_minutes = route.total_minutes
                if route.total_minutes > 0:
                    flip.profit_per_hour = flip.net_profit / (
                        route.total_minutes / 60.0
                    )
            else:
                # Same city or no route — assume minimal time
                flip.travel_time_minutes = 1.0
                flip.profit_per_hour = flip.net_profit * 60


# ─── Scanner (Orchestrator) ──────────────────────────────────────────────────


class AlbionMarketScanner:
    """
    Main scanner: fetches market data, calculates flips, returns results.

    Can be used as:
    1. CLI tool (runs once, prints results)
    2. As a module imported by the FastAPI web app
    3. As a NATS subscriber for real-time updates
    """

    def __init__(
        self,
        items: Optional[list[str]] = None,
        cities: Optional[list[str]] = None,
        route_finder=None,
    ):
        self.items = items or DEFAULT_ITEMS
        self.cities = cities or ROYAL_CITIES
        self.fetcher = MarketDataFetcher()
        self.calculator = FlipCalculator(route_finder=route_finder)

    def scan_once(
        self,
        quality: int = 1,
        min_profit: int = 100,
        min_margin: float = 0.05,
    ) -> list[FlipOpportunity]:
        """Run a single scan and return flip opportunities."""
        log.info(f"Fetching prices for {len(self.items)} items in {self.cities}...")

        data = self.fetcher.get_prices(
            items=self.items,
            locations=self.cities,
            quality=quality,
        )

        if not data:
            log.warning("No market data received")
            return []

        log.info(f"Received {len(data)} price entries, calculating flips...")

        flips = self.calculator.calculate_flips(
            market_data=data,
            cities=self.cities,
            min_profit=min_profit,
            min_margin=min_margin,
        )

        log.info(f"Found {len(flips)} flip opportunities")
        return flips

    def close(self):
        self.fetcher.close()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _print_flips(flips: list[FlipOpportunity], limit: int = 50):
    """Pretty-print flip opportunities."""
    if not flips:
        print("\nNo profitable flips found.")
        return

    print(f"\n{'=' * 100}")
    print(f"  PROFITABLE FLIPS FOUND: {min(len(flips), limit)} of {len(flips)}")
    print(f"{'=' * 100}")

    print(
        f"  {'Item':<25} {'From':<16} {'To':<16} {'Buy':>10} {'Sell':>10} {'Tax':>8} {'Net':>10} {'Margin':>7} {'Qty':>6} {'$/hr':>10}"
    )
    print(
        f"\n  {'─' * 25} {'─' * 16} {'─' * 16} {'─' * 10} {'─' * 10} {'─' * 8} {'─' * 10} {'─' * 7} {'─' * 6} {'─' * 10}"
    )

    for flip in flips[:limit]:
        item_short = flip.item_id[:24]
        profit_str = f"{flip.net_profit:,}"
        margin_str = f"{flip.profit_margin * 100:.1f}%"
        ph_str = f"{flip.profit_per_hour:,.0f}" if flip.profit_per_hour > 0 else "N/A"

        print(
            f"  {item_short:<25} "
            f"{flip.from_city:<16} "
            f"{flip.to_city:<16} "
            f"{flip.buy_price:>10,} "
            f"{flip.sell_price:>10,} "
            f"{flip.sell_tax:>8,} "
            f"{profit_str:>10} "
            f"{margin_str:>7} "
            f"{flip.quantity:>6} "
            f"{ph_str:>10}"
        )

    print(f"\n{'=' * 100}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Albion Market Scanner — Smart City Flipping"
    )
    parser.add_argument(
        "--items", nargs="+", help="Items to scan (default: built-in list)"
    )
    parser.add_argument(
        "--cities", nargs="+", help="Cities to scan (default: royal cities)"
    )
    parser.add_argument(
        "--quality", type=int, default=1, help="Quality level (1-4, default: 1)"
    )
    parser.add_argument(
        "--min-profit", type=int, default=100, help="Minimum profit in silver"
    )
    parser.add_argument(
        "--min-margin", type=float, default=0.05, help="Minimum margin (0.05 = 5%)"
    )
    parser.add_argument("--limit", type=int, default=50, help="Max results to show")
    parser.add_argument(
        "--route-data", help="Path to zone JSON for travel time calculation"
    )

    args = parser.parse_args()

    # Load route finder if available
    route_finder = None
    if args.route_data:
        try:
            from albion_route_finder import AlbionRouteFinder

            route_finder = AlbionRouteFinder(Path(args.route_data))
            log.info(f"Route finder loaded with {len(route_finder.zones)} zones")
        except ImportError:
            log.warning(
                "albion_route_finder not available, travel times won't be calculated"
            )

    scanner = AlbionMarketScanner(
        items=args.items,
        cities=args.cities,
        route_finder=route_finder,
    )

    try:
        flips = scanner.scan_once(
            quality=args.quality,
            min_profit=args.min_profit,
            min_margin=args.min_margin,
        )
        _print_flips(flips, limit=args.limit)
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
