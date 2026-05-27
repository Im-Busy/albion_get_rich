"""
Albion Navigator & Market Scanner API
FastAPI backend for route finding, zone data, and market flip scanning.

v0.4.0 — Enhanced with:
- 11,000+ item database
- Smart filters (stale data, outliers, fake order detection)
- Premium vs non-premium profit calculation
- Black Market support
- Real-time NATS monitoring with auto-start
- WebSocket push for live flip updates
- SSE streaming for global scanner progress
- Scan job management (start/stop/status)
"""

import asyncio
import time
import json
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import sys

sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))

log = logging.getLogger(__name__)

# ─── Global State ─────────────────────────────────────────────────────────────

_finder = None
_enhanced_scanner = None
_nats_monitor = None
_nats_auto_started = False

_scan_jobs: dict[str, dict] = {}
_ws_clients: list[WebSocket] = []

ZONE_TYPE_NAMES = {
    0: "City",
    1: "Blue",
    2: "Yellow",
    3: "Red",
    4: "Black",
    5: "Dungeon",
    6: "Portal",
    7: "Outlands Town",
}


def get_finder():
    global _finder
    if _finder is None:
        from albion_route_finder import AlbionRouteFinder

        zones_path = (
            Path(__file__).parent.parent / "extracted_maps" / "albion_zones.json"
        )
        _finder = AlbionRouteFinder(zones_path)
    return _finder


def get_enhanced_scanner():
    global _enhanced_scanner
    if _enhanced_scanner is None:
        from albion_market_scanner_enhanced import EnhancedMarketScanner

        _enhanced_scanner = EnhancedMarketScanner()
    return _enhanced_scanner


def get_nats_monitor():
    global _nats_monitor
    if _nats_monitor is None:
        from albion_nats_monitor import NatsMarketMonitor

        _nats_monitor = NatsMarketMonitor()
    return _nats_monitor


async def maybe_auto_start_nats():
    global _nats_auto_started
    if _nats_auto_started:
        return
    _nats_auto_started = True
    monitor = get_nats_monitor()
    if not monitor.is_connected():
        log.info("Auto-starting NATS monitor...")
        try:
            await monitor.start()
            log.info("NATS monitor auto-started successfully")
        except Exception as e:
            log.warning(f"NATS auto-start failed: {e}")


# ─── Lifespan Context Manager ─────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    await maybe_auto_start_nats()
    yield
    monitor = get_nats_monitor()
    if monitor.is_connected():
        await monitor.stop()


# ─── App Setup ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Albion Navigator & Market Scanner",
    description="Route finder, zone explorer, and market flip scanner for Albion Online",
    version="0.4.0",
    lifespan=lifespan,
)


# ─── Route Finder Models ─────────────────────────────────────────────────────


class RouteRequest(BaseModel):
    start: str
    end: str
    avoid_black: bool = False
    avoid_red: bool = False
    avoid_yellow: bool = False


class ZoneInfo(BaseModel):
    id: int
    name: str
    x: float
    y: float
    zone_type: int
    zone_type_name: str
    connections: list[int]


class RouteStepResponse(BaseModel):
    from_zone: str
    to_zone: str
    distance: float
    duration_seconds: float
    zone_type: int
    zone_type_name: str


class RouteResponse(BaseModel):
    steps: list[RouteStepResponse]
    total_distance: float
    total_km: float
    total_duration_seconds: float
    total_minutes: float
    zone_breakdown: dict[str, tuple[float, float]]


# ─── Enhanced Market Scanner Models ──────────────────────────────────────────


class FlipResponse(BaseModel):
    item_id: str
    item_name: str
    quality: int
    enchantment: int
    buy_city: str
    buy_price: int
    sell_city: str
    sell_price: int
    gross_profit: int
    profit_premium: int
    profit_no_premium: int
    margin_premium: float
    margin_no_premium: float
    is_black_market: bool
    data_age_seconds: float
    source: str


