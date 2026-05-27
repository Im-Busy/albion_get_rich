"""
Market PvP Scanner — Intra-City Spread Manipulation Detector

Scans Albion Online markets within a single city to find items with wide spreads
between best sell offer and best buy order — opportunities for the "Market PvP"
strategy where you place a decoy sell order to manipulate perceived market price.

Strategy Overview:
1. Find item selling at ~27,000 in city
2. Place decoy Sell Order: 1 unit at 17,000 (false floor)
3. Place Buy Order: 10+ units at 16,999 (1 silver below decoy)
4. Lazy/desperate players sell at or below your floor → Buy Order absorbs them
5. Cancel decoy, sell accumulated stock at real price (~27,000)

Usage:
    uv run python -m market_pvp_scanner
    uv run python -m market_pvp_scanner --city Lymhurst --min-spread 5000
    uv run python -m market_pvp_scanner --city Martlock --min-volume 50 --sell-tax 0.025
    uv run python -m market_pvp_scanner --no-history   # skip liquidity analysis
"""

import json
import sys
import time
import statistics
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional
from itertools import islice

import httpx

# Force UTF-8 output on Windows console
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

API_BASE = "https://west.albion-online-data.com/api/v2/stats"

ROYAL_CITIES = [
    "Martlock",
    "Lymhurst",
    "Thetford",
    "Bridgewatch",
    "Fort Sterling",
    "Caerleon",
]

# ─── Sell Tax Rates (Premium vs Non-Premium) ─────────────────────────────────
# Premium: ~2.5% sell tax
# Non-Premium: ~4% sell tax (varies by market standing)
# Buy Orders: free to place
SELL_TAX_PREMIUM = 0.025
SELL_TAX_NON_PREMIUM = 0.04

# ─── Liquidity Defaults ──────────────────────────────────────────────────────
HISTORY_DAYS = 7  # Lookback period for trade volume
HISTORY_TIME_SCALE = 24  # 24 = daily aggregation

# ─── Data Types ──────────────────────────────────────────────────────────────


@dataclass
class LiquidityStats:
    """Estimated liquidity metrics for an item based on historical sales data."""

    avg_daily_volume: float  # Average items sold per day
    recent_volume_24h: float  # Items sold in last 24 hours (if data available)
    recent_volume_48h: float  # Items sold in last 48 hours
    volume_std_dev: float  # Standard deviation of daily volume
    volume_cv: float  # Coefficient of variation (std_dev / mean); lower = more stable
    has_sales_pct: float  # Percentage of days with at least 1 sale
    total_volume: int  # Total items sold over the lookback period
    days_tracked: int  # Number of days of history available

    # Composite score 0-100 (higher = more liquid)
    liquidity_score: float

    # Classification
    liquidity_grade: str = ""  # S, A, B, C, D, F

    def classification(self):
        s = self.liquidity_score
        if s >= 80:
            return "S"  # Extremely liquid - safe
        elif s >= 60:
            return "A"  # Very liquid
        elif s >= 40:
            return "B"  # Moderately liquid
        elif s >= 20:
            return "C"  # Low liquidity - risky
        elif s >= 5:
            return "D"  # Very low liquidity - dangerous
        else:
            return "F"  # Illiquid - avoid


@dataclass
class SpreadOpportunity:
    """
    An item where the Market PvP spread manipulation strategy could work.

    The spread = sell_price_min - buy_price_max
    A wide spread means room to place a deceptive floor price.
    """

    item_id: str
    location: str
    quality: int

    # Current market data
    sell_price_min: int
    sell_amount_min: int
    buy_price_max: int
    buy_amount_max: int
    sell_price_max: int
    buy_price_min: int

    # Calculated
    spread: int
    spread_pct: float

    # Strategy implications
    suggested_decoy_price: int
    suggested_buy_price: int
    max_profit_per_unit: int
    estimated_tax: int
    net_profit_per_unit: int

    # Safety check
    has_one_silver_trap: bool

    # Liquidity info
    liquidity: Optional[LiquidityStats] = None


# ─── Liquidity Analyzer ──────────────────────────────────────────────────────


