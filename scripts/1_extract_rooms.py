"""
Merge rooms from all available timetables and classify by building block.
Creates a unified CSV with all rooms sorted by building.
"""
import pandas as pd
from collections import defaultdict
import os
import re

# Get the path to the TimeTables folder
TIMETABLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'TimeTables')

COMPUTING_FILE = os.path.join(TIMETABLES_DIR, "FSC TT Spring 2026 v1.3.xlsx")
COMPUTING_SHEETS = ["CS", "DS", "SE", "AI", "CY"]

MANAGEMENT_FILE = os.path.join(TIMETABLES_DIR, "Spring_26 FSM Time Table (1.0).xlsx")
MANAGEMENT_SHEET = "19-Mar-26; 3.40 pm"

# Building block mapping (first character or pattern-based)
BUILDING_MAP = {
    'A': 'A-Block (Admin)',
    'B': 'B-Block (Civil)',
    'C': 'C-Block (Computing)',
    'D': 'D-Block (Electrical/Management)',
    'E': 'E-Block (Library)',
    'F': 'F-Block (New Building)',
    'L': 'L-Block (Labs)',
}

def get_header_row(df, search_col=0, search_value="Code"):
    """Find the row index where the first column contains 'Code' (case-insensitive)."""
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[search_col]) and str(row.iloc[search_col]).strip().lower() == search_value.lower():
            return idx
    return 0

def extract_computing_rooms():
    """Extract rooms from FSC (Computing) timetables."""
    rooms = set()
    
    for sheet in COMPUTING_SHEETS:
        try:
            df_raw = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=None)
            header_idx = get_header_row(df_raw)
            df = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=header_idx)
            
            # Extract from Venue 1 and Venue 2 columns
            for i in [1, 2]:
                venue_col = f"Venue {i}"
                if venue_col not in df.columns:
                    continue
                for _, row in df.iterrows():
                    venue = row[venue_col]
                    if pd.notna(venue):
                        room_str = str(venue).strip()
                        if room_str:
                            rooms.add(room_str)
        except Exception as e:
            print(f"  Note: Could not read Computing sheet {sheet}: {e}")
    
    return rooms

def is_valid_room(name):
    """Check if a string looks like a room (not a time slot or label)."""
    # Filter out time slots and common labels
    time_patterns = [
        r'\d{1,2}:\d{2}',  # time like 10:30
        r'AM|PM|am|pm',    # AM/PM markers
        'to',
        'Period',
        'Color',
        'Days',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
        'Room',  # generic label
    ]
    
    name_lower = name.lower()
    for pattern in time_patterns:
        if re.search(pattern, name_lower):
            return False
    
    return True

def extract_management_rooms():
    """Extract rooms from FSM (Management) timetable."""
    rooms = set()
    
    try:
        df = pd.read_excel(MANAGEMENT_FILE, sheet_name=MANAGEMENT_SHEET, header=None)
        
        # Scan entire sheet for room-like patterns
        for _, row in df.iterrows():
            for col_idx, val in enumerate(row):
                if pd.notna(val) and isinstance(val, str):
                    val = val.strip()
                    # Room patterns: C-5, D-11, A-7, Lab-1, Seminar Hall, etc.
                    if val and is_valid_room(val):
                        if re.match(r'^[A-Z]-\d{1,3}$', val):  # X-## format
                            rooms.add(val)
                        elif val.startswith('Lab-'):
                            rooms.add(val)
                        elif val.startswith('Eng Lab-'):
                            rooms.add(val)
                        elif val in ['Seminar Hall', 'Old Audi', 'CRMG']:
                            rooms.add(val)
    except Exception as e:
        print(f"  Note: Could not read Management timetable: {e}")
    
    return rooms

