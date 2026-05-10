# Refresher: `11_smart_navigator.py`
### Smart Campus Navigator — The Core ML Routing Engine

---

## TL;DR (30-second summary)
Script 11 is the "brain" connecting the A* algorithm (Script 5) with the Machine Learning model (Scripts 8/9).
It introduces the concept of **Smart Cost**, which artificially inflates the physical distance of a room if the ML model predicts it will be noisy or occupied. 

`Smart Cost = Pure Distance + ML Penalty`

---

## 1. The Pre-Computation Engine (`build_feature_extractors`)

To make predictions, the ML model needs 19 features (like `block_hour_occupancy_rate` and `room_popularity_bucket`). 
Calculating these on-the-fly for every single room, every time the user clicks a button, would make the app very slow.

**The Solution:**
When the Streamlit app boots up, it calls `build_feature_extractors(rooms_df, occupied_set)`.
This function sweeps through the entire dataset *once* and builds 4 high-speed lookup dictionaries:
1. `room_occupancy` (e.g., F-202 is occupied 60% of the time)
2. `block_hour_occupancy` (e.g., C-Block at 10:00 AM is 80% full)
3. `neighbor_hour_occupancy` (e.g., Rooms adjacent to F-202 are 90% full at 10:00 AM)
4. `quartile_thresholds` (Data-driven boundaries for defining popularity buckets 0, 1, 2, and 3)

These are passed around as a tuple called `extractors`.

---

## 2. Feature Assembly (`compute_room_features`)

When the engine evaluates a specific candidate room (e.g., `A-4`), it calls this function to construct the exact 19-feature dictionary the Random Forest expects.

It uses:
- The time the user selected (`hour`, `day_of_week`, `hour_sin`, `hour_cos`)
- Static rules (`floor`, `is_lab`, `is_special`)
- The high-speed lookup dictionaries from the `extractors` tuple (`room_overall_occupancy_rate`, `neighbor_hour_occupancy_rate`)

It then formats these precisely using `extract_feature_vector()` so the Random Forest model doesn't crash from a misaligned column.

---

## 3. The Core Innovation (`compute_occupancy_penalty`)

This is the most important mathematical concept in the project. How do we combine "steps walked" with "machine learning probability"?

```python
usability_prob = model.predict_proba(feature_vec)[0, 1] 
penalty        = penalty_scale * (1 - usability_prob)
```

**Variables:**
- `usability_prob`: The AI's confidence (0.0 to 1.0) that the room is FREE and QUIET. 
- `penalty_scale`: A slider in the app (default 50). Controls how much you hate walking into a busy room.

**How the math plays out:**
* **Scenario A (Guaranteed Empty):** `usability_prob = 0.99`.
  `Penalty = 50 * (1 - 0.99) = 0.5 steps`. (Virtually zero penalty, highly recommended).
* **Scenario B (Completely Packed):** `usability_prob = 0.05`.
  `Penalty = 50 * (1 - 0.05) = 47.5 steps`. (Massive penalty, telling A* to avoid this room unless it's literally next door).

---

## 4. The Final Showdown (`compare_routing`)

This function is called by the Streamlit app to generate the final Leaderboard. 

It takes a list of `candidate_rooms` and loops through them one by one:
1. Calls Script 5 (`total_path_cost`) to get the physical walking distance (`pure_cost`).
2. Calls `compute_occupancy_penalty()` to get the AI penalty.
3. Adds them together to get the `smart_cost`.

```python
results.append({
    'room':           candidate,
    'pure_cost':      pure_cost,            # e.g., 40.5 steps
    'occupancy_prob': usability_prob,       # e.g., 90%
    'penalty':        penalty,              # e.g., 5.0 steps
    'smart_cost':     pure_cost + penalty,  # e.g., 45.5 steps
})
```

It then returns the `pure_best` (the room with the lowest `pure_cost`) and the `smart_best` (the room with the lowest `smart_cost`), along with the full sorted list so Streamlit can find fallback alternatives.

---

## Why Script 11 is Built This Way
* **Modular:** It separates the math from the Streamlit UI. This means you could theoretically plug this engine into a Mobile App or Telegram bot without rewriting the routing logic.
* **Fast:** Precomputing the extractors allows it to evaluate 70+ rooms simultaneously in milliseconds. 
* **Tunable:** Passing `penalty_scale` as an argument allows the Streamlit app UI slider to dynamically update the A* behavior in real-time.
