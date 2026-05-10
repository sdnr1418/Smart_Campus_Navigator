"""
Merge rooms from all available timetables and classify by building block.
Creates a unified CSV with all rooms sorted by building.

Fixes applied:
- FSC uses 'Eng Lab-1..6', FSM uses 'English Lab-I..VI' — these are the SAME labs.
  All are normalized to 'Eng Lab-1' ... 'Eng Lab-6' as the canonical name.
- 'lab-17' (lowercase) normalized to 'Lab-17'.
- 'S. Hall' and 'Seminar Hall' are the same venue — normalized to 'Seminar Hall'.
- Correct block assignments:
    Micro Lab      → D-Block
    Physics Lab    → D-Block
    Seminar Hall   → C-Block
    CRMG           → B-Block
    Old Audi       → D-Block
    Embedded Lab   → B-Block
    Eng Lab-*      → E-Block (English Labs)
"""
import pandas as pd
import os
import re

# ── Paths ─────────────────────────────────────────────────────────────────────
TIMETABLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'TimeTables')

COMPUTING_FILE   = os.path.join(TIMETABLES_DIR, "FSC TT Spring 2026 v1.3.xlsx")
COMPUTING_SHEETS = ["CS", "DS", "SE", "AI", "CY"]

MANAGEMENT_FILE  = os.path.join(TIMETABLES_DIR, "Spring_26 FSM Time Table (1.0).xlsx")
MANAGEMENT_SHEET = "19-Mar-26; 3.40 pm"

# ── Building labels ───────────────────────────────────────────────────────────
BLOCK = {
    'A': 'A-Block (Admin)',
    'B': 'B-Block (Civil)',
    'C': 'C-Block (Computing)',
    'D': 'D-Block (Electrical/Management)',
    'E': 'E-Block (English Labs)',
    'F': 'F-Block (New Building)',
    'L': 'L-Block (Labs)',
}

# Roman-numeral → Arabic for English Lab normalization
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6}

# ── Name normalizer ───────────────────────────────────────────────────────────
def normalize_room(name: str) -> str:
    """
    Return the canonical room name so duplicates across timetables collapse.
      'English Lab-I'  → 'Eng Lab-1'
      'English Lab-VI' → 'Eng Lab-6'
      'lab-17'         → 'Lab-17'
      'S. Hall'        → 'Seminar Hall'
    """
    name = name.strip()

    # lowercase 'lab-17' → 'Lab-17'
    if re.match(r'^lab-\d+$', name, re.IGNORECASE):
        name = 'Lab-' + re.search(r'\d+', name).group()

    # 'English Lab-I' … 'English Lab-VI'  →  'Eng Lab-1' … 'Eng Lab-6'
    m = re.match(r'^English\s+Lab[- ]([IVX]+)$', name, re.IGNORECASE)
    if m:
        roman = m.group(1).upper()
        arabic = ROMAN.get(roman, roman)
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

# ── Extractors ────────────────────────────────────────────────────────────────
def extract_computing_rooms():
    """Extract and normalize rooms from FSC (Computing) timetables."""
    rooms = set()
    for sheet in COMPUTING_SHEETS:
        try:
            df_raw = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=None)
            header_idx = get_header_row(df_raw)
            df = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=header_idx)
            for i in [1, 2]:
                col = f"Venue {i}"
                if col not in df.columns:
                    continue
                for val in df[col].dropna():
                    raw = str(val).strip()
                    if raw:
                        rooms.add(normalize_room(raw))
        except Exception as e:
            print(f"  Warning: could not read Computing sheet '{sheet}': {e}")
    return rooms