def classify_room(room_name):
    """Classify room by building block based on naming pattern."""
    if not room_name:
        return 'Unknown'
    
    # Check first character
    first_char = room_name[0].upper()
    
    # Special cases
    if room_name.lower().startswith('lab-'):
        return BUILDING_MAP.get('L', 'Lab Block')
    elif room_name.lower().startswith('eng lab-'):
        return BUILDING_MAP.get('E', 'E-Block')
    elif room_name == 'Embedded Lab':
        return BUILDING_MAP.get('E', 'E-Block')
    elif room_name == 'Micro Lab':
        return BUILDING_MAP.get('D', 'D-Block (Electrical/Management)')
    elif room_name == 'Physics Lab':
        return BUILDING_MAP.get('D', 'D-Block (Electrical/Management)')
    elif room_name == 'Seminar Hall' or room_name == 'S. Hall':
        return BUILDING_MAP.get('D', 'D-Block (Electrical/Management)')
    elif room_name == 'CRMG':
        return BUILDING_MAP.get('D', 'D-Block (Electrical/Management)')
    elif room_name == 'Old Audi':
        return BUILDING_MAP.get('C', 'C-Block (Computing)')
    elif first_char in BUILDING_MAP:
        return BUILDING_MAP[first_char]
    else:
        return 'Other'

def extract_floor_number(room_name):
    """Extract or infer floor number from room name."""
    if not room_name:
        return 1
    
    # Extract numbers from room name
    numbers = re.findall(r'\d+', room_name)
    
    if not numbers:
        return 1  # Default to floor 1 if no numbers found
    
    # Get the first (or main) number
    room_num = int(numbers[0])
    
    # Pattern: X-YYY where YYY encodes floor
    # F-201 = floor 2, F-301 = floor 3
    # Lab-1 = floor 1, Lab-13 = floor 2
    # C-1 = floor 1, C-10+ = floor 2
    
    if room_num >= 300:
        return 3
    elif room_num >= 200:
        return 2
    elif room_num >= 100:
        return 2  # 100-199 could be floor 1 or 2; assume 2 for labs
    elif room_num >= 10:
        return 2
    else:
        return 1

def main():
    print("=" * 60)
    print("EXTRACTING AND MERGING ROOMS FROM ALL TIMETABLES")
    print("=" * 60)
    
    # Extract from both timetables
    print("\n[1] Extracting rooms from Computing timetable...")
    computing_rooms = extract_computing_rooms()
    print(f"    Found {len(computing_rooms)} unique rooms from Computing")
    
    print("\n[2] Extracting rooms from Management timetable...")
    management_rooms = extract_management_rooms()
    print(f"    Found {len(management_rooms)} unique rooms from Management")
    
    # Merge
    all_rooms = computing_rooms | management_rooms
    print(f"\n[3] Total unique rooms after merge: {len(all_rooms)}")
    
    # Create dataframe with classification and floor
    data = []
    for room in sorted(all_rooms):
        building = classify_room(room)
        floor = extract_floor_number(room)
        data.append({
            'Room': room,
            'Building': building,
            'Department': 'Computing' if room in computing_rooms else 'Management' if room in management_rooms else 'Both',
            'floor_number': floor
        })
    
    df = pd.DataFrame(data)
    
    # Save to CSV
    output_file = os.path.join(os.path.dirname(__file__), '..', 'all_rooms.csv')
    df.to_csv(output_file, index=False)
    print(f"\n[4] Saved merged list to: {output_file}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("ROOMS BY BUILDING BLOCK")
    print("=" * 60)
    
    building_groups = df.groupby('Building')
    for building in sorted(df['Building'].unique()):
        rooms_in_building = df[df['Building'] == building].sort_values('Room')
        print(f"\n{building} ({len(rooms_in_building)} rooms)")
        for idx, row in rooms_in_building.iterrows():
            dept_badge = f" [{row['Department']}]"
            floor_badge = f" (F{row['floor_number']})"
            print(f"  {idx+1:3d}. {row['Room']:<20}{dept_badge:<20}{floor_badge}")
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL ROOMS: {len(df)}")
    print(f"{'=' * 60}\n")

if __name__ == "__main__":
    main()
