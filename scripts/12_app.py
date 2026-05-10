"""
Smart Campus Navigator - Streamlit App
=======================================
Interactive web UI comparing Pure A* vs Smart A* (ML-integrated) routing.
Features a streamlined UX based on user priorities.

Usage:
  streamlit run scripts/12_app.py
"""

import streamlit as st
import pandas as pd
import pickle
import os
import sys
import importlib.util
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SCRIPT_DIR)

# Import Script 11 engine
spec = importlib.util.spec_from_file_location(
    "smart_nav", os.path.join(SCRIPT_DIR, "11_smart_navigator.py")
)
smart_nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smart_nav)

load_rooms               = smart_nav.load_rooms
build_feature_extractors = smart_nav.build_feature_extractors
compare_routing          = smart_nav.compare_routing

MODEL_PKL      = os.path.join(PROJECT_ROOT, "Models", "room_usability_model_tuned_rf.pkl")
BASE_MODEL_PKL  = os.path.join(PROJECT_ROOT, "Models", "room_usability_model.pkl")
DATASET_CSV    = os.path.join(PROJECT_ROOT, "Data", "room_usability_dataset.csv")
ROOMS_CSV      = os.path.join(PROJECT_ROOT, "Data", "raw", "all_rooms.csv")
TIMETABLE_CSV  = os.path.join(PROJECT_ROOT, "Data", "raw", "room_timetable.csv")

FEATURE_COLS = [
    "day_of_week", "hour", "hour_sin", "hour_cos",
    "floor", "is_lab", "is_special",
    "room_overall_occupancy_rate", "block_hour_occupancy_rate",
    "neighbor_hour_occupancy_rate", "is_weekday", "room_popularity_bucket",
    "block_A", "block_B", "block_C", "block_D",
    "block_E", "block_F", "block_L",
]
TARGET_COL = "usable"