class EnhancedScanRequest(BaseModel):
    items: Optional[list[str]] = None
    cities: Optional[list[str]] = None
    quality: Optional[int] = 1
    min_profit: int = 100
    min_margin: float = 0.02
    max_stale_hours: float = 2.0
    outlier_multiplier: float = 4.0
    include_black_market: bool = True
    limit: int = 50


class GlobalScanRequest(BaseModel):
    min_profit: int = 100
    min_margin: float = 0.02
    max_stale_hours: float = 2.0
    include_black_market: bool = True
    quality: Optional[int] = 1


class EnhancedScanResponse(BaseModel):
    flips: list[FlipResponse]
    total_found: int
    scan_timestamp: float
    items_scanned: int
    cities_scanned: int


class ItemSearchResponse(BaseModel):
    items: list[dict]


class NatsStatusResponse(BaseModel):
    connected: bool
    cache_entries: int
    cache_updates: int
    last_update: Optional[float]


class ScanJobStatus(BaseModel):
    job_id: str
    status: str
    scanned: int
    total: int
    flips_found: int
    started_at: float
    elapsed_seconds: float


# ─── Routes ───────────────────────────────────────────────────────────────────


@app.get("/")
async def root():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ─── Zone / Route Endpoints ──────────────────────────────────────────────────


@app.get("/api/zones")
async def get_zones():
    f = get_finder()
    return [
        ZoneInfo(
            id=z.id,
            name=z.name,
            x=z.x,
            y=z.y,
            zone_type=z.zone_type,
            zone_type_name=ZONE_TYPE_NAMES.get(z.zone_type, f"Type {z.zone_type}"),
            connections=z.connections,
        )
        for z in f.zones.values()
    ]


@app.get("/api/zones/search")
async def search_zones(q: str):
    f = get_finder()
    results = []
    q_lower = q.lower()
    for zone in f.zones.values():
        if q_lower in zone.name.lower():
            results.append(
                {"id": zone.id, "name": zone.name, "zone_type": zone.zone_type}
            )
    return results[:20]


@app.post("/api/route")
async def find_route(request: RouteRequest):
    from albion_route_finder import DEFAULT_WEIGHTS

    f = get_finder()
    weights = DEFAULT_WEIGHTS.copy()
    if request.avoid_black:
        weights[4] = 100.0
    if request.avoid_red:
        weights[3] = 50.0
    if request.avoid_yellow:
        weights[2] = 10.0

    route = f.find_route(request.start, request.end, weights)
    if route is None:
        raise HTTPException(status_code=404, detail="No route found")

    return RouteResponse(
        steps=[
            RouteStepResponse(
                from_zone=step.from_zone.name,
                to_zone=step.to_zone.name,
                distance=step.distance,
                duration_seconds=step.duration_seconds,
                zone_type=step.zone_type,
                zone_type_name=ZONE_TYPE_NAMES.get(step.zone_type, "Unknown"),
            )
            for step in route.steps
        ],
        total_distance=route.total_distance,
        total_km=route.total_km,
        total_duration_seconds=route.total_duration_seconds,
        total_minutes=route.total_minutes,
        zone_breakdown=route.zone_breakdown,
    )


@app.get("/api/connections")
async def get_connections():
    f = get_finder()
    edges = []
    seen = set()
    for zone_id, neighbors in f.graph.items():
        for neighbor_id in neighbors:
            key = tuple(sorted([zone_id, neighbor_id]))
            if key not in seen:
                seen.add(key)
                edges.append({"from": zone_id, "to": neighbor_id})
    return edges


# ─── Enhanced Market Scanner Endpoints ────────────────────────────────────────


