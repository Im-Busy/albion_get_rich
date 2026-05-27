---
name: scrapling
description: High-performance undetectable web scraping with adaptive parsing, Cloudflare bypass, and spider framework. Use when fetching data from protected websites (Cloudflare, anti-bot), scraping financial/API data, or building periodic data collection pipelines. 12-784x faster than BeautifulSoup.
metadata:
  skill-author: Scrapling (BSD-3-Clause)
  project-integration: phase-18-useful-repos
---

# Scrapling — Adaptive Web Scraping

## When to Use

- Fetching data from websites protected by Cloudflare Turnstile/bot-detection
- Scraping websites that frequently change HTML structure (adaptive selectors)
- Building periodic data collection spiders with pause/resume
- Need stealthy HTTP fetching with TLS fingerprint impersonation
- Replacing curl_cffi + SeleniumBase + Camoufox tiered bypass with single call

## Quick Start

```python
from scrapling.fetchers import StealthyFetcher

# Enable adaptive mode (auto-relocates selectors when pages change)
StealthyFetcher.adaptive = True

# Fetch with full anti-bot stealth
resp = StealthyFetcher.fetch(
    "https://albiononline2d.com/en/map",
    headless=True,
    network_idle=True,
    solve_cloudflare=True,
)
html = resp.html_content  # inner HTML as text
```

## Project Integration

This project has a Scrapling-based data source at `data_sources/scrapling_source.py`:

```python
from data_sources.scrapling_source import ScraplingSource

source = ScraplingSource(adaptive=True)
result = await source.fetch("https://albiononline2d.com/en/map")
# result["html"] — page content
# result["cookies"] — session cookies for reuse
```

## StealthyFetcher Options

| Option | Default | Purpose |
|--------|---------|---------|
| `headless` | True | Hidden browser window |
| `network_idle` | True | Wait for network to settle |
| `solve_cloudflare` | True | Auto-solve CF challenges |
| `timeout` | 30000 | Max wait in ms |
| `hide_canvas` | False | Anti-fingerprinting |
| `block_webrtc` | False | Prevent IP leak |

## Spider Framework (Periodic Collection)

```python
from scrapling.spiders import Spider

spider = Spider(
    start_urls=["https://target.com/page1"],
    concurrency=3,
    checkpoint=True,  # resume after crash
)
await spider.run()
```

## Performance

- Text extraction: 2.02ms (vs BeautifulSoup: 1,584ms) — **784x faster**
- Element similarity: 2.39ms (vs AutoScraper: 12.45ms) — **5x faster**
- 92% test coverage