class LiquidityAnalyzer:
    """
    Estimates item liquidity using the AO Data History API.

    The history endpoint returns aggregated sell order data:
    - item_count: total number of items sold in the time period
    - avg_price: average price of items sold
    - timestamp: end of the time period

    We analyze volume patterns to assess how easy it will be to re-sell
    items acquired through the Market PvP strategy.
    """

    def __init__(
        self,
        api_base: str = API_BASE,
        days: int = HISTORY_DAYS,
        time_scale: int = HISTORY_TIME_SCALE,
        rate_limit_delay: float = 1.2,  # seconds between requests (180/min → ~0.33s, be safe)
    ):
        self.api_base = api_base
        self.days = days
        self.time_scale = time_scale
        self.rate_limit_delay = rate_limit_delay
        self._client = httpx.Client(timeout=30)
        self._last_request_time = 0.0

    def analyze(
        self,
        items: list[tuple[str, str]],  # list of (item_id, city)
    ) -> dict[tuple[str, str], LiquidityStats]:
        """
        Analyze liquidity for multiple item-city pairs.
        Returns a dict mapping (item_id, city) → LiquidityStats.
        """
        results: dict[tuple[str, str], LiquidityStats] = {}

        # History API: 1 item per request, 1 city per request
        # We must call per (item, city) pair
        for item_id, city in items:
            self._rate_limit_sleep()
            stats = self._analyze_single(item_id, city)
            results[(item_id, city)] = stats

        return results

    def _rate_limit_sleep(self):
        """Respect API rate limit (180 req/min)."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _analyze_single(self, item_id: str, city: str) -> LiquidityStats:
        """Analyze liquidity for a single item-city pair."""
        # Calculate date range (MM-DD-YYYY format for API)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.days)

        date_str = start_date.strftime("%m-%d-%Y")
        end_date_str = end_date.strftime("%m-%d-%Y")

        url = (
            f"{self.api_base}/history/{item_id}"
            f"?locations={city}"
            f"&time-scale={self.time_scale}"
            f"&date={date_str}"
            f"&end_date={end_date_str}"
        )

        try:
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.debug(f"History fetch failed for {item_id}@{city}: {e}")
            return LiquidityStats(
                avg_daily_volume=0,
                recent_volume_24h=0,
                recent_volume_48h=0,
                volume_std_dev=0,
                volume_cv=999,
                has_sales_pct=0,
                total_volume=0,
                days_tracked=0,
                liquidity_score=0,
            )

        if not data:
            return LiquidityStats(
                avg_daily_volume=0,
                recent_volume_24h=0,
                recent_volume_48h=0,
                volume_std_dev=0,
                volume_cv=999,
                has_sales_pct=0,
                total_volume=0,
                days_tracked=0,
                liquidity_score=0,
            )

        # Parse the history data
        # API returns: [{"location": "...", "item_id": "...", "quality": N, "data": [...]}]
        volumes: list[float] = []
        for entry in data:
            history_data = entry.get("data", [])
            for point in history_data:
                item_count = point.get("item_count", 0)
                volumes.append(float(item_count))

        if not volumes:
            return LiquidityStats(
                avg_daily_volume=0,
                recent_volume_24h=0,
                recent_volume_48h=0,
                volume_std_dev=0,
                volume_cv=999,
                has_sales_pct=0,
                total_volume=0,
                days_tracked=0,
                liquidity_score=0,
            )

        # Calculate metrics
        days_tracked = len(volumes)
        total_volume = int(sum(volumes))
        avg_daily = total_volume / days_tracked if days_tracked > 0 else 0
        std_dev = statistics.stdev(volumes) if len(volumes) >= 2 else 0
        cv = (std_dev / avg_daily) if avg_daily > 0 else 999
        has_sales_pct = (
            (sum(1 for v in volumes if v > 0) / days_tracked * 100)
            if days_tracked > 0
            else 0
        )

        # Recent volumes (last 1 = 24h, last 2 = 48h for daily scale)
        recent_24h = volumes[-1] if len(volumes) >= 1 else 0
        recent_48h = sum(volumes[-2:]) if len(volumes) >= 2 else recent_24h

        # ─── Composite Liquidity Score (0-100) ───
        # Based on 4 factors:
        # 1. Volume score (0-30): Higher avg volume = more liquid
        # 2. Consistency score (0-25): Lower CV = more predictable
        # 3. Sales frequency score (0-25): More days with sales = more liquid
        # 4. Recent activity score (0-20): Recent volume > 0 = active market
        #
        # Thresholds designed for Albion market realities:
        # - T4-CLOTH sells 10,000-50,000/day → S grade
        # - T5-SWORD might sell 100-500/day → B grade
        # - Rare items sell 1-10/day → F grade

        volume_score = min(avg_daily / 500.0, 1.0) * 30  # 500/day = max
        consistency_score = max(0, 1 - cv / 2.0) * 25  # CV < 0.5 = max
        frequency_score = (has_sales_pct / 100.0) * 25
        recent_score = min(recent_48h / 100.0, 1.0) * 20  # 100 in 48h = max

        raw_score = volume_score + consistency_score + frequency_score + recent_score

        # Bonus for very high volume items (they have guaranteed buyers)
        if avg_daily > 1000:
            raw_score = min(raw_score + 10, 100)
        elif avg_daily > 5000:
            raw_score = min(raw_score + 20, 100)

        liquidity_score = round(min(raw_score, 100), 1)

        stats = LiquidityStats(
            avg_daily_volume=round(avg_daily, 1),
            recent_volume_24h=int(recent_24h),
            recent_volume_48h=int(recent_48h),
            volume_std_dev=round(std_dev, 1),
            volume_cv=round(cv, 2),
            has_sales_pct=round(has_sales_pct, 1),
            total_volume=total_volume,
            days_tracked=days_tracked,
            liquidity_score=liquidity_score,
        )
        stats.liquidity_grade = stats.classification()

        return stats

    def close(self):
        self._client.close()


# ─── Market Data Fetcher ─────────────────────────────────────────────────────


class MarketPvPDataFetcher:
    """Fetches current market prices from AO Data API."""

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
        Fetch current prices. Response includes:
        - sell_price_min: cheapest sell listing
        - sell_price_max: most expensive sell listing
        - buy_price_min: lowest buy order (check for 1-silver traps!)
        - buy_price_max: highest buy order (what instant-sell gives)

        Batches requests to stay within the 4096 char URL limit.
        """
        loc_param = ",".join(locations)
        results: list[dict] = []

        batch: list[str] = []
        batch_len = 0
        MAX_URL_LEN = 3800

        for item in items:
            item_len = len(item) + 1
            if batch_len + item_len > MAX_URL_LEN:
                results.extend(self._fetch_batch(batch, loc_param, quality))
                batch = []
                batch_len = 0
            batch.append(item)
            batch_len += item_len

        if batch:
            results.extend(self._fetch_batch(batch, loc_param, quality))

        return results

    def _fetch_batch(
        self, items: list[str], loc_param: str, quality: int
    ) -> list[dict]:
        """Fetch a single batch of items."""
        if not items:
            return []

        item_param = ",".join(items)
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
            log.error(f"API request failed for batch: {e}")
            return []

    def close(self):
        self._client.close()


