# DECISIONS.md — Smart Campus Navigator

> **Who is this document for?**
> This document is written for someone who is new to software engineering or algorithms. Every decision is explained from first principles — not just *what* was decided, but *why*, with plain-English reasoning before any technical detail.

---

## Table of Contents

1. [Decision 1 — How We Extract Rooms from Timetables](#1-data-ingestion--room-extraction)
2. [Decision 2 — How We Model the Campus Spatially](#2-spatial-modelling--the-two-layer-graph)
3. [Decision 3 — How A\* Search Works and Why the Heuristic is Safe](#3-heuristic-design-for-a-search)
4. [Decision 4 — Why a Hierarchical (Two-Layer) Navigator](#4-hierarchical-navigation--why-not-one-flat-graph)
5. [Decision 5 — How Visualisations Are Built](#5-visualisation-choices)
6. [Decision 6 — How We Test Correctness](#6-testing--validation)
7. [Appendix — Files and Their Roles](#appendix-files-and-their-roles)

---

## 1. Data Ingestion & Room Extraction

**Script:** `scripts/1_extract_rooms.py`  
**Output:** `all_rooms.csv` → `rooms_complete.csv`

---

### What problem are we solving?

Before the navigator can find paths, it needs to know *which rooms exist* on campus and *which building and floor* each room belongs to.

We have two Excel timetable files as our source of truth:
- **FSC timetable** — for Computing departments (CS, SE, DS, AI, CY)
- **FSM timetable** — for Management departments

The problem: these timetables are designed for *scheduling classes*, not for spatial navigation. Room names appear as strings like `"F-201"`, `"Lab-13"`, `"Seminar Hall"`, scattered across many cells, columns, and sheets.

---

### What did we decide?

We use **deterministic, rule-based parsing** to:
1. Find the cells that contain room names (filtering out times, days, headers, etc.)
2. Map each room name to its building using a letter-based convention (e.g. `F-XXX` → F-Block, `Lab-XX` → L-Block)
3. Infer the floor number from the room number (e.g. `F-201` → floor 2, `F-301` → floor 3)

Key functions:
- `classify_room(room_name)` — maps a room name string to its building block
- `extract_floor_number(room_name)` — infers the floor from the numeric part of the name

---

### Why rule-based instead of machine learning?

A beginner might wonder: why not train a model to classify rooms automatically?

**Answer:** We don't need to. The naming convention at FAST-NUCES is **consistent and structured**:

| Room Name Pattern | Building | Floor Rule |
|---|---|---|
| `C-1` to `C-9` | C-Block | Floor 1 (number < 10) |
| `C-10` to `C-16` | C-Block | Floor 2 (number ≥ 10) |
| `F-201` to `F-210` | F-Block | Floor 2 (number 200–299) |
| `F-301` to `F-312` | F-Block | Floor 3 (number 300–399) |
| `Lab-1` to `Lab-12` | L-Block | Floor 1 |
| `Lab-13` to `Lab-18` | L-Block | Floor 2 |
| `Seminar Hall` | D-Block | Floor 1 (hardcoded exception) |

Rules are **transparent** — if a room is misclassified, you can immediately see why and fix the rule. A machine-learning model would be a black box that's hard to debug, and we have no training labels anyway.

**Special cases** like `"Seminar Hall"`, `"Old Audi"`, `"CRMG"` are handled by explicit `if/elif` branches in `classify_room()` — simple and auditable.

---

### What alternatives were considered?

- **PDF parsing:** The university also publishes PDFs. We chose Excel because the structure is more machine-readable (cells, not free text).
- **Manual curation:** We could hand-type every room. Rejected because it doesn't scale and introduces human error.
- **ML classification:** Rejected. Naming patterns are deterministic; ML adds complexity without benefit.

---

### What could be improved in the future?

- Add a small GUI that lets an administrator flag a "misclassified room" and log the correction. Over time, these corrections could train a future ML model if the naming convention ever becomes inconsistent.
- Validate against a physical room list provided by the university registrar.

---

## 2. Spatial Modelling — The Two-Layer Graph

**Script:** `scripts/4_visualise_graph.py`, `scripts/hierarchical_navigator.py`  
**Config:** `config.py`

---

### What problem are we solving?

We need a data structure that represents *where rooms are* and *how you move between them*. This is fundamentally a **graph problem**: nodes are locations, edges are paths between them, and edge weights represent the cost (time/effort) of travelling that path.

But the campus is large — 7 buildings, ~79 rooms. If we put every room into one single graph with edges connecting all buildings, the graph becomes huge, redundant, and slow to search.

---

### What did we decide?

We build **two separate layers of graphs**:

#### Layer 1 — Building Graph (Macro)

One node per building. Edges connect buildings that have a direct walking path between them, with **hand-tuned integer weights** representing relative walking time.

```
Buildings (nodes): A-Block, B-Block, C-Block, D-Block, E-Block, F-Block, L-Block
Edges (sample):    F-Block ↔ L-Block  (cost 10)
                   F-Block ↔ D-Block  (cost 15)
                   D-Block ↔ C-Block  (cost 10)
```

This graph is defined in `config.py` as `BUILDING_GRAPH` and visualised below:

![FAST Campus Building Graph](Uni_diagrams/FAST_NUCES_CAMPUS_BUILDING_GRAPH.png)

#### Layer 2 — Room Graphs (Micro, one per building)

Inside each building, one node per room. Two types of edges:

| Edge Type | Connects | Cost |
|---|---|---|
| **Corridor** | Adjacent rooms on the same floor (sorted by room number) | 1 |
| **Staircase** | A room on one floor to a specific room on another floor | 5 |

The idea behind corridor edges: rooms are numbered sequentially along a corridor. `C-1, C-2, C-3 ...` are physically next to each other, so connecting them by numeric adjacency is a good approximation of reality.

Below are the room graphs for each building:

**C-Block (Computing)** — Floor 1: Old Audi, C-1 through C-9. Floor 2: C-10 through C-16.
![C-Block Room Graph](Uni_diagrams/C_Block.png)

**D-Block (Electrical/Management)** — Floor 1: CRMG, Micro Lab, Physics Lab, S. Hall, Seminar Hall, D-1 through D-5. Floor 2: D-11 through D-17.
![D-Block Room Graph](Uni_diagrams/D_Block.png)

**F-Block (New Building)** — Floor 2: F-201 through F-210. Floor 3: F-301 through F-312. (Note: F-Block has no floor 1.)
![F-Block Room Graph](Uni_diagrams/F_Block.png)

**L-Block (Labs)** — Floor 1: Lab-1 through Lab-8. Floor 2: Lab-13 through Lab-18.
![L-Block Room Graph](Uni_diagrams/L_Block.png)

---

### Why are stairs explicit instead of inferred?

A beginner might ask: "Can't you infer stairs the same way you infer corridors?"

**Answer:** No. Corridor adjacency works because rooms along a corridor are numbered consecutively — `D-1, D-2, D-3` really are next to each other. But staircases connect rooms on *different floors*, and there is no reliable naming rule for which rooms happen to be next to a staircase.

For example, in F-Block, the two staircases connect `F-201↔F-301` and `F-210↔F-312`. There is no pattern in those numbers that would let you infer staircase connections automatically. So we enumerate them explicitly in `STAIRS_CONFIG`:

```python
STAIRS_CONFIG = {
    "F-Block (New Building)": [("F-201", "F-301"), ("F-210", "F-312")],
    "C-Block (Computing)":    [("C-1", "C-10"),   ("C-9", "C-16")],
    "D-Block (Electrical/Management)": [("D-1", "D-11"), ("D-5", "D-17")],
    "L-Block (Labs)":         [("Lab-1", "Lab-13"), ("Lab-8", "Lab-18")],
}
```

This is a small, auditable list that can be updated if the physical layout changes.

---

### What alternatives were considered?

- **One flat global graph:** Put all rooms from all buildings into a single graph, with long edges between buildings. This would work but makes the graph much larger (O(n²) edges in the worst case) and loses the natural building-level abstraction. A* on a large flat graph would also be slower.
- **Real GPS coordinates:** We could use actual latitude/longitude for nodes. This would improve heuristic accuracy but requires surveying the campus or using maps APIs. The current approach uses relative (x, y) positions that are "good enough" for heuristic computation and visualisation.

---

## 3. Heuristic Design for A\* Search

**Script:** `scripts/hierarchical_navigator.py` (functions `compute_building_scaling`, `compute_room_scaling`)

---

### What is A\* and why does it need a heuristic?

**Dijkstra's algorithm** finds the shortest path by exploring every reachable node in order of increasing cost. It always finds the correct answer but can be slow because it explores in all directions equally.

**A\*** speeds this up by using a **heuristic function** `h(node)` that estimates how far away the goal is from any given node. A\* prioritises nodes that appear "closer" to the goal, so it explores fewer nodes overall.

The critical requirement: the heuristic must **never overestimate** the true remaining cost. If `h(node)` is too high, A\* might skip the real shortest path. This property is called **admissibility**.

---

### What heuristic did we choose?

We use **Euclidean (straight-line) distance**, scaled by a conservative factor `r_min`:

```
h(node) = r_min × euclidean_distance(pos(node), pos(goal))
```

Where:
```
r_min = minimum over all edges of (edge_cost / euclidean_distance(u, v))
```

In plain English: `r_min` is the smallest "cost per unit of Euclidean distance" observed across all edges in the graph. It represents the best-case movement efficiency.

---

### Proof that this heuristic is admissible (beginner-friendly)

Let's say you're at node `X` and the goal is `G`.

- Any path from `X` to `G` must travel at least `euclidean_distance(X, G)` units of Euclidean distance (because a straight line is the shortest possible path).
- Every unit of Euclidean distance costs *at least* `r_min` in graph cost (by definition of `r_min`).
- Therefore, any path from `X` to `G` costs *at least* `r_min × euclidean_distance(X, G)`.
- Our heuristic `h(X) = r_min × euclidean_distance(X, G)` equals exactly that lower bound.
- So `h(X) ≤ true shortest path cost` — the heuristic never overestimates. ✅

This is computed separately for the **building graph** (using `compute_building_scaling()`) and for each **room graph** (using `compute_room_scaling()`), because the two graphs have very different edge weights.

---

### Why not use `h = 0`?

`h = 0` is always admissible (it never overestimates) and would turn A\* into plain Dijkstra. This is correct but slow — it explores every node equally. Our Euclidean heuristic prunes away nodes that are geometrically far from the goal, making the search faster.

---

### Why not use Manhattan distance?

Manhattan distance (`|x1-x2| + |y1-y2|`) is another common heuristic. It's admissible in grid graphs where movement is only horizontal/vertical. In our graph, edges can connect rooms at arbitrary angles, so Euclidean distance is more accurate.

---

### Trade-off

The more `r_min` underestimates the real movement efficiency, the less the heuristic helps. If some edges are very cheap relative to their Euclidean length, `r_min` becomes small and the heuristic barely prunes anything. In practice, our campus graph is well-behaved and the heuristic provides meaningful guidance.

---

## 4. Hierarchical Navigation — Why Not One Flat Graph?

**Script:** `scripts/hierarchical_navigator.py` (function `total_path_cost`)

---

### The flat-graph alternative

A simpler approach: put every room as a node in one giant graph. Add corridor edges within buildings (cost 1), stair edges within buildings (cost 5), and long "walking" edges between buildings (cost 10–20). Then run A\* on this single graph.

**This would work** — and it might even give more optimal paths in edge cases. So why don't we do it?

---

### Why we chose hierarchical decomposition

**1. Separation of concerns.** Campus-level routing (which buildings to pass through) is a different problem from room-level routing (which corridor to walk down). Keeping them separate makes each part easier to reason about, debug, and modify independently.

**2. Scalability.** If the campus grows (more buildings, more rooms), the flat graph grows quadratically because inter-building edges multiply. The two-layer approach grows linearly.

**3. Clarity of output.** The hierarchical structure produces a naturally readable path description:

```
F-201 → F-201 (exit)
[F-Block → D-Block → C-Block]
C-1 → C-2 → ... → C-9
```

A flat graph would produce a single flat list of nodes that is harder to interpret.

**4. Real-world validity.** People actually navigate this way — first decide which building to go to, then figure out how to get to the specific room inside.

---

### How the composition works

The function `total_path_cost(start, goal, rooms_info)` does the following:

**Case 1: Same building**
```python
cost, path = shortest_room_path(start, goal, building, ...)
```
Just run room-level A\* directly. No inter-building travel needed.

**Case 2: Different buildings**
```python
exit_start = get_building_exit(source_building)    # lowest-numbered room on ground floor
exit_goal  = get_building_exit(dest_building)

cost1, path1 = shortest_room_path(start, exit_start, ...)     # inside source building
cost2, path2 = a_star_buildings(source_building, dest_building) # between buildings
cost3, path3 = shortest_room_path(exit_goal, goal, ...)        # inside dest building

total = cost1 + cost2 + cost3
```

**Building exit:** Defined as the lowest-numbered room on the ground floor (floor 1 for most buildings, floor 2 for F-Block which has no floor 1). This is a practical heuristic — the smallest room number is typically closest to the building entrance.

---

### Known limitation

The hierarchical approach may occasionally miss a globally optimal path. For example, if two buildings share a back-corridor shortcut that bypasses the canonical "exit room", the navigator would not discover it. In the current campus layout, this is not a problem because the campus graph is based on actual walking paths between the main building exits.

---

## 5. Visualisation Choices

**Script:** `scripts/4_visualise_graph.py`  
**Output:** `University_Graph/*.html`

---

### What problem are we solving?

After building the graphs, we need a way to **verify** that they are correct:
- Are all rooms connected on the right floors?
- Do staircase edges connect the right rooms?
- Do building edges look spatially reasonable?

A printed list of edges is hard to inspect by eye. A visual graph makes errors obvious immediately.

---

### What did we decide?

We use **Plotly** to generate interactive HTML files — one for the campus building graph and one per building for room graphs.

**Room layout algorithm:**
1. Group rooms by floor.
2. Within each floor, sort rooms by their numeric suffix (`C-1, C-2, C-3 ...`).
3. Assign X positions proportionally (left to right = ascending room number).
4. Assign Y positions by floor (each floor is at a fixed Y offset: floor 1 at y=50, floor 2 at y=200, floor 3 at y=350).

This produces a **linear corridor representation** — rooms on the same floor appear as a horizontal line, stairs appear as diagonal lines connecting floors.

---

### Why Plotly instead of matplotlib or a static image?

| Tool | Interactive? | Zoom/pan? | Hover info? | Easy to share? |
|---|---|---|---|---|
| matplotlib (static PNG) | ❌ | ❌ | ❌ | ✅ |
| Plotly (interactive HTML) | ✅ | ✅ | ✅ | ✅ (open in browser) |
| networkx + matplotlib | ❌ | ❌ | ❌ | ✅ |

Plotly HTML files can be opened in any browser without installing anything extra. Hover tooltips show edge costs and types (`corridor` / `stairs`), which is essential for validation.

---

### Why sorted numeric order for room layout?

Sorting rooms by numeric suffix (`C-1, C-2, ..., C-9`) creates a layout where adjacent rooms in the graph are also visually adjacent on screen. This makes corridor edges appear as short horizontal connections — intuitive and easy to verify.

If rooms were placed in arbitrary order, corridor edges would criss-cross the diagram and look chaotic.

---

## 6. Testing & Validation

**Script:** `scripts/test_navigator.py`

---

### Why do we test?

Every time you change the graph (add a staircase, adjust an edge weight, fix a room classification), there is a risk of breaking navigation paths that previously worked. This is called a **regression**.

Automated tests catch regressions immediately. Without tests, you would need to manually re-verify navigation every time you make a change — tedious and error-prone.

---

### What do the tests cover?

The test file defines 11 scenarios with **expected cost ranges** (not exact values, to allow minor implementation adjustments):

| Test | Expected Cost Range | What it validates |
|---|---|---|
| `F-201 → F-202` | 0–2 | Adjacent rooms on same floor (pure corridor, cost 1) |
| `F-201 → F-301` | 4–6 | Single staircase hop (cost 5) |
| `F-201 → F-303` | 6–8 | Staircase + short corridor |
| `F-311 → F-201` | 14–16 | Long reverse corridor + stairs |
| `F-201 → D-2` | 20–22 | Cross-building (F→D), one building hop |
| `F-201 → C-1` | 24–28 | Cross-building (F→D→C), two hops |
| `F-201 → A-4` | 28–32 | Cross-building (F→D→A), two hops |
| `F-201 → Lab-13` | 15–30 | Cross-building (F→L), one hop |
| `C-1 → C-15` | 9–11 | Long corridor chain within C-Block |
| `D-2 → D-11` | 4–6 | Staircase between floors in D-Block |
| `A-4 → B-Block` | No path | B-Block has no timetabled rooms |

---

### Why cost ranges instead of exact values?

The exact cost depends on which specific corridor path is chosen and which exit room is selected. Small changes in the staircase configuration or room order can shift costs by 1–2 units without the path being "wrong". Ranges make tests robust to these minor variations while still catching real errors.

---

### How to run

```bash
cd scripts
python test_navigator.py
```

Expected output: `RESULTS: 11 passed, 0 failed`

If any test fails, the output shows the actual cost alongside the expected range, making it easy to diagnose what changed.

---

## Appendix: Files and Their Roles

| File | What it does |
|---|---|
| `config.py` | Defines `BUILDING_GRAPH`, `BUILDING_POS`, `STAIRS_CONFIG` — the central campus topology |
| `scripts/1_extract_rooms.py` | Parses FSC and FSM timetable Excel files → produces `all_rooms.csv` |
| `scripts/2_free_rooms_hourly_availability.py` | Merges timetable occupancy data, counts free rooms by hour/day → produces `room_availability_histogram.png` |
| `scripts/3_extract_occupancy_by_room.py` | Breaks down occupancy on a per-room basis |
| `scripts/4_visualise_graph.py` | Builds NetworkX graphs, renders interactive Plotly HTML → `University_Graph/` |
| `scripts/hierarchical_navigator.py` | Core pathfinding engine: room graph builder, A\* implementations, hierarchical path composer |
| `scripts/test_navigator.py` | Automated test suite with expected cost ranges |
| `all_rooms.csv` | Intermediate output: all rooms from both timetables, with building and floor labels |
| `rooms_complete.csv` | Final room inventory used by the navigator and visualiser |
| `room_availability_histogram.png` | Visual output of free-room analysis |
| `University_Graph/*.html` | Interactive Plotly campus maps |
| `Uni_diagrams/*.png` | Static PNG snapshots of the graphs (for README and documentation) |

---

*For the high-level overview, see `README.md`. This document focuses on the reasoning behind each decision.*