def extract_management_rooms():
    """
    Extract and normalize rooms from FSM (Management) timetable.
    Column 1 is dedicated to room names after the header row.
    """
    rooms = set()
    try:
        df = pd.read_excel(MANAGEMENT_FILE, sheet_name=MANAGEMENT_SHEET, header=None)

        # Find header row containing 'Days' and 'Room'
        header_row = None
        for idx, row in df.iterrows():
            vals = [str(x).strip().lower() for x in row if pd.notna(x)]
            if 'days' in vals and 'room' in vals:
                header_row = idx
                break
        if header_row is None:
            raise ValueError("Could not find header row in FSM timetable.")

        for idx in range(header_row + 1, len(df)):
            cell = df.iloc[idx, 1]
            if pd.notna(cell):
                raw = str(cell).strip()
                if raw:
                    rooms.add(normalize_room(raw))
    except Exception as e:
        print(f"  Warning: could not read Management timetable: {e}")
    return rooms

# ── Classifier ────────────────────────────────────────────────────────────────
def classify_room(room: str) -> str:
    """Return the building block for a normalized room name."""
    SPECIAL = {
        'Micro Lab':    BLOCK['D'],
        'Physics Lab':  BLOCK['D'],
        'Old Audi':     BLOCK['D'],
        'Seminar Hall': BLOCK['C'],
        'CRMG':         BLOCK['B'],
        'Embedded Lab': BLOCK['B'],
    }
    if room in SPECIAL:
        return SPECIAL[room]
    if re.match(r'^Eng Lab-\d+$', room):
        return BLOCK['E']
    if re.match(r'^Lab-\d+$', room, re.IGNORECASE):
        return BLOCK['L']
    first = room[0].upper()
    if first in BLOCK:
        return BLOCK[first]
    return 'Other'

# ── Floor inference ───────────────────────────────────────────────────────────
def extract_floor(room: str) -> int:
    """
    Infer floor number from room name.
      F-201..F-210  → floor 2 | F-301..F-312 → floor 3
      C-1..C-9      → floor 1 | C-10..C-16   → floor 2
      D-1..D-5      → floor 1 | D-11..D-17   → floor 2
      Lab-1..Lab-8  → floor 1 | Lab-13+      → floor 2
      Everything else → floor 1
    """
    numbers = re.findall(r'\d+', room)
    if not numbers:
        return 1
    n = int(numbers[0])
    if n >= 300:
        return 3
    if n >= 200:
        return 2
    if room.startswith('D-') and n >= 11:
        return 2
    if room.startswith('C-') and n >= 10:
        return 2
    if re.match(r'^Lab-\d+$', room, re.IGNORECASE) and n >= 13:
        return 2
    return 1

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("EXTRACTING AND MERGING ROOMS FROM ALL TIMETABLES")
    print("=" * 60)

    print("\n[1] Extracting rooms from Computing timetable...")
    computing_rooms = extract_computing_rooms()
    print(f"    Found {len(computing_rooms)} unique rooms")

    print("\n[2] Extracting rooms from Management timetable...")
    management_rooms = extract_management_rooms()
    print(f"    Found {len(management_rooms)} unique rooms")

    both      = computing_rooms & management_rooms
    all_rooms = computing_rooms | management_rooms
    print(f"\n[3] Total unique rooms after merge: {len(all_rooms)}")

    data = []
    for room in sorted(all_rooms):
        dept = 'Both' if room in both else ('Computing' if room in computing_rooms else 'Management')
        data.append({
            'Room':         room,
            'Building':     classify_room(room),
            'Department':   dept,
            'floor_number': extract_floor(room),
        })

    df = pd.DataFrame(data).sort_values(['Building', 'Room']).reset_index(drop=True)

    output_file = os.path.join(os.path.dirname(__file__), '..', 'Data', 'raw', 'all_rooms.csv')
    df.to_csv(output_file, index=False)
    print(f"\n[4] Saved to: {output_file}")

    print("\n" + "=" * 60)
    print("ROOMS BY BUILDING BLOCK")
    print("=" * 60)
    for building in sorted(df['Building'].unique()):
        subset = df[df['Building'] == building].reset_index(drop=True)
        print(f"\n{building}  ({len(subset)} rooms)")
        for i, row in subset.iterrows():
            print(f"  {i+1:3d}. {row['Room']:<22} [{row['Department']:<10}]  F{row['floor_number']}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL ROOMS: {len(df)}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
