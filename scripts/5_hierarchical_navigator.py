"""
Hierarchical Navigator for FAST Campus
- Inter-building: weighted graph (custom weights)
- Intra-building: corridor graph (adjacent rooms cost 1) + configured stairs (cost 5)
- Building exit: lowest-numbered room on ground floor (floor 1; F-Block floor 2)
- Path composition: start->exit + building_path + exit->goal
"""

import heapq
import pandas as pd
import re
from collections import defaultdict
import math
import os
import sys

# ============================================================
# BUILDING GRAPH (custom inter-building weights)
# ============================================================
# Load shared configuration from project root `config.py`
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from config import BUILDING_GRAPH, BUILDING_POS, STAIRS_CONFIG


def euclidean(a, b):
    (x1, y1), (x2, y2) = a, b
    return math.hypot(x1 - x2, y1 - y2)


def compute_building_scaling():
    """Compute conservative scaling r_min so that for every building edge:
    edge_weight >= r_min * euclidean(u, v). We return r_min (<=1e9).
    """
    ratios = []
    for u, neighs in BUILDING_GRAPH.items():
        pos_u = BUILDING_POS.get(u)
        if not pos_u:
            continue
        for v, w in neighs.items():
            pos_v = BUILDING_POS.get(v)
            if not pos_v:
                continue
            d = euclidean(pos_u, pos_v)
            if d > 0:
                ratios.append(w / d)
    if not ratios:
        return 1.0
    return min(ratios)


def compute_room_positions_for_building(building, rooms_info):
    """Compute 2D positions for rooms in a building using floor and room number ordering."""
    # Gather rooms
    rooms = [r for r, info in rooms_info.items() if info["building"] == building]
    floor_rooms = defaultdict(list)
    for r in rooms:
        fl = rooms_info[r]["floor"]
        floor_rooms[fl].append(r)

    for fl in floor_rooms:
        floor_rooms[fl].sort(key=extract_room_number)

    pos = {}
    x_step = 180
    y_step = 150
    for fl, nodes in floor_rooms.items():
        y = (fl - 1) * y_step + 50
        for i, node in enumerate(nodes):
            x = 100 + i * x_step
            pos[node] = (x, y)
    return pos


def compute_room_scaling(building, room_graph, positions):
    """Compute conservative scaling r_room so that every room-edge cost >= r_room * euclid."""
    ratios = []
    for u, edges in room_graph.items():
        pu = positions.get(u)
        if not pu:
            continue
        for v, w, _t in edges:
            pv = positions.get(v)
            if not pv:
                continue
            d = euclidean(pu, pv)
            if d > 0:
                ratios.append(w / d)
    if not ratios:
        return 1.0
    return min(ratios)

def verify_graph_connected(graph):
    """Check that all buildings are reachable from each other."""
    all_nodes = set(graph.keys())
    if not all_nodes:
        return False
    start = next(iter(all_nodes))
    visited = set()
    queue = [start]
    while queue:
        node = queue.pop()
        if node in visited:
            continue
        visited.add(node)
        for neigh in graph.get(node, {}):
            if neigh not in visited:
                queue.append(neigh)
    return visited == all_nodes

# ============================================================
# LOAD ROOMS
# ============================================================
def load_rooms(csv_path=None):
    if csv_path is None:
        # Resolve path relative to this file's location
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        csv_path = os.path.join(project_root, "Data", "raw", "all_rooms.csv")
    df = pd.read_csv(csv_path)
    rooms_info = {}
    for _, row in df.iterrows():
        room = row["Room"].strip()
        building = row["Building"].strip()
        floor = int(row["floor_number"])
        rooms_info[room] = {"building": building, "floor": floor}
    return rooms_info

# ============================================================
# BUILDING EXIT ROOM (lowest-numbered room on ground floor)
# ============================================================
def extract_room_number(room):
    """Extract numeric suffix from room name (e.g., 'F-201' -> 201).

    Named rooms with no digits (for example, 'Micro Lab' or 'Seminar Hall')
    should sort after numbered rooms when picking exits.
    """
    m = re.search(r'\d+', room)
    return int(m.group()) if m else 999_999