@app.post("/api/market/scan")
async def scan_market(request: EnhancedScanRequest):
    """Scan the market for profitable arbitrage opportunities using the enhanced scanner."""
    from albion_market_scanner_enhanced import (
        EnhancedMarketScanner,
        ALL_TRADE_HUBS,
        ROYAL_CITIES,
    )

    scanner = EnhancedMarketScanner(
        items=request.items,
        cities=request.cities,
        max_stale_hours=request.max_stale_hours,
        outlier_multiplier=request.outlier_multiplier,
        min_profit=request.min_profit,
        min_margin=request.min_margin,
        include_black_market=request.include_black_market,
    )

    try:
        flips = scanner.scan(quality=request.quality, limit=request.limit)

        return EnhancedScanResponse(
            flips=[
                FlipResponse(
                    item_id=f.item_id,
                    item_name=f.item_name,
                    quality=f.quality,
                    enchantment=f.enchantment,
                    buy_city=f.buy_city,
                    buy_price=f.buy_price,
                    sell_city=f.sell_city,
                    sell_price=f.sell_price,
                    gross_profit=f.gross_profit,
                    profit_premium=f.profit_premium,
                    profit_no_premium=f.profit_no_premium,
                    margin_premium=f.margin_premium,
                    margin_no_premium=f.margin_no_premium,
                    is_black_market=f.is_black_market,
                    data_age_seconds=f.data_age_seconds,
                    source=f.source,
                )
                for f in flips
            ],
            total_found=len(flips),
            scan_timestamp=time.time(),
            items_scanned=len(scanner.items),
            cities_scanned=len(scanner.cities),
        )
    finally:
        scanner.close()


@app.get("/api/market/items/search")
async def search_items(q: str, limit: int = 20):
    """Search the 11K item database by name."""
    from albion_market_scanner_enhanced import ItemDatabase

    db = ItemDatabase()
    results = db.search(q, limit=limit)
    return ItemSearchResponse(
        items=[{"item_id": i.item_id, "name": i.name} for i in results]
    )


@app.get("/api/market/items")
async def get_available_items():
    """Get item database stats and trade hubs."""
    from albion_market_scanner_enhanced import (
        ItemDatabase,
        ALL_TRADE_HUBS,
        ROYAL_CITIES,
    )

    db = ItemDatabase()
    return {
        "total_items": len(db.get_all_ids()),
        "trade_hubs": ALL_TRADE_HUBS,
        "royal_cities": ROYAL_CITIES,
    }


# ─── Global Scanner SSE Endpoint ──────────────────────────────────────────────


