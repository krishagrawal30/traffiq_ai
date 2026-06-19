"""
Agent 02 — Route Recommendation Agent

Monitors corridor-level congestion along Bengaluru's Silk Board corridor
and recommends traffic diversions when congestion thresholds are exceeded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

CORRIDOR_CONFIG = {
    "N-S Hosur Road Corridor": {
        "junctions": ["HSR_Layout", "Silk_Board", "Madiwala"],
        "primary_approach": "NS_Hosur_Road",
        "alternate_route": "NICE Road / Bannerghatta Road via Jayanagar",
        "congestion_capacity": 20,
    },
    "E-W ORR Corridor (Silk Board)": {
        "junctions": ["Silk_Board"],
        "primary_approach": "EW_ORR",
        "alternate_route": "Deve Gowda Road / KHB Colony Road",
        "congestion_capacity": 20,
    },
    "Bannerghatta Road Corridor": {
        "junctions": ["BTM_Layout", "Silk_Board"],
        "primary_approach": "SW_Bannerghatta",
        "alternate_route": "Jayanagar 4th Block / NICE Road",
        "congestion_capacity": 20,
    },
}

THRESHOLDS = [
    ("LOW", 0, 35, "No action required. Flow normal."),
    ("MODERATE", 35, 55, "Monitor closely. Pre-position adjacent signal capacity."),
    ("HIGH", 55, 75, "Activate diversions. Coordinate with Agent 01 for alternate green time."),
    ("CRITICAL", 75, 100, "IMMEDIATE DIVERSION. Notify city operators. Block corridor entry."),
]

@dataclass
class RouteRecommendation:
    corridor: str
    congestion_pct: float
    severity: str
    action: str
    alternate_route: str
    estimated_saving_s: float
    affected_junctions: list[str]

class RouteRecommenderAgent:
    def __init__(self):
        self._history: dict[str, list[float]] = {c: [] for c in CORRIDOR_CONFIG}
        self._decision_log: list[str] = []

    def analyse(self, signal_states: list[dict]) -> list[RouteRecommendation]:
        state_map = {s["name"]: s for s in signal_states}
        recs: list[RouteRecommendation] = []

        for corridor, config in CORRIDOR_CONFIG.items():
            queues = []
            for j_name in config["junctions"]:
                s = state_map.get(j_name)
                if not s:
                    continue
                approach = config["primary_approach"]
                if approach == "NS_Hosur_Road" or approach == "NS_Bannerghatta":
                    q = s.get("ns_queue", 0)
                elif approach == "EW_ORR":
                    q = s.get("ew_queue", 0)
                elif approach == "SW_Bannerghatta":
                    q = s.get("sw_queue", 0)
                else:
                    q = 0
                queues.append(q)

            if not queues:
                continue

            avg_queue = sum(queues) / len(queues)
            capacity = config["congestion_capacity"]
            congestion = min(100.0, avg_queue / capacity * 100)
            self._history[corridor].append(congestion)
            if len(self._history[corridor]) > 300:
                self._history[corridor].pop(0)

            severity, action = self._classify(congestion)
            saving = self._estimate_saving(severity)

            rec = RouteRecommendation(
                corridor=corridor,
                congestion_pct=round(congestion, 1),
                severity=severity,
                action=action,
                alternate_route=config["alternate_route"],
                estimated_saving_s=saving,
                affected_junctions=config["junctions"],
            )
            self._decision_log.append(
                f"[{corridor}] Congestion {congestion:.0f}% → {severity}. {action[:50]}"
            )
            recs.append(rec)
        return recs

    def _classify(self, congestion: float) -> tuple[str, str]:
        for level, lo, hi, base_action in THRESHOLDS:
            if lo <= congestion < hi:
                if level in ("HIGH", "CRITICAL"):
                    corridor_info = next(
                        (c for c, v in CORRIDOR_CONFIG.items()
                         if self._history.get(c, []) and self._history[c][-1] == congestion),
                        ""
                    )
                    alt = CORRIDOR_CONFIG.get(corridor_info, {}).get("alternate_route", "alternate route")
                    action = base_action + f" Recommend: {alt}"
                else:
                    action = base_action
                return level, action
        return "CRITICAL", "IMMEDIATE DIVERSION. All approaches congested."

    @staticmethod
    def _estimate_saving(severity: str) -> float:
        savings = {"LOW": 0, "MODERATE": 5, "HIGH": 18, "CRITICAL": 35}
        return float(savings.get(severity, 0))

    def get_log(self) -> list[str]:
        return self._decision_log[-20:]
