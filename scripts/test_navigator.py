"""
Test cases with expected ranges for graph-based intra-building navigator.
"""
from hierarchical_navigator import load_rooms, total_path_cost

rooms_info = load_rooms()
print(f"Loaded {len(rooms_info)} rooms\n")

def format_path(desc):
    """Format path description into readable string."""
    if not desc or isinstance(desc, list):
        return "Direct path"
    
    # Dict format: cross-building or same-building
    parts = []
    if desc.get("start_to_exit"):
        parts.append(" → ".join(desc["start_to_exit"]))
    if desc.get("building_path"):
        parts.append("[" + " → ".join(desc["building_path"]) + "]")
    if desc.get("exit_to_goal"):
        parts.append(" → ".join(desc["exit_to_goal"]))
    
    # Filter out empty parts and clean up empty brackets
    parts = [p for p in parts if p and p != "[]"]
    return " → ".join(parts) if parts else "Direct path"

def get_path_desc(start, goal):
    cost, desc = total_path_cost(start, goal, rooms_info)
    if cost == float('inf'):
        return cost, "No path"
    return cost, format_path(desc)

# Expected ranges after switching to corridor+stairs room graph costs
test_cases = [
    ("F-201", "F-202", (0, 2), "Same floor, same building (cost 1)"),
    ("F-201", "F-301", (4, 6), "Different floor, same building (cost 5)"),
    ("F-201", "F-303", (6, 8), "Different floor, corridor + stairs path (cost ~7)"),
    ("F-311", "F-201", (14, 16), "Reverse direction over corridor chain + stairs (cost ~15)"),
    ("F-201", "D-2", (20, 22), "Cross-building F→D with realistic room traversal (cost ~21)"),
    ("F-201", "C-1", (24, 28), "Cross-building F→D→C (cost ~25-26)"),
    ("F-201", "A-4", (28, 32), "Cross-building F→D→A (cost 30)"),
    ("F-201", "Lab-13", (15, 30), "Cross-building F→L (cost 15)"),
    ("C-1", "C-15", (9, 11), "Same building, corridor chain via room sequence (cost ~10)"),
    ("D-2", "D-11", (4, 6), "Same building, floor 1→2 (cost 5)"),
    ("A-4", "B-Block (Civil)", (None, None), "Building with no rooms – expect no path"),
]

passed = failed = 0
for start, goal, expected_range, desc_str in test_cases:
    print(f"\nTest: {start} → {goal}")
    print(f"  {desc_str}")
    if goal == "B-Block (Civil)":
        cost, _ = total_path_cost(start, goal, rooms_info)
        if cost == float('inf'):
            print("  ✅ PASSED (no path)")
            passed += 1
        else:
            print(f"  ❌ FAILED (expected no path, got {cost})")
            failed += 1
        continue
    cost, path = get_path_desc(start, goal)
    if cost == float('inf'):
        print("  ❌ FAILED (no path found)")
        failed += 1
        continue
    print(f"  Cost: {cost:.1f}")
    print(f"  Path: {path[:100]}...")
    if expected_range[0] is not None:
        if expected_range[0] <= cost <= expected_range[1]:
            print(f"  ✅ PASSED (cost within {expected_range})")
            passed += 1
        else:
            print(f"  ❌ FAILED (cost {cost} outside {expected_range})")
            failed += 1
    else:
        passed += 1

print(f"\nRESULTS: {passed} passed, {failed} failed")