# ─── Spread Calculator ───────────────────────────────────────────────────────

# Spread-specific scoring weights for combining with liquidity:
# Spread score max: 100
# Liquidity score min threshold: 20 (D grade)


class SpreadCalculator:
    """Identifies items where the Market PvP spread strategy is viable."""

    MIN_SPREAD = 1000
    MIN_SPREAD_PCT = 10.0
    MIN_REAL_PRICE = 1000

    def __init__(
        self,
        sell_tax: float = SELL_TAX_PREMIUM,
        min_spread: int = MIN_SPREAD,
        min_spread_pct: float = MIN_SPREAD_PCT,
        min_real_price: int = MIN_REAL_PRICE,
        min_liquidity_score: float = 0,  # 0 = don't filter by liquidity
    ):
        self.sell_tax = sell_tax
        self.min_spread = min_spread
        self.min_spread_pct = min_spread_pct
        self.min_real_price = min_real_price
        self.min_liquidity_score = min_liquidity_score

    def calculate_spreads(
        self,
        market_data: list[dict],
        liquidity_data: Optional[dict[tuple[str, str], LiquidityStats]] = None,
    ) -> list[SpreadOpportunity]:
        """Calculate spread opportunities, enriched with liquidity data if available."""
        opportunities: list[SpreadOpportunity] = []

        for entry in market_data:
            item_id = entry.get("item_id", "")
            location = entry.get("city", "")
            quality = entry.get("quality", 1)

            sell_price_min = entry.get("sell_price_min", 0)
            sell_amount = entry.get("sell_listings", 0)
            buy_price_max = entry.get("buy_price_max", 0)
            buy_amount = entry.get("sell_listings", 0)
            sell_price_max = entry.get("sell_price_max", 0)
            buy_price_min = entry.get("buy_price_min", 0)

            # Skip items with no real market activity
            if sell_price_min <= 0 or buy_price_max <= 0:
                continue

            spread = sell_price_min - buy_price_max
            spread_pct = (spread / sell_price_min) * 100 if sell_price_min > 0 else 0

            # Filter by minimum spread criteria
            if spread < self.min_spread:
                continue
            if spread_pct < self.min_spread_pct:
                continue
            if sell_price_min < self.min_real_price:
                continue

            # Strategy parameters
            spread_room = sell_price_min - buy_price_max
            suggested_decoy = buy_price_max + int(spread_room * 0.35)
            suggested_buy = suggested_decoy - 1

            if suggested_decoy > sell_price_min:
                suggested_decoy = sell_price_min - int(spread_room * 0.3)
                suggested_buy = suggested_decoy - 1

            # Profit calculation
            max_profit = sell_price_min - suggested_buy
            estimated_tax = int(sell_price_min * self.sell_tax)
            net_profit = max_profit - estimated_tax

            if net_profit <= 0:
                continue

            # 1-silver trap check
            has_one_silver_trap = buy_price_min <= 2

            # Attach liquidity if available
            liquidity = None
            if liquidity_data:
                liquidity = liquidity_data.get((item_id, location))
                if liquidity and liquidity.liquidity_score < self.min_liquidity_score:
                    continue  # Filter out illiquid items

            opp = SpreadOpportunity(
                item_id=item_id,
                location=location,
                quality=quality,
                sell_price_min=sell_price_min,
                sell_amount_min=sell_amount,
                buy_price_max=buy_price_max,
                buy_amount_max=buy_amount,
                sell_price_max=sell_price_max,
                buy_price_min=buy_price_min,
                spread=spread,
                spread_pct=spread_pct,
                suggested_decoy_price=suggested_decoy,
                suggested_buy_price=suggested_buy,
                max_profit_per_unit=max_profit,
                estimated_tax=estimated_tax,
                net_profit_per_unit=net_profit,
                has_one_silver_trap=has_one_silver_trap,
                liquidity=liquidity,
            )
            opportunities.append(opp)

        # Sort by: liquidity_score * net_profit (combined score)
        # Items that are both profitable AND liquid rank highest
        def _sort_key(opp: SpreadOpportunity) -> float:
            liq_score = opp.liquidity.liquidity_score if opp.liquidity else 50
            spread_score = min(opp.spread_pct, 100)  # cap at 100
            profit_norm = min(opp.net_profit_per_unit / 100000.0, 1.0)  # normalize
            # Weight: 40% liquidity, 30% spread %, 30% profit
            return liq_score * 0.4 + spread_score * 0.3 + profit_norm * 100 * 0.3

        opportunities.sort(key=_sort_key, reverse=True)
        return opportunities


