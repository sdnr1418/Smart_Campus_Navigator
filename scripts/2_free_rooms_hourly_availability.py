"""
Analyze and plot free room availability by hour for each day.
Creates histograms showing which hours have most/least free rooms.
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta
import numpy as np

# Get paths
TIMETABLES_DIR = os.path.join(os.path.dirname(__file__), '..', 'TimeTables')
ROOMS_CSV = os.path.join(os.path.dirname(__file__), '..', 'all_rooms.csv')

COMPUTING_FILE = os.path.join(TIMETABLES_DIR, "FSC TT Spring 2026 v1.3.xlsx")
COMPUTING_SHEETS = ["CS", "DS", "SE", "AI", "CY"]

MANAGEMENT_FILE = os.path.join(TIMETABLES_DIR, "Spring_26 FSM Time Table (1.0).xlsx")
MANAGEMENT_SHEET = "19-Mar-26; 3.40 pm"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Cache for Excel data
_computing_cache = {}

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
    # Remove punctuation from AM/PM formatting like P.M.
    slot = slot.replace('.', '').replace('a m', ' AM').replace('p m', ' PM')
    if 'to' in slot.lower():
        slot = slot.lower().split('to')[0].strip()
    for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p", "%I %p"]:
        try:
            return datetime.strptime(slot, fmt).hour
        except ValueError:
            continue
    return None

def load_computing_data():
    """Load all computing timetable data into cache."""
    global _computing_cache
    
    if _computing_cache:
        return _computing_cache
    
    print("Loading Computing timetable data...")
    occupancy = {}  # {(day, hour): {rooms}}
    
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
                
                if day_col not in df.columns or slot_col not in df.columns or venue_col not in df.columns:
                    continue
                
                for _, row in df.iterrows():
                    row_day = str(row[day_col]).strip() if pd.notna(row[day_col]) else ""
                    slot_str = str(row[slot_col]).strip() if pd.notna(row[slot_col]) else ""
                    room = str(row[venue_col]).strip() if pd.notna(row[venue_col]) else ""
                    
                    if row_day.lower() in [d.lower() for d in DAYS] and room:
                        slot_hour = parse_time_to_hour(slot_str)
                        if slot_hour is not None:
                            key = (row_day.lower(), slot_hour)
                            if key not in occupancy:
                                occupancy[key] = set()
                            occupancy[key].add(room)
            print("OK")
        except Exception as e:
            print(f"Error: {e}")
    
    _computing_cache = occupancy
    return occupancy

def load_management_data():
    """Load all management timetable data."""
    print("Loading Management timetable data...")
    occupancy = {}  # {(day, hour): {rooms}}
    
    try:
        print(f"  Reading {MANAGEMENT_SHEET}...", end=" ")
        df = pd.read_excel(MANAGEMENT_FILE, sheet_name=MANAGEMENT_SHEET, header=None)
        
        # Find the header row containing Days/Room/time slots
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
                        key = (current_day.lower(), slot_hour)
                        occupancy.setdefault(key, set()).add(room_name)
        
        print("OK")
    except Exception as e:
        print(f"Error reading Management timetable: {e}")
    
    return occupancy

def get_all_rooms():
    """Load all rooms from CSV."""
    if not os.path.exists(ROOMS_CSV):
        print(f"Error: {ROOMS_CSV} not found.")
        return set()
    
    df = pd.read_csv(ROOMS_CSV)
    return set(df['Room'].values)

def get_free_rooms_by_hour(day, hour, occupancy, all_rooms):
    """Get count of free rooms at a given day and hour."""
    key = (day.lower(), hour)
    occupied = occupancy.get(key, set())
    free_count = len(all_rooms) - len(occupied)
    return free_count

def main():
    print("=" * 70)
    print("ROOM AVAILABILITY ANALYSIS - HOURLY HISTOGRAM")
    print("=" * 70 + "\n")
    
    # Get all rooms for reference
    print("Loading rooms data...")
    all_rooms = get_all_rooms()
    total_rooms = len(all_rooms)
    print(f"Total unique rooms: {total_rooms}\n")
    
    # Load occupancy data from BOTH departments
    occupancy_fsc = load_computing_data()
    occupancy_fsm = load_management_data()
    print()
    
    # Merge occupancy data
    occupancy = {}
    for key in set(list(occupancy_fsc.keys()) + list(occupancy_fsm.keys())):
        occupancy[key] = occupancy_fsc.get(key, set()) | occupancy_fsm.get(key, set())
    
    # Define hour range (8 AM to 8 PM)
    hours = list(range(8, 21))  # 8:00 to 20:00
    hour_labels = [f"{h:02d}:00" for h in hours]
    
    # Collect data for each day
    print("Creating visualization...")
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    fig.suptitle('Free Rooms by Hour - Computing & Management Departments', fontsize=16, fontweight='bold')
    
    axes_flat = axes.flatten()
    
    for day_idx, day in enumerate(DAYS):
        print(f"Processing {day}...", end=" ")
        free_counts = []
        
        for hour in hours:
            free_count = get_free_rooms_by_hour(day, hour, occupancy, all_rooms)
            free_counts.append(free_count)
        
        # Plot
        ax = axes_flat[day_idx]
        bars = ax.bar(hour_labels, free_counts, color='steelblue', edgecolor='navy', alpha=0.7, width=0.6)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontsize=9)
        
        # Formatting
        ax.set_title(f'{day.upper()}', fontsize=12, fontweight='bold')
        ax.set_xlabel('Time', fontsize=10)
        ax.set_ylabel('Free Rooms', fontsize=10)
        ax.set_ylim(0, total_rooms + 5)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_xticklabels(hour_labels, rotation=45, ha='right', fontsize=9)
        
        # Add average line
        avg_free = np.mean(free_counts)
        ax.axhline(y=avg_free, color='red', linestyle='--', linewidth=2, alpha=0.6, label=f'Avg: {avg_free:.1f}')
        ax.legend(fontsize=9)
        
        # Print data
        print("\n")
        print(f"  {day.upper()}:")
        print(f"  {'Hour':<10} {'Free Rooms':<15} {'Percentage':<15}")
        print(f"  {'-'*40}")
        for hour, free_count in zip(hour_labels, free_counts):
            percentage = (free_count / total_rooms * 100)
            print(f"  {hour:<10} {free_count:<15} {percentage:>6.1f}%")
        
        min_free = min(free_counts)
        max_free = max(free_counts)
        avg_free = np.mean(free_counts)
        print(f"  {'-'*40}")
        print(f"  Min: {min_free}, Max: {max_free}, Avg: {avg_free:.1f}\n")
    
    # Hide the 6th subplot (we only have 6 days)
    axes_flat[5].axis('off')
    
    plt.tight_layout()
    
    # Save figure
    output_path = os.path.join(os.path.dirname(__file__), '..', 'room_availability_histogram.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"{'=' * 70}")
    print(f"Histogram saved to: {output_path}")
    print(f"{'=' * 70}\n")
    plt.close()

if __name__ == "__main__":
    main()
