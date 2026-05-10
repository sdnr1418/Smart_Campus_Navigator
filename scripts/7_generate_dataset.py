"""
Script 7 — Generate Room Usability Dataset (from prev-sem CSV)
===============================================================
Reads previous-semester CSV if present (`prev_sem_data.csv`) or falls
back to Excel timetables. Produces `Data/room_usability_dataset.csv` with
the agreed feature set for training.

New features added: `is_weekday`, `room_popularity_bucket` (quartile).
Neighbor feature is the non-leaky `neighbor_hour_occupancy_rate`.
"""

import os
import re
import pandas as pd
import numpy as np
from datetime import datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

ROOMS_CSV        = os.path.join(PROJECT_ROOT, "Data", "raw", "all_rooms.csv")
OUTPUT_DIR  = os.path.join(PROJECT_ROOT, "Data")
OUTPUT_CSV  = os.path.join(OUTPUT_DIR, "room_usability_dataset.csv")

DAYS  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
HOURS = list(range(8, 21))

SPECIAL_ROOMS = {"Seminar Hall", "Old Audi", "CRMG", "Embedded Lab", "Micro Lab", "Physics Lab"}

def normalize_room(name: str) -> str:
    if pd.isna(name):
        return ""
    name = str(name).strip()
    m = re.match(r"^lab-(\d+)$", name, re.IGNORECASE)
    if m:
        return f"Lab-{m.group(1)}"
    m = re.match(r"^English\s+Lab[- ]([IVX]+)$", name, re.IGNORECASE)
    if m:
        return f"Eng Lab-{m.group(1).upper()}"
    if name == "S. Hall":
        return "Seminar Hall"
    return name

def build_occupied_set_from_csv(prev_csv: str) -> set:
    occ = set()
    dfr = pd.read_csv(prev_csv)
    for _, r in dfr.iterrows():
        try:
            room = normalize_room(r.get('Room', ''))
            day = str(r.get('Day', '')).strip()
            hour = int(r.get('Hour'))
            status = int(r.get('Status', 0))
        except Exception:
            continue
        if status == 1 and room and day[:3].capitalize() in DAYS:
            occ.add((day[:3].lower(), hour, room))
    return occ

def build_room_occupancy_rates(occupied: set, rooms: list) -> dict:
    total_slots = len(DAYS) * len(HOURS)
    rates = {}
    for room in rooms:
        count = sum(1 for day in DAYS for hour in HOURS if (day.lower(), hour, room) in occupied)
        rates[room] = count / total_slots
    return rates

def build_block_hour_occupancy_rates(occupied: set, rooms_df: pd.DataFrame) -> dict:
    block_rooms = {}
    for _, row in rooms_df.iterrows():
        m = re.match(r"([A-Z])-Block", row['Building'])
        if m:
            block_rooms.setdefault(m.group(1), []).append(row['Room'])
    rates = {}
    for block, room_list in block_rooms.items():
        n = len(room_list)
        for hour in HOURS:
            total = sum(1 for day in DAYS for room in room_list if (day.lower(), hour, room) in occupied)
            rates[(block, hour)] = total / (n * len(DAYS)) if n > 0 else 0.0
    return rates

def build_neighbor_lookup(rooms_df: pd.DataFrame) -> dict:
    lookup = {}
    for _, row in rooms_df.iterrows():
        m_block = re.match(r"([A-Z])-Block", row['Building'])
        m_num = re.search(r"(\d+)", str(row['Room']))
        if m_block and m_num:
            lookup[(m_block.group(1), int(m_num.group()))] = row['Room']
    return lookup

def build_neighbor_hour_rates(occupied: set, rooms_df: pd.DataFrame, neighbor_lookup: dict, radius: int = 2) -> dict:
    rates = {}
    for _, row in rooms_df.iterrows():
        room = row['Room']
        m = re.search(r"(\d+)", str(room))
        if not m:
            for hour in HOURS:
                rates[(room, hour)] = 0.0
            continue
        block_m = re.match(r"([A-Z])-Block", row['Building'])
        block = block_m.group(1) if block_m else None
        room_num = int(m.group())
        nb_list = [neighbor_lookup.get((block, room_num + d)) for d in range(-radius, radius+1) if d != 0]
        nb_list = [n for n in nb_list if n]
        if not nb_list:
            for hour in HOURS:
                rates[(room, hour)] = 0.0
            continue
        for hour in HOURS:
            total = sum(1 for day in DAYS for nb in nb_list if (day.lower(), hour, nb) in occupied)
            denom = len(nb_list) * len(DAYS)
            rates[(room, hour)] = total / denom if denom > 0 else 0.0
    return rates

