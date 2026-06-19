"""
Agent 03 — Emergency Priority Agent

Detects emergency vehicles on the Bengaluru Silk Board corridor,
calculates optimal green corridor path, and preemptively overrides
signals along the route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from simulation.topology import ROAD_SEGMENTS

class EmergencyStatus(str, Enum):
    STANDBY = "STANDBY"
    DETECTED = "DETECTED"
    CORRIDOR_ACTIVE = "CORRIDOR_ACTIVE"
    RESOLVED = "RESOLVED"

JUNCTION_GRAPH = {
    "HSR_Layout": ["Silk_Board"],
    "Silk_Board": ["HSR_Layout", "Madiwala", "BTM_Layout"],
    "Madiwala": ["Silk_Board"],
    "BTM_Layout": ["Silk_Board"],
}

PRIORITY_MAP = {"ambulance": 100, "fire": 90, "police": 80}
ETA_THRESHOLD_S = 15.0

@dataclass
class EmergencyEvent:
    vehicle_id: int
    vehicle_type: str
    entry_junction: str
    entry_approach: str
    corridor_path: list[str]
    detected_at_s: float
    cleared_at_s: Optional[float] = None
    response_time_s: float = 0.0
    clearance_time_s: float = 0.0
    priority: int = 100
    explanation: str = ""
    time_saved: float = 0.0

class EmergencyPriorityAgent:
    def __init__(self):
        self.status = EmergencyStatus.STANDBY
        self.current_event: Optional[EmergencyEvent] = None
        self.event_log: list[EmergencyEvent] = []
        self.decision_log: list[str] = []
        self.emergency_eta: float = 0.0

    def detect(self, sim, vehicle_type: str = "ambulance",
               entry_junction: str = "HSR_Layout",
               entry_approach: str = "NS_Hosur_Road") -> EmergencyEvent:
        self.status = EmergencyStatus.DETECTED
        vehicle_type = vehicle_type.lower()
        priority = PRIORITY_MAP.get(vehicle_type, 100)

        route = self._find_route(entry_junction)
        if not route:
            route = [entry_junction]

        congestion_data = self._measure_corridor_congestion(sim, route)
        explanation = self._generate_explanation(vehicle_type, route, congestion_data)

        event = EmergencyEvent(
            vehicle_id=sim.dispatch_emergency(entry_junction, entry_approach, vehicle_type),
            vehicle_type=vehicle_type,
            entry_junction=entry_junction,
            entry_approach=entry_approach,
            corridor_path=route,
            detected_at_s=sim.time_s,
            priority=priority,
            explanation=explanation,
            time_saved=congestion_data["time_saved"],
        )
        self.current_event = event
        self.emergency_eta = congestion_data["estimated_time_s"]
        self.status = EmergencyStatus.CORRIDOR_ACTIVE

        self.decision_log.append(
            f"CORRIDOR ACTIVE — {vehicle_type.upper()} #{event.vehicle_id} from "
            f"{entry_junction}. Path: {' → '.join(route)}. ETA: {self.emergency_eta:.0f}s."
        )
        return event

    def poll(self, sim):
        if self.status != EmergencyStatus.CORRIDOR_ACTIVE:
            return
        if not self.current_event:
            return

        emerg_vehicles = [v for v in sim.vehicles if v.is_emergency and v.vid == self.current_event.vehicle_id]
        if not emerg_vehicles:
            self._resolve(sim)
            return

        v = emerg_vehicles[0]
        remaining = v.route[v.route.index(v.junction):] if v.junction in v.route else v.route

        for node in remaining:
            sig = sim.signals.get(node)
            if sig:
                sig.override = True
                sig.corridor_phase = self._required_phase(node, remaining)
                sig.override_priority = self.current_event.priority

        self.current_event.corridor_path = remaining
        self.emergency_eta = len(remaining) * 8.0

    def _resolve(self, sim):
        self.status = EmergencyStatus.RESOLVED
        if self.current_event:
            self.current_event.cleared_at_s = sim.time_s
            self.current_event.clearance_time_s = sim.time_s - self.current_event.detected_at_s
            self.event_log.append(self.current_event)
            self.decision_log.append(
                f"RESOLVED — {self.current_event.vehicle_type.upper()} cleared "
                f"in {self.current_event.clearance_time_s:.1f}s."
            )
        sim.release_corridor()
        self.current_event = None
        self.emergency_eta = 0.0
        self.status = EmergencyStatus.STANDBY

    @staticmethod
    def _find_route(start: str) -> list[str]:
        if start == "HSR_Layout":
            return ["HSR_Layout", "Silk_Board", "Madiwala"]
        if start == "BTM_Layout":
            return ["BTM_Layout", "Silk_Board"]
        if start == "Madiwala":
            return ["Madiwala", "Silk_Board"]
        return [start]

    def _measure_corridor_congestion(self, sim, route: list[str]) -> dict:
        total_queue = 0
        num_queues = 0
        for node in route:
            sig = sim.signals.get(node)
            if sig:
                total_queue += sig.ns_queue + sig.ew_queue + sig.sw_queue + sig.ne_queue
                num_queues += 1
        avg_queue = total_queue / max(num_queues, 1)
        clearance_delay = avg_queue * 2.0
        free_flow_time = len(route) * 6.0
        standard_time = len(route) * 25.0 + avg_queue * 5.0
        estimated_time_s = free_flow_time + clearance_delay
        return {
            "avg_queue": avg_queue,
            "estimated_time_s": estimated_time_s,
            "standard_time": standard_time,
            "time_saved": max(0, standard_time - estimated_time_s),
        }

    @staticmethod
    def _required_phase(node: str, route: list[str]) -> SignalPhase:
        from simulation.engine import SignalPhase as SP
        try:
            idx = route.index(node)
            if idx < len(route) - 1:
                next_node = route[idx + 1]
                if next_node in ("Madiwala", "HSR_Layout"):
                    return SP.NS
                return SP.EW
        except ValueError:
            pass
        return SP.NS

    @staticmethod
    def _generate_explanation(vehicle_type: str, route: list[str],
                               congestion: dict) -> str:
        route_str = " → ".join(route)
        return (
            f"Green corridor activated for {vehicle_type.capitalize()}. "
            f"Route: {route_str}. "
            f"Estimated clearance: {congestion['estimated_time_s']:.0f}s "
            f"(saves {congestion['time_saved']:.0f}s vs standard traffic)."
        )

    def resolve_manually(self, sim):
        self._resolve(sim)

    def format_summary(self) -> str:
        if not self.event_log:
            return "No emergency events recorded."
        e = self.event_log[-1]
        return (
            f"Last: {e.vehicle_type} #{e.vehicle_id} | "
            f"Entry: {e.entry_junction} | "
            f"Response: {e.response_time_s:.1f}s | "
            f"Clearance: {e.clearance_time_s:.1f}s"
        )
