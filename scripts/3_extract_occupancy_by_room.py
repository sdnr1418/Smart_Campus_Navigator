"""
Extract timetable data into a room-centric format:
- Rows: Rooms
- Columns: Day + Time slots (08:00, 09:00, ..., 20:00)
- Cells: Course names occupying that room at that time
"""
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

# Get paths
TIMETABLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'TimeTables')
ROOMS_CSV = os.path.join(os.path.dirname(__file__), '..', 'rooms_complete.csv')

COMPUTING_FILE = os.path.join(TIMETABLES_DIR, "FSC TT Spring 2026 v1.3.xlsx")
COMPUTING_SHEETS = ["CS", "DS", "SE", "AI", "CY"]

MANAGEMENT_FILE = os.path.join(TIMETABLES_DIR, "Spring_26 FSM Time Table (1.0).xlsx")
MANAGEMENT_SHEET = "19-Mar-26; 3.40 pm"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
HOURS = list(range(8, 21))  # 8:00 to 20:00

def get_header_row(df, search_col=0, search_value="Code"):
    """Find the row index where the first column contains 'Code' (case-insensitive)."""
    for idx, row in df.iterrows():
        if pd.notna(row.iloc[search_col]) and str(row.iloc[search_col]).strip().lower() == search_value.lower():
            return idx
    return 0

def parse_time_to_hour(time_str):
    """Convert a time string to hour (0-23) from either 24h or 12h formats."""
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

def load_computing_data_with_courses():
    """Load computing timetable data with course information."""
    print("Loading Computing timetable data with courses...")
    occupancy = {}  # {(day, hour, room): course_code}
    
    for sheet in COMPUTING_SHEETS:
        try:
            print(f"  Reading {sheet}...", end=" ")
            df_raw = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=None)
            header_idx = get_header_row(df_raw)
            df = pd.read_excel(COMPUTING_FILE, sheet_name=sheet, header=header_idx)
            
            for i in [1, 2]:
                day_col = f"Day {i}"
                slot_col = f"Slot {i}"
                venue_col = f"Venue {i}"
                code_col = "Code"
                
                if day_col not in df.columns or slot_col not in df.columns or venue_col not in df.columns:
                    continue
                
                for _, row in df.iterrows():
                    row_day = str(row[day_col]).strip() if pd.notna(row[day_col]) else ""
                    slot_str = str(row[slot_col]).strip() if pd.notna(row[slot_col]) else ""
                    room = str(row[venue_col]).strip() if pd.notna(row[venue_col]) else ""
                    course_code = str(row[code_col]).strip() if pd.notna(row[code_col]) else "Unknown"
                    
                    if row_day.lower() in [d.lower() for d in DAYS] and room:
                        slot_hour = parse_time_to_hour(slot_str)
                        if slot_hour is not None:
                            key = (row_day.lower(), slot_hour, room)
                            occupancy[key] = course_code
            print("OK")
        except Exception as e:
            print(f"Error: {e}")
    
    return occupancy

