# Shared campus configuration for navigator and visualiser

BUILDING_GRAPH = {
    "F-Block (New Building)": {"L-Block (Labs)": 10, "D-Block (Electrical/Management)": 15, "E-Block (Library)": 20},
    "L-Block (Labs)": {"F-Block (New Building)": 10, "D-Block (Electrical/Management)": 15},
    "D-Block (Electrical/Management)": {"L-Block (Labs)": 10, "F-Block (New Building)": 15,
                                        "E-Block (Library)": 10, "C-Block (Computing)": 10, "A-Block (Admin)": 15},
    "E-Block (Library)": {"D-Block (Electrical/Management)": 10, "B-Block (Civil)": 10, "F-Block (New Building)": 20},
    "B-Block (Civil)": {"E-Block (Library)": 10, "A-Block (Admin)": 10},
    "A-Block (Admin)": {"D-Block (Electrical/Management)": 15, "C-Block (Computing)": 10, "B-Block (Civil)": 10},
    "C-Block (Computing)": {"D-Block (Electrical/Management)": 10, "A-Block (Admin)": 10},
}

BUILDING_POS = {
    "F-Block (New Building)": (400, 100),
    "L-Block (Labs)": (300, 200),
    "D-Block (Electrical/Management)": (400, 300),
    "E-Block (Library)": (500, 200),
    "B-Block (Civil)": (600, 300),
    "A-Block (Admin)": (500, 400),
    "C-Block (Computing)": (400, 500),
}

STAIRS_CONFIG = {
    "F-Block (New Building)": [("F-201", "F-301"), ("F-210", "F-312")],
    "E-Block (Library)": [],
    "D-Block (Electrical/Management)": [("D-1", "D-11"), ("D-5", "D-17")],
    "C-Block (Computing)": [("C-1", "C-10"), ("C-9", "C-16")],
    "A-Block (Admin)": [],
    "L-Block (Labs)": [("Lab-1", "Lab-13"), ("Lab-8", "Lab-18")],
}
