"""
Script 11 - Smart Navigator Engine
====================================
Provides the core logic for ML-integrated A* routing.
Imported by Script 12 (comparison tests) and the Streamlit app.

Public API:
  build_feature_extractors(rooms_df, occupied_set) -> extractors tuple
  compare_routing(start_room, candidate_rooms, day_idx, hour,
                  rooms_info, model, rooms_df, extractors, feature_cols)
                  -> (pure_best, smart_best, all_results)

How Smart A* works:
  - Pure A* : picks the candidate room with the lowest path cost (distance only)
  - Smart A*: picks the candidate with the lowest (path cost + ML penalty)
              ML penalty = penalty_scale x (1 - usability_prob)
              High usability (free room) -> low penalty -> preferred route
"""

import os
import sys
import pickle
import pandas as pd
import numpy as np
import re

# ============================================================
# PATH SETUP
# ============================================================
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SCRIPT_DIR)

# Import A* navigator from Script 5
import importlib.util
spec = importlib.util.spec_from_file_location(
    "nav", os.path.join(SCRIPT_DIR, "5_hierarchical_navigator.py")
)
nav = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nav)

load_rooms      = nav.load_rooms
total_path_cost = nav.total_path_cost

from config import BUILDING_GRAPH, BUILDING_POS

# Paths
MODEL_TUNED_RF = os.path.join(PROJECT_ROOT, "Models", "room_usability_model_tuned_rf.pkl")
RESULTS_DIR    = os.path.join(PROJECT_ROOT, "Results")

# ============================================================
# FEATURE EXTRACTION FOR ML PREDICTION
# ============================================================

def extract_room_number(room):
    """Extract numeric suffix from room name."""
    m = re.search(r'\d+', room)
    return int(m.group()) if m else 0


def get_block_letter(room):
    """Extract block letter (e.g., 'C-11' -> 'C')."""
    m = re.match(r'([A-Z])-', room)
    return m.group(1) if m else None


def build_feature_extractors(rooms_df, occupied_set, day_offset=0):
    """
    Pre-compute lookup tables for all ML features.
    Must be called once and the result passed to compare_routing().

    Args:
        rooms_df    : DataFrame from all_rooms.csv
        occupied_set: set of (day_str, hour, room) tuples where scheduled_class==1
        day_offset  : unused — kept for API compatibility

    Returns:
        (room_occupancy, block_hour_occupancy, neighbor_hour_occupancy, quartile_thresholds)
    """
    DAYS  = ["mon", "tue", "wed", "thu", "fri", "sat"]
    HOURS = list(range(8, 21))

    # Room-level overall occupancy rate
    room_occupancy = {}
    for room in rooms_df['Room'].unique():
        count = sum(1 for day in DAYS for hour in HOURS
                    if (day, hour, room) in occupied_set)
        room_occupancy[room] = count / (len(DAYS) * len(HOURS))

    # Block-hour occupancy rate
    block_hour_occupancy = {}
    for block in ['A', 'B', 'C', 'D', 'E', 'F', 'L']:
        block_rooms = rooms_df[
            rooms_df['Building'].str.contains(f"{block}-Block", na=False)
        ]['Room'].tolist()
        for hour in HOURS:
            count = sum(1 for day in DAYS for room in block_rooms
                        if (day, hour, room) in occupied_set)
            total = len(block_rooms) * len(DAYS)
            block_hour_occupancy[(block, hour)] = count / total if total > 0 else 0.0

    # Neighbor-hour occupancy rate (radius=2 room numbers)
    neighbor_hour_occupancy = {}
    for _, row in rooms_df.iterrows():
        room       = row['Room']
        block_m    = re.match(r"([A-Z])-Block", row['Building'])
        room_num_m = re.search(r"(\d+)", str(room))

        if block_m and room_num_m:
            block    = block_m.group(1)
            room_num = int(room_num_m.group())
            neighbors_list = []
            for _, row2 in rooms_df.iterrows():
                if re.match(f"{block}-Block", row2['Building']):
                    m2 = re.search(r"(\d+)", str(row2['Room']))
                    if m2 and abs(int(m2.group()) - room_num) <= 2:
                        neighbors_list.append(row2['Room'])
            for hour in HOURS:
                count = sum(1 for day in DAYS for n in neighbors_list
                            if (day, hour, n) in occupied_set)
                total = len(neighbors_list) * len(DAYS)
                neighbor_hour_occupancy[(room, hour)] = count / total if total > 0 else 0.0
        else:
            for hour in HOURS:
                neighbor_hour_occupancy[(room, hour)] = 0.0

    # Data-driven quartile thresholds (matches Script 7's pd.qcut logic)
    all_rates_sorted = sorted(room_occupancy.values())
    n   = len(all_rates_sorted)
    q25 = all_rates_sorted[max(0, int(n * 0.25) - 1)]
    q50 = all_rates_sorted[max(0, int(n * 0.50) - 1)]
    q75 = all_rates_sorted[max(0, int(n * 0.75) - 1)]

    return room_occupancy, block_hour_occupancy, neighbor_hour_occupancy, (q25, q50, q75)