# ─── Scanner ─────────────────────────────────────────────────────────────────


class MarketPvPScanner:
    """Main scanner for Market PvP spread opportunities with liquidity analysis."""

    def __init__(
        self,
        items: Optional[list[str]] = None,
        cities: Optional[list[str]] = None,
        sell_tax: float = SELL_TAX_PREMIUM,
        min_spread: int = 1000,
        min_spread_pct: float = 10.0,
        use_history: bool = True,
        min_liquidity_score: float = 0,
        history_days: int = HISTORY_DAYS,
    ):
        self.items = items or []
        self.cities = cities or ROYAL_CITIES
        self.fetcher = MarketPvPDataFetcher()
        self.use_history = use_history
        self.calculator = SpreadCalculator(
            sell_tax=sell_tax,
            min_spread=min_spread,
            min_spread_pct=min_spread_pct,
            min_liquidity_score=min_liquidity_score,
        )
        self.liquidity_analyzer = (
            LiquidityAnalyzer(
                days=history_days,
            )
            if use_history
            else None
        )

    def scan_once(
        self,
        quality: int = 1,
    ) -> list[SpreadOpportunity]:
        """Run a single scan and return spread opportunities with liquidity data."""
        if not self.items:
            log.error("No items specified for scanning")
            return []

        log.info(f"Fetching prices for {len(self.items)} items in {self.cities}...")

        data = self.fetcher.get_prices(
            items=self.items,
            locations=self.cities,
            quality=quality,
        )

        if not data:
            log.warning("No market data received")
            return []

        log.info(f"Received {len(data)} price entries, calculating spreads...")

        # Pre-filter spread opportunities
        spread_opps = self.calculator.calculate_spreads(market_data=data)
        log.info(f"Found {len(spread_opps)} spread opportunities (pre-liquidity)")

        # Fetch liquidity data for spread opportunities only
        if self.use_history and spread_opps:
            liquidity_pairs = [(opp.item_id, opp.location) for opp in spread_opps]
            # Deduplicate
            liquidity_pairs = list(dict.fromkeys(liquidity_pairs))
            log.info(
                f"Analyzing liquidity for {len(liquidity_pairs)} item-city pairs..."
            )

            liquidity_data = self.liquidity_analyzer.analyze(liquidity_pairs)

            # Enrich spread opportunities with liquidity
            liquidity_dict: dict = {}
            for (item, city), stats in liquidity_data.items():
                liquidity_dict[(item, city)] = stats

            spread_opps = self.calculator.calculate_spreads(
                market_data=data,
                liquidity_data=liquidity_dict,
            )
            log.info(f"Found {len(spread_opps)} opportunities after liquidity filter")

        return spread_opps

    def close(self):
        self.fetcher.close()
        if self.liquidity_analyzer:
            self.liquidity_analyzer.close()


