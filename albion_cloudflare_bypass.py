"""
Unified Cloudflare Bypass Engine for Albion Get Rich.

Proven architecture (tested against albiononline2d.com):
- Tier 1: curl_cffi with cached session (UA + cf_clearance) -- ~2s
- Tier 2: SeleniumBase UC Mode solve Cloudflare -- ~40s
- Tier 3: Camoufox (anti-detect Firefox) -- fallback
- Tier 4: FlareSolverr (local service) -- last resort

First visit: solves Cloudflare via SeleniumBase UC Mode, caches session.
Subsequent visits: uses cached session with curl_cffi (~2s, no browser).
"""

import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

try:
    from seleniumbase import Driver

    HAS_SELENIUMBASE = True
except ImportError:
    HAS_SELENIUMBASE = False

try:
    from camoufox.sync_api import Camoufox

    HAS_CAMOUFOX = True
except ImportError:
    HAS_CAMOUFOX = False

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("albion_cf_bypass")

CACHE_DIR = Path(__file__).parent / ".cf_cache"
CACHE_DIR.mkdir(exist_ok=True)


class CloudflareBypass:
    """
    Unified HTTP client that automatically manages Cloudflare sessions.

    Usage:
        bypasser = CloudflareBypass()
        result = bypasser.get("https://site-behind-cloudflare.com")
        print(result["html"])

    For domain-specific caching (auto-manages sessions per domain):
        bypasser = CloudflareBypass()
        bypasser.set_domain("example.com")  # Optional: uses parsed domain by default
    """

    def __init__(
        self,
        proxy: str = None,
        flare_solverr_url: str = "http://localhost:8191",
        session_max_age: int = 6 * 3600,  # 6 hours default
    ):
        self.proxy = proxy
        self.flare_solverr_url = flare_solverr_url
        self.session_max_age = session_max_age
        self._domain = None
        self._session_cache = {}

    def set_domain(self, domain: str):
        """Set specific domain for session caching."""
        self._domain = domain

    def _cache_path(self, url: str) -> Path:
        domain = self._domain or urlparse(url).netloc
        safe = "".join(c if c.isalnum() else "_" for c in domain)
        return CACHE_DIR / f"cf_session_{safe}.json"

    def _load_session(self, url: str) -> dict | None:
        path = self._cache_path(url)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if time.time() - data.get("timestamp", 0) < self.session_max_age:
                    return data
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def _save_session(self, url: str, session: dict):
        path = self._cache_path(url)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(session, f, indent=2)
        except OSError as e:
            logger.warning(f"Failed to save session: {e}")

    def _is_cloudflare_block(self, text: str, status_code: int) -> bool:
        if status_code in (403, 503):
            return True
        if not text:
            return True
        for kw in (
            "Just a moment...",
            "Enable JavaScript and cookies to continue",
            "Checking if the site connection is secure",
            "Verify you are human",
            "cf-challenge",
            "window._cf_chl_opt",
        ):
            if kw in text:
                return True
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, url: str, force_fresh: bool = False) -> dict:
        """
        GET request with automatic Cloudflare bypass.

        Args:
            url: Target URL
            force_fresh: Skip cache, solve Cloudflare from scratch

        Returns:
            Dict with keys: status_code, html, cookies_raw, source
        """
        logger.info("GET %s", url)

        # Step 0 — cached session
        if not force_fresh:
            session = self._load_session(url)
            if session:
                age = int(time.time() - session["timestamp"])
                logger.info(f"Trying cached session (age: {age}s)")
                res = self._try_curl_cffi(url, session)
                if res and not self._is_cloudflare_block(
                    res["html"], res["status_code"]
                ):
                    res["source"] = "cached"
                    return res
                logger.info("Cached session expired/invalid, solving challenge...")

        # Tier 1 — curl_cffi (first attempt, no cache)
        if HAS_CURL_CFFI and force_fresh:
            logger.info("Tier 1: curl_cffi (no cache)")
            # Try with default Chrome impersonate
            res = self._try_curl_cffi(url, None)
            if res and not self._is_cloudflare_block(res["html"], res["status_code"]):
                self._save_session(
                    url,
                    {
                        "cookies_raw": res["cookies_raw"],
                        "user_agent": res.get("user_agent", ""),
                        "timestamp": time.time(),
                    },
                )
                res["source"] = "curl_cffi"
                return res

        # Tier 2 — SeleniumBase UC Mode (primary solver)
        if HAS_SELENIUMBASE:
            logger.info("Tier 2: SeleniumBase UC Mode")
            res = self._try_seleniumbase(url)
            if res and not self._is_cloudflare_block(res["html"], res["status_code"]):
                session = {
                    "cookies_raw": res["cookies_raw"],
                    "user_agent": res.get("user_agent", ""),
                    "timestamp": time.time(),
                }
                self._save_session(url, session)
                res["source"] = "seleniumbase_uc"
                return res

        # Tier 3 — Camoufox
        if HAS_CAMOUFOX:
            logger.info("Tier 3: Camoufox")
            res = self._try_camoufox(url)
            if res and not self._is_cloudflare_block(res["html"], res["status_code"]):
                self._save_session(
                    url,
                    {
                        "cookies_raw": res["cookies_raw"],
                        "user_agent": res.get("user_agent", ""),
                        "timestamp": time.time(),
                    },
                )
                res["source"] = "camoufox"
                return res

        # Tier 4 — FlareSolverr
        logger.info("Tier 4: FlareSolverr")
        flare = self._try_flaresolverr(url)
        if flare:
            return flare

        logger.error("All tiers failed for %s", url)
        return {
            "status_code": 403,
            "html": "BLOCKED",
            "cookies_raw": [],
            "source": "failed",
        }

    # ------------------------------------------------------------------
    # Tier implementations
    # ------------------------------------------------------------------
    def _try_curl_cffi(self, url: str, session: dict | None) -> dict | None:
        if not HAS_CURL_CFFI:
            return None
        sess = curl_requests.Session()

        if session:
            for c in session.get("cookies_raw", []):
                sess.cookies.set(c.get("name"), c.get("value"))
            headers = {"User-Agent": session.get("user_agent", "")}
        else:
            headers = None

        try:
            r = sess.get(
                url, impersonate="chrome", headers=headers, proxy=self.proxy, timeout=30
            )
            cookies_raw = []
            for c in sess.cookies:
                if hasattr(c, "name"):
                    cookies_raw.append({"name": c.name, "value": c.value})
                elif isinstance(c, dict):
                    cookies_raw.append({"name": c["name"], "value": c["value"]})
            return {
                "status_code": r.status_code,
                "html": r.text,
                "cookies_raw": cookies_raw,
            }
        except Exception as exc:
            logger.error("curl_cffi: %s", exc)
            return None

    def _try_seleniumbase(self, url: str) -> dict | None:
        if not HAS_SELENIUMBASE:
            return None
        driver = None
        try:
            driver = Driver(uc=True, headless=True, browser="chrome")
            driver.get(url)
            for i in range(10):
                time.sleep(3)
                if "Just a moment" not in driver.title:
                    break
            html = driver.page_source
            cookies_raw = [
                {"name": c["name"], "value": c["value"]} for c in driver.get_cookies()
            ]
            user_agent = driver.execute_script("return navigator.userAgent;")
            return {
                "status_code": 200,
                "html": html,
                "cookies_raw": cookies_raw,
                "user_agent": user_agent,
            }
        except Exception as exc:
            logger.error("SeleniumBase UC: %s", exc)
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _try_camoufox(self, url: str) -> dict | None:
        if not HAS_CAMOUFOX:
            return None
        try:
            with Camoufox(headless=True, os="windows") as browser:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)
                html = page.content()
                cookies_raw = [
                    {"name": c["name"], "value": c["value"]}
                    for c in page.context.cookies()
                ]
                return {"status_code": 200, "html": html, "cookies_raw": cookies_raw}
        except Exception as exc:
            logger.error("Camoufox: %s", exc)
            return None

    def _try_flaresolverr(self, url: str) -> dict | None:
        if not requests:
            return None
        try:
            resp = requests.post(
                self.flare_solverr_url,
                json={"cmd": "request.get", "url": url, "maxTimeout": 60000},
                timeout=70,
            )
            data = resp.json()
            if data.get("status") == "ok":
                sol = data.get("solution", {})
                return {
                    "status_code": sol.get("status", 200),
                    "html": sol.get("response", ""),
                    "cookies_raw": sol.get("cookies", []),
                    "source": "flaresolverr",
                }
        except Exception as exc:
            logger.warning("FlareSolverr unavailable: %s", exc)
        return None


# Convenience
def get(url: str, proxy: str = None, force_fresh: bool = False) -> dict:
    return CloudflareBypass(proxy=proxy).get(url, force_fresh=force_fresh)