def build_room_graph(building, rooms_info):
    """Build weighted adjacency for rooms in one building.

    Corridor edges connect adjacent room numbers on the same floor (cost 1).
    Stair edges come from STAIRS_CONFIG (cost 5).
    """
    rooms = [r for r, info in rooms_info.items() if info["building"] == building]
    graph = {r: [] for r in rooms}
    if not rooms:
        return graph

    floor_rooms = defaultdict(list)
    for r in rooms:
        floor_rooms[rooms_info[r]["floor"]].append(r)

    for floor, rlist in floor_rooms.items():
        rlist.sort(key=extract_room_number)
        for i in range(len(rlist) - 1):
            r1, r2 = rlist[i], rlist[i + 1]
            graph[r1].append((r2, 1, "corridor"))
            graph[r2].append((r1, 1, "corridor"))

    for r1, r2 in STAIRS_CONFIG.get(building, []):
        if r1 in graph and r2 in graph:
            graph[r1].append((r2, 5, "stairs"))
            graph[r2].append((r1, 5, "stairs"))

    return graph


def shortest_room_path(start_room, goal_room, building, rooms_info, room_graphs):
    """A* shortest path between two rooms inside the same building using
    Euclidean-based admissible heuristic per building.
    """
    if start_room == goal_room:
        return 0, [start_room]

    graph = room_graphs.get(building)
    if not graph or start_room not in graph or goal_room not in graph:
        return float('inf'), []

    # Compute positions and scaling for this building
    positions = compute_room_positions_for_building(building, rooms_info)
    r_room = compute_room_scaling(building, graph, positions)

    def h(node):
        p = positions.get(node)
        pg = positions.get(goal_room)
        if not p or not pg:
            return 0
        return r_room * euclidean(p, pg)

    # frontier entries: (f = g+h, g, node, path)
    frontier = [(h(start_room), 0, start_room, [start_room])]
    best_g = {start_room: 0}

    while frontier:
        f, g, current, path = heapq.heappop(frontier)
        if current == goal_room:
            return g, path
        if g > best_g.get(current, float('inf')):
            continue
        for neighbor, edge_cost, _edge_type in graph[current]:
            tentative_g = g + edge_cost
            if tentative_g < best_g.get(neighbor, float('inf')):
                best_g[neighbor] = tentative_g
                heapq.heappush(frontier, (tentative_g + h(neighbor), tentative_g, neighbor, path + [neighbor]))

    return float('inf'), []

def get_building_exit(building, rooms_info):
    """Return the room that serves as exit (ground floor, smallest number)."""
    if building == "F-Block (New Building)":
        ground_floor = 2
    else:
        ground_floor = 1
    candidates = [r for r, info in rooms_info.items() if info["building"] == building and info["floor"] == ground_floor]
    if not candidates:
        return None
    return min(candidates, key=extract_room_number)

# ============================================================
# INTRA-BUILDING COST
# ============================================================
def intra_building_cost(room1, room2, rooms_info):
    """Backward-compatible wrapper that returns only the intra-building cost."""
    info1 = rooms_info.get(room1)
    info2 = rooms_info.get(room2)
    if not info1 or not info2 or info1["building"] != info2["building"]:
        return float('inf')

    building = info1["building"]
    room_graphs = {building: build_room_graph(building, rooms_info)}
    cost, _path = shortest_room_path(room1, room2, building, rooms_info, room_graphs)
    return cost

