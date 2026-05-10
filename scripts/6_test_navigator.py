"""
Test cases for verifying building exits and cross-building route composition.
"""
import importlib.util
from pathlib import Path

navigator_path = Path(__file__).with_name("5_hierarchical_navigator.py")
spec = importlib.util.spec_from_file_location("hierarchical_navigator", navigator_path)
navigator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(navigator)

load_rooms = navigator.load_rooms
total_path_cost = navigator.total_path_cost
get_building_exit = navigator.get_building_exit

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

def assert_exact_path(start, goal, expected_start_to_exit, expected_building_path, expected_exit_to_goal, label):
    cost, desc = total_path_cost(start, goal, rooms_info)
    print(f"\nTest: {label}")
    print(f"  Start: {start}")
    print(f"  Goal:  {goal}")
    if cost == float('inf') or not isinstance(desc, dict):
        print("  ❌ FAILED (no valid path)")
        return False

    actual_start_to_exit = desc.get("start_to_exit", [])
    actual_building_path = desc.get("building_path", [])
    actual_exit_to_goal = desc.get("exit_to_goal", [])

    print(f"  Cost: {cost:.1f}")
    print(f"  start_to_exit: expected {expected_start_to_exit}")
    print(f"                 actual   {actual_start_to_exit}")
    print(f"  building_path: expected {expected_building_path}")
    print(f"                 actual   {actual_building_path}")
    print(f"  exit_to_goal:  expected {expected_exit_to_goal}")
    print(f"                 actual   {actual_exit_to_goal}")

    if (
        actual_start_to_exit == expected_start_to_exit
        and actual_building_path == expected_building_path
        and actual_exit_to_goal == expected_exit_to_goal
    ):
        print("  ✅ PASSED")
        return True

    print("  ❌ FAILED")
    return False

building_exit_cases = [
    ("A-Block (Admin)", "A-4", "Lowest numbered room on floor 1"),
    ("B-Block (Civil)", "CRMG", "No numbered rooms on floor 1, so CSV order decides between named rooms"),
    ("C-Block (Computing)", "C-1", "Named room Seminar Hall must sort after numbered rooms"),
    ("D-Block (Electrical/Management)", "D-1", "Named rooms on floor 1 must not beat numbered rooms"),
    ("E-Block (English Labs)", "Eng Lab-1", "Only floor 1 rooms are available"),
    ("F-Block (New Building)", "F-201", "Special case: ground floor is floor 2"),
    ("L-Block (Labs)", "Lab-1", "Lowest numbered room on floor 1"),
]

cross_building_cases = [
    ("F-210", "D-2", "F-201", "D-1", "Direct F → D route should use F-201 and D-1 as exits"),
    ("D-5", "C-16", "D-1", "C-1", "Direct D → C route should use D-1 and C-1 as exits"),
    ("Embedded Lab", "A-7", "CRMG", "A-4", "B-Block should use CRMG as its exit even though it has no numbered rooms"),
]

exact_path_cases = [
    (
        "F-210",
        "D-2",
        ["F-210", "F-209", "F-208", "F-207", "F-206", "F-205", "F-204", "F-203", "F-202", "F-201"],
        ["F-Block (New Building)", "D-Block (Electrical/Management)"],
        ["D-1", "D-2"],
        "F-210 to D-2 full composed path",
    ),
    (
        "D-5",
        "C-16",
        ["D-5", "D-4", "D-3", "D-2", "D-1"],
        ["D-Block (Electrical/Management)", "C-Block (Computing)"],
        ["C-1", "C-10", "C-11", "C-12", "C-13", "C-14", "C-15", "C-16"],
        "D-5 to C-16 full composed path",
    ),
    (
        "Embedded Lab",
        "A-7",
        ["Embedded Lab", "CRMG"],
        ["B-Block (Civil)", "A-Block (Admin)"],
        ["A-4", "A-7"],
        "Embedded Lab to A-7 full composed path",
    ),
]

passed = failed = 0

print("Building exit tests")
for building, expected_exit, why in building_exit_cases:
    actual_exit = get_building_exit(building, rooms_info)
    print(f"\nTest: {building}")
    print(f"  {why}")
    print(f"  Expected exit: {expected_exit}")
    print(f"  Actual exit:   {actual_exit}")
    if actual_exit == expected_exit:
        print("  ✅ PASSED")
        passed += 1
    else:
        print("  ❌ FAILED")
        failed += 1

print("\nCross-building path tests")
for start, goal, expected_start_exit, expected_goal_exit, why in cross_building_cases:
    cost, desc = total_path_cost(start, goal, rooms_info)
    print(f"\nTest: {start} → {goal}")
    print(f"  {why}")
    if cost == float('inf') or not isinstance(desc, dict):
        print("  ❌ FAILED (no valid path)")
        failed += 1
        continue

    start_path = desc.get("start_to_exit", [])
    goal_path = desc.get("exit_to_goal", [])
    building_path = desc.get("building_path", [])
    actual_start_exit = start_path[-1] if start_path else None
    actual_goal_exit = goal_path[0] if goal_path else None

    print(f"  Cost: {cost:.1f}")
    print(f"  Start exit: expected {expected_start_exit}, actual {actual_start_exit}")
    print(f"  Goal exit:  expected {expected_goal_exit}, actual {actual_goal_exit}")
    print(f"  Building path: {' → '.join(building_path) if building_path else 'Direct path'}")

    if actual_start_exit == expected_start_exit and actual_goal_exit == expected_goal_exit:
        print("  ✅ PASSED")
        passed += 1
    else:
        print("  ❌ FAILED")
        failed += 1

print("\nExact path shape tests")
for start, goal, expected_start_to_exit, expected_building_path, expected_exit_to_goal, label in exact_path_cases:
    if assert_exact_path(start, goal, expected_start_to_exit, expected_building_path, expected_exit_to_goal, label):
        passed += 1
    else:
        failed += 1

print(f"\nRESULTS: {passed} passed, {failed} failed")