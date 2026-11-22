"""
Road graph and vehicle-aware routing.
Uses a hand-crafted demo graph that maps to real Bengaluru coordinates
so it renders meaningfully on the Leaflet map.

Node layout (approximate lat/lon):
  A = Silk Board (origin cluster)
  B = Koramangala (bottleneck junction)
  C = BTM Layout (alternate corridor)
  D = HSR Layout (common destination)
  E = Jayanagar (bypass)

Edges encode:
  - distance_m      : metres
  - lanes           : number of lanes
  - max_width_m     : narrowest point (affects truck routing)
  - max_height_m    : bridge/underpass clearance
  - max_weight_ton  : bridge weight limit
  - speed_limit_kmh : posted limit
"""

import math
import networkx as nx
from traffic_state import state_store

# ------------------------------------------------------------------
# Node coordinates  (lat, lon)
# ------------------------------------------------------------------
NODES = {
    "A": (12.9176, 77.6227),  # Silk Board
    "B": (12.9352, 77.6245),  # Koramangala
    "C": (12.9165, 77.6101),  # BTM Layout
    "D": (12.9116, 77.6413),  # HSR Layout
    "E": (12.9255, 77.5934),  # Jayanagar
}

# ------------------------------------------------------------------
# Edge definitions
# ------------------------------------------------------------------
EDGES = [
    # (from, to, attrs)
    ("A", "B", {"distance_m": 2100, "lanes": 3, "max_width_m": 7.5,
                 "max_height_m": 5.5, "max_weight_ton": 40, "speed_limit_kmh": 50}),
    ("A", "C", {"distance_m": 1800, "lanes": 2, "max_width_m": 6.0,
                 "max_height_m": 4.2, "max_weight_ton": 20, "speed_limit_kmh": 40}),
    ("B", "D", {"distance_m": 2500, "lanes": 4, "max_width_m": 10.0,
                 "max_height_m": 5.5, "max_weight_ton": 40, "speed_limit_kmh": 60}),
    ("C", "D", {"distance_m": 2800, "lanes": 2, "max_width_m": 5.5,
                 "max_height_m": 3.8, "max_weight_ton": 15, "speed_limit_kmh": 40}),
    ("B", "E", {"distance_m": 3100, "lanes": 2, "max_width_m": 6.0,
                 "max_height_m": 4.5, "max_weight_ton": 25, "speed_limit_kmh": 50}),
    ("E", "D", {"distance_m": 2700, "lanes": 2, "max_width_m": 6.5,
                 "max_height_m": 5.0, "max_weight_ton": 25, "speed_limit_kmh": 50}),
]

# ------------------------------------------------------------------
# Vehicle profiles
# ------------------------------------------------------------------
VEHICLE_PROFILES = {
    "car":        {"width_m": 2.0, "height_m": 1.5, "weight_ton": 1.5,  "pcu": 1.0},
    "suv":        {"width_m": 2.2, "height_m": 1.8, "weight_ton": 2.5,  "pcu": 1.0},
    "motorcycle": {"width_m": 0.9, "height_m": 1.2, "weight_ton": 0.3,  "pcu": 0.5},
    "auto":       {"width_m": 1.4, "height_m": 1.8, "weight_ton": 0.6,  "pcu": 1.2},
    "bus":        {"width_m": 2.5, "height_m": 3.8, "weight_ton": 12.0, "pcu": 3.0},
    "truck":      {"width_m": 2.6, "height_m": 4.2, "weight_ton": 18.0, "pcu": 2.5},
    "minivan":    {"width_m": 2.1, "height_m": 2.1, "weight_ton": 2.8,  "pcu": 1.2},
}


