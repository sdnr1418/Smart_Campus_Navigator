"""
Extract timetable data into a room-centric format.

Output shape:
  Rows    → Rooms  (normalized canonical names)
  Columns → Day + Hour slots  (Mon_08:00 … Sat_20:00)
  Cells   → Course code(s) occupying that room at that time, or "" if free

Fixes vs v1:
  - Room names normalized via normalize_room() — same logic as script 1 —
    so 'English Lab-I', 'S. Hall', 'lab-17' etc. map to canonical keys.
  - Rooms loaded from all_rooms.csv (output of script 1).
    Falls back to deriving the room list from occupancy data if CSV missing.
  - FSM course info preserved in full (no truncation, no lossy split on '(').
  - Merge collision handled correctly: if FSC and FSM both schedule something
    in the same room+slot (shouldn't happen physically, but data may overlap),
    both course codes are joined with ' / ' instead of one silently winning.
  - Computing: room name normalized before storing key.
  - Management: room name normalized before storing key.
"""

import pandas as pd
import os
import re
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────────────────────
TIMETABLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'TimeTables')
ROOMS_CSV      = os.path.join(os.path.dirname(__file__), '..', 'Data', 'raw', 'all_rooms.csv')

COMPUTING_FILE   = os.path.join(TIMETABLES_DIR, "FSC TT Spring 2026 v1.3.xlsx")
COMPUTING_SHEETS = ["CS", "DS", "SE", "AI", "CY"]

MANAGEMENT_FILE  = os.path.join(TIMETABLES_DIR, "Spring_26 FSM Time Table (1.0).xlsx")
MANAGEMENT_SHEET = "19-Mar-26; 3.40 pm"

DAYS  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
HOURS = list(range(8, 21))   # 08:00 – 20:00

# ── Name normalizer (mirrors script 1) ───────────────────────────────────────
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}

def normalize_room(name: str) -> str:
    """Return the canonical room name (same logic as 1_extract_rooms.py)."""
    name = name.strip()
    # 'lab-17' → 'Lab-17'
    if re.match(r'^lab-\d+$', name, re.IGNORECASE):
        return 'Lab-' + re.search(r'\d+', name).group()
    # 'English Lab-I' … 'English Lab-VI' → 'Eng Lab-1' … 'Eng Lab-6'
    m = re.match(r'^English\s+Lab[- ]([IVX]+)$', name, re.IGNORECASE)
    if m:
        arabic = ROMAN.get(m.group(1).upper(), m.group(1))
        return f'Eng Lab-{arabic}'
    # 'S. Hall' → 'Seminar Hall'
    if name == 'S. Hall':
        return 'Seminar Hall'
    return name

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_header_row(df, search_col=0, search_value="Code"):
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[search_col]) and \
           str(row.iloc[search_col]).strip().lower() == search_value.lower():
            return idx
    return 0


def parse_time_to_hour(time_str) -> int | None:
    """Convert a time string to an integer hour (0-23)."""
    if pd.isna(time_str):
        return None
    slot = str(time_str).strip()
    slot = slot.replace('.', '').replace('a m', ' AM').replace('p m', ' PM')
    if 'to' in slot.lower():
        slot = slot.lower().split('to')[0].strip()
    for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"]:
        try:
            return datetime.strptime(slot, fmt).hour
        except ValueError:
            continue
    return None


def add_entry(occupancy: dict, key: tuple, course: str):
    """
    Insert (or append) a course into the occupancy dict.
    If the slot is already occupied (data overlap), join with ' / '.
    """
    if not course:
        return
    if key in occupancy:
        existing = occupancy[key]
        if course not in existing:                # avoid exact duplicates
            occupancy[key] = existing + ' / ' + course
    else:
        occupancy[key] = course

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_computing_data_with_courses() -> dict:
    """
    Returns {(day_lower, hour, canonical_room): course_code}.
    e.g. ('mon', 8, 'F-201') → 'CS101'
    """
    print("Loading Computing timetable data...")
    occupancy = {}

    for sheet in COMPUTING_SHEETS:
        try:
            print(f"  Reading {sheet}...", end=" ")
            df_raw = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=None)
            header_idx = get_header_row(df_raw)
            df = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=header_idx)

            for i in [1, 2]:
                day_col   = f"Day {i}"
                slot_col  = f"Slot {i}"
                venue_col = f"Venue {i}"

                if not all(c in df.columns for c in [day_col, slot_col, venue_col, "Code"]):
                    continue

                for _, row in df.iterrows():
                    day_raw  = str(row[day_col]).strip()  if pd.notna(row[day_col])  else ""
                    slot_raw = str(row[slot_col]).strip() if pd.notna(row[slot_col]) else ""
                    room_raw = str(row[venue_col]).strip() if pd.notna(row[venue_col]) else ""
                    course   = str(row["Code"]).strip()   if pd.notna(row["Code"])   else ""

                    if day_raw.lower() not in [d.lower() for d in DAYS] or not room_raw:
                        continue

                    hour = parse_time_to_hour(slot_raw)
                    if hour is None:
                        continue

                    room = normalize_room(room_raw)
                    key  = (day_raw.lower(), hour, room)
                    add_entry(occupancy, key, course)

            print("OK")
        except Exception as e:
            print(f"ERROR: {e}")

    return occupancy