@app.post("/api/market/scan/global")
async def scan_global(request: GlobalScanRequest):
    """Start a global scan and return SSE stream."""
    import uuid
    from albion_market_scanner_enhanced import EnhancedMarketScanner, ALL_TRADE_HUBS

    job_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    _scan_jobs[job_id] = {
        "status": "running",
        "scanned": 0,
        "total": 0,
        "flips_found": 0,
        "started_at": start_time,
        "cancelled": False,
    }

    async def event_stream():
        scanner = EnhancedMarketScanner(
            cities=ALL_TRADE_HUBS if request.include_black_market else None,
            max_stale_hours=request.max_stale_hours,
            min_profit=request.min_profit,
            min_margin=request.min_margin,
            include_black_market=request.include_black_market,
        )

        try:
            for update in scanner.scan_all_items_progress(
                quality=request.quality,
                min_profit=request.min_profit,
                min_margin=request.min_margin,
                include_black_market=request.include_black_market,
            ):
                if _scan_jobs.get(job_id, {}).get("cancelled"):
                    _scan_jobs[job_id]["status"] = "cancelled"
                    yield f'event: cancelled\ndata: {{"job_id": "{job_id}"}}\n\n'
                    break

                _scan_jobs[job_id]["scanned"] = update["scanned"]
                _scan_jobs[job_id]["total"] = update["total"]
                _scan_jobs[job_id]["flips_found"] = update["flips_found"]

                event_type = update["type"]

                if event_type == "progress":
                    data = {
                        "job_id": job_id,
                        "scanned": update["scanned"],
                        "total": update["total"],
                        "flips_found": update["flips_found"],
                        "batch": update.get("batch"),
                        "total_batches": update.get("total_batches"),
                    }
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"

                elif event_type == "flips":
                    flips_data = [
                        {
                            "item_id": f.item_id,
                            "item_name": f.item_name,
                            "quality": f.quality,
                            "enchantment": f.enchantment,
                            "buy_city": f.buy_city,
                            "buy_price": f.buy_price,
                            "sell_city": f.sell_city,
                            "sell_price": f.sell_price,
                            "gross_profit": f.gross_profit,
                            "profit_premium": f.profit_premium,
                            "profit_no_premium": f.profit_no_premium,
                            "margin_premium": f.margin_premium,
                            "margin_no_premium": f.margin_no_premium,
                            "is_black_market": f.is_black_market,
                            "data_age_seconds": f.data_age_seconds,
                        }
                        for f in update["flips"]
                    ]
                    data = {
                        "job_id": job_id,
                        "scanned": update["scanned"],
                        "total": update["total"],
                        "flips_found": update["flips_found"],
                        "flips": flips_data,
                    }
                    yield f"event: flips\ndata: {json.dumps(data)}\n\n"

                elif event_type == "complete":
                    flips_data = [
                        {
                            "item_id": f.item_id,
                            "item_name": f.item_name,
                            "quality": f.quality,
                            "enchantment": f.enchantment,
                            "buy_city": f.buy_city,
                            "buy_price": f.buy_price,
                            "sell_city": f.sell_city,
                            "sell_price": f.sell_price,
                            "gross_profit": f.gross_profit,
                            "profit_premium": f.profit_premium,
                            "profit_no_premium": f.profit_no_premium,
                            "margin_premium": f.margin_premium,
                            "margin_no_premium": f.margin_no_premium,
                            "is_black_market": f.is_black_market,
                            "data_age_seconds": f.data_age_seconds,
                        }
                        for f in update["flips"]
                    ]
                    data = {
                        "job_id": job_id,
                        "total_scanned": update["scanned"],
                        "total_flips": update["flips_found"],
                        "duration_seconds": time.time() - start_time,
                        "flips": flips_data,
                    }
                    _scan_jobs[job_id]["status"] = "complete"
                    yield f"event: complete\ndata: {json.dumps(data)}\n\n"

        except Exception as e:
            log.error(f"Scan error: {e}")
            _scan_jobs[job_id]["status"] = "error"
            yield f'event: error\ndata: {{"job_id": "{job_id}", "error": "{str(e)}"}}\n\n'
        finally:
            scanner.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/market/scan/jobs")
async def get_scan_jobs():
    """Get all scan job statuses."""
    now = time.time()
    return [
        ScanJobStatus(
            job_id=job_id,
            status=job["status"],
            scanned=job["scanned"],
            total=job["total"],
            flips_found=job["flips_found"],
            started_at=job["started_at"],
            elapsed_seconds=now - job["started_at"],
        )
        for job_id, job in _scan_jobs.items()
    ]


@app.delete("/api/market/scan/jobs/{job_id}")
async def cancel_scan_job(job_id: str):
    """Cancel a running scan job."""
    if job_id not in _scan_jobs:
        raise HTTPException(status_code=404, detail="Scan job not found")

    _scan_jobs[job_id]["cancelled"] = True
    return {"status": "cancelling", "job_id": job_id}


# ─── NATS Real-Time Endpoints ────────────────────────────────────────────────


@app.get("/api/nats/status")
async def nats_status():
    """Get NATS monitor status."""
    monitor = get_nats_monitor()
    stats = monitor.cache_stats()
    return NatsStatusResponse(
        connected=monitor.is_connected(),
        cache_entries=stats["entries"],
        cache_updates=stats["updates"],
        last_update=stats["last_update"] or None,
    )


@app.post("/api/nats/start")
async def nats_start():
    """Start the NATS real-time monitor."""
    monitor = get_nats_monitor()
    if monitor.is_connected():
        return {"status": "already_connected"}

    connected = await monitor.start()
    if connected:
        return {"status": "connected"}
    raise HTTPException(status_code=503, detail="Failed to connect to NATS server")