# ─── Display ─────────────────────────────────────────────────────────────────


def print_opportunities(opportunities: list[SpreadOpportunity], limit: int = 50):
    """Pretty-print spread opportunities with liquidity grades."""
    if not opportunities:
        print("\nNo spread opportunities found matching criteria.")
        return

    use_liquidity = any(opp.liquidity is not None for opp in opportunities)

    if use_liquidity:
        print(f"\n{'=' * 180}")
        print(
            f"  MARKET PvP OPPORTUNITIES (with Liquidity): {min(len(opportunities), limit)} of {len(opportunities)}"
        )
        print(f"{'=' * 180}")

        print(
            f"  {'Item':<25} {'City':<14} {'SellMin':>10} {'BuyMax':>10} {'NetProfit':>10} "
            f"{'Spread%':>7} {'Decoy':>10} {'Liq':>3} {'Grade':>5} "
            f"{'DailyVol':>8} {'48hVol':>8} {'HasSales%':>9} {'1$Trap':>7}"
        )
        print(
            f"  {'─' * 25} {'─' * 14} {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 7} "
            f"{'─' * 10} {'─' * 3} {'─' * 5} {'─' * 8} {'─' * 8} {'─' * 9} {'─' * 7}"
        )

        for opp in opportunities[:limit]:
            item_short = opp.item_id[:24]
            trap_str = "YES" if opp.has_one_silver_trap else "no"
            liq_score = opp.liquidity.liquidity_score if opp.liquidity else "N/A"
            grade = opp.liquidity.liquidity_grade if opp.liquidity else "—"
            daily_vol = (
                f"{opp.liquidity.avg_daily_volume:,.0f}" if opp.liquidity else "N/A"
            )
            vol_48h = f"{opp.liquidity.recent_volume_48h:,}" if opp.liquidity else "N/A"
            has_sales = (
                f"{opp.liquidity.has_sales_pct:.0f}%" if opp.liquidity else "N/A"
            )

            print(
                f"  {item_short:<25} "
                f"{opp.location:<14} "
                f"{opp.sell_price_min:>10,} "
                f"{opp.buy_price_max:>10,} "
                f"{opp.net_profit_per_unit:>10,} "
                f"{opp.spread_pct:>6.1f}% "
                f"{opp.suggested_decoy_price:>10,} "
                f"{liq_score:>3} "
                f"{grade:>5} "
                f"{daily_vol:>8} "
                f"{vol_48h:>8} "
                f"{has_sales:>9} "
                f"{trap_str:>7}"
            )

        print(f"\n{'=' * 180}")
        print(f"\n  Liquidity Grade Legend:")
        print(f"    S (80-100) = Extremely liquid — safe to accumulate and resell")
        print(f"    A (60-79)  = Very liquid — easy to resell")
        print(f"    B (40-59)  = Moderately liquid — resellable but may take time")
        print(f"    C (20-39)  = Low liquidity — risky, may be hard to resell")
        print(f"    D (5-19)   = Very low liquidity — dangerous")
        print(f"    F (0-4)    = Illiquid — avoid! You may not find buyers")
    else:
        # Fallback without liquidity data
        print(f"\n{'=' * 140}")
        print(
            f"  MARKET PvP SPREAD OPPORTUNITIES: {min(len(opportunities), limit)} of {len(opportunities)}"
        )
        print(f"{'=' * 140}")

        print(
            f"  {'Item':<25} {'City':<14} {'SellMin':>10} {'BuyMax':>10} {'Spread':>10} {'Spread%':>7} "
            f"{'Decoy':>10} {'Buy@':>10} {'NetProfit':>10} {'Tax':>6} "
            f"{'1$Trap':>7}"
        )
        print(
            f"  {'─' * 25} {'─' * 14} {'─' * 10} {'─' * 10} {'─' * 10} {'─' * 7} "
            f"{'─' * 10} {'─' * 10} {'─' * 10} {'─' * 6} {'─' * 7}"
        )

        for opp in opportunities[:limit]:
            item_short = opp.item_id[:24]
            trap_str = "YES" if opp.has_one_silver_trap else "no"

            print(
                f"  {item_short:<25} "
                f"{opp.location:<14} "
                f"{opp.sell_price_min:>10,} "
                f"{opp.buy_price_max:>10,} "
                f"{opp.spread:>10,} "
                f"{opp.spread_pct:>6.1f}% "
                f"{opp.suggested_decoy_price:>10,} "
                f"{opp.suggested_buy_price:>10,} "
                f"{opp.net_profit_per_unit:>10,} "
                f"{opp.estimated_tax:>6,} "
                f"{trap_str:>7}"
            )

    print(f"\n{'=' * 140}")
    print(f"\n  NOTE: Buy Orders are free. Only sell tax applies when you re-sell.")
    print(f"  '1$Trap' = a 1-silver buy order exists (someone fishing for cheap items)")
    print(f"  Liquidity data from {HISTORY_DAYS}-day history (daily aggregation)")
    print(f"{'=' * 140}")


