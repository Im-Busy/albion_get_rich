"""
Production-ready Cloudflare bypass + map data fetcher for albiononline2d.com.

Strategy:
1. First run: SeleniumBase UC Mode solves Cloudflare, extracts page + cookies + UA
2. Saves cookies + UA to .cf_cache/ for reuse
3. Subsequent runs: curl_cffi with cached cookie + matched UA (fast!)
4. If cookie expires or fails: fallback to SeleniumBase
5. Extracts embedded map node config from HTML (no separate API needed)
"""

import json
import logging
import re
import time
from pathlib import Path

from curl_cffi import requests as curl_requests
from seleniumbase import Driver

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("albion_map_fetcher")

BASE_URL = "https://albiononline2d.com"
CACHE_DIR = Path(__file__).parent / ".cf_cache"
CACHE_DIR.mkdir(exist_ok=True)
COOKIE_FILE = CACHE_DIR / "albiononline2d_session.json"


def load_session() -> dict | None:
    """Load cached session (cookies + UA) if not expired."""
    if COOKIE_FILE.exists():
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Session valid for 6 hours
        if time.time() - data.get("timestamp", 0) < 6 * 3600:
            age = int(time.time() - data["timestamp"])
            logger.info(
                f"Loaded cached session (age: {age}s, UA: {data.get('user_agent', '')[:30]}...)"
            )
            return data
        else:
            logger.info("Cached session expired")
    return None


def save_session(cookies: list[dict], user_agent: str):
    """Save session to disk."""
    data = {
        "cookies": cookies,
        "user_agent": user_agent,
        "timestamp": time.time(),
    }
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved session with {len(cookies)} cookies")


def try_with_session(url: str, session: dict) -> str | None:
    """Try to fetch URL with curl_cffi using cached session."""
    sess = curl_requests.Session()
    cookies = session.get("cookies", [])
    for c in cookies:
        sess.cookies.set(c["name"], c["value"])

    headers = {
        "User-Agent": session.get("user_agent", ""),
    }

    try:
        r = sess.get(url, impersonate="chrome", headers=headers, timeout=30)
        if "Just a moment" not in r.text:
            logger.info(f"  [curl_cffi] Success! ({len(r.text):,} bytes)")
            return r.text
        else:
            logger.info("  [curl_cffi] Blocked - CF challenge detected")
            return None
    except Exception as e:
        logger.error(f"  [curl_cffi] Error: {e}")
        return None


def solve_cloudflare(url: str) -> tuple[str, list[dict], str]:
    """Use SeleniumBase UC Mode to solve Cloudflare."""
    logger.info("[SeleniumBase UC] Launching browser to solve Cloudflare...")
    driver = None
    try:
        driver = Driver(uc=True, headless=True, browser="chrome")
        driver.get(url)

        # Wait for challenge to resolve
        for i in range(10):
            time.sleep(3)
            title = driver.title
            if "Just a moment" not in title:
                logger.info(f"  Challenge resolved! Title: {title}")
                break

        html = driver.page_source
        cookies = driver.get_cookies()

        # Get the User-Agent SeleniumBase used
        user_agent = driver.execute_script("return navigator.userAgent;")

        return html, cookies, user_agent
    except Exception as e:
        logger.error(f"  [SeleniumBase UC] Error: {e}")
        return "", [], ""
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_page(url: str) -> str:
    """Fetch page, using cached session or solving Cloudflare if needed."""
    session = load_session()

    if session:
        result = try_with_session(url, session)
        if result:
            return result

    # Need to solve Cloudflare from scratch
    html, cookies, user_agent = solve_cloudflare(url)
    if html and cookies:
        save_session(cookies, user_agent)
        return html

    logger.error("Failed to fetch page")
    return ""


def extract_map_config(html: str) -> dict | None:
    """Extract the embedded map node config from the page HTML."""
    match = re.search(r"var config\s*=\s*({.*?});\s*</script>", html, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"  Failed to parse config JSON: {e}")
    return None


def main():
    """Fetch map data from albiononline2d.com, bypassing Cloudflare."""
    url = f"{BASE_URL}/en/map"
    logger.info(f"Fetching: {url}")

    html = fetch_page(url)
    if not html:
        logger.error("No page content retrieved")
        return

    config = extract_map_config(html)
    if not config:
        logger.error("Could not extract map config from page")
        return

    nodes = config.get("nodes", [])
    logger.info(f"Extracted {len(nodes)} map nodes")

    # Save the extracted config
    output_file = Path(__file__).parent / "extracted_map_config.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved map config to {output_file}")

    # Show summary
    print(f"\n{'=' * 60}")
    print(f"Map Data Summary")
    print(f"{'=' * 60}")
    print(f"  Total nodes: {len(nodes)}")

    # Categorize nodes by type
    types = {}
    for node in nodes:
        attrs = node.get("_attr", {})
        typ = attrs.get("type", "UNKNOWN")
        types[typ] = types.get(typ, 0) + 1

    print(f"\n  Node types:")
    for typ, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {typ}: {count}")

    # Show cities specifically
    cities = [n for n in nodes if "CITY" in n.get("_attr", {}).get("type", "")]
    print(f"\n  Cities/Zones ({len(cities)}):")
    for city in cities[:15]:
        name = city.get("_attr", {}).get("displayname", "Unknown")
        typ = city.get("_attr", {}).get("type", "Unknown")
        print(f"    {name} ({typ})")

    print(f"\n{'=' * 60}")
    print(f"Cloudflare bypass: SUCCESS")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
