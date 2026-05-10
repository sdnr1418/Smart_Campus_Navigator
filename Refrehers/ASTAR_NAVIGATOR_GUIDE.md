# A* Navigator Guide (Beginner-Friendly)

## 1. What This Project Is Doing

This project finds the best route between campus rooms.

Example:
- Start room: F-201
- Goal room: D-2

It returns:
- total travel cost
- path details (inside building + between buildings)

The navigator uses a hierarchical approach:
1. Room-level pathfinding inside a building.
2. Building-level pathfinding between buildings.
3. Combine both into one final route.

---

## 2. Where The Main Logic Lives

Primary file:
- scripts/hierarchical_navigator.py

Key data sources:
- config.py
- all_rooms.csv

What each provides:
- all_rooms.csv: room, building, floor mapping.
- config.py / BUILDING_GRAPH: building-to-building weighted edges.
- config.py / BUILDING_POS: 2D coordinates for building heuristic.
- config.py / STAIRS_CONFIG: stair links between floors within a building.

---

## 3. Why Hierarchical Instead Of One Giant Graph?

If you model every room and every transition in one giant campus graph, logic gets harder to manage and debug.

This project separates concerns:
1. Intra-building navigation (room graph).
2. Inter-building navigation (building graph).

Benefits:
- easier to reason about
- modular testing
- cleaner path explanations

---

## 4. Graph Models Used

## 4.1 Building Graph (Campus Level)

Node:
- each building (A-Block, C-Block, D-Block, etc.)

Edge weight:
- walking cost between buildings from BUILDING_GRAPH

Used by:
- a_star_buildings(start_building, goal_building)

## 4.2 Room Graph (Per Building)

Node:
- each room in that building

Edges:
1. Corridor edges:
- adjacent rooms on the same floor
- cost = 1

2. Stair edges:
- from STAIRS_CONFIG
- cost = 5

Used by:
- shortest_room_path(start_room, goal_room, building, rooms_info, room_graphs)

---

## 5. A* Refresher (In This Project)

A* picks nodes by minimizing:

f(n) = g(n) + h(n)

Where:
- g(n): exact cost from start to current node
- h(n): estimated cost from current node to goal (heuristic)

A* gives optimal routes when h(n) does not overestimate.

---

## 6. How A* Is Applied Here

## 6.1 A* On Building Graph

Function:
- a_star_buildings(...)

Heuristic base:
- Euclidean distance between building coordinates (from BUILDING_POS)

To keep heuristic safe, code scales Euclidean by a conservative factor:

r_min = min( edge_weight / euclidean_distance ) over building edges

Then:

h(building) = r_min * euclidean(building, goal)

Why this matters:
- It avoids overestimation.
- A* remains optimal under this model.

## 6.2 A* On Room Graph

Function:
- shortest_room_path(...)

Room positions are synthesized from:
- floor index (y axis)
- sorted room order (x axis)

Heuristic is also scaled safely per building:

r_room = min( edge_cost / euclidean_distance ) over room edges
h(room) = r_room * euclidean(room, goal_room)

Again, this keeps heuristic conservative for A*.

---

## 7. Exit-Room Concept (Very Important)

When start and goal are in different buildings, this project uses one exit room per building.

Rule in get_building_exit(...):
- normal buildings: floor 1 is ground floor
- F-Block special case: floor 2 is ground floor
- pick smallest room number on ground floor

This creates a deterministic bridge between room-level and building-level routing.

Cross-building route composition:
1. start_room -> start_building_exit (room A*)
2. start_building -> goal_building (building A*)
3. goal_building_exit -> goal_room (room A*)

Total:

total_cost = cost1 + building_cost + cost3

---

## 8. Important Fixes Already Applied

Your current script includes these fixes:

1. CSV source fix:
- load_rooms defaults to all_rooms.csv (correct source).

2. Named-room sorting fix:
- extract_room_number uses regex for digits anywhere.
- if no digits, returns 999999 so named rooms sort after numbered rooms.

Why fix #2 matters:
- Prevents named rooms like Micro Lab or Seminar Hall from becoming exits before D-1/C-1 when choosing building exits.

---

## 9. End-to-End Flow Of total_path_cost

Function:
- total_path_cost(start, goal, rooms_info)

Execution path:

1. Validate both rooms exist.
2. Identify start building and goal building.
3. Build room graphs for buildings in data.

Case A: same building
- run shortest_room_path directly
- return room path only

Case B: different buildings
- get exit of start building
- get exit of goal building
- room A*: start -> start_exit
- building A*: start_building -> goal_building
- room A*: goal_exit -> goal
- sum costs and return structured description

Returned description keys:
- start_to_exit
- building_path
- exit_to_goal

---

## 10. How To Run And Verify

From project root:

1) Run demo:

python scripts/hierarchical_navigator.py

2) Run tests:

python scripts/test_navigator.py

Expected current status:
- tests pass (11/11)
- building graph connected prints True in demo

---

## 11. Reading The Path Output

Formatted output includes:
- room path segment in source building
- building path in brackets
- room path segment in destination building

Example style:

F-201 -> [F-Block (New Building) -> D-Block (Electrical/Management)] -> D-1 -> D-2

Interpretation:
1. F-201 already at exit in F-Block (no movement cost inside source building).
2. Move building-level F -> D (cost from BUILDING_GRAPH).
3. In D-Block, move from exit D-1 to D-2.

---

## 12. Limitations (Design Assumptions)

These are model assumptions, not coding errors:

1. Corridor adjacency is based on sorted room numbers.
2. Stairs only exist where STAIRS_CONFIG defines links.
3. One exit room per building (fixed policy).
4. Room coordinates for heuristic are synthetic, not architectural CAD coordinates.

If you later need real-world precision, you can replace these assumptions with measured geometry and true connectivity maps.

---

## 13. Quick Mental Model (One-Line)

Your project runs A* three times for cross-building routes:
- room A* out of source building
- building A* across campus
- room A* into destination room

That is the full hierarchical A* strategy implemented in this codebase.