def load_management_data_with_courses() -> dict:
    """
    Returns {(day_lower, hour, canonical_room): course_info}.

    The FSM sheet has a wide format:
      col 0 → Day (appears only on first row of each day group)
      col 1 → Room name
      col 2+ → Time-slot columns (header row contains time strings)
      Cells  → Full course description strings
    """
    print("Loading Management timetable data...")
    occupancy = {}

    try:
        print(f"  Reading {MANAGEMENT_SHEET}...", end=" ")
        df = pd.read_excel(MANAGEMENT_FILE, sheet_name=MANAGEMENT_SHEET, header=None)

        # Locate the header row (contains 'Days' and 'Room')
        header_row = None
        for idx, row in df.iterrows():
            vals = [str(x).strip().lower() for x in row if pd.notna(x)]
            if 'days' in vals and 'room' in vals:
                header_row = idx
                break
        if header_row is None:
            raise ValueError("Could not find header row in FSM timetable.")

        # Map column index → hour for every time-slot column
        slot_columns = []
        for col_idx, cell in enumerate(df.iloc[header_row]):
            if pd.notna(cell) and col_idx > 1:
                hour = parse_time_to_hour(cell)
                if hour is not None:
                    slot_columns.append((col_idx, hour))

        current_day = None
        for idx in range(header_row + 1, len(df)):
            row       = df.iloc[idx]
            day_cell  = row.iloc[0]
            room_cell = row.iloc[1]

            # Update current day when a new day label appears
            if pd.notna(day_cell) and isinstance(day_cell, str):
                d = day_cell.strip().lower()
                for day_name in DAYS:
                    if d.startswith(day_name.lower()):
                        current_day = day_name
                        break

            if current_day is None or pd.isna(room_cell):
                continue

            room = normalize_room(str(room_cell).strip())
            if not room:
                continue

            for col_idx, hour in slot_columns:
                cell = row.iloc[col_idx]
                if pd.notna(cell):
                    content = str(cell).strip()
                    if content:
                        key = (current_day.lower(), hour, room)
                        add_entry(occupancy, key, content)

        print("OK")
    except Exception as e:
        print(f"ERROR: {e}")

    return occupancy

# ── Room list ─────────────────────────────────────────────────────────────────
def get_all_rooms(occupancy_fsc: dict, occupancy_fsm: dict) -> list:
    """
    Load canonical room list from all_rooms.csv (produced by script 1).
    Falls back to deriving rooms from occupancy data if the CSV is missing.
    """
    if os.path.exists(ROOMS_CSV):
        df = pd.read_csv(ROOMS_CSV)
        rooms = sorted(df['Room'].tolist())
        print(f"  Loaded {len(rooms)} rooms from {ROOMS_CSV}")
        return rooms

    print(f"  WARNING: {ROOMS_CSV} not found — deriving room list from occupancy data.")
    rooms_from_data = set()
    for (_, _, room) in list(occupancy_fsc.keys()) + list(occupancy_fsm.keys()):
        rooms_from_data.add(room)
    return sorted(rooms_from_data)

# ── DataFrame builder ─────────────────────────────────────────────────────────
def create_timetable_dataframe(occupancy_fsc: dict, occupancy_fsm: dict) -> pd.DataFrame:
    """
    Merge both occupancy dicts and pivot into a room × time-slot DataFrame.
    Columns: Mon_08:00, Mon_09:00, …, Sat_20:00
    """
    print("\nMerging occupancy data...")

    # Start with FSC, then layer FSM on top using add_entry to handle overlaps
    merged = dict(occupancy_fsc)
    for key, course in occupancy_fsm.items():
        add_entry(merged, key, course)

    print(f"  FSC entries : {len(occupancy_fsc)}")
    print(f"  FSM entries : {len(occupancy_fsm)}")
    print(f"  Merged total: {len(merged)}")

    print("\nLoading room list...")
    all_rooms = get_all_rooms(occupancy_fsc, occupancy_fsm)

    # Build column index
    columns = [f"{day}_{hour:02d}:00" for day in DAYS for hour in HOURS]

    # Build rows
    rows = {}
    for room in all_rooms:
        row_data = []
        for day in DAYS:
            for hour in HOURS:
                row_data.append(merged.get((day.lower(), hour, room), ""))
        rows[room] = row_data

    df = pd.DataFrame.from_dict(rows, orient='index', columns=columns)
    df.index.name = "Room"
    return df

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("EXTRACTING TIMETABLE DATA BY ROOM")
    print("=" * 70 + "\n")

    occupancy_fsc = load_computing_data_with_courses()
    occupancy_fsm = load_management_data_with_courses()

    df_timetable = create_timetable_dataframe(occupancy_fsc, occupancy_fsm)

    occupied_cells = (df_timetable != "").sum().sum()
    total_cells    = df_timetable.size
    print(f"\nTimetable shape : {df_timetable.shape[0]} rooms × {df_timetable.shape[1]} time slots")
    print(f"Occupied slots  : {occupied_cells} / {total_cells} "
          f"({occupied_cells / total_cells * 100:.1f}%)")

    # Write to temp file first, then rename (avoids OneDrive lock issues)
    output_path = os.path.join(os.path.dirname(__file__), '..', 'Data', 'raw', 'room_timetable.csv')
    temp_path = output_path + '.tmp'
    
    try:
        df_timetable.to_csv(temp_path)
        os.replace(temp_path, output_path)
        print(f"\n{'=' * 70}")
        print(f"Timetable exported to: {output_path}")
        print(f"{'=' * 70}\n")
    except Exception as e:
        print(f"Error writing output: {e}")
        print(f"Attempting to write to temp location...")
        temp_output = os.path.join(os.environ.get('TEMP', '.'), 'room_timetable.csv')
        df_timetable.to_csv(temp_output)
        print(f"Written to: {temp_output}")

    print("Sample (first 5 rooms, first 10 time slots):")
    print(df_timetable.iloc[:5, :10].to_string())


if __name__ == "__main__":
    main()
