# Project Guidelines

## Session Start Protocol — CRITICAL FOR ALL SESSIONS

**Every new AI session MUST start by reading these files in order:**

1. **`MEMORY.md`** (project root) — Persistent handover state: current objective, system metrics, completed tasks, discovered issues, next session priorities.
2. **`IDEAS_AND_PLAN.md`** — Master plan: 8 money-making directions, BattlEye analysis, data source strategy.
3. **`progress_docs/current.md`** — Session log with timestamps and detailed action history.

After reading state, consult `progress_docs/plans/full.md` for pending tasks and dependencies. The agent updates `MEMORY.md` continuously during the session.

## Python Environment

This project uses **uv** for Python package and environment management. Always use uv commands:

- `uv run <command>` - Run Python scripts/commands in the project environment
- `uv add <package>` - Add a package to the project
- `uv remove <package>` - Remove a package from the project
- `uv sync` - Sync the environment with the lock file
- `uv pip install <package>` - Install packages using uv's pip interface (if needed)

**NEVER** use `python`, `pip`, `python3`, or `pip3` directly. Always prefix commands with `uv`.

## Key Commands

```bash
# Start the FastAPI web dashboard
uv run uvicorn web.api:app --reload --port 8501

# Run the enhanced market scanner (11K items, smart filters)
uv run albion_market_scanner_enhanced.py

# Run the real-time NATS monitor (WebSocket flip alerts)
uv run albion_nats_monitor.py

# Run the Market PvP scanner (intra-city spread manipulation)
uv run market_pvp_scanner.py

# Start the full scanner via the web runner
uv run web/run.py

# Test NATS connectivity
uv run test_nats.py

# Test Cloudflare bypass engine
uv run test_cf_bypass.py
```

## Project Architecture

```
albion_get_rich/
├── albion_market_scanner.py              # Basic scanner (~50 items, Dijkstra integration)
├── albion_market_scanner_enhanced.py     # Production scanner (11K items, smart filters, Black Market)
├── albion_nats_monitor.py                # Real-time NATS price cache + WebSocket flip alerts
├── albion_route_finder.py                # Dijkstra pathfinding on Albion zone graph
├── albion_cloudflare_bypass.py           # 4-tier Cloudflare bypass engine
├── market_pvp_scanner.py                 # Intra-city spread manipulation + liquidity grading
├── data_sources/                         # Abstracted data sources with fallback chains
│   ├── market_sources.py                 # NATS → REST API → Cache fallback
│   └── zone_sources.py                   # Live Albion2D → Static JSON fallback
├── web/                                  # FastAPI backend + SPA dashboard
│   ├── api.py                            # REST API + SSE + WebSocket endpoints
│   ├── run.py                            # Uvicorn launcher
│   └── static/index.html                 # 4-tab dashboard (Scanner, Real-Time, Routes, Lookup)
├── albion_map_pathfinder/                # Zone graph construction from game .tres files
├── data/items.json                       # 11,000+ item database
├── extracted_maps/                       # Zone graph JSON output
└── project_research/                     # Anti-cheat & overlay risk analysis
```

## Data Source Fallback Chain

Every data fetch follows the same fallback pattern:

1. **NATS** (real-time, no rate limits) → 2. **REST API** (rate-limited, ~100 req/min) → 3. **On-disk cache** (stale but available)

For zone data: **Live Albion2D** (Cloudflare-bypassed) → **Static JSON** from `extracted_maps/`.

## Cloudflare Bypass Protocol

When encountering Cloudflare blocks on albiononline2d.com, use the 4-tier engine:

1. `curl_cffi` with cached session (~2s) → 2. SeleniumBase UC Mode (~40s) → 3. Camoufox anti-detect Firefox → 4. FlareSolverr

First successful bypass caches the session for subsequent fast access. NEVER skip tiers — go in order.

## Coding Conventions

- **Async-first**: All HTTP/network calls use `httpx.AsyncClient` or `nats-py` async. No blocking I/O in the web server.
- **Type hints** on all function signatures and return types.
- **`pathlib.Path`** over `os.path`.
- **f-strings** over `.format()` or `%`.
- **Specific exception handling** — never bare `except:` or `except Exception:` without re-raise.
- **`logging`** over `print` in any non-throwaway code.
- **Constants** in UPPER_SNAKE_CASE at module top.
- **Private helpers** prefixed with `_`.

## Anti-Patterns

- **NO game process injection** — never read game memory, simulate input, or interact with the Albion client process. All tools are pure external API/overlay.
- **NO rate limit bypassing** — respect the AO Data API's ~100 req/min limit. Use NATS for high-frequency data.
- **NO hardcoded credentials** — API keys and tokens go in `.env` or environment variables.
- **NO wildcard imports** (`from module import *`).
- **NO mutable default arguments** (`def f(x=[])`).

## Safety Rules

- All tools are designed for **zero ban risk**: external API calls, transparent overlays, no game process interaction. Benchmark: RatScanner (5+ years, 1000+ users, 0 bans in BattlEye-protected game).
- Profit calculations are **premium-aware**: separate estimates for premium (2.5% sell tax) and non-premium (4.5% sell tax) accounts.
- Smart filters detect **stale data** (configurable max hours), **fake orders** (outlier price ratios), and **1-silver traps**.

## Asking for User Help

If you encounter something you cannot accomplish—such as accessing credentials, logging into external services, performing manual approvals, obtaining information behind authentication, or any action requiring human intervention—**explicitly ask the user for help**. Do not silently fail or work around limitations without notifying the user.

## Repository Architecture — Dual-Repo (Private → Public)

This project uses a **dual-remote** Git architecture to publish a curated subset to a public mirror while keeping private files secure.

| Remote | Branch | Purpose |
|--------|--------|---------|
| `origin` (private) | `main` | All files: source, tests, internal tools, IDE configs |
| `public` (public) | `public` | Curated files only: source code, docs, plans, skills |

### Sync Workflow

| Agent | File | Purpose |
|-------|------|---------|
| **repo-syncer** | `.kilo/agent/repo-syncer.md` | Merges main→public, runs safety checks, strips private data, pushes only the clean public branch |

### Slash Commands

| Command | Usage |
|---------|-------|
| `/repo-sync` | Full sync: merge main → public → push |
| `/repo-sync check` | Safety check only — verify no private files on public branch |
| `/repo-sync status` | Show current branch state and remote config |
