"""
Script to extract full Albion Online maps from cloned research repositories
and download additional maps from various sources.
"""

import os
import json
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent


def extract_world_map_from_navigator():
    """Extract the full world map from albion-navigator repository."""
    print("=" * 60)
    print("Extracting full world map from albion-navigator")
    print("=" * 60)

    output_dir = BASE_DIR / "extracted_maps"
    output_dir.mkdir(exist_ok=True)

    map_src = BASE_DIR / "albion_navigator_research/Assets/Images/map-background-hq.png"

    if map_src.exists():
        size_mb = map_src.stat().st_size / (1024 * 1024)
        print(f"Found world map: {map_src.name} ({size_mb:.1f} MB)")
        dst = output_dir / "albion_world_map.png"
        shutil.copy2(map_src, dst)
        print(f"Copied to: {dst}")
    else:
        print(f"World map not found at: {map_src}")

    return output_dir


# Map from .tres type_code to zone_type used by the route-finder
# (0=city, 1=blue, 2=yellow, 3=red, 4=black, 5=dungeon, 6=portal, 7=outlands)
TYPE_CODE_TO_ZONE_TYPE = {
    0: 0,  # undefined
    1: 0,  # starting_city -> city
    2: 0,  # city
    3: 1,  # zone_home -> blue
    4: 2,  # zone_highland -> yellow
    5: 3,  # zone_steppe -> red
    6: 2,  # zone_highway -> yellow
    7: 4,  # outland -> black
    8: 6,  # portal_entrance -> portal
    9: 6,  # portal_exit -> portal
    10: 1,  # safe_area -> blue
}


def extract_zone_data_from_navigator():
    """Extract all zone data (positions, connections, types) from .tres files."""
    print("\nExtracting zone data...")

    zones_dir = BASE_DIR / "albion_navigator_research/Resources/Zones"
    output_dir = BASE_DIR / "extracted_maps"
    output_dir.mkdir(exist_ok=True)

    zones_data = []
    tres_files = list(zones_dir.glob("*.tres"))

    for tres_file in tres_files:
        try:
            content = tres_file.read_text(encoding="utf-8")
            zone_info = {"file": tres_file.stem}

            for line in content.splitlines():
                if line.startswith("DisplayName = "):
                    zone_info["name"] = line.split('"')[1]
                elif line.startswith("Type = "):
                    zone_info["type"] = int(line.split("=")[1].strip())
                elif line.startswith("Layer = "):
                    zone_info["layer"] = int(line.split("=")[1].strip())
                elif line.startswith("Position = "):
                    pos = line.split("Vector2(")[1].rstrip(")")
                    x, y = pos.split(", ")
                    zone_info["x"] = float(x)
                    zone_info["y"] = float(y)
                elif line.startswith("Connections = "):
                    conns = line.split("[")[1].rstrip("]")
                    zone_info["connections"] = [
                        int(c.strip()) for c in conns.split(",")
                    ]
                elif line.startswith("Id = "):
                    zone_info["id"] = int(line.split("=")[1].strip())

            # Map type_code to zone_type
            zone_info["zone_type"] = TYPE_CODE_TO_ZONE_TYPE.get(
                zone_info.get("type", 0), 2
            )

            zones_data.append(zone_info)
        except Exception as e:
            print(f"  Error parsing {tres_file.name}: {e}")

    output_json = output_dir / "albion_zones.json"
    output_json.write_text(json.dumps(zones_data, indent=2, ensure_ascii=False))
    print(f"Extracted {len(zones_data)} zones to {output_json}")

    return zones_data


def summarize_avalon_roads_maps():
    """Summarize the Avalon Roads maps already downloaded."""
    print("\n" + "=" * 60)
    print("Avalon Roads Maps (already downloaded)")
    print("=" * 60)

    maps_dir = BASE_DIR / "avalon_roads_downloads/public/maps"
    if not maps_dir.exists():
        print("Avalon Roads maps directory not found")
        return

    png_files = list(maps_dir.glob("*.png"))
    total_size_mb = sum(f.stat().st_size for f in png_files) / (1024 * 1024)

    tiers = {}
    for f in png_files:
        tier = None
        for t in ["T_8", "T_6", "T_4"]:
            if t in f.name:
                tier = t.replace("_", "")
                break
        if tier:
            tiers[tier] = tiers.get(tier, 0) + 1

    print(f"Total maps: {len(png_files)}")
    print(f"Total size: {total_size_mb:.1f} MB")
    print(f"By tier: {tiers}")


def summarize_albionmaps_br():
    """Summarize the albionmaps.com.br maps already downloaded."""
    print("\n" + "=" * 60)
    print("AlbionMaps.com.br Maps (already downloaded)")
    print("=" * 60)

    maps_dir = BASE_DIR / "albionmaps_br_downloads"
    if not maps_dir.exists():
        print("Maps directory not found")
        return

    webp_files = list(maps_dir.glob("*.webp"))
    total_size_mb = sum(f.stat().st_size for f in webp_files) / (1024 * 1024)

    print(f"Total maps: {len(webp_files)}")
    print(f"Total size: {total_size_mb:.1f} MB")
    print("Maps:")
    for f in sorted(webp_files):
        print(f"  - {f.name}")


def print_summary():
    """Print overall summary of all downloaded/extracted maps."""
    print("\n" + "=" * 60)
    print("ALBION ONLINE MAPS - COMPLETE SUMMARY")
    print("=" * 60)

    # World map
    world_map = BASE_DIR / "extracted_maps/albion_world_map.png"
    if world_map.exists():
        print(
            f"\n Full World Map: albion_world_map.png ({world_map.stat().st_size / (1024 * 1024):.1f} MB)"
        )

    # Zone data
    zone_data = BASE_DIR / "extracted_maps/albion_zones.json"
    if zone_data.exists():
        data = json.loads(zone_data.read_text())
        print(f" Zone Data: albion_zones.json ({len(data)} zones)")

    # Avalon Roads
    avalon_dir = BASE_DIR / "avalon_roads_downloads/public/maps"
    if avalon_dir.exists():
        count = len(list(avalon_dir.glob("*.png")))
        print(f" Avalon Roads Maps: {count} PNG files")

    # albionmaps.com.br
    br_dir = BASE_DIR / "albionmaps_br_downloads"
    if br_dir.exists():
        count = len(list(br_dir.glob("*.webp")))
        print(f" Hidden Outpost/Tunnel Maps: {count} WebP files")

    # albion-navigator zones
    nav_zones = BASE_DIR / "albion_navigator_research/Resources/Zones"
    if nav_zones.exists():
        count = len(list(nav_zones.glob("*.tres")))
        print(
            f" Albion Navigator Zone Data: {count} .tres files (zone connections/types)"
        )

    print("\nAll maps extracted to extracted_maps/")
    print("=" * 60)


if __name__ == "__main__":
    extract_world_map_from_navigator()
    extract_zone_data_from_navigator()
    summarize_avalon_roads_maps()
    summarize_albionmaps_br()
    print_summary()