def _travel_time_seconds(edge_attrs: dict, segment_id: str, vehicle_type: str) -> float | None:
    """
    Compute traversal cost for a vehicle on a segment.
    Returns None if the vehicle is physically restricted from using this edge.
    """
    vp = VEHICLE_PROFILES.get(vehicle_type, VEHICLE_PROFILES["car"])

    # Hard restrictions — vehicle cannot use this edge
    if vp["width_m"] > edge_attrs["max_width_m"] * 0.95:
        return None   # too wide
    if vp["height_m"] > edge_attrs["max_height_m"]:
        return None   # height restriction
    if vp["weight_ton"] > edge_attrs["max_weight_ton"]:
        return None   # weight limit

    dist = edge_attrs["distance_m"]
    limit = edge_attrs["speed_limit_kmh"]

    # Live congestion from traffic state
    seg = state_store.get_segment(segment_id)
    effective_speed = min(limit, max(5.0, seg.avg_speed_kmh))

    # Size penalty — wider vehicle on narrower road is slower
    width_ratio = vp["width_m"] / edge_attrs["max_width_m"]
    size_penalty = 1.0 + max(0.0, width_ratio - 0.5)   # penalty kicks in above 50% width use

    # PCU congestion factor
    pcu_load = seg.density * vp["pcu"]
    congestion_factor = 1.0 + pcu_load * 0.8

    travel_time = (dist / 1000.0) / effective_speed * 3600  # seconds
    return travel_time * size_penalty * congestion_factor


def build_graph(vehicle_type: str) -> nx.DiGraph:
    """Build a directed graph with costs specific to the given vehicle type."""
    G = nx.DiGraph()
    for node, coords in NODES.items():
        G.add_node(node, pos=coords)

    for u, v, attrs in EDGES:
        seg_id = f"{u}-{v}"
        cost = _travel_time_seconds(attrs, seg_id, vehicle_type)
        if cost is not None:
            G.add_edge(u, v, weight=cost, segment_id=seg_id, **attrs)
        # reverse direction (bidirectional roads)
        seg_id_rev = f"{v}-{u}"
        cost_rev = _travel_time_seconds(attrs, seg_id_rev, vehicle_type)
        if cost_rev is not None:
            G.add_edge(v, u, weight=cost_rev, segment_id=seg_id_rev, **attrs)

    return G


def get_route(origin: str, destination: str, vehicle_type: str) -> dict:
    """
    Returns the shortest vehicle-valid path and estimated travel time.
    """
    G = build_graph(vehicle_type)
    try:
        path = nx.shortest_path(G, source=origin, target=destination, weight="weight")
        total_time = sum(
            G[path[i]][path[i + 1]]["weight"] for i in range(len(path) - 1)
        )
        segments = [G[path[i]][path[i + 1]]["segment_id"] for i in range(len(path) - 1)]
        coords = [NODES[n] for n in path]
        return {
            "path": path,
            "segments": segments,
            "coords": coords,
            "eta_seconds": round(total_time),
            "eta_minutes": round(total_time / 60, 1),
            "valid": True,
        }
    except nx.NetworkXNoPath:
        return {"valid": False, "reason": f"No valid route for {vehicle_type}"}


def get_k_routes(origin: str, destination: str, vehicle_type: str, k: int = 3) -> list:
    """Return up to k shortest valid paths for use by the allocator."""
    G = build_graph(vehicle_type)
    try:
        paths = list(nx.shortest_simple_paths(G, origin, destination, weight="weight"))
        result = []
        for path in paths[:k]:
            total_time = sum(
                G[path[i]][path[i + 1]]["weight"] for i in range(len(path) - 1)
            )
            segments = [G[path[i]][path[i + 1]]["segment_id"] for i in range(len(path) - 1)]
            coords = [NODES[n] for n in path]
            result.append({
                "path": path,
                "segments": segments,
                "coords": coords,
                "eta_seconds": round(total_time),
                "eta_minutes": round(total_time / 60, 1),
                "valid": True,
            })
        return result
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def node_coords() -> dict:
    """Return all node coordinates for the frontend map."""
    return {n: {"lat": lat, "lon": lon} for n, (lat, lon) in NODES.items()}
