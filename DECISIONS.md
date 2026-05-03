DECISIONS.md

This document explains design decisions and trade-offs made while building the Smart Campus Navigator. It is organized by pipeline stage and describes rationale, alternatives considered, and future extensions.

1. Data ingestion & canonical rooms

Goal
- Produce a canonical catalogue of rooms with `building`, `floor`, and `room_id` that is deterministic and auditable.

Decision
- Use rule-based parsing and deterministic heuristics to merge timetable sources (FSC + FSM). Implement `classify_room()` for mapping exceptional names and `extract_floor_number()` to infer floors from numeric patterns.

Rationale
- Deterministic rules are easy to inspect and correct when errors appear. Navigation correctness depends on an accurate room inventory; opaque ML-based extraction is riskier without substantial training data and labels.

Alternatives considered
- Train a small ML model to classify room types from text. Rejected due to limited labelled data and need for explainability.

Future improvements
- Add a small GUI to correct misclassified rooms; log corrections to improve any future ML model.

2. Spatial modelling

Goal
- Build a two-layer spatial model: a building-level macro graph for campus travel and per-building room graphs for intra-building navigation.

Decisions
- Building graph nodes are buildings; edges have hand-tuned walking costs.
- Room graphs: nodes are rooms; corridor edges connect numerically adjacent rooms on the same floor with cost=1. Stairs are configured explicitly in `STAIRS_CONFIG` with cost=5.

Rationale
- Corridor numeric adjacency is a practical heuristic that maps to real corridor layouts. Stairs cannot always be inferred from numbering, so we enumerate necessary stair edges in `STAIRS_CONFIG` to ensure path realism.

Alternatives
- Create a single global graph with all rooms + inter-building edges. This would be complete but much larger to search. Hierarchical approach reduces search complexity.

3. Heuristic design for A*

Goal
- Provide admissible and monotone heuristics for both building-level and room-level A* searches.

Decision
- Use Euclidean straight-line distances computed from layout positions, scaled by a conservative ratio r = min(edge_cost / euclidean(u,v)) across the relevant graph. Set h(x) = r * euclidean(pos(x), pos(goal)).

Proof sketch
- For any edge (u,v), cost(u,v) >= r * euclidean(u,v) by construction of r. For any path P to goal, path_cost(P) >= r * euclidean(start, goal). Thus h(start) <= true shortest path, making it admissible. Because the same scaling applies to all edges consistently, monotonicity also holds.

Trade-offs
- The heuristic underestimates true distances (conservative) but is far better than h=0 for pruning. If edge weights are highly inconsistent with Euclidean distances (e.g., very large shortcuts), r becomes small and heuristic benefit decreases.

4. Visualisation choices

Goal
- Produce easy-to-read, interactive diagrams that help validate graphs, stairs, and layout.

Decisions
- For room layout per building: group by floor (Y coordinate) and sort by numeric suffix for X coordinate. Use Plotly for interactive HTML outputs.

Rationale
- Sorted numeric order creates linear corridor representations that are visually intuitive. Plotly HTML files allow interactive inspection without additional tooling.

5. Testing & validation

Goal
- Ensure navigation correctness and stability across model adjustments.

Decisions
- Implement `scripts/test_navigator.py` with realistic scenarios and expected cost ranges. Re-run tests after any change to heuristics or cost model.

Rationale
- Tests help detect regressions introduced by heuristic changes, graph modifications, or config tuning.

6. Future work

- `scripts/recommender.py`: Combine occupancy forecasts with routing to produce top-k room recommendations given a start/time constraints.
- Dynamic weights: incorporate crowding or accessibility constraints into edge weights.
- CI: Add GitHub Actions to run `scripts/test_navigator.py` on push.

Appendix: Files touched

- `config.py`: central graph & layout.
- `scripts/hierarchical_navigator.py`: hierarchical A* + heuristics.
- `scripts/4_visualise_graph.py`: visualisations.
- `scripts/test_navigator.py`: tests.

If you'd like, I can expand any section with diagrams, mathematical proofs, or example outputs from the visualiser.