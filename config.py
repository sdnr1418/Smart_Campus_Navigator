# Shared campus configuration for navigator and visualiser
#
# Corrections vs v1:
#   Seminar Hall → C-Block (was D-Block)
#   CRMG         → B-Block (was D-Block)
#   Old Audi     → D-Block (was C-Block)
#   Embedded Lab → B-Block (was E-Block)
#   Eng Lab-*    → E-Block (English Labs)
#   Micro Lab    → D-Block
#   Physics Lab  → D-Block

BUILDING_GRAPH = {
    "F-Block (New Building)":          {"L-Block (Labs)": 10, "D-Block (Electrical/Management)": 15, "E-Block (English Labs)": 20},
    "L-Block (Labs)":                  {"F-Block (New Building)": 10, "D-Block (Electrical/Management)": 15},
    "D-Block (Electrical/Management)": {"L-Block (Labs)": 10, "F-Block (New Building)": 15,
                                        "E-Block (English Labs)": 10, "C-Block (Computing)": 10, "A-Block (Admin)": 15},
    "E-Block (English Labs)":          {"D-Block (Electrical/Management)": 10, "B-Block (Civil)": 10, "F-Block (New Building)": 20},
    "B-Block (Civil)":                 {"E-Block (English Labs)": 10, "A-Block (Admin)": 10},
    "A-Block (Admin)":                 {"D-Block (Electrical/Management)": 15, "C-Block (Computing)": 10, "B-Block (Civil)": 10},
    "C-Block (Computing)":             {"D-Block (Electrical/Management)": 10, "A-Block (Admin)": 10},
}

BUILDING_POS = {
    "F-Block (New Building)":          (400, 100),
    "L-Block (Labs)":                  (300, 200),
    "D-Block (Electrical/Management)": (400, 300),
    "E-Block (English Labs)":          (500, 200),
    "B-Block (Civil)":                 (600, 300),
    "A-Block (Admin)":                 (500, 400),
    "C-Block (Computing)":             (400, 500),
}

STAIRS_CONFIG = {
    "F-Block (New Building)":          [("F-201", "F-301"), ("F-210", "F-312")],
    "E-Block (English Labs)":          [],
    "D-Block (Electrical/Management)": [("D-1",   "D-11"),  ("D-5",   "D-17")],
    "C-Block (Computing)":             [("C-1",   "C-10"),  ("C-9",   "C-16")],
    "A-Block (Admin)":                 [],
    "L-Block (Labs)":                  [("Lab-1", "Lab-13"), ("Lab-8", "Lab-18")],
    "B-Block (Civil)":                 [],
}

# Canonical room → building lookup (generated from 1_extract_rooms.py output)
# Useful for quick classification without re-running the extractor.
ROOM_BLOCK = {
    # A-Block
    "A-4": "A-Block (Admin)", "A-7": "A-Block (Admin)",
    # B-Block
    "CRMG": "B-Block (Civil)", "Embedded Lab": "B-Block (Civil)",
    # C-Block
    **{f"C-{n}": "C-Block (Computing)" for n in
       [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]},
    "Seminar Hall": "C-Block (Computing)",
    "Old Audi":     "D-Block (Electrical/Management)",   # D-Block, not C
    # D-Block
    **{f"D-{n}": "D-Block (Electrical/Management)" for n in
       [1,2,3,4,5,11,12,13,14,15,16,17]},
    "Micro Lab":   "D-Block (Electrical/Management)",
    "Physics Lab": "D-Block (Electrical/Management)",
    # E-Block (English Labs)
    **{f"Eng Lab-{n}": "E-Block (English Labs)" for n in range(1, 7)},
    # F-Block
    **{f"F-{n}": "F-Block (New Building)" for n in
       [201,202,203,204,205,206,207,208,209,210,
        301,302,303,304,305,306,307,308,309,310,311,312]},
    # L-Block
    **{f"Lab-{n}": "L-Block (Labs)" for n in
       [1,2,3,4,6,7,8,13,14,15,16,17,18]},
}
