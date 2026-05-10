# Refresher: `12_app.py`
### Smart Campus Navigator — Streamlit User Interface

---

## TL;DR (30-second summary)
Script 12 is the final culmination of the entire project. It takes the dataset (Script 7), the ML Model (Script 9), the A* Algorithm (Script 5), and the Routing Engine (Script 11) and wraps them all into a beautiful, interactive web application using **Streamlit**. 

It visually proves why the ML integration is valuable by forcing a side-by-side comparison between **Pure A*** and **Smart A***.

---

## 1. High-Performance Data Loading (`@st.cache`)

Loading the Graph, computing ML extractors, and parsing the Timetable CSV takes a few seconds. If the app did this every time you changed a slider, it would be unusably slow.

```python
@st.cache_data(show_spinner=False)
def load_timetable(): ...

@st.cache_resource(show_spinner="Loading campus data...")
def load_all_data(): ...
```

* `@st.cache_data`: Used for the timetable. If the CSV doesn't change, Streamlit memorizes the output.
* `@st.cache_resource`: Used for the ML Model and Feature Extractors. These are complex Python objects that Streamlit loads into RAM *once* and shares across all user interactions.

---

## 2. Timetable Integration ("Ground Truth")

The app deliberately separates the "AI Prediction" from the "Live Timetable". 

* **The AI** predicts if a room is usable/quiet based on historical data.
* **The Timetable** provides absolute Ground Truth on whether a class is running.

```python
def get_vacancy_duration(room, day_idx, start_hour, timetable):
```
This function looks ahead. If the app finds a free room at 14:00, it checks 15:00, 16:00, etc., until it hits an occupied slot. This allows the UI to display extremely helpful tags like: `✅ FREE (Until 16:00 (2 hrs))`.

---

## 3. The Comparison Logic

When you hit the "Find Best Room" button, the app branches into two separate logic flows.

### Flow 1: Pure A* (Distance Only)
1. It filters the candidate rooms using the live timetable to find *only* rooms that are currently `FREE`.
2. It runs standard A* on those vacant rooms.
3. It picks the one with the lowest `pure_cost` (closest distance).
* **The Flaw:** It guarantees the room is empty, but ignores ambient noise, floor levels, or crowding in that building.

### Flow 2: Smart A* (Distance + ML Prediction)
1. It passes **ALL** candidate rooms to the engine (Script 11).
2. The engine ranks them based on `smart_cost` (Distance + ML Penalty).
3. The app takes the #1 ranked room and checks the timetable:
   * **If FREE:** It displays it as the "Primary Recommendation".
   * **If OCCUPIED:** It displays a Warning card ("Top Pick is Occupied!"), drops down to the rest of the leaderboard, and finds the top 3 best ML-ranked rooms that *are* free.

---

## 4. The "Presets" Feature

Instead of making the user manually select 10 rooms every time, the app provides dropdown presets:
* **Entire Campus:** Evaluates all ~70 rooms.
* **Cross-Block Mix:** Evaluates 7 rooms deliberately scattered across different blocks to force the A* algorithm to calculate long, cross-campus walks.
* **Labs Only / Computing Block:** Thematic stress tests.

---

## 5. UI & Aesthetics

The app doesn't use standard Streamlit defaults. It injects a custom CSS `<style>` block to make it look like a premium SaaS dashboard:
* Uses the **Inter** font (standard in modern tech).
* Uses deep slate/indigo gradients for the header.
* Uses custom "Cards" with thick accent borders (Green for Success, Amber for Warning, Blue for Pure A*).
* Automatically adapts text colors (`#0f172a`) so it remains perfectly legible regardless of whether the user has Light Mode or Dark Mode enabled.