def print_strategy_guide():
    """Print the Market PvP strategy guide."""
    guide = """
╔═══════════════════════════════════════════════════════════════╗
║                    MARKET PvP STRATEGY GUIDE                   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. IDENTIFY an item selling at ~27,000 in your city          ║
║                                                                ║
║  2. PLACE A DECOY SELL ORDER:                                 ║
║     - 1 unit at a LOWER price (e.g., 17,000)                  ║
║     - This creates a false "market price" signal              ║
║     - You can CANCEL this anytime — minimal risk              ║
║                                                                ║
║  3. PLACE YOUR BUY ORDER:                                     ║
║     - Multiple units at 1 silver below your decoy (16,999)    ║
║     - If someone sells instantly, your order fills first      ║
║                                                                ║
║  4. WAIT AND ABSORB:                                          ║
║     - Lazy players hit "Sell" → system shows your price       ║
║     - They undercut by 1 silver → your Buy Order triggers     ║
║     - Desperate sellers list at your floor → you can buy      ║
║                                                                ║
║  5. PROFIT:                                                   ║
║     - Cancel your decoy (if not filled)                       ║
║     - Sell accumulated stock at real market price             ║
║     - Spread = your acquisition cost vs. real selling price   ║
║                                                                ║
║  6. WATCH OUT FOR:                                            ║
║     - 1-silver safety net buy orders (other players)          ║
║     - Market sell tax (~2.5% premium, ~4% non-premium)       ║
║     - Items that are illiquid (hard to re-sell)              ║
║                                                                ║
╠═══════════════════════════════════════════════════════════════╣
║  LIQUIDITY GRADES                                              ║
║  S/A = Safe to trade. These items sell hundreds/thousands per  ║
║      day. You'll have no trouble reselling.                    ║
║  B   = Acceptable. May take 1-2 days to sell accumulated stock║
║  C/D = Risky. Consider smaller quantities.                    ║
║  F   = Avoid! You may acquire items you can't sell at all.    ║
╠═══════════════════════════════════════════════════════════════╣
║  REVERSE TACTIC: The "1 Silver Safety Net"                    ║
║  Some players place Buy Orders at 1 silver, hoping desperate  ║
║  sellers will hit Sell and get everything for 1 silver.       ║
║  This scanner flags items with active 1-silver traps.         ║
╚═══════════════════════════════════════════════════════════════╝
"""
    print(guide)


