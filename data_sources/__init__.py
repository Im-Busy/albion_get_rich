"""
Abstracted Data Sources for Albion Get Rich.

Provides a unified interface for market and zone data with automatic fallback:
- Market Data: NATS (real-time) → REST API → Cache
- Zone Data: Live CF Bypass → Static JSON
"""

from .market_sources import (
    MarketDataSource,
    NATSMarketSource,
    RESTAPIMarketSource,
    CachedMarketSource,
    MarketDataOrchestrator,
)
from .zone_sources import (
    ZoneDataSource,
    Albion2DZoneSource,
    StaticFileZoneSource,
    ZoneDataOrchestrator,
)

__all__ = [
    "MarketDataSource",
    "NATSMarketSource",
    "RESTAPIMarketSource",
    "CachedMarketSource",
    "MarketDataOrchestrator",
    "ZoneDataSource",
    "Albion2DZoneSource",
    "StaticFileZoneSource",
    "ZoneDataOrchestrator",
]
