# Albion Market and Route Toolkit

Python tools for comparing Albion Online market prices and planning travel
through the game's zone graph, with a FastAPI dashboard.

The public source includes market scanners, a NATS price monitor, weighted
route finding and a browser interface. Market data comes from external
providers; results depend on coverage and freshness. This checkout has not
been revalidated against the current game or live data services.

## Components

| Component | Source | Purpose |
| --- | --- | --- |
| Enhanced market scanner | [albion_market_scanner_enhanced.py](albion_market_scanner_enhanced.py) | Compare city prices with configurable profit, staleness and outlier filters |
| Price monitor | [albion_nats_monitor.py](albion_nats_monitor.py) | Maintain a price cache from the Albion Online Data Project's NATS stream |
| Route finder | [albion_route_finder.py](albion_route_finder.py) | Find weighted paths with Dijkstra's algorithm; report distance, estimated time and zone exposure |
| Web dashboard | [web/api.py](web/api.py), [web/static/index.html](web/static/index.html) | Expose scanning, route lookup, scan progress and price updates |
| Data adapters | [data_sources/](data_sources/) | HTTP, stream, cache and zone-data access |

## Run From Source

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).
Run these commands from the repository root:

```sh
uv sync
uv run uvicorn web.api:app --host 127.0.0.1 --port 8501
```

Open `http://127.0.0.1:8501`. Starting the application attempts a connection
to the external NATS stream. The standalone `web/run.py` launcher uses port
8000 instead; the explicit command above selects port 8501.

For the market scanner's options:

```sh
uv run albion_market_scanner_enhanced.py --help
```

For a targeted scan, supply item IDs with `--items`, for example:

```sh
uv run albion_market_scanner_enhanced.py --items T4_BAG --limit 10
```

The root `main.py` prints a placeholder greeting. It is not the dashboard or
scanner entry point.

## Required Data Files

The default/global scanner and item-name lookup use `data/items.json`, which
is absent from this public checkout. Supply a JSON list of objects containing
`value` (item ID) and `label` (display name), for example:

```json
[{"value": "T4_BAG", "label": "Adept's Bag"}]
```

Without that database, the default item set is empty and name searches have
no catalogue to search. Explicit `--items` allows targeted scanning without
the catalogue; external price-data availability still determines the results.

The route finder loads `extracted_maps/albion_zones.json` by default.
That generated file is absent from this public checkout. Route endpoints
need a compatible zone graph supplied at that path before they can work.
The [map tools](albion_map_pathfinder/) and their data files describe the
existing map-processing approach; they are not a verified replacement for
the missing generated graph.

Travel-time estimates use fixed assumptions in the route finder. Risk
weights express route preferences, not guarantees about safe travel.

## Outputs and Limits

The scanner calculates estimated price differences and exposes filtering
controls. An estimated margin is not a completed trade, a guaranteed return
or evidence that an item is available at that price. REST access, streaming
coverage and third-party site behavior can change independently of this
source.

The web API contains SSE scan-progress and WebSocket price-update endpoints.
Live connectivity, dashboard behavior and current data quality were not
tested as part of this documentation review.