@app.post("/api/nats/stop")
async def nats_stop():
    """Stop the NATS real-time monitor."""
    monitor = get_nats_monitor()
    await monitor.stop()
    return {"status": "stopped"}


@app.get("/api/nats/flips")
async def nats_flips(
    min_profit: int = 100,
    min_margin: float = 0.02,
    max_stale_seconds: float = 3600,
    limit: int = 50,
):
    """Get current flips from the NATS real-time cache."""
    monitor = get_nats_monitor()
    if not monitor.is_connected():
        raise HTTPException(
            status_code=503,
            detail="NATS monitor not connected. Start it first via /api/nats/start",
        )

    flips = await monitor.get_flips(
        min_profit=min_profit,
        min_margin=min_margin,
        max_stale_seconds=max_stale_seconds,
    )

    return EnhancedScanResponse(
        flips=[
            FlipResponse(
                item_id=f.item_id,
                item_name=f.item_name,
                quality=f.quality,
                enchantment=f.enchantment,
                buy_city=f.buy_city,
                buy_price=f.buy_price,
                sell_city=f.sell_city,
                sell_price=f.sell_price,
                gross_profit=f.gross_profit,
                profit_premium=f.profit_premium,
                profit_no_premium=f.profit_no_premium,
                margin_premium=f.margin_premium,
                margin_no_premium=f.margin_no_premium,
                is_black_market=f.is_black_market,
                data_age_seconds=f.data_age_seconds,
                source="nats_realtime",
            )
            for f in flips[:limit]
        ],
        total_found=len(flips),
        scan_timestamp=time.time(),
        items_scanned=monitor.cache_stats()["entries"],
        cities_scanned=7,
    )


@app.websocket("/ws/flips")
async def websocket_flips(websocket: WebSocket):
    """WebSocket endpoint for real-time flip updates with connection management."""
    await websocket.accept()
    _ws_clients.append(websocket)

    monitor = get_nats_monitor()

    if not monitor.is_connected():
        connected = await monitor.start()
        if not connected:
            await websocket.send_json(
                {"type": "error", "message": "NATS connection failed"}
            )
            await websocket.close()
            _ws_clients.remove(websocket)
            return

    stats = monitor.cache_stats()
    await websocket.send_json(
        {
            "type": "connected",
            "cache_entries": stats["entries"],
            "cache_updates": stats["updates"],
            "last_update": stats["last_update"],
        }
    )

    async def on_flips(flips):
        try:
            stats = monitor.cache_stats()
            await websocket.send_json(
                {
                    "type": "flips_update",
                    "count": len(flips),
                    "cache_entries": stats["entries"],
                    "cache_updates": stats["updates"],
                    "top_flips": [
                        {
                            "item_id": f.item_id,
                            "item_name": f.item_name,
                            "quality": f.quality,
                            "enchantment": f.enchantment,
                            "buy_city": f.buy_city,
                            "buy_price": f.buy_price,
                            "sell_city": f.sell_city,
                            "sell_price": f.sell_price,
                            "profit_premium": f.profit_premium,
                            "profit_no_premium": f.profit_no_premium,
                            "margin_premium": f.margin_premium,
                            "is_black_market": f.is_black_market,
                        }
                        for f in flips[:20]
                    ],
                    "timestamp": time.time(),
                }
            )
        except Exception:
            pass

    await monitor.subscribe_flips(on_flips)

    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
            elif data == "status":
                stats = monitor.cache_stats()
                await websocket.send_json(
                    {
                        "type": "status",
                        "cache_entries": stats["entries"],
                        "cache_updates": stats["updates"],
                        "connected": monitor.is_connected(),
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        await monitor.unsubscribe_flips(on_flips)
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)


# ─── Static Files ────────────────────────────────────────────────────────────

app.mount(
    "/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static"
)
