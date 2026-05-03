# 🏫 Smart Campus Navigator
### Graph-Based Hierarchical Pathfinding for FAST-NUCES Campus

> Navigate from any room to any other room across the FAST-NUCES campus using a two-layer A\* search — room-level corridors inside buildings, building-level graph between them.

---

## 📌 What Does This Project Do?

Imagine you're a student standing in **Room F-201** (F-Block, 2nd floor) and you need to get to **Room C-9** (C-Block, Computing). How do you find the shortest path — factoring in corridors, staircases, and cross-building walking distances?

**Smart Campus Navigator** solves exactly this problem. It:

1. **Reads real university timetables** (FSC + FSM Spring 2026) to build a canonical catalogue of every room on campus.
2. **Builds a spatial graph** — one graph per building (rooms as nodes, corridors and stairs as edges) and one campus-wide graph (buildings as nodes).
3. **Runs hierarchical A\*** — finds the shortest intra-building path, then the shortest inter-building path, and stitches them together.
4. **Analyses room occupancy** — tells you which rooms are free at which hours, across all 6 days of the week.
5. **Generates interactive HTML visualisations** for every building and the campus graph.

---

## 🗂️ Repository Structure

```
Smart_Campus_Navigator/
├── README.md                          ← You are here
├── DECISIONS.md                       ← Step-by-step design rationale (beginner-friendly)
├── config.py                          ← Campus topology (graph edges, positions, stairs)
│
├── all_rooms.csv                      ← Intermediate: rooms extracted from timetables
├── rooms_complete.csv                 ← Final: production room inventory
├── room_timetable.xlsx                ← Room-centric timetable output
├── room_availability_histogram.png    ← Free-room counts by hour (Mon–Sat)
│
├── TimeTables/                        ← Source timetable Excel files (FSC + FSM)
│
├── Uni_diagrams/                      ← Static PNG snapshots of each building graph
│   ├── FAST_NUCES_CAMPUS_BUILDING_GRAPH.png
│   ├── C_Block.png
│   ├── D_Block.png
│   ├── E_Block.png
│   ├── F_Block.png
│   └── L_Block.png
│
├── University_Graph/                  ← Interactive HTML graph visualisations (output)
│   ├── building_graph.html
│   ├── room_graph_C-Block_(Computing).html
│   ├── room_graph_D-Block_(Electrical_Management).html
│   ├── room_graph_E-Block_(Library).html
│   ├── room_graph_F-Block_(New_Building).html
│   ├── room_graph_L-Block_(Labs).html
│   └── room_graph_A-Block_(Admin).html
│
└── scripts/
    ├── 1_extract_rooms.py             ← Parse timetables → rooms_complete.csv
    ├── 2_free_rooms_hourly_availability.py  ← Occupancy analysis + histogram
    ├── 3_extract_occupancy_by_room.py ← Per-room occupancy breakdown
    ├── 4_visualise_graph.py           ← Generate interactive HTML graphs
    ├── hierarchical_navigator.py      ← Core A* pathfinding engine
    └── test_navigator.py              ← Automated correctness tests
```

---

## 🚀 Quickstart

### 1. Install Dependencies

```bash
pip install pandas networkx plotly matplotlib openpyxl joblib
```

### 2. Run the Full Pipeline (in order)

```bash
# Step 1: Extract rooms from timetables → produces rooms_complete.csv
python scripts/1_extract_rooms.py

# Step 2: Analyse room occupancy → produces room_availability_histogram.png
python scripts/2_free_rooms_hourly_availability.py

# Step 3: Extract per-room occupancy breakdown
python scripts/3_extract_occupancy_by_room.py

# Step 4: Build interactive HTML visualisations → saved into University_Graph/
python scripts/4_visualise_graph.py

# Step 5: Run the navigator demo (finds best path from F-201 to multiple candidates)
python scripts/hierarchical_navigator.py

# Step 6: Run automated tests to verify path costs
python scripts/test_navigator.py
```

### 3. Open the Interactive Campus Maps

```bash
# Open in your browser:
University_Graph/building_graph.html          ← Campus-wide building graph
University_Graph/room_graph_C-Block_*.html    ← C-Block room layout
University_Graph/room_graph_F-Block_*.html    ← F-Block room layout
# ... and so on for each building
```

---

## 🏛️ Campus Overview — The Building Graph

The campus consists of **7 buildings** connected by walking paths with hand-tuned travel costs. The building graph is the "macro layer" of navigation — it tells you which buildings to pass through when travelling between two distant rooms.

![FAST Campus Building Graph](Uni_diagrams/FAST_NUCES_CAMPUS_BUILDING_GRAPH.png)

**Buildings and their primary use:**

| Building | Abbreviation | Primary Use |
|---|---|---|
| A-Block | Admin | Administration |
| B-Block | Civil | Civil Engineering (no timetabled rooms) |
| C-Block | Computing | CS, SE, DS, AI, CY departments |
| D-Block | Electrical/Mgmt | Electrical Eng + Management |
| E-Block | Library | Library + Embedded/Eng Labs |
| F-Block | New Building | New classrooms (2nd & 3rd floor) |
| L-Block | Labs | Computer Labs (Lab-1 to Lab-18) |

**Edge costs** represent estimated walking time between building exits (scale: 10 = ~1 minute of walking).

---

## 🗺️ Room-Level Graphs — Inside Each Building

Each building has its own **room graph**. Rooms on the same floor are connected by **corridor edges (cost = 1)**. Staircases between floors are **explicit edges (cost = 5)**.

### C-Block (Computing)

10 rooms on Floor 1 (C-1 through C-9 + Old Audi) and 7 rooms on Floor 2 (C-10 through C-16), connected by two staircase links.

![C-Block Room Graph](Uni_diagrams/C_Block.png)

