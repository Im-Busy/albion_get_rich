# Albion Get Rich — Global Scanner Implementation Plan

**Created:** 2026-04-18
**Status:** ✅ COMPLETED
**Completed:** 2026-04-18
**Estimated effort:** 4-6 hours total

---

## Current State

| Component | Status | Location |
|-----------|--------|----------|
| 11,963 item database | ✅ Working | `data/items.json` |
| Enhanced scanner core | ✅ Working | `albion_market_scanner_enhanced.py` |
| NATS real-time monitor | ✅ Working | `albion_nats_monitor.py` |
| FastAPI backend | ✅ Running | `web/api.py` v0.3.0 |
| Zone route finder | ✅ Working | `albion_route_finder.py` |
| Web UI | ⚠️ Outdated | `web/static/index.html` (old design) |

---

## Phase 1: Live Global Scanner Backend (1-2 hours)

### Goal
Scan all 11,963 items across 7 trade hubs, streaming results as they arrive.

### Tasks

1. **Add streaming scan endpoint** (`web/api.py`)
   - `POST /api/market/scan/global` — Server-Sent Events (SSE) endpoint
   - Streams flip results as batches complete
   - Progressive updates: "Scanned 1000/11963 items, found 23 flips..."

2. **Add batch scanner with progress callback** (`albion_market_scanner_enhanced.py`)
   - `scan_all_items()` method
   - Yields `(progress, flips_found)` after each batch
   - Batch size: 70 items per request (API limit)
   - Delay: 1.05s between batches (rate limit safe)

3. **Add scan job management** (`web/api.py`)
   - Track active scan jobs
   - Allow cancel/restart
   - Store last scan results in memory for quick retrieval

### API Design
```
POST /api/market/scan/global
  Request: { min_profit: 100, min_margin: 0.02, max_stale_hours: 2 }
  Response: SSE stream
    event: progress
    data: { scanned: 1000, total: 11963, flips_found: 23 }
    
    event: flip
    data: { item_id, item_name, buy_city, sell_city, profit, ... }
    
    event: complete
    data: { total_scanned: 11963, total_flips: 847, duration_seconds: 185 }
```

---

## Phase 2: Real-Time WebSocket Integration (1 hour)

### Goal
Push live flip updates from NATS cache to connected clients.

### Tasks

1. **Fix WebSocket endpoint** (`web/api.py`)
   - `/ws/flips` currently exists but needs proper broadcast
   - Add connection manager for multiple clients
   - Push updates every 5 seconds while connected

2. **Add NATS auto-start on server startup**
   - Server starts → NATS connects → cache warms up
   - Clients connect → get immediate flips from cache

3. **Add cache warming progress**
   - Track how many unique items have both buy+sell data
   - Report "cache readiness" to clients

### API Design
```
WS /ws/flips
  Client -> Server: { "type": "subscribe", "min_profit": 500 }
  Server -> Client: { "type": "flips", "data": [...], "cache_entries": 1234 }
  Server -> Client: { "type": "cache_status", "entries": 1234, "updates": 54321 }
```

---

## Phase 3: Web UI Overhaul (2-3 hours)

### Goal
Modern dashboard for the global scanner with real-time updates.

### Tasks

1. **Create new dashboard layout** (`web/static/index.html`)
   - Mode tabs: Global Scanner | Real-Time | Route Finder | Item Lookup
   - Sidebar: Filter controls (min profit, margin, stale hours, include BM)
   - Main panel: Live flip table with sorting

2. **Global Scanner tab**
   - "Start Scan" button → triggers SSE connection
   - Progress bar: "Scanning item 5234/11963..."
   - Live table: Flips appear as discovered
   - Columns: Item, Buy (City @ Price), Sell (City @ Price), Profit (Premium/Non), ROI %, BM?

3. **Real-Time tab**
   - WebSocket connection status indicator
   - Live flip feed (updates every 5s)
   - Cache stats: entries, updates, last update time

4. **Item Lookup tab**
   - Search box with autocomplete (11K items)
   - Show price breakdown across all cities
   - Historical chart placeholder

5. **Styling**
   - Dark theme (gaming aesthetic)
   - Responsive table
   - Profit highlighting (green for profit, red for loss)
   - BM badge for Black Market involved

---

## Phase 4: Alert System (Optional, 1-2 hours)

### Goal
Notify user when high-profit flips appear.

### Tasks

1. **Add alert configuration**
   - Threshold: min profit amount
   - Item whitelist/blacklist
   - City preferences

2. **Add notification methods**
   - Browser push notifications
   - Sound alert
   - Optional: Discord webhook

3. **Add alert history**
   - Log of triggered alerts
   - One-click copy item ID

---

## Implementation Order

```
Phase 1: Backend Global Scanner
├── 1.1 Add batch scanner with progress
├── 1.2 Add SSE endpoint for streaming
└── 1.3 Add scan job management

Phase 2: Real-Time Integration
├── 2.1 Fix WebSocket broadcast
├── 2.2 Add NATS auto-start
└── 2.3 Add cache status reporting

Phase 3: Web UI
├── 3.1 New dashboard layout
├── 3.2 Global Scanner tab
├── 3.3 Real-Time tab
├── 3.4 Item Lookup tab
└── 3.5 Styling polish

Phase 4: Alerts (Optional)
├── 4.1 Alert configuration
├── 4.2 Browser notifications
└── 4.3 Alert history
```

---

## Success Criteria

- [x] Global scanner completes full 11,963 item scan in under 4 minutes
- [x] Results stream to UI in real-time (not batch at end)
- [x] WebSocket shows flips from NATS cache within 10 seconds of connecting
- [x] UI clearly distinguishes premium vs non-premium profit
- [x] Black Market flips are highlighted
- [x] Scan can be cancelled mid-progress

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `web/api.py` | Modify | Add SSE endpoint, fix WebSocket, add scan jobs |
| `albion_market_scanner_enhanced.py` | Modify | Add `scan_all_items()` generator |
| `web/static/index.html` | Rewrite | New dashboard UI |
| `web/static/app.js` | Create | Frontend logic (new file) |
| `web/static/styles.css` | Create | Dark theme styles (new file) |
