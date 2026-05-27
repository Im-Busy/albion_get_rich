"""Verify the unified Cloudflare bypass engine."""

from albion_cloudflare_bypass import CloudflareBypass
import json

# Test 1: Fresh request (solves Cloudflare)
print("Test 1: Fresh request (may solve Cloudflare)...")
b = CloudflareBypass()
r = b.get("https://albiononline2d.com/en/map")
blocked = "Just a moment" in r["html"]
length = len(r["html"])
print(f"  Source: {r.get('source', 'unknown')}")
print(f"  Status: {r.get('status_code', 'N/A')}")
print(f"  Length: {length:,}")
print(f"  Blocked: {blocked}")
print()

# Test 2: Cached session (should be fast)
print("Test 2: Cached session (should use curl_cffi)...")
r2 = b.get("https://albiononline2d.com/en/map")
blocked2 = "Just a moment" in r2["html"]
length2 = len(r2["html"])
print(f"  Source: {r2.get('source', 'unknown')}")
print(f"  Status: {r2.get('status_code', 'N/A')}")
print(f"  Length: {length2:,}")
print(f"  Blocked: {blocked2}")
print()

if not blocked and not blocked2:
    print("SUCCESS: Cloudflare bypass working on both fresh and cached!")
else:
    print(f"Fresh blocked: {blocked}, Cached blocked: {blocked2}")