# ============================================================
# A* ON BUILDING GRAPH (with h=0)
# ============================================================
def a_star_buildings(start_building, goal_building):
    """A* search on building graph using admissible Euclidean-based heuristic.

    Heuristic: h(b) = r_min * euclidean(pos(b), pos(goal)), where r_min is the
    minimum ratio edge_weight / euclidean(u,v) across building edges. This ensures
    admissibility and consistency.
    """
    # Precompute scaling and goal position
    r_min = compute_building_scaling()
    goal_pos = BUILDING_POS.get(goal_building)

    frontier = []
    # heap entries: (f_score, g_score, node, path)
    start_h = 0
    if goal_pos and BUILDING_POS.get(start_building):
        start_h = r_min * euclidean(BUILDING_POS[start_building], goal_pos)
    heapq.heappush(frontier, (start_h, 0, start_building, [start_building]))
    best_g = {start_building: 0}

    while frontier:
        f, g, current, path = heapq.heappop(frontier)
        if current == goal_building:
            return g, path
        # Skip if we have a better g already
        if g > best_g.get(current, float('inf')):
            continue
        for neighbor, edge_cost in BUILDING_GRAPH.get(current, {}).items():
            tentative_g = g + edge_cost
            if tentative_g < best_g.get(neighbor, float('inf')):
                best_g[neighbor] = tentative_g
                # heuristic for neighbor
                h = 0
                if goal_pos and BUILDING_POS.get(neighbor):
                    h = r_min * euclidean(BUILDING_POS[neighbor], goal_pos)
                heapq.heappush(frontier, (tentative_g + h, tentative_g, neighbor, path + [neighbor]))
    return float('inf'), []

# ============================================================
# TOTAL PATH COST (hierarchical composition)
# ============================================================
def total_path_cost(start, goal, rooms_info):
    """
    Returns (total_cost, description) where description is a dict with keys:
    - 'start_to_exit': room-level path from start to local exit (or full path in same-building case)
    - 'building_path': building-level path
    - 'exit_to_goal': room-level path from destination building exit to goal
    """
    if start == goal:
        return 0, {"start_to_exit": [start], "building_path": [], "exit_to_goal": []}

    info1 = rooms_info.get(start)
    info2 = rooms_info.get(goal)
    if not info1 or not info2:
        return float('inf'), None

    b1, b2 = info1["building"], info2["building"]
    buildings_in_rooms = {info["building"] for info in rooms_info.values()}
    room_graphs = {b: build_room_graph(b, rooms_info) for b in buildings_in_rooms}

    if b1 == b2:
        cost, room_path = shortest_room_path(start, goal, b1, rooms_info, room_graphs)
        if cost == float('inf'):
            return float('inf'), None
        return cost, {"start_to_exit": room_path, "building_path": [], "exit_to_goal": []}
    else:
        exit_start = get_building_exit(b1, rooms_info)
        exit_goal = get_building_exit(b2, rooms_info)
        if not exit_start or not exit_goal:
            return float('inf'), None

        cost1, start_to_exit = shortest_room_path(start, exit_start, b1, rooms_info, room_graphs)
        building_cost, building_path = a_star_buildings(b1, b2)
        cost3, exit_to_goal = shortest_room_path(exit_goal, goal, b2, rooms_info, room_graphs)

        if cost1 == float('inf') or building_cost == float('inf') or cost3 == float('inf'):
            return float('inf'), None

        total = cost1 + building_cost + cost3
        desc = {
            "start_to_exit": start_to_exit,
            "building_path": building_path,
            "exit_to_goal": exit_to_goal
        }
        return total, desc

# ============================================================
# BEST GOAL AMONG CANDIDATES
# ============================================================
def best_goal(start, goals, rooms_info):
    best = None
    best_cost = float('inf')
    best_desc = None
    for goal in goals:
        cost, desc = total_path_cost(start, goal, rooms_info)
        if cost < best_cost:
            best_cost = cost
            best = goal
            best_desc = desc
    return best, best_cost, best_desc

# ============================================================
# PATH FORMATTING
# ============================================================
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
    
    # Filter out empty parts
    parts = [p for p in parts if p and p != "[]"]
    return " → ".join(parts) if parts else "Direct path"

# ============================================================
# MAIN DEMO (without ML)
# ============================================================
if __name__ == "__main__":
    rooms_info = load_rooms()
    print(f"Loaded {len(rooms_info)} rooms.")
    connected = verify_graph_connected(BUILDING_GRAPH)
    print(f"Building graph connected: {connected}\n")

    start = "F-201"
    candidates = ["C-1", "D-2", "Lab-13", "A-4", "F-202", "F-301"]
    best, cost, desc = best_goal(start, candidates, rooms_info)
    if best:
        print(f"Start: {start}")
        print(f"Best goal: {best} (cost = {cost:.1f})")
        path_str = format_path(desc)
        print(f"Path: {path_str}")
    else:
        print("No reachable goal.")