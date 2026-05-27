"""
Test the Cloudflare bypass engine against albiononline2d.com.
This verifies that we can access the map API and other endpoints.
"""

import logging
import json
import re
from albion_cloudflare_bypass import CloudflareBypass

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

TARGETS = [
    "https://albiononline2d.com/en/map",
    "https://albiononline2d.com/en/map/api/nodes/1",  # Map node API?
]


def test_bypass():
    bypasser = CloudflareBypass()

    for url in TARGETS:
        print(f"\n{'=' * 60}")
        print(f"Testing: {url}")
        print(f"{'=' * 60}")

        result = bypasser.get(url)

        print(f"Source: {result.get('source', 'unknown')}")
        print(f"Status: {result.get('status_code', 'N/A')}")

        html = result.get("html", "")
        print(f"Content Length: {len(html):,} chars")

        # Check for success indicators
        success = False
        if "Just a moment" in html:
            print("❌ Still blocked by Cloudflare challenge")
        elif "<!DOCTYPE html>" in html or "<html" in html:
            print("✅ Received HTML content")
            # Check if it looks like real content
            if "map" in html.lower() or "albion" in html.lower():
                print("✅ Content looks relevant to Albion")
                success = True

        # For API endpoints
        if url.endswith("/api/"):
            try:
                data = json.loads(html)
                print(f"✅ Valid JSON response!")
                print(f"   Preview: {json.dumps(data, indent=2)[:200]}...")
                success = True
            except json.JSONDecodeError:
                print("⚠️  Expected JSON but got non-JSON content")

        # Print first 500 chars for debugging
        print("\n--- First 500 chars of response ---")
        print(html[:500])
        print("--- End of preview ---\n")

        if success:
            # Save result for inspection
            safe_filename = (
                url.replace("https://", "").replace("/", "_").replace("%", "")
            )
            with open(f"test_cf_{safe_filename}.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"💾 Saved full response to test_cf_{safe_filename}.html")


if __name__ == "__main__":
    test_bypass()