DAY_PREFIXES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# ============================================================
# PAGE CONFIG & CSS
# ============================================================
st.set_page_config(page_title="Smart Campus Navigator", page_icon="🏫", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc; 
        padding: 2.5rem 2rem; 
        border-radius: 12px;
        margin-bottom: 2rem; 
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid #334155;
    }
    .main-header h1 {
        color: #ffffff;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        letter-spacing: -0.025em;
    }
    .main-header p {
        color: #94a3b8;
        font-size: 1.1rem;
        font-weight: 400;
    }
    .card-success {
        background: #ffffff; 
        color: #0f172a;
        border-left: 6px solid #10b981;
        padding: 1.5rem; 
        border-radius: 10px; 
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
    }
    .card-warning {
        background: #ffffff; 
        color: #0f172a;
        border-left: 6px solid #f59e0b;
        padding: 1.5rem; 
        border-radius: 10px; 
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
    }
    .card-pure {
        background: #ffffff; 
        color: #0f172a;
        border-left: 6px solid #3b82f6;
        padding: 1.5rem; 
        border-radius: 10px; 
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
    }
    .badge-free { 
        background: #d1fae5; 
        color: #065f46; 
        padding: 4px 12px; 
        border-radius: 9999px; 
        font-size: 0.875rem;
        font-weight: 600; 
        display: inline-block;
        border: 1px solid #34d399;
    }
    .badge-occupied { 
        background: #fee2e2; 
        color: #991b1b; 
        padding: 4px 12px; 
        border-radius: 9999px; 
        font-size: 0.875rem;
        font-weight: 600; 
        display: inline-block;
        border: 1px solid #f87171;
    }
    .metric-label { 
        font-size: 0.875rem; 
        color: #64748b; 
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 4px; 
    }
    .metric-value { 
        font-size: 1.8rem; 
        font-weight: 700; 
        color: #0f172a; 
    }
    .alt-room { 
        padding: 1rem; 
        background: #f8fafc; 
        color: #0f172a;
        border-radius: 8px; 
        margin: 0.5rem 0; 
        border: 1px solid #e2e8f0;
        transition: all 0.2s ease;
    }
    .alt-room:hover {
        background: #ffffff;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-color: #cbd5e1;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏫 Smart Campus Navigator</h1>
    <p style="margin:0;opacity:0.9;">AI-Powered Room Recommendations</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# TIMETABLE & DATA LOADING
# ============================================================
@st.cache_data(show_spinner=False)
def load_timetable():
    df = pd.read_csv(TIMETABLE_CSV)
    df.set_index("Room", inplace=True)
    timetable = {}
    for col in df.columns:
        try:
            day_str, time_str = col.split("_")
            hour = int(time_str.split(":")[0])
            day_idx = DAY_PREFIXES.index(day_str)
        except (ValueError, IndexError):
            continue
        for room, cell in df[col].items():
            key = (str(room).strip(), day_idx, hour)
            timetable[key] = "" if pd.isna(cell) or str(cell).strip() == "" else str(cell).strip()
    return timetable

def get_room_status(room, day_idx, hour, timetable):
    key = (room, day_idx, hour)
    if key not in timetable:
        return "FREE", ""  # Assume free if not explicitly scheduled
    val = timetable[key]
    if val:
        return "OCCUPIED", val
    return "FREE", ""

def get_vacancy_duration(room, day_idx, start_hour, timetable):
    """Returns the number of hours the room is vacant, up to the end of the day (20:00)."""
    status, _ = get_room_status(room, day_idx, start_hour, timetable)
    if status == "OCCUPIED":
        return 0
    duration = 1
    for h in range(start_hour + 1, 21):
        status, _ = get_room_status(room, day_idx, h, timetable)
        if status == "OCCUPIED":
            break
        duration += 1
    return duration

@st.cache_resource(show_spinner="Loading campus data and ML model...")
def load_all_data():
    rooms_info = load_rooms()
    rooms_df   = pd.read_csv(ROOMS_CSV)
    
    occupied_set = set()
    if os.path.exists(DATASET_CSV):
        df = pd.read_csv(DATASET_CSV)
        day_names = ["mon", "tue", "wed", "thu", "fri", "sat"]
        for _, row in df.iterrows():
            if row.get("scheduled_class", 0) == 1:
                occupied_set.add((
                    day_names[int(row["day_of_week"]) % 6],
                    int(row["hour"]),
                    row.get("room", ""),
                ))
                
    extractors = build_feature_extractors(rooms_df, occupied_set)

    bundle = None
    for model_path in (MODEL_PKL, BASE_MODEL_PKL):
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                bundle = pickle.load(f)
            break

    if bundle is None:
        df = pd.read_csv(DATASET_CSV)
        missing_cols = [col for col in FEATURE_COLS + [TARGET_COL] if col not in df.columns]
        if missing_cols:
            raise FileNotFoundError(
                "No model artifact found and the fallback training dataset is incomplete. "
                f"Missing columns: {', '.join(missing_cols)}"
            )

        fallback_model = RandomForestClassifier(
            n_estimators=200,
            max_depth=15,
            random_state=42,
            n_jobs=-1,
        )
        fallback_model.fit(df[FEATURE_COLS], df[TARGET_COL])
        bundle = {
            "model": fallback_model,
            "model_name": "Random Forest (Fallback)",
            "feature_cols": FEATURE_COLS,
        }

    model        = bundle["model"]
    feature_cols = bundle["feature_cols"]
    all_rooms    = sorted(rooms_df["Room"].unique().tolist())
    return rooms_info, rooms_df, extractors, model, feature_cols, all_rooms

rooms_info, rooms_df, extractors, model, feature_cols, all_rooms = load_all_data()
timetable = load_timetable()

# ============================================================
# USER INPUTS
# ============================================================
st.subheader("📍 Navigation Details")

col1, col2, col3 = st.columns([1.5, 2, 2])

with col1:
    start_room = st.selectbox(
        "Current Location",
        options=all_rooms,
        index=all_rooms.index("F-201") if "F-201" in all_rooms else 0,
    )

with col2:
    use_now = st.checkbox("📅 Use Current Time", value=True)
    if use_now:
        now     = datetime.now()
        day_idx = min(now.weekday(), 5)
        hour    = max(8, min(20, now.hour))
        st.info(f"**{DAY_PREFIXES[day_idx]}, {hour}:00**")
    else:
        day_name = st.selectbox("Day", ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"])
        day_idx  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"].index(day_name)
        hour     = st.slider("Hour", min_value=8, max_value=20, value=14)

with col3:
    PRESETS = {
        "Entire Campus (All Rooms)": all_rooms,
        "Cross-Block Mix":   ["C-1", "C-11", "D-2", "Lab-13", "A-4", "E-1", "F-202"],
        "F-Block Rooms":     ["F-202","F-203","F-205","F-301","F-302","F-305"],
        "Labs Only":         ["Lab-1","Lab-2","Lab-3","Lab-13","Lab-14","Lab-6"],
        "Computing Block":   ["C-1","C-5","C-11","C-12","C-13","C-14"],
        "Custom":            [],
    }
    preset = st.selectbox("Target Region / Candidates", list(PRESETS.keys()))

if preset == "Custom":
    raw_candidates = st.multiselect("Select rooms", [r for r in all_rooms if r != start_room], default=["C-1", "D-2", "Lab-13"])
else:
    raw_candidates = [r for r in PRESETS[preset] if r != start_room]

if not raw_candidates:
    st.warning("⚠️ Please select at least one candidate room.")
    st.stop()

st.divider()

# ============================================================
# ROUTING PREFERENCE
# ============================================================
st.subheader("🎯 Routing Preference")
pref = st.radio(
    "What is your priority?",
    [
        "🤖 Smart A* (Find a guaranteed quiet/usable room, even if it's a slightly longer walk)",
        "🏃 Pure A* (I'm in a hurry! Just find the absolute closest vacant room)"
    ],
    index=0
)

# Advance settings in expander (cleaner UI)
with st.expander("⚙️ Advanced Settings"):
    penalty_scale = st.slider("ML Penalty Scale (Smart A* only)", 10, 200, 50, step=5)

st.divider()

# ============================================================
# EXECUTION LOGIC
# ============================================================
with st.spinner("Finding the best route..."):

    if "Pure A*" in pref:
        # MODE 1: PURE A* (VACANT ROOMS ONLY)
        
        # 1. Filter candidates using current timetable
        vacant_candidates = []
        for c in raw_candidates:
            status, _ = get_room_status(c, day_idx, hour, timetable)
            if status == "FREE":
                vacant_candidates.append(c)
                
        if not vacant_candidates:
            st.error("❌ **All candidate rooms are currently OCCUPIED according to the timetable!** Please select different rooms.")
            st.stop()
            
        # 2. Run A* ONLY on vacant rooms
        pure_best, _, _ = compare_routing(
            start_room, vacant_candidates, day_idx, hour, rooms_info, model, rooms_df, extractors, feature_cols, penalty_scale
        )
        
        if pure_best['pure_cost'] == float('inf'):
            st.error("❌ No path found to the vacant candidates.")
            st.stop()

        # Display Pure A* Result
        duration = get_vacancy_duration(pure_best['room'], day_idx, hour, timetable)
        end_time = hour + duration
        dur_text = f"Until {end_time}:00 ({duration} hr{'s' if duration > 1 else ''})" if end_time <= 20 else "Rest of the day"
        
        st.markdown("### 🏃 Recommended: Closest Vacant Room")
        st.markdown(f"""
        <div class="card-pure">
            <div class="metric-label">Target Room</div>
            <div class="metric-value">{pure_best['room']}</div>
            <br>
            <div class="metric-label">Status</div>
            <span class="badge-free">✅ FREE ({dur_text})</span>
            <br><br>
            <div class="metric-label">Distance (steps)</div>
            <div class="metric-value" style="color:#2d6a9f">{pure_best['pure_cost']:.1f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("Note: Pure A* guarantees this room is scheduled as free and is physically closest, but does not predict ambient noise or crowd levels.")

    else:
        # MODE 2: SMART A* (ML-ENHANCED)
        
        # 1. Run Smart A* on ALL candidates (unfiltered)
        _, smart_best, all_results = compare_routing(
            start_room, raw_candidates, day_idx, hour, rooms_info, model, rooms_df, extractors, feature_cols, penalty_scale
        )
        
        # Sort results by Smart Cost
        ranked_results = sorted(all_results, key=lambda x: x['smart_cost'])
        top_pick = ranked_results[0]
        
        # Get timetable status for the top pick
        top_status, top_class = get_room_status(top_pick['room'], day_idx, hour, timetable)
        
        if top_status == "FREE":
            # Best case scenario: ML picked it, and it's free.
            duration = get_vacancy_duration(top_pick['room'], day_idx, hour, timetable)
            end_time = hour + duration
            dur_text = f"Until {end_time}:00 ({duration} hr{'s' if duration > 1 else ''})" if end_time <= 20 else "Rest of the day"

            st.markdown("### 🤖 Primary Recommendation")
            st.markdown(f"""
            <div class="card-success">
                <div class="metric-label">Target Room</div>
                <div class="metric-value">{top_pick['room']}</div>
                <br>
                <div class="metric-label">Current Status</div>
                <span class="badge-free">✅ FREE ({dur_text})</span>
                <br><br>
                <div class="metric-label">AI Quietness Prediction (Usability)</div>
                <div class="metric-value" style="color:#16a34a">{top_pick['occupancy_prob']:.0%} Likely Quiet</div>
                <br>
                <div class="metric-label">Distance (steps)</div>
                <div class="metric-value">{top_pick['pure_cost']:.1f}</div>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            # ML picked it (lowest smart cost), but it's currently occupied!
            st.markdown("### ⚠️ Top Pick is Occupied")
            st.markdown(f"""
            <div class="card-warning">
                The ML model predicted <b>{top_pick['room']}</b> would be a great quiet spot, but the current semester timetable shows a class is running!
                <br><br>
                <span class="badge-occupied">🔴 OCCUPIED: {top_class}</span>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("### 🔄 Alternative Vacant Recommendations")
            
            # Find the next best rooms that ARE FREE
            alternatives_found = 0
            for alt in ranked_results[1:]:
                alt_status, _ = get_room_status(alt['room'], day_idx, hour, timetable)
                if alt_status == "FREE":
                    duration = get_vacancy_duration(alt['room'], day_idx, hour, timetable)
                    end_time = hour + duration
                    dur_text = f"Until {end_time}:00" if end_time <= 20 else "Rest of the day"

                    st.markdown(f"""
                    <div class="alt-room">
                        <span style="font-size:1.2rem; font-weight:bold; color:#1e3a5f;">{alt['room']}</span>
                        <span class="badge-free" style="margin-left:10px;">✅ FREE ({dur_text})</span>
                        <div style="margin-top:8px; font-size:0.9rem; color:#64748b;">
                            <b>{alt['occupancy_prob']:.0%}</b> Quiet Prediction | <b>{alt['pure_cost']:.1f}</b> steps walk
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    alternatives_found += 1
                    
                if alternatives_found >= 3:  # Show top 3 free alternatives
                    break
                    
            if alternatives_found == 0:
                st.error("No other candidate rooms are currently vacant.")
