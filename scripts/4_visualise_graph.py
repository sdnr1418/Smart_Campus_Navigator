"""
Visualise FAST Campus graphs using NetworkX + Plotly.
- Building graph: manual positions, edge weight labels.
- Room graphs: corridors (adjacent rooms, cost 1) + user-defined stairs (cost 5) per building.
- Nodes aligned by floor (same Y for same floor).
"""

import networkx as nx
import pandas as pd
import re
import os
from collections import defaultdict
import plotly.graph_objects as go
import sys

# import shared config
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
from config import BUILDING_GRAPH, BUILDING_POS, STAIRS_CONFIG

# ============================================================
# LOAD ROOMS INFO
# ============================================================
def load_rooms(csv_path="rooms_complete.csv"):
    df = pd.read_csv(csv_path)
    rooms_info = {}
    for _, row in df.iterrows():
        room = row["Room"].strip()
        building = row["Building"].strip()
        floor = int(row["floor_number"])
        rooms_info[room] = {"building": building, "floor": floor}
    return rooms_info

# ============================================================
# BUILDING GRAPH (loaded from shared config)
# ============================================================
def build_building_graph():
    G = nx.Graph()
    for node, neighbors in BUILDING_GRAPH.items():
        for neigh, weight in neighbors.items():
            G.add_edge(node, neigh, weight=weight)
    return G

# ============================================================
# ROOM GRAPH: Corridors + User-defined stairs
# ============================================================
def get_room_number(room):
    match = re.search(r'-(\d+)', room)
    return int(match.group(1)) if match else 0

# Stairs config is loaded from shared `config.py` as `STAIRS_CONFIG`

def build_room_graph(building, rooms_info):
    rooms = [r for r, info in rooms_info.items() if info["building"] == building]
    if not rooms:
        return nx.Graph()
    G = nx.Graph()
    for r in rooms:
        G.add_node(r, floor=rooms_info[r]["floor"])
    
    # Group rooms by floor for corridors
    floor_rooms = defaultdict(list)
    for r in rooms:
        fl = rooms_info[r]["floor"]
        floor_rooms[fl].append(r)
    for fl in floor_rooms:
        floor_rooms[fl].sort(key=get_room_number)
    
    # Corridors (adjacent rooms on same floor, cost 1)
    for fl, rlist in floor_rooms.items():
        for i in range(len(rlist)-1):
            r1, r2 = rlist[i], rlist[i+1]
            G.add_edge(r1, r2, weight=1, type="corridor")
    
    # User-defined stairs (cost 5)
    if building in STAIRS_CONFIG:
        for r1, r2 in STAIRS_CONFIG[building]:
            # only add if both rooms exist in this building
            if r1 in G and r2 in G:
                G.add_edge(r1, r2, weight=5, type="stairs")
    return G

def compute_room_positions(G):
    """Place rooms: same floor = same Y, ordered by room number along X."""
    floor_nodes = defaultdict(list)
    for node, attr in G.nodes(data=True):
        floor = attr.get("floor", 0)
        floor_nodes[floor].append(node)
    for fl in floor_nodes:
        floor_nodes[fl].sort(key=get_room_number)
    pos = {}
    x_step = 180
    y_step = 150
    for fl, nodes in floor_nodes.items():
        y = (fl - 1) * y_step + 50   # floor 1 at y=50
        for i, node in enumerate(nodes):
            x = 100 + i * x_step
            pos[node] = (x, y)
    return pos

# ============================================================
# PLOTLY VISUALISATION
# ============================================================
def plot_graph(G, title, filename, pos, node_attr=None):
    node_x, node_y, node_text = [], [], []
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        label = node
        if node_attr and node_attr in G.nodes[node]:
            label = f"{node}<br>(floor {G.nodes[node][node_attr]})"
        node_text.append(label)
    
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition="top center",
        hoverinfo='text',
        marker=dict(size=20, color='lightblue', line=dict(color='darkblue', width=1)),
        textfont=dict(size=10)
    )
    
    edge_traces = []
    annotations = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        weight = data.get("weight", 1)
        etype = data.get("type", "")
        hover_text = f"{u} → {v}<br>{etype}<br>cost = {weight}"
        edge_trace = go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode='lines',
            line=dict(width=2, color='gray'),
            hoverinfo='text',
            text=hover_text,
            opacity=0.7
        )
        edge_traces.append(edge_trace)
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        annotations.append(dict(
            x=mid_x, y=mid_y,
            text=str(weight),
            showarrow=False,
            font=dict(size=12, color="red"),
            bgcolor="white",
            borderpad=2
        ))
    
    fig = go.Figure(data=edge_traces + [node_trace],
                    layout=go.Layout(
                        title=title,
                        showlegend=False,
                        hovermode='closest',
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        width=1100, height=800,
                        margin=dict(l=50, r=50, t=80, b=50),
                        annotations=annotations
                    ))
    fig.write_html(filename)
    print(f"Saved {filename}")

def safe_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).replace(" ", "_")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    rooms_info = load_rooms()
    output_dir = "University_Graph"
    os.makedirs(output_dir, exist_ok=True)
    
    # Building graph
    G_build = build_building_graph()
    plot_graph(
        G_build,
        "FAST Campus - Building Graph",
        os.path.join(output_dir, "building_graph.html"),
        pos=BUILDING_POS,
    )
    
    # Room graphs per building
    buildings = set(info["building"] for info in rooms_info.values())
    for building in buildings:
        G_room = build_room_graph(building, rooms_info)
        if G_room.number_of_nodes() == 0:
            continue
        positions = compute_room_positions(G_room)
        safe_name = safe_filename(building)
        plot_graph(
            G_room,
            f"Room Graph - {building}",
            os.path.join(output_dir, f"room_graph_{safe_name}.html"),
            pos=positions,
            node_attr="floor",
        )
    
    print(f"All graphs saved in: {output_dir}")