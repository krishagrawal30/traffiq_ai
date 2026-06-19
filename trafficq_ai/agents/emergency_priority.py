"""
TRAFFICQ AI — Agent 03: Emergency Priority (Upgraded)
Detects emergency vehicles, calculates the fastest dynamic route,
predictively overrides signal phases based on priority ETAs, and resolves
intersections node-by-node.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from simulation.engine import LANE_DEFS, SignalPhase

# ─── Types ────────────────────────────────────────────────────────────────────

class EmergencyStatus(str, Enum):
    STANDBY  = "STANDBY"
    DETECTED = "DETECTED"
    CORRIDOR = "CORRIDOR_ACTIVE"
    CLEARING = "CLEARING"
    RESOLVED = "RESOLVED"


@dataclass
class EmergencyEvent:
    vehicle_id: int
    vehicle_type: str            # "ambulance" | "fire" | "police"
    entry_lane: str              # which lane the vehicle enters from
    detected_at_s: float         # simulation time of detection
    cleared_at_s: Optional[float] = None
    corridor_intersections: List[str] = field(default_factory=list)
    response_time_s: float = 0.0   # seconds from detect → corridor active
    clearance_time_s: float = 0.0  # seconds from corridor → vehicle cleared
    priority: int = 100
    average_congestion: float = 0.0
    estimated_travel_time: float = 0.0
    time_saved: float = 0.0
    response_time_improvement_pct: float = 0.0
    explanation: str = ""


# ─── Graph / Routing Configs ──────────────────────────────────────────────────

GRAPH: Dict[str, List[str]] = {
    "NW": ["NE", "SW"],
    "NE": ["NW", "SE"],
    "SW": ["NW", "SE"],
    "SE": ["NE", "SW"],
}

HOP_TO_LANE: Dict[Tuple[str, str], str] = {
    ("NW", "NE"): "EB_top",
    ("NE", "NW"): "WB_top",
    ("SW", "SE"): "EB_bot",
    ("SE", "SW"): "WB_bot",
    ("NW", "SW"): "SB_left",
    ("SW", "NW"): "NB_left",
    ("NE", "SE"): "SB_right",
    ("SE", "NE"): "NB_right",
}

LANE_OD: Dict[str, Tuple[str, str]] = {
    "EB_top": ("NW", "NE"),
    "WB_top": ("NE", "NW"),
    "EB_bot": ("SW", "SE"),
    "WB_bot": ("SE", "SW"),
    "SB_left": ("NW", "SW"),
    "NB_left": ("SW", "NW"),
    "SB_right": ("NE", "SE"),
    "NB_right": ("SE", "NE"),
}

PRIORITIES: Dict[str, int] = {
    "ambulance": 100,
    "fire": 90,
    "police": 80,
}

ETA_THRESHOLDS: Dict[int, float] = {
    100: 15.0,  # Ambulance: switch signals 15s in advance
    90: 12.0,   # Fire Truck: switch signals 12s in advance
    80: 10.0,   # Police: switch signals 10s in advance
}


# ─── Path Finding Helper ──────────────────────────────────────────────────────

def find_all_paths(start: str, end: str, path: Optional[List[str]] = None) -> List[List[str]]:
    """Recursively find all simple paths between start and end nodes on the graph."""
    if path is None:
        path = []
    path = path + [start]
    if start == end:
        return [path]
    if start not in GRAPH:
        return []
    paths = []
    for node in GRAPH[start]:
        if node not in path:
            newpaths = find_all_paths(node, end, path)
            for newpath in newpaths:
                paths.append(newpath)
    return paths


# ─── Agent ────────────────────────────────────────────────────────────────────

class EmergencyPriorityAgent:
    """
    Agent 03 — Intelligent Dynamic Green Corridor Optimization Agent
    """

    def __init__(self) -> None:
        self.status: EmergencyStatus = EmergencyStatus.STANDBY
        self.current_event: Optional[EmergencyEvent] = None
        self.event_log: List[EmergencyEvent] = []
        self.decision_log: List[str] = []
        self._t0: float = 0.0
        
        # Expose dashboard metrics
        self.emergency_eta: float = 0.0
        self.corridor_length_m: float = 0.0
        self.predicted_delay_reduction_s: float = 0.0
        self.response_time_improvement_pct: float = 0.0
        self.selected_route_str: str = "N/A"
        self.latest_explanation: str = ""

    # ── Public ────────────────────────────────────────────────────────────────

    def detect(
        self,
        sim,
        vehicle_id: int,
        vehicle_type: str = "ambulance",
        entry_lane: str   = "EB_top",
    ) -> EmergencyEvent:
        """
        Detects emergency vehicle, evaluates paths, selects optimal corridor,
        and dispatches vehicle.
        """
        self.status = EmergencyStatus.DETECTED
        self._t0    = sim.time_s
        vehicle_type = vehicle_type.lower()
        priority = PRIORITIES.get(vehicle_type, 100)

        # 1. Identify source and destination
        od = LANE_OD.get(entry_lane, ("NW", "NE"))
        source, destination = od

        # 2. Evaluate all available paths
        paths = find_all_paths(source, destination)
        evaluated_paths = []

        for path in paths:
            metrics = self._evaluate_path_metrics(sim, path, priority)
            evaluated_paths.append((path, metrics))

        # 3. Select optimal path (lowest emergency travel time)
        selected_path, metrics = min(evaluated_paths, key=lambda x: x[1]["T_emergency"])

        # 4. Generate structured AI explanation
        explanation = self._generate_explanation(
            vehicle_type=vehicle_type,
            vehicle_id=vehicle_id,
            route=selected_path,
            avg_congestion=metrics["avg_congestion"],
            t_standard=metrics["T_standard"],
            t_emergency=metrics["T_emergency"],
            clearance_delay=metrics["clearance_delay"]
        )
        self.latest_explanation = explanation

        # 5. Populate EmergencyEvent
        event = EmergencyEvent(
            vehicle_id=vehicle_id,
            vehicle_type=vehicle_type,
            entry_lane=entry_lane,
            detected_at_s=sim.time_s,
            corridor_intersections=selected_path,
            priority=priority,
            average_congestion=metrics["avg_congestion"],
            estimated_travel_time=metrics["T_emergency"],
            time_saved=metrics["time_saved"],
            response_time_improvement_pct=metrics["response_improvement"],
            explanation=explanation
        )
        self.current_event = event

        # 6. Expose dashboard metrics
        self.emergency_eta = metrics["T_emergency"]
        # Assuming each grid block is 500m
        self.corridor_length_m = len(selected_path) * 500.0
        self.predicted_delay_reduction_s = metrics["time_saved"]
        self.response_time_improvement_pct = metrics["response_improvement"]
        self.selected_route_str = " → ".join(selected_path)

        self._log(
            f"🚨 DETECT — {vehicle_type.upper()} #{vehicle_id} approaching via {entry_lane}. "
            f"Priority: {priority}. Path selected: {self.selected_route_str}."
        )

        # 7. Spawn vehicle in simulation
        first_hop_lane = HOP_TO_LANE.get((selected_path[0], selected_path[1]), entry_lane)
        actual_vid = sim.dispatch_emergency(
            lane=first_hop_lane,
            route=selected_path,
            priority=priority,
            vehicle_type=vehicle_type
        )
        event.vehicle_id = actual_vid
        
        event.response_time_s = sim.time_s - self._t0
        self.status = EmergencyStatus.CORRIDOR
        
        # Log active state
        self._log(
            f"🟢 DYNAMIC CORRIDOR ACTIVE — Adaptive clearance for {self.selected_route_str}. "
            f"Response time: {event.response_time_s:.2f}s."
        )
        
        return event

    def poll(self, sim) -> None:
        """
        Call every simulation step while corridor is active.
        Predicts ETA and preemptively clears intersections, releasing them node-by-node.
        """
        # Check if RESOLVED status should transition to STANDBY
        self._check_resolved_timeout(sim)
        
        if self.status not in (EmergencyStatus.CORRIDOR, EmergencyStatus.CLEARING):
            return

        event = self.current_event
        if event is None:
            return

        # Find the emergency vehicle in the simulation
        emerg_vehicles = [v for v in sim.vehicles if v.is_emergency and v.vid == event.vehicle_id]
        if not emerg_vehicles:
            # If no longer in simulation, resolve the corridor
            self._resolve(sim)
            return

        v = emerg_vehicles[0]
        
        # Update remaining route intersections in the event
        event.corridor_intersections = list(v.route_remaining)
        self.selected_route_str = " → ".join(v.route_remaining) if v.route_remaining else "Cleared"
        
        # Predict ETAs to each remaining intersection
        etas = self._predict_etas(v, sim)
        
        # Update dashboard metrics
        if etas and len(v.route_remaining) >= 2:
            next_node = v.route_remaining[1]
            self.emergency_eta = etas.get(next_node, 0.0)
        elif etas and len(v.route_remaining) == 1:
            self.emergency_eta = etas.get(v.route_remaining[0], 0.0)
        else:
            self.emergency_eta = 0.0

        priority = getattr(v, "priority", 100)
        threshold = ETA_THRESHOLDS.get(priority, 10.0)
        
        # Preemptively override signals
        for node in v.route_remaining:
            eta = etas.get(node, 999.0)
            if eta <= threshold:
                required_phase = self._get_required_phase(node, v.route)
                inter = sim.intersections[node]
                
                # Apply override if not overridden or if we have >= priority
                if not inter.override or priority >= inter.override_priority:
                    inter.override = True
                    inter.corridor_phase = required_phase
                    inter.override_priority = priority

        # Dynamic Restoration: release overrides for nodes we have passed
        for node in v.route:
            if node not in v.route_remaining:
                inter = sim.intersections[node]
                if inter.override and inter.override_priority == priority:
                    inter.override = False
                    inter.override_priority = 0

    def resolve_manually(self, sim) -> None:
        """Force resolution (for testing / manual override)."""
        self._resolve(sim)

    def format_summary(self) -> str:
        lines = ["Agent 03 — Emergency Priority Log", "=" * 40]
        lines.extend(self.decision_log[-20:])
        if self.event_log:
            e = self.event_log[-1]
            lines.append(
                f"\nLast event: {e.vehicle_type} #{e.vehicle_id}  "
                f"response={e.response_time_s:.1f}s  clearance={e.clearance_time_s:.1f}s"
            )
        return "\n".join(lines)

    # ── Private ───────────────────────────────────────────────────────────────

    def _evaluate_path_metrics(self, sim, path: List[str], priority: int) -> dict:
        """Evaluate traffic metrics (queue, congestion, travel time, ETA) for a path."""
        hops = [(path[i], path[i+1]) for i in range(len(path)-1)]
        K = len(hops)
        
        total_queue = 0.0
        total_wait = 0.0
        clearance_delay = 0.0
        congested_delay = 0.0
        
        for u, v in hops:
            lane = HOP_TO_LANE.get((u, v))
            if not lane:
                continue
            l_def = LANE_DEFS[lane]
            inter_v = sim.intersections[v]
            is_horiz = l_def["dir"] == "H"
            
            # Queue size on this hop approach
            q = inter_v.ew_queue if is_horiz else inter_v.ns_queue
            total_queue += q
            
            # Cumulative wait frames
            wait_time = sum(veh.wait_frames / sim.fps for veh in sim.vehicles if veh.lane == lane and veh.waiting)
            total_wait += wait_time
            
            # Clearance delay (1.5s per vehicle in queue)
            clearance_delay += q * 1.5
            
            # Congested delay (8.0s per vehicle for standard traffic)
            congested_delay += q * 8.0
            
        # Free-flow calculations (speed = 0.625 progress units / s)
        distance = 0.5 * K + 0.5
        t_free_emergency = distance / 0.625
        t_free_standard = distance / 0.4
        
        T_emergency = t_free_emergency + clearance_delay
        T_standard = t_free_standard + congested_delay
        
        time_saved = max(0.0, T_standard - T_emergency)
        response_improvement = (time_saved / max(0.1, T_standard)) * 100.0
        avg_congestion = (total_queue / max(0.1, 20.0 * K)) * 100.0
        avg_congestion = min(100.0, avg_congestion)
        
        return {
            "total_queue": total_queue,
            "total_wait": total_wait,
            "clearance_delay": clearance_delay,
            "T_emergency": T_emergency,
            "T_standard": T_standard,
            "time_saved": time_saved,
            "response_improvement": response_improvement,
            "avg_congestion": avg_congestion
        }

    def _predict_etas(self, v, sim) -> Dict[str, float]:
        """Predict real-time ETA in seconds to each remaining intersection in route_remaining."""
        etas = {}
        fps = sim.fps
        speed_pps = v.speed * fps  # progress units per second
        if speed_pps <= 0:
            return etas
            
        l_def = LANE_DEFS[v.lane]
        xd = l_def.get("xd", l_def.get("yd", 1))
        
        inters = l_def["inters"]
        stops = l_def["stops"]
        
        # Calculate time to remaining stops in the current lane
        time_to_inters = []
        for iname, sp in zip(inters, stops):
            dist = (sp - v.progress) * xd
            if dist > -0.01:
                t = dist / speed_pps
                time_to_inters.append((iname, t))
                
        if not time_to_inters:
            return etas
            
        next_node, next_time = time_to_inters[0]
        try:
            start_idx = v.route_remaining.index(next_node)
        except ValueError:
            start_idx = 0
            
        accumulated_time = next_time
        etas[next_node] = accumulated_time
        
        for iname, t in time_to_inters[1:]:
            etas[iname] = t
            accumulated_time = t
            
        # Extrapolate for subsequent hops in route_remaining
        last_current_node = time_to_inters[-1][0]
        try:
            last_idx = v.route_remaining.index(last_current_node)
        except ValueError:
            last_idx = len(v.route_remaining) - 1
            
        hop_time = 0.5 / speed_pps
        for idx in range(last_idx + 1, len(v.route_remaining)):
            accumulated_time += hop_time
            etas[v.route_remaining[idx]] = accumulated_time
            
        return etas

    def _get_required_phase(self, node: str, route: List[str]) -> SignalPhase:
        """Get the required signal phase at a node based on vehicle heading."""
        try:
            idx = route.index(node)
            if idx < len(route) - 1:
                from_node = node
                to_node = route[idx+1]
            else:
                from_node = route[idx-1]
                to_node = node
                
            lane = HOP_TO_LANE.get((from_node, to_node))
            if lane:
                l_def = LANE_DEFS[lane]
                return SignalPhase.EW if l_def["dir"] == "H" else SignalPhase.NS
        except Exception:
            pass
        return SignalPhase.EW

    def _generate_explanation(
        self,
        vehicle_type: str,
        vehicle_id: int,
        route: List[str],
        avg_congestion: float,
        t_standard: float,
        t_emergency: float,
        clearance_delay: float
    ) -> str:
        """Generate a structured, human-readable explanation of the AI's route choice."""
        route_str = " → ".join(route)
        explanation = (
            f"Green corridor activated for {vehicle_type.capitalize()} #{vehicle_id}.\n"
            f"Route {route_str} selected.\n"
            f"Average congestion: {avg_congestion:.0f}%.\n"
            f"Estimated travel time reduced from {t_standard:.0f}s to {t_emergency:.0f}s.\n"
            f"Predicted clearance time: {clearance_delay:.0f}s."
        )
        return explanation

    def _resolve(self, sim) -> None:
        """Step 4: restore all overridden intersections."""
        self.status = EmergencyStatus.CLEARING
        event = self.current_event

        if event:
            event.cleared_at_s    = sim.time_s
            event.clearance_time_s = sim.time_s - event.detected_at_s
            self._log(
                f"✅ RESOLVED — Corridor dissolved for {event.vehicle_type.upper()} #{event.vehicle_id}. "
                f"Total clearance time: {event.clearance_time_s:.1f}s. "
                f"Intersections {', '.join(event.corridor_intersections)} returned to adaptive control."
            )
            self.event_log.append(event)
            
            # Reset overrides for intersections held by this priority
            priority = getattr(event, "priority", 100)
            for inter in sim.intersections.values():
                if inter.override and inter.override_priority == priority:
                    inter.override = False
                    inter.override_priority = 0
            
            # Keep current_event alive so dashboard can display time-saved
            # It will be cleared when transitioning to STANDBY

        sim.release_corridor()
        self.status = EmergencyStatus.RESOLVED
        self._resolved_at = sim.time_s
        
        # Reset metric values
        self.emergency_eta = 0.0
        self.selected_route_str = "N/A"
        
        # Do NOT immediately go to STANDBY — let poll() handle it after a delay

    def _check_resolved_timeout(self, sim) -> None:
        """Transition from RESOLVED to STANDBY after a delay so the dashboard can show results."""
        if self.status == EmergencyStatus.RESOLVED and hasattr(self, '_resolved_at'):
            if sim.time_s - self._resolved_at > 10.0:  # Show resolved status for 10 seconds
                self.status = EmergencyStatus.STANDBY
                self.current_event = None

    def _log(self, msg: str) -> None:
        ts  = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.decision_log.append(entry)
        if len(self.decision_log) > 200:
            self.decision_log.pop(0)

