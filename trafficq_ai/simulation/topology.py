"""
Bengaluru Silk Board Corridor — Road Network Topology

Models the Silk Board junction (12.9180°N, 77.6228°E) and 3 surrounding
signalized junctions forming the most congested traffic corridor in Bengaluru.

Junctions
---------
Silk_Board  : 4-arm intersection (Hosur Rd NS, ORR EW, Bannerghatta SW)
Madiwala    : 2-arm intersection (Hosur Rd NS x BC Road) — 2 km north
HSR_Layout  : 2-arm intersection (Hosur Rd NS x HSR Sector 1) — 1.2 km south
BTM_Layout  : 2-arm intersection (Bannerghatta NS x BTM Main) — 1.5 km SW
"""

JUNCTION_COORDS = {
    "Silk_Board":  (12.9180, 77.6228),
    "Madiwala":    (12.9330, 77.6200),
    "HSR_Layout":  (12.9080, 77.6240),
    "BTM_Layout":  (12.9080, 77.6100),
}

JUNCTION_APPROACHES = {
    "Silk_Board": ["NS_Hosur_Road", "EW_ORR", "SW_Bannerghatta", "NE_Central_Silk_Board"],
    "Madiwala":    ["NS_Hosur_Road", "EW_BC_Road"],
    "HSR_Layout":  ["NS_Hosur_Road", "EW_HSR_Sector1"],
    "BTM_Layout":  ["NS_Bannerghatta", "EW_BTM_Main"],
}

ROAD_SEGMENTS = [
    {"from_junction": "HSR_Layout",  "to_junction": "Silk_Board", "road": "Hosur_Road",  "dir": "NS", "dist_km": 1.2, "lanes": 3},
    {"from_junction": "Silk_Board",  "to_junction": "Madiwala",   "road": "Hosur_Road",  "dir": "NS", "dist_km": 2.0, "lanes": 3},
    {"from_junction": "BTM_Layout",  "to_junction": "Silk_Board", "road": "Bannerghatta","dir": "SW", "dist_km": 1.5, "lanes": 2},
]

class Junction:
    __slots__ = ("name", "lat", "lon", "approaches", "incoming_roads", "outgoing_roads")
    def __init__(self, name: str):
        self.name = name
        self.lat, self.lon = JUNCTION_COORDS[name]
        self.approaches = JUNCTION_APPROACHES[name]
        self.incoming_roads: list[RoadSegment] = []
        self.outgoing_roads: list[RoadSegment] = []

class RoadSegment:
    def __init__(self, from_junction=None, to_junction=None, road=None, dir=None, dist_km=None, lanes=None, **kwargs):
        self.from_junction = from_junction
        self.to_junction = to_junction
        self.road_name = road
        self.direction = dir
        self.dist_km = dist_km
        self.lanes = lanes

def build_topology() -> dict[str, Junction]:
    junctions = {name: Junction(name) for name in JUNCTION_COORDS}
    segments = []
    for rs in ROAD_SEGMENTS:
        seg = RoadSegment(**rs)
        segments.append(seg)
        junctions[rs["from_junction"]].outgoing_roads.append(seg)
        junctions[rs["to_junction"]].incoming_roads.append(seg)
    return junctions
