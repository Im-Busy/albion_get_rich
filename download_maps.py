"""
Script to download all map images from albionmaps.com.br
And attempt to download from albiononline2d.com
"""

import requests
from bs4 import BeautifulSoup
import os
import time
from pathlib import Path
import re

BASE_DIR = Path(__file__).parent


def download_albionmaps_br():
    """Download all maps from albionmaps.com.br"""
    print("=" * 60)
    print("Downloading maps from albionmaps.com.br")
    print("=" * 60)

    url = "https://www.albionmaps.com.br/?lang=en"
    output_dir = BASE_DIR / "albionmaps_br_downloads"
    output_dir.mkdir(exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    print(f"Fetching page: {url}")
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    map_images = soup.find_all("img", src=re.compile(r"/mapsImg/.*\.webp"))

    print(f"Found {len(map_images)} map images")

    downloaded = 0
    for img in map_images:
        src = img.get("src", "")
        alt = img.get("alt", "")

        if "/mapsImg/" in src:
            map_url = f"https://www.albionmaps.com.br{src}"
            filename = os.path.basename(src.split("?")[0])
            filepath = output_dir / filename

            if filepath.exists():
                print(f"Skipping (exists): {filename}")
                downloaded += 1
                continue

            try:
                print(f"Downloading: {filename}")
                img_response = requests.get(map_url, headers=headers)
                img_response.raise_for_status()

                with open(filepath, "wb") as f:
                    f.write(img_response.content)

                downloaded += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"Failed to download {filename}: {e}")

    print(f"\nDownloaded {downloaded}/{len(map_images)} maps to {output_dir}")
    return output_dir


def download_albiononline2d():
    """Attempt to download map tiles from albiononline2d.com"""
    print("\n" + "=" * 60)
    print("Attempting to download from albiononline2d.com")
    print("=" * 60)

    output_dir = BASE_DIR / "albiononline2d_downloads"
    output_dir.mkdir(exist_ok=True)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://albiononline2d.com/en/map",
    }

    tile_base_urls = [
        "https://albiononline2d.com/map/tiles",
    ]

    print("\nAlbionOnline2D uses Leaflet.js with tile-based maps.")
    print("The tile URL pattern is typically:")
    print("  https://albiononline2d.com/map/tiles/{z}/{x}/{y}.png")
    print("\nThis site has Cloudflare protection.")
    print("To download tiles, you need to:")
    print("1. Visit https://albiononline2d.com/en/map in your browser")
    print("2. Pass the Cloudflare verification")
    print("3. Open browser DevTools (F12) -> Network tab")
    print("4. Look for tile requests (they match *.png)")
    print("5. Copy the tile URLs and use them in the script below")
    print("\nAlternatively, if you can provide me with:")
    print("- A valid cookie/session token")
    print("- Or the actual tile URL pattern from your browser's network tab")
    print("I can automate the download using that information.")

    print("\nFor now, creating a template script for manual use...")

    template_script = output_dir / "download_tiles_template.py"
    template_script.write_text(
        '''"""
Template script to download tiles from albiononline2d.com
You need to fill in the actual tile URLs from your browser's network tab.
"""

import requests
import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "tiles"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://albiononline2d.com/en/map",
}

def download_tile(url, filename):
    """Download a single tile"""
    filepath = OUTPUT_DIR / filename
    if filepath.exists():
        print(f"Skipping (exists): {filename}")
        return

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(response.content)
        print(f"Downloaded: {filename}")
    except Exception as e:
        print(f"Failed {filename}: {e}")


if __name__ == "__main__":
    # Example: Replace these with actual URLs from your browser's network tab
    # The pattern is typically: https://albiononline2d.com/map/tiles/{z}/{x}/{y}.png
    tiles_to_download = [
        # ("https://albiononline2d.com/map/tiles/0/0/0.png", "tile_0_0_0.png"),
        # Add more tiles here
    ]

    if not tiles_to_download:
        print("No tiles configured. Please:")
        print("1. Visit https://albiononline2d.com/en/map in your browser")
        print("2. Open DevTools (F12) -> Network tab")
        print("3. Find tile requests (*.png)")
        print("4. Copy the URLs and add them to tiles_to_download list")
    else:
        for url, filename in tiles_to_download:
            download_tile(url, filename)
'''
    )

    print(f"Template script created at: {template_script}")
    return output_dir


if __name__ == "__main__":
    download_albionmaps_br()
    download_albiononline2d()
