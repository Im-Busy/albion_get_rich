# Agent Handover State

> Auto-updated each session. Read this first when resuming.

## Current Objective

Maintain and enhance the Albion Online market scanner suite. MVP is complete — current focus is improving scan coverage, reducing latency, and adding new profit strategies.

## System State & Metrics

- **Scanner:** Enhanced scanner functional (11K items, smart filters, Black Market support)
- **NATS Monitor:** Real-time price cache active (~3-5s latency on market orders)
- **Route Finder:** Dijkstra pathfinding functional with PvP zone weighting
- **Market PvP:** Spread manipulation scanner with liquidity grading (S/A/B/C/D/F)
- **Web Dashboard:** FastAPI + SPA dashboard functional (4 tabs: Scanner, Real-Time, Routes, Lookup)
- **Cloudflare Bypass:** 4-tier engine functional (curl_cffi → SeleniumBase → Camoufox → FlareSolverr)

## Completed Tasks

- [x] Enhanced market scanner with 11K item database
- [x] NATS real-time price monitor with WebSocket push
- [x] Dijkstra route finder with PvP zone weighting
- [x] Market PvP scanner with liquidity analyzer
- [x] Cloudflare bypass engine (4 tiers)
- [x] FastAPI web dashboard with 4-tab SPA
- [x] Abstracted data source layer with fallback chains
- [x] Anti-cheat research (RatScanner benchmark, zero ban risk design)

## Discovered Issues & Blockers

- [ ] AlbionOnline2D.com blocked by Cloudflare — bypass engine works but slow on first visit (~40s)
- [ ] AO Data REST API rate-limited (~100 req/min) — NATS is the workaround
- [ ] Some items have stale prices (no recent trades) — smart filters detect but don't solve

## Next Session Agent Must

1. Run the web dashboard: `uv run web/run.py`
2. Test NATS connectivity: `uv run test_nats.py`
3. Check for stale data issues in the enhanced scanner
4. Consider: optimize NATS subscription filtering to reduce memory usage
5. Update this MEMORY.md with new state