### D-Block (Electrical / Management)

10 rooms on Floor 1 (CRMG, Micro Lab, Physics Lab, S. Hall, Seminar Hall, D-1 through D-5) and 7 rooms on Floor 2 (D-11 through D-17), with two staircase links.

![D-Block Room Graph](Uni_diagrams/D_Block.png)

### F-Block (New Building)

F-Block is special — its **ground floor is Floor 2** (F-201 through F-210). Floor 3 (F-301 through F-312) is above it. Two staircase links connect them.

![F-Block Room Graph](Uni_diagrams/F_Block.png)

### L-Block (Labs)

Labs are spread across Floor 1 (Lab-1 through Lab-8) and Floor 2 (Lab-13 through Lab-18), with two staircase connections.

![L-Block Room Graph](Uni_diagrams/L_Block.png)

---

## 🧭 How Navigation Works — Step by Step

### The Two-Layer (Hierarchical) Approach

Rather than building one giant graph with every room from every building, the navigator uses a **hierarchical strategy** that mirrors how a human would naturally navigate campus:

```
Step 1: Find the shortest path from START ROOM → START BUILDING EXIT
        (room-level A* inside the source building)

Step 2: Find the shortest building-to-building path
        (building-level A* on the campus graph)

Step 3: Find the shortest path from DESTINATION EXIT → GOAL ROOM
        (room-level A* inside the destination building)

Total Cost = Step 1 + Step 2 + Step 3
```

### Example: F-201 → C-9

```
[Start]  F-201 (F-Block, floor 2)
         ↓ corridor chain to F-201 (already exit, cost 0)
[Inter]  F-Block → D-Block → C-Block  (cost: 10 + 10 = 20)
         ↓ enter C-Block at exit C-1
[End]    C-1 → C-2 → C-3 → ... → C-9  (corridor chain, cost 8)

Total ≈ 0 + 20 + 8 = 28
```

### A\* Heuristic — Why It's Admissible

Standard Dijkstra explores every node. A\* uses a **heuristic** estimate of remaining distance to skip unlikely paths. For this to work correctly, the heuristic must never *overestimate* the true remaining cost — this property is called **admissibility**.

The heuristic used here:

```
h(node) = r_min × euclidean_distance(node, goal)

where r_min = min over all edges of (edge_cost / euclidean_length)
```

This guarantees that `h(node) ≤ true shortest path cost`, because every real path must pay at least `r_min` per unit of Euclidean distance travelled. See `DECISIONS.md` for a full proof.

---

## 📊 Room Occupancy Analysis

Script `2_free_rooms_hourly_availability.py` merges timetable data from both the FSC (Computing) and FSM (Management) departments and counts how many rooms are **free** at each hour of each day.

![Room Availability Histogram](room_availability_histogram.png)

**Key observations from the histogram:**
- **Peak congestion** (fewest free rooms) is typically around **10:00–11:00** on weekdays, when the most classes run simultaneously.
- **Quietest period** on weekdays is usually **08:00** and **17:00–20:00**.
- **Saturday** is almost entirely free (avg ~78 free rooms out of 79), confirming minimal Saturday scheduling.
- **Friday** has more free rooms on average (~69.5) compared to Mon–Thu (~54).

This analysis directly feeds a future **room recommender** feature: given a start location and time, the system could suggest the nearest free room.

---

## ⚙️ Configuration — `config.py`

All campus topology is centralised in `config.py`. You never need to modify the navigator or visualiser scripts to change the campus layout — only `config.py`.

```python
# Inter-building travel costs (undirected)
BUILDING_GRAPH = {
    "F-Block (New Building)": {"L-Block (Labs)": 10, "D-Block (Electrical/Management)": 15, ...},
    ...
}

# (x, y) positions for visualisation and heuristic computation
BUILDING_POS = {
    "F-Block (New Building)": (400, 100),
    ...
}

# Explicit staircase connections per building: (room_on_floor_A, room_on_floor_B)
STAIRS_CONFIG = {
    "F-Block (New Building)": [("F-201", "F-301"), ("F-210", "F-312")],
    "C-Block (Computing)":    [("C-1", "C-10"),   ("C-9", "C-16")],
    ...
}
```

---

## 🧪 Testing

`scripts/test_navigator.py` runs 11 automated test scenarios covering:
- Same floor, same building (corridor-only path)
- Different floors, same building (requires staircase)
- Cross-building paths (F→D, F→D→C, F→D→A, F→L)
- Edge cases (building with no timetabled rooms)

```bash
python scripts/test_navigator.py
```

Expected output:

```
Loaded 79 rooms

Test: F-201 → F-202
  Same floor, same building (cost 1)
  Cost: 1.0
  ✅ PASSED (cost within (0, 2))

Test: F-201 → F-301
  Different floor, same building (cost 5)
  Cost: 5.0
  ✅ PASSED (cost within (4, 6))

...
RESULTS: 11 passed, 0 failed
```

---

## 🔮 Next Steps

| Feature | Description |
|---|---|
| `scripts/recommender.py` | Given a start room + current time, return the top-k nearest *free* rooms |
| Dynamic edge weights | Incorporate crowding or accessibility constraints into graph edges |
| CI pipeline | GitHub Actions to run `test_navigator.py` on every push |
| YAML config | Replace `config.py` with a YAML file for non-Python editing of topology |
| Web / CLI interface | Interactive query tool: enter start + goal, get step-by-step directions |

---

## 📄 Further Reading

- **`DECISIONS.md`** — Detailed, beginner-friendly explanation of every design decision made in this project: why rule-based parsing, how the heuristic is proven admissible, why a two-layer graph instead of one flat graph, and more.

---

*FAST-NUCES Karachi Campus — Spring 2026*