# ─── CLI ─────────────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Market PvP Scanner — Find spread manipulation opportunities"
    )
    parser.add_argument(
        "--items", nargs="+", help="Items to scan (default: common trade goods)"
    )
    parser.add_argument(
        "--city",
        nargs="+",
        choices=ROYAL_CITIES,
        help="Specific city/cities to scan",
    )
    parser.add_argument(
        "--quality", type=int, default=1, help="Quality level (1-4, default: 1)"
    )
    parser.add_argument(
        "--min-spread",
        type=int,
        default=1000,
        help="Minimum spread in silver",
    )
    parser.add_argument(
        "--min-spread-pct",
        type=float,
        default=10.0,
        help="Minimum spread percentage",
    )
    parser.add_argument(
        "--sell-tax",
        type=float,
        default=SELL_TAX_PREMIUM,
        help=f"Sell tax rate (default: {SELL_TAX_PREMIUM} premium)",
    )
    parser.add_argument("--limit", type=int, default=50, help="Max results to show")
    parser.add_argument("--guide", action="store_true", help="Print the strategy guide")
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Skip liquidity analysis (faster, but no grades)",
    )
    parser.add_argument(
        "--min-liquidity",
        type=float,
        default=0,
        help="Minimum liquidity score to show (0-100, 0=show all)",
    )
    parser.add_argument(
        "--history-days",
        type=int,
        default=HISTORY_DAYS,
        help=f"Days of history for liquidity analysis (default: {HISTORY_DAYS})",
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Export results to JSON file",
    )

    args = parser.parse_args()

    if args.guide:
        print_strategy_guide()
        return

    default_items = [
        # T4-T8 raw materials
        "T4_CLOTH",
        "T5_CLOTH",
        "T6_CLOTH",
        "T4_LEATHER",
        "T5_LEATHER",
        "T6_LEATHER",
        "T4_METALBAR",
        "T5_METALBAR",
        "T6_METALBAR",
        "T4_PLANKS",
        "T5_PLANKS",
        "T6_PLANKS",
        "T4_ROCK",
        "T5_ROCK",
        "T6_ROCK",
        # Food
        "T4_FISH",
        "T5_FISH",
        "T6_FISH",
        # Equipment
        "T4_BAG",
        "T5_BAG",
        "T4_CAPE",
        "T5_CAPE",
        # Weapons
        "T4_SWORD",
        "T5_SWORD",
        "T6_SWORD",
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

    items = args.items or default_items
    cities = args.city or ROYAL_CITIES

    scanner = MarketPvPScanner(
        items=items,
        cities=cities,
        sell_tax=args.sell_tax,
        min_spread=args.min_spread,
        min_spread_pct=args.min_spread_pct,
        use_history=not args.no_history,
        min_liquidity_score=args.min_liquidity,
        history_days=args.history_days,
    )

    try:
        opportunities = scanner.scan_once(
            quality=args.quality,
        )
        print_opportunities(opportunities, limit=args.limit)

        if args.export:
            export_data = []
            for opp in opportunities:
                d = {
                    "item_id": opp.item_id,
                    "location": opp.location,
                    "sell_price_min": opp.sell_price_min,
                    "buy_price_max": opp.buy_price_max,
                    "spread": opp.spread,
                    "spread_pct": round(opp.spread_pct, 1),
                    "suggested_decoy": opp.suggested_decoy_price,
                    "suggested_buy": opp.suggested_buy_price,
                    "net_profit_per_unit": opp.net_profit_per_unit,
                    "has_one_silver_trap": opp.has_one_silver_trap,
                    "one_silver_trap_at": opp.buy_price_min
                    if opp.has_one_silver_trap
                    else None,
                }
                if opp.liquidity:
                    d["liquidity"] = {
                        "score": opp.liquidity.liquidity_score,
                        "grade": opp.liquidity.liquidity_grade,
                        "avg_daily_volume": opp.liquidity.avg_daily_volume,
                        "recent_48h_volume": opp.liquidity.recent_volume_48h,
                        "has_sales_pct": opp.liquidity.has_sales_pct,
                        "total_volume": opp.liquidity.total_volume,
                    }
                export_data.append(d)

            with open(args.export, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"\nExported {len(export_data)} opportunities to {args.export}")
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