def load_management_data_with_courses():
    """Load management timetable data with course information."""
    print("Loading Management timetable data with courses...")
    occupancy = {}
    
    try:
        print(f"  Reading {MANAGEMENT_SHEET}...", end=" ")
        df = pd.read_excel(MANAGEMENT_FILE, sheet_name=MANAGEMENT_SHEET, header=None)
        
        # Find the header row
        header_row = None
        for idx, row in df.iterrows():
            row_vals = [str(x).strip().lower() for x in row.tolist() if pd.notna(x)]
            if 'days' in row_vals and 'room' in row_vals:
                header_row = idx
                break
        
        if header_row is None:
            raise ValueError('Could not find header row in FSM timetable')
        
        # Build slot columns from header row
        slot_columns = []
        for col_idx, cell in enumerate(df.iloc[header_row].tolist()):
            if pd.notna(cell) and col_idx > 1:
                slot_hour = parse_time_to_hour(cell)
                if slot_hour is not None:
                    slot_columns.append((col_idx, slot_hour))
        
        current_day = None
        for idx in range(header_row + 1, len(df)):
            row = df.iloc[idx]
            day_cell = row[0]
            room_cell = row[1]
            
            if pd.notna(day_cell) and isinstance(day_cell, str):
                day_value = day_cell.strip().lower()
                if day_value.startswith('mon'):
                    current_day = 'Mon'
                elif day_value.startswith('tue'):
                    current_day = 'Tue'
                elif day_value.startswith('wed'):
                    current_day = 'Wed'
                elif day_value.startswith('thu'):
                    current_day = 'Thu'
                elif day_value.startswith('fri'):
                    current_day = 'Fri'
                elif day_value.startswith('sat'):
                    current_day = 'Sat'
            
            if current_day is None or pd.isna(room_cell):
                continue
            
            room_name = str(room_cell).strip()
            if not room_name:
                continue
            
            for col_idx, slot_hour in slot_columns:
                cell = row[col_idx]
                if pd.notna(cell):
                    content = str(cell).strip()
                    if content:
                        key = (current_day.lower(), slot_hour, room_name)
                        # Extract course code from cell content (usually first part before space/parenthesis)
                        course_info = content.split('(')[0].strip() if '(' in content else content
                        occupancy[key] = course_info[:30]  # Truncate for readability
        
        print("OK")
    except Exception as e:
        print(f"Error reading Management timetable: {e}")
    
    return occupancy

def get_all_rooms():
    """Load all rooms from CSV."""
    if not os.path.exists(ROOMS_CSV):
        print(f"Error: {ROOMS_CSV} not found.")
        return []
    
    df = pd.read_csv(ROOMS_CSV)
    return sorted(df['Room'].values.tolist())

def create_timetable_dataframe(occupancy_fsc, occupancy_fsm):
    """Create a DataFrame with rooms as rows and day+time as columns."""
    print("\nCreating timetable dataframe...")
    
    # Merge occupancy data
    occupancy = {**occupancy_fsc, **occupancy_fsm}
    
    # Get all unique rooms
    all_rooms = get_all_rooms()
    
    # Create column names for each day+hour combination
    column_names = []
    for day in DAYS:
        for hour in HOURS:
            column_names.append(f"{day}_{hour:02d}:00")
    
    # Initialize dataframe
    data = {}
    for room in all_rooms:
        row_data = []
        for day in DAYS:
            for hour in HOURS:
                key = (day.lower(), hour, room)
                # Get course name if occupied, otherwise empty
                course = occupancy.get(key, "")
                row_data.append(course)
        data[room] = row_data
    
    # Transpose so rooms are rows and time slots are columns
    df = pd.DataFrame(data).T
    df.columns = column_names
    df.index.name = "Room"
    
    return df

def main():
    print("=" * 70)
    print("EXTRACTING TIMETABLE DATA BY ROOM")
    print("=" * 70 + "\n")
    
    # Load occupancy with course information
    occupancy_fsc = load_computing_data_with_courses()
    occupancy_fsm = load_management_data_with_courses()
    
    print(f"\nTotal FSC occupancy entries: {len(occupancy_fsc)}")
    print(f"Total FSM occupancy entries: {len(occupancy_fsm)}")
    
    # Create timetable dataframe
    df_timetable = create_timetable_dataframe(occupancy_fsc, occupancy_fsm)
    
    print(f"\nTimetable shape: {df_timetable.shape[0]} rooms × {df_timetable.shape[1]} time slots")
    
    # Export to Excel
    output_path = os.path.join(os.path.dirname(__file__), '..', 'room_timetable.xlsx')
    df_timetable.to_excel(output_path)
    
    print(f"\n{'=' * 70}")
    print(f"Timetable exported to: {output_path}")
    print(f"{'=' * 70}\n")
    
    # Also show sample
    print("Sample (first 5 rooms, first 10 time slots):")
    print(df_timetable.iloc[:5, :10])

if __name__ == "__main__":
    main()
