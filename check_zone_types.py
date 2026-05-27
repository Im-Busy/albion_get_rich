import json
from pathlib import Path

data = json.loads(Path("./extracted_maps/albion_zones.json").read_text())

# Find all type 7 zones
type7 = [z for z in data if z.get("type") == 7]
print(f"Type 7 zones: {len(type7)}")
for z in type7:
    print(
        f"  ID={z.get('id')}, name={z.get('name')}, x={z.get('x')}, y={z.get('y')}, conn={z.get('connections')}"
    )

# Also show all unique zone types
all_types = set(z.get("type") for z in data)
print(f"\nAll zone types in data: {sorted(all_types)}")

# Count by type
from collections import Counter

counter = Counter(z.get("type") for z in data)
for t in sorted(counter):
    print(f"  Type {t}: {counter[t]} zones")