def compute_room_features(room, day_idx, hour, rooms_df, extractors):
    """
    Build the 19-feature dict for a room at a given day/hour.
    Returns None if the room is not in rooms_df.
    """
    room_occupancy, block_hour_occupancy, neighbor_hour_occupancy, quartile_thresholds = extractors

    room_info = rooms_df[rooms_df['Room'] == room]
    if room_info.empty:
        return None

    floor = room_info['floor_number'].iloc[0]
    block = get_block_letter(room)

    features = {}

    # Temporal
    features['day_of_week'] = day_idx
    features['hour']        = hour
    features['hour_sin']    = np.sin(2 * np.pi * hour / 24)
    features['hour_cos']    = np.cos(2 * np.pi * hour / 24)
    features['is_weekday']  = 1 if day_idx < 5 else 0

    # Room static
    features['floor']      = floor
    features['is_lab']     = 1 if 'Lab' in room else 0
    features['is_special'] = 1 if any(
        s in room for s in ['Seminar', 'Audi', 'CRMG', 'Embedded', 'Micro', 'Physics']
    ) else 0

    # Occupancy rates
    features['room_overall_occupancy_rate']  = room_occupancy.get(room, 0.0)
    features['block_hour_occupancy_rate']    = block_hour_occupancy.get((block, hour), 0.0) if block else 0.0
    features['neighbor_hour_occupancy_rate'] = neighbor_hour_occupancy.get((room, hour), 0.0)

    # Popularity bucket — data-driven quartile thresholds matching Script 7
    occupancy_rate = room_occupancy.get(room, 0.0)
    q25, q50, q75  = quartile_thresholds
    if   occupancy_rate < q25: features['room_popularity_bucket'] = 0
    elif occupancy_rate < q50: features['room_popularity_bucket'] = 1
    elif occupancy_rate < q75: features['room_popularity_bucket'] = 2
    else:                      features['room_popularity_bucket'] = 3

    # Block one-hot encoding
    for b in ['A', 'B', 'C', 'D', 'E', 'F', 'L']:
        features[f'block_{b}'] = 1 if block == b else 0

    return features


def extract_feature_vector(features, feature_cols):
    """Convert feature dict to numpy array in the exact column order the model expects."""
    return np.array([features.get(col, 0.0) for col in feature_cols]).reshape(1, -1)


# ============================================================
# SMART A* ML PENALTY
# ============================================================

def compute_occupancy_penalty(candidate_room, day_idx, hour, model,
                               rooms_df, extractors, feature_cols, penalty_scale=50):
    """
    Returns (penalty, usability_prob) for a candidate room.

    usability_prob = P(class=1) = probability the room is FREE/USABLE.
    penalty        = penalty_scale x (1 - usability_prob)
                     -> freely usable room has near-zero penalty
                     -> heavily occupied room has ~penalty_scale penalty
    """
    features_dict = compute_room_features(candidate_room, day_idx, hour, rooms_df, extractors)
    if features_dict is None:
        return 0.0, 0.0

    feature_vec    = extract_feature_vector(features_dict, feature_cols)
    usability_prob = model.predict_proba(feature_vec)[0, 1]  # class 1 = USABLE (free)
    penalty        = penalty_scale * (1 - usability_prob)

    return penalty, usability_prob


# ============================================================
# CORE COMPARISON FUNCTION  (imported by Script 12 and the app)
# ============================================================

def compare_routing(start_room, candidate_rooms, day_idx, hour,
                    rooms_info, model, rooms_df, extractors, feature_cols,
                    penalty_scale=50):
    """
    Evaluate every candidate room under both Pure A* and Smart A*.

    Returns:
        pure_best  : dict — room chosen by Pure A* (lowest path cost)
        smart_best : dict — room chosen by Smart A* (lowest path + ML penalty)
        all_results: list of dicts — one entry per candidate

    Each result dict contains:
        room, pure_cost, occupancy_prob (= usability %), penalty, smart_cost, description
    """
    results = []

    for candidate in candidate_rooms:
        pure_cost, desc = total_path_cost(start_room, candidate, rooms_info)

        if pure_cost == float('inf'):
            results.append({
                'room': candidate, 'pure_cost': float('inf'),
                'occupancy_prob': 0.0, 'penalty': 0.0,
                'smart_cost': float('inf'), 'description': None,
            })
            continue

        penalty, usability_prob = compute_occupancy_penalty(
            candidate, day_idx, hour, model, rooms_df, extractors,
            feature_cols, penalty_scale
        )

        results.append({
            'room':           candidate,
            'pure_cost':      pure_cost,
            'occupancy_prob': usability_prob,   # P(room is FREE/USABLE)
            'penalty':        penalty,
            'smart_cost':     pure_cost + penalty,
            'description':    desc,
        })

    pure_best  = min(results, key=lambda x: x['pure_cost'])
    smart_best = min(results, key=lambda x: x['smart_cost'])

    return pure_best, smart_best, results