def build_popularity_buckets(room_rates: dict, q: int = 4) -> dict:
    s = pd.Series(room_rates)
    try:
        cats = pd.qcut(s, q=q, labels=False, duplicates='drop')
    except Exception:
        cats = pd.Series(0, index=s.index)
    return cats.to_dict()

def main():
    prev_csv = os.path.join(PROJECT_ROOT, 'Data', 'raw', 'prev_sem_data.csv')
    print('Building occupied set...')
    if os.path.exists(prev_csv):
        occupied = build_occupied_set_from_csv(prev_csv)
        print(f'  Loaded prev-sem CSV, occupied slots: {len(occupied)}')
    else:
        print('  prev_sem_data.csv not found — please provide it in project root.')
        occupied = set()

    rooms_df = pd.read_csv(ROOMS_CSV)
    room_occ_rates = build_room_occupancy_rates(occupied, rooms_df['Room'].tolist())
    block_hour_rates = build_block_hour_occupancy_rates(occupied, rooms_df)
    nb_lookup = build_neighbor_lookup(rooms_df)
    neighbor_hour_rates = build_neighbor_hour_rates(occupied, rooms_df, nb_lookup, radius=2)
    pop_buckets = build_popularity_buckets(room_occ_rates, q=4)

    rows = []
    day_index = {d.lower(): i for i, d in enumerate(DAYS)}
    for _, r in rooms_df.iterrows():
        room = r['Room']
        building = r['Building']
        floor = int(r['floor_number'])
        block = re.match(r"([A-Z])-Block", building)
        block = block.group(1) if block else '?'
        is_lab = 1 if re.match(r"^Lab-\d+$", str(room)) or re.match(r"^Eng Lab-\d+$", str(room)) else 0
        is_special = 1 if room in SPECIAL_ROOMS else 0
        room_rate = room_occ_rates.get(room, 0.0)
        for day in DAYS:
            for hour in HOURS:
                sched = 1 if (day.lower(), hour, room) in occupied else 0
                prev_occ = 1 if (day.lower(), hour-1, room) in occupied else 0
                next_occ = 1 if (day.lower(), hour+1, room) in occupied else 0
                usable = 0 if (sched or prev_occ or next_occ or is_special) else 1
                bh = block_hour_rates.get((block, hour), 0.0)
                nb_rate = neighbor_hour_rates.get((room, hour), 0.0)
                h_sin = np.sin(2*np.pi*hour/24)
                h_cos = np.cos(2*np.pi*hour/24)
                is_weekday = 1 if day in ['Mon','Tue','Wed','Thu','Fri'] else 0
                pop_bucket = int(pop_buckets.get(room, 0))
                rows.append({
                    'room': room, 'building': building, 'block': block,
                    'day_of_week': day_index[day.lower()], 'hour': hour,
                    'hour_sin': round(h_sin,6), 'hour_cos': round(h_cos,6),
                    'floor': floor, 'is_lab': is_lab, 'is_special': is_special,
                    'room_overall_occupancy_rate': round(room_rate,6),
                    'block_hour_occupancy_rate': round(bh,6),
                    'neighbor_hour_occupancy_rate': round(nb_rate,6),
                    'is_weekday': is_weekday, 'room_popularity_bucket': pop_bucket,
                    'scheduled_class': sched, 'prev_hour_occupied': prev_occ,
                    'next_hour_occupied': next_occ, 'usable': usable
                })

    df = pd.DataFrame(rows)
    block_dummies = pd.get_dummies(df['block'], prefix='block')
    for letter in list('ABCDEFL'):
        col = f'block_{letter}'
        if col not in block_dummies.columns:
            block_dummies[col] = 0
    df = pd.concat([df, block_dummies.astype(int)], axis=1)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f'Wrote dataset to {OUTPUT_CSV}  rows={len(df)}')

if __name__ == '__main__':
    main()
