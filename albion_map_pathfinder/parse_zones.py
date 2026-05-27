"""
Parse albion-navigator .tres files into a comprehensive zones JSON with:
- id, name, x, y coordinates
- connections (neighbor zone IDs)
- zone_type (mapped to PvP type: blue, yellow, red, black, city, outland, etc.)
- layer
"""

import json
import re
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent
ZONES_DIR = BASE_DIR / "albion_navigator_research/Resources/Zones"
OUTPUT_DIR = BASE_DIR / "albion_map_pathfinder/data"


ZONE_TYPE_MAP = {
    0: {"name": "undefined", "pvp": None},
    1: {"name": "starting_city", "pvp": "blue"},
    2: {"name": "city", "pvp": "blue"},
    3: {"name": "zone_home", "pvp": "blue"},
    4: {"name": "zone_highland", "pvp": "yellow"},
    5: {"name": "zone_steppe", "pvp": "red"},
    6: {"name": "zone_highway", "pvp": "yellow"},
    7: {"name": "outland", "pvp": "black"},
    8: {"name": "portal_entrance", "pvp": None},
    9: {"name": "portal_exit", "pvp": None},
    10: {"name": "safe_area", "pvp": "blue"},
}


def parse_tres_files():
    """Parse all .tres zone files from albion-navigator repository."""
    zones = []
    tres_files = sorted(ZONES_DIR.glob("*.tres"))

    print(f"Found {len(tres_files)} .tres files")

    for tres_file in tres_files:
        try:
            content = tres_file.read_text(encoding="utf-8")
            zone = {}

            # Parse fields
            for match in re.finditer(r"Id\s*=\s*(-?\d+)", content):
                zone["id"] = int(match.group(1))
            if "id" not in zone:
                continue

            for match in re.finditer(r"Type\s*=\s*(-?\d+)", content):
                zone["type_code"] = int(match.group(1))

            for match in re.finditer(r"Layer\s*=\s*(-?\d+)", content):
                zone["layer"] = int(match.group(1))

            for match in re.finditer(r'DisplayName\s*=\s*"([^"]*)"', content):
                zone["name"] = match.group(1)

            pos_match = re.search(
                r"Position\s*=\s*Vector2\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)",
                content,
            )
            if pos_match:
                zone["x"] = float(pos_match.group(1))
                zone["y"] = float(pos_match.group(1))

            conn_match = re.search(r"Connections\s*=\s*\[([^\]]*)\]", content)
            if conn_match:
                conns = conn_match.group(1).strip()
                zone["connections"] = (
                    [int(c.strip()) for c in conns.split(",") if c.strip()]
                    if conns
                    else []
                )

            # Determine PVC type
            type_code = zone.get("type_code", 0)
            pvp_info = ZONE_TYPE_MAP.get(type_code, {"name": "unknown", "pvp": None})
            zone["zone_type"] = pvp_info["name"]
            zone["pvp_type"] = pvp_info["pvp"]

            zone["file"] = tres_file.stem
            zones.append(zone)
        except Exception as e:
            print(f"  Error parsing {tres_file.name}: {e}", file=sys.stderr)

    return zones


def build_graph(zones):
    """Create a mapping from zone_id to zone for quick lookup."""
    id_to_zone = {z["id"]: z for z in zones if "id" in z and "id" in z and "x" in z}
    print(f"Built graph with {len(id_to_zone)} valid zones")
    return id_to_zone


def main():
    print("Albion Online Zone Data Parser")
    print("=" * 50)

    zones = parse_tres_files()
    graph = build_graph(zones)

    # Summary stats
    pvp_counts = {}
    for z in zones:
        pvp = z.get("pvp_type")
        if pvp:
            pvp_counts[pvp] = pvp_counts.get(pvp, 0) + 1

    print(f"\nZone distribution by PvP type:")
    for pvp, count in sorted(pvp_counts.items()):
        print(f"  {pvp}: {count}")

    print(f"  unknown: {sum(1 for z in zones if not z.get('pvp_type'))}")

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "zones_complete.json"
    output_file.write_text(json.dumps(zones, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(zones)} zones to {output_file}")

    # Also write graph as adjacency list
    adj = {}
    for z in zones:
        zid = z.get("id")
        conns = z.get("connections", [])
        if zid and conns:
            adj[str(zid)] = conns

    adj_file = OUTPUT_DIR / "zone_adjacency.json"
    adj_file.write_text(json.dumps(adj, indent=2))
    print(f"Wrote adjacency list to {adj_file}")


if __name__ == "__main__":
    main()
