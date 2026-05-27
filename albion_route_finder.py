#!/usr/bin/env python3
"""
Albion Online Travel Time Calculator & Route Finder
Calculates optimal routes between two zones with weighted pathfinding.
Supports distance calculation, time estimation, and zone type filtering.
"""

import json
import math
import heapq
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

BASE_DIR = Path(__file__).parent

# Zone type code to PvP type mapping (from parse_zones.py)
TYPE_CODE_TO_ZONE_TYPE = {
    0: 0,  # undefined -> city
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

ZONE_TYPE_NAMES = {
    0: "City",
    1: "Blue",
    2: "Yellow",
    3: "Red",
    4: "Black",
    5: "Dungeon",
    6: "Portal",
    7: "Black",
}

# Default PvP weights (lower = preferred)
DEFAULT_WEIGHTS: dict[int, float] = {
    0: 0.5,  # City - very safe
    1: 1.0,  # Blue/Safe - very safe
    2: 1.5,  # Yellow - mostly safe
    3: 3.0,  # Red - PvP risk
    4: 5.0,  # Black - high PvP risk
    6: 10.0,  # Portal - avoid for route-finding
    7: 1.0,  # Outlands Safe Town - same as blue
}

# Movement speed: ~5 m/s running
RUNNING_SPEED_MPS = 5.0
SECONDS_PER_METER = 1.0 / RUNNING_SPEED_MPS


@dataclass
class ZoneNode:
    """Represents a zone in the Albion world."""

    id: int
    name: str
    x: float
    y: float
    zone_type: int = 1
    connections: list[int] = field(default_factory=list)

    @property
    def distance_from_origin(self) -> float:
        """Distance from world origin (0,0)."""
        return math.sqrt(self.x**2 + self.y**2)


@dataclass
class RouteStep:
    """One step in a route."""

    from_zone: ZoneNode
    to_zone: ZoneNode
    distance: float
    duration_seconds: float
    zone_type: int


@dataclass
class Route:
    """Complete route from A to B."""

    steps: list[RouteStep]
    total_distance: float
    total_duration_seconds: float
    zone_breakdown: dict[str, tuple[float, float]]

    @property
    def total_minutes(self) -> float:
        return self.total_duration_seconds / 60.0

    @property
    def total_km(self) -> float:
        return self.total_distance / 1000.0


class AlbionRouteFinder:
    """
    Finds optimal routes between Albion Online zones.
    Uses Dijkstra's algorithm with weighted zone costs.
    """

    def __init__(self, zones_json_path: Optional[Path] = None):
        self.zones: dict[int, ZoneNode] = {}
        self.zone_by_name: dict[str, ZoneNode] = {}
        self.graph: dict[int, list[int]] = {}

        if zones_json_path is None:
            zones_json_path = BASE_DIR / "extracted_maps/albion_zones.json"

        self.load_zones(zones_json_path)

    def load_zones(self, json_path: Path):
        """Load zone data from the extracted JSON."""
        if not json_path.exists():
            raise FileNotFoundError(
                f"Zone data not found at {json_path}. "
                "Run download_all_maps.py first to extract zone data."
            )

        data = json.loads(json_path.read_text())

        zone_id_map: dict[int, ZoneNode] = {}

        for item in data:
            zone_id = item.get("id", 0)
            if not zone_id:
                # Skip zones without IDs
                continue

            name = item.get("name", item.get("file", "Unknown"))
            x = item.get("x", 0.0)
            y = item.get("y", 0.0)
            connections = item.get("connections", [])

            # Prefer the already-converted zone_type field; fall back to mapping from raw type_code
            if "zone_type" in item:
                zone_type = item["zone_type"]
            elif "type" in item:
                zone_type = TYPE_CODE_TO_ZONE_TYPE.get(item["type"], 2)
            else:
                zone_type = 2

            # Ensure x/y are floats
            try:
                x = float(x)
                y = float(y)
            except (ValueError, TypeError):
                continue

            zone = ZoneNode(
                id=zone_id,
                name=name,
                x=x,
                y=y,
                zone_type=zone_type,
                connections=connections,
            )
            zone_id_map[zone_id] = zone

        # Resolve connections to actual edges
        for zone_id, zone in zone_id_map.items():
            self.graph[zone_id] = []
            for conn_id in zone.connections:
                if conn_id in zone_id_map and conn_id != zone_id:
                    self.graph[zone_id].append(conn_id)

        self.zones = zone_id_map
        self.zone_by_name = {z.name.lower(): z for z in zone_id_map.values()}

        print(
            f"Loaded {len(self.zones)} zones with {sum(len(v) for v in self.graph.values())} connections"
        )

    def find_zone(self, query: str) -> Optional[ZoneNode]:
        """Find a zone by name (case-insensitive partial match)."""
        q = query.lower()
        # Exact match first
        if q in self.zone_by_name:
            return self.zone_by_name[q]
        # Partial match
        for name, zone in self.zone_by_name.items():
            if q in name:
                return zone
        return None

    def _get_edge_distance(self, from_zone: ZoneNode, to_zone: ZoneNode) -> float:
        """Calculate distance between two connected zones (in world units)."""
        dx = to_zone.x - from_zone.x
        dy = to_zone.y - from_zone.y
        return math.sqrt(dx**2 + dy**2)

    def _edge_weighted_cost(
        self, from_zone: ZoneNode, to_zone: ZoneNode, weights: dict[int, float]
    ) -> float:
        """Weighted cost of traversing an edge (distance * zone type weight)."""
        base = self._get_edge_distance(from_zone, to_zone)
        weight = weights.get(to_zone.zone_type, 1.0)
        return base * weight

    def find_route(
        self,
        start: str | ZoneNode,
        end: str | ZoneNode,
        weights: Optional[dict[int, float]] = None,
    ) -> Optional[Route]:
        """
        Find the optimal route between two zones using Dijkstra's algorithm.

        Args:
            start: Starting zone (name or ZoneNode)
            end: Destination zone (name or ZoneNode)
            weights: Zone type weights for pathfinding (lower = preferred)

        Returns:
            Route with steps, total distance, and zone breakdown
        """
        if weights is None:
            weights = DEFAULT_WEIGHTS

        if isinstance(start, str):
            start_node = self.find_zone(start)
        else:
            start_node = start

        if isinstance(end, str):
            end_node = self.find_zone(end)
        else:
            end_node = end

        if not start_node:
            raise ValueError(f"Start zone '{start}' not found")
        if not end_node:
            raise ValueError(f"End zone '{end}' not found")

        if start_node.id == end_node.id:
            return Route(
                steps=[],
                total_distance=0,
                total_duration_seconds=0,
                zone_breakdown={},
            )

        if start_node.id not in self.graph or end_node.id not in self.graph:
            # Try fallback: direct line distance
            dist = self._get_edge_distance(start_node, end_node)
            duration = dist * SECONDS_PER_METER
            return Route(
                steps=[
                    RouteStep(
                        from_zone=start_node,
                        to_zone=end_node,
                        distance=dist,
                        duration_seconds=duration,
                        zone_type=end_node.zone_type,
                    )
                ],
                total_distance=dist,
                total_duration_seconds=duration,
                zone_breakdown={},
            )

        # Dijkstra's algorithm
        # Priority queue: (cost, zone_id)
        pq: list[tuple[float, int]] = [(0.0, start_node.id)]
        came_from: dict[int, int] = {}
        costs: dict[int, float] = {start_node.id: 0.0}
        visited: set[int] = set()

        while pq:
            current_cost, current_id = heapq.heappop(pq)

            if current_id == end_node.id:
                break

            if current_id in visited:
                continue
            visited.add(current_id)

            current = self.zones[current_id]

            for neighbor_id in self.graph.get(current_id, []):
                if neighbor_id not in self.zones:
                    continue

                neighbor = self.zones[neighbor_id]
                edge_cost = self._edge_weighted_cost(current, neighbor, weights)
                new_cost = current_cost + edge_cost

                if neighbor_id not in costs or new_cost < costs[neighbor_id]:
                    costs[neighbor_id] = new_cost
                    came_from[neighbor_id] = current_id
                    heapq.heappush(pq, (new_cost, neighbor_id))

        # Reconstruct path
        if end_node.id not in came_from and start_node.id != end_node.id:
            print(f"No route found between {start_node.name} and {end_node.name}")
            return None

        path_ids = [end_node.id]
        current = end_node.id
        while current != start_node.id:
            parent = came_from.get(current)
            if parent is None:
                break
            path_ids.append(parent)
            current = parent

        path_ids.reverse()

        if len(path_ids) < 2:
            return None

        # Build route steps
        steps: list[RouteStep] = []
        total_distance = 0.0
        zone_types: dict[int, list[float]] = {}

        for i in range(len(path_ids) - 1):
            from_node = self.zones[path_ids[i]]
            to_node = self.zones[path_ids[i + 1]]

            dist = self._get_edge_distance(from_node, to_node)
            duration = dist * SECONDS_PER_METER

            steps.append(
                RouteStep(
                    from_zone=from_node,
                    to_zone=to_node,
                    distance=dist,
                    duration_seconds=duration,
                    zone_type=to_node.zone_type,
                )
            )

            total_distance += dist
            zt = to_node.zone_type
            if zt not in zone_types:
                zone_types[zt] = []
            zone_types[zt].append(dist)

        total_duration = total_distance * SECONDS_PER_METER

        # Zone breakdown
        zone_breakdown: dict[str, tuple[float, float]] = {}
        for zt, dists in zone_types.items():
            total_d = sum(dists)
            name = ZONE_TYPE_NAMES.get(zt, f"Type {zt}")
            pct = (total_d / total_distance * 100) if total_distance > 0 else 0
            zone_breakdown[name] = (total_d, pct)

        return Route(
            steps=steps,
            total_distance=total_distance,
            total_duration_seconds=total_duration,
            zone_breakdown=zone_breakdown,
        )

    def print_route(self, route: Route):
        """Print route summary."""
        print("\n" + "=" * 60)
        print("ROUTE SUMMARY")
        print("=" * 60)
        print(
            f"Total Distance: {route.total_km:.2f} km ({route.total_distance:.0f} units)"
        )
        print(f"Est. Travel Time: {route.total_minutes:.1f} minutes")
        print(f"Number of Steps: {len(route.steps)}")

        if route.zone_breakdown:
            print("\nZone Breakdown:")
            for name, (dist, pct) in sorted(
                route.zone_breakdown.items(), key=lambda x: -x[1][1]
            ):
                print(f"  {name}: {pct:.1f}% ({dist:.0f} units)")

        if route.steps:
            print("\nRoute Steps:")
            for i, step in enumerate(route.steps, 1):
                print(f"  {i:3d}. {step.from_zone.name} -> {step.to_zone.name}")
                print(
                    f"       {ZONE_TYPE_NAMES.get(step.zone_type, 'Unknown')}: {step.distance:.0f} units (~{step.duration_seconds / 60:.1f} min)"
                )


def main():
    """Interactive route finder."""
    print("Albion Online Travel Route Finder")
    print("=" * 60)
    print()

    finder = AlbionRouteFinder()

    # Example routes
    examples = [
        ("Thetford", "Bridgewatch"),
        ("Lymhurst", "Martlock"),
        ("Bridgewatch", "Caerleon"),
        ("Thetford", "Fort Sterling"),
    ]

    print("\nExample Routes:")
    for start_name, end_name in examples:
        print(f"\n{'=' * 40}")
        print(f"From: {start_name}")
        print(f"To:   {end_name}")

        route = finder.find_route(start_name, end_name)
        if route:
            finder.print_route(route)
        else:
            print(f"  No route found")

    print("\n" + "=" * 60)
    print("Interactive Mode")
    print("=" * 60)
    print("Type zone names to find routes (or 'quit' to exit)")

    while True:
        start = input("\nStart zone: ").strip()
        if start.lower() in ("q", "quit", "exit"):
            break

        end = input("End zone: ").strip()

        if finder.find_zone(start) is None:
            print(f"  Warning: '{start}' not found. Try a partial name match.")
            continue
        if finder.find_zone(end) is None:
            print(f"  Warning: '{end}' not found. Try a partial name match.")
            continue

        route = finder.find_route(start, end)
        if route:
            finder.print_route(route)
        else:
            print(f"  No route found between {start} and {end}")


if __name__ == "__main__":
    main()
