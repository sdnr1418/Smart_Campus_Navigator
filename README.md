# Smart Campus Navigator

Smart Campus Navigator is a compact, reproducible project that:

- Parses university timetables and extracts a canonical room inventory.
- Builds a two-layer spatial model (building-level + room-level).
- Visualises campus topology and room graphs (interactive HTML).
- Implements a hierarchical A* navigator with admissible, monotone heuristics.

This repository is an example of data engineering + algorithms + systems integration — a strong portfolio item to showcase in interviews.

## Repository structure

```
Smart_Campus_Navigator/
├── README.md                          # this file (high-level)
├── DECISIONS.md                       # detailed design & decision rationale (per-step)
├── config.py                          # shared graph + layout configuration
├── all_rooms.csv                      # extracted rooms (intermediate)
├── rooms_complete.csv                 # consolidated rooms (production input)
├── room_timetable.xlsx                # room-centric timetable (output)
├── room_availability_histogram.png    # visualisation output
├── University_Graph/                  # interactive HTML visualisations (output)
└── scripts/
    ├── 1_extract_rooms.py
    ├── 2_free_rooms_hourly_availability.py
    ├── 3_extract_occupancy_by_room.py
    ├── 4_visualise_graph.py
    ├── hierarchical_navigator.py
    └── test_navigator.py
```

## Quickstart

1. Install dependencies (example):

```bash
python -m pip install pandas networkx plotly matplotlib openpyxl joblib
```

2. Generate visualisations (saves into `University_Graph/`):

```bash
python scripts/4_visualise_graph.py
```

3. Run navigator demo and tests:

```bash
python scripts/hierarchical_navigator.py
python scripts/test_navigator.py
```

## Core concepts (short)

- Data ingestion: deterministic rule-based parsing extracts rooms and infers `building` and `floor` from names.
- Spatial model: two layers — building graph (macro) and room graphs (micro). Corridor edges connect adjacent room numbers, stairs are explicit.
- Navigation: hierarchical A* — room-level A* inside buildings, building-level A* between buildings. Heuristics are Euclidean distances scaled conservatively to guarantee admissibility & consistency.

## Configuration

All topology, edge weights, and layout positions live in `config.py`:
- `BUILDING_GRAPH`: inter-building weighted adjacency.
- `BUILDING_POS`: (x,y) positions for visualisation and heuristics.
- `STAIRS_CONFIG`: explicit (room1, room2) stair links per building.

## Design highlights (short)

- Heuristics: For each search (building-level or room-level) we compute r = min(edge_cost / euclidean(u,v)) across edges, then set h(x) = r * euclidean(pos(x), pos(goal)). This guarantees h <= true shortest-path cost (admissible) and preserves monotonicity.
- Room layout: rooms per floor are sorted by numeric suffix, X positions are proportional to index, Y positions map to floor — this makes straight-line heuristics spatially meaningful.

## Visuals

- Open `University_Graph/building_graph.html` and `University_Graph/room_graph_*.html` in a browser.
- The repo root contains `room_availability_histogram.png` showing hourly free-room distribution.

## Next steps (recommended)

- Add `scripts/recommender.py` to combine occupancy predictions with routing for top-k recommendations.
- Add CI with GitHub Actions to run `scripts/test_navigator.py` on push.
- Convert `config.py` into a small YAML or JSON if you want non-Python editing of layout/weights.

## Contact / Notes

If you want a compact interview one-pager summarising technical decisions, I can add `README_SAMPLE.md`. The repository already includes `DECISIONS.md` with step-by-step rationale.

---
If you'd like, I can also:
- Add a `requirements.txt` and `setup` instructions.
- Add a short `README_SAMPLE.md` with one-page talking points for interviewing.
- Implement `scripts/recommender.py` and a simple CLI or Flask API.

If you want any changes to tone/length or to include inline static PNG thumbnails for the room graphs, tell me which images to embed and I will add them to the repo and update this README.
