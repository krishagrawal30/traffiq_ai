"""
TRAFFICQ AI — Agent 03: Emergency Priority
Detects emergency vehicles (camera / GPS beacon), calculates the
fastest path, overrides all signals along the route to create a
real-time green corridor, then restores normal operation as the
vehicle clears each intersection.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


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


# ─── Agent ────────────────────────────────────────────────────────────────────

class EmergencyPriorityAgent:
    """
    Agent 03 — Emergency Priority

    Four-step process (mirrors Slide 8 of the deck):
      1. Detect  — camera / GPS beacon signals approaching vehicle.
      2. Calculate — find shortest path through intersection grid.
      3. Synchronise — override signals on path to green for vehicle direction.
      4. Restore — revert each node as vehicle clears it.

    Every override is logged as a natural-language explanation for auditability.
    """

    # Corridor route presets (entry-lane → intersections in order)
    CORRIDOR_ROUTES: Dict[str, List[str]] = {
        "EB_top":  ["NW", "NE"],
        "WB_top":  ["NE", "NW"],
        "EB_bot":  ["SW", "SE"],
        "WB_bot":  ["SE", "SW"],
        "SB_left": ["NW", "SW"],
        "NB_left": ["SW", "NW"],
        "SB_right":["NE", "SE"],
        "NB_right":["SE", "NE"],
    }

    def __init__(self) -> None:
        self.status: EmergencyStatus = EmergencyStatus.STANDBY
        self.current_event: Optional[EmergencyEvent] = None
        self.event_log: List[EmergencyEvent] = []
        self.decision_log: List[str] = []
        self._t0: float = 0.0

    # ── Public ────────────────────────────────────────────────────────────────

    def detect(
        self,
        sim,
        vehicle_id: int,
        vehicle_type: str = "ambulance",
        entry_lane: str   = "EB_top",
    ) -> EmergencyEvent:
        """
        Step 1 + 2: detect the vehicle and compute its route.
        Step 3: activate the corridor.
        Returns the EmergencyEvent for logging.
        """
        self.status = EmergencyStatus.DETECTED
        self._t0    = sim.time_s
        route = self.CORRIDOR_ROUTES.get(entry_lane, ["NW", "NE"])
        event = EmergencyEvent(
            vehicle_id=vehicle_id,
            vehicle_type=vehicle_type,
            entry_lane=entry_lane,
            detected_at_s=sim.time_s,
            corridor_intersections=route,
        )
        self.current_event = event
        self._log(
            f"🚨 DETECT — {vehicle_type.upper()} #{vehicle_id} approaching via {entry_lane}. "
            f"Calculated corridor: {' → '.join(route)}."
        )
        # ── Step 3: synchronise ──────────────────────────────────────────────
        emerg_vid = sim.dispatch_emergency(lane=entry_lane)
        event.response_time_s = sim.time_s - self._t0

        self.status = EmergencyStatus.CORRIDOR
        self._log(
            f"🟢 CORRIDOR ACTIVE — All signals on {' → '.join(route)} forced GREEN "
            f"for {entry_lane} direction. Cross-traffic HELD. "
            f"Response time: {event.response_time_s:.2f}s."
        )
        return event

    def poll(self, sim) -> None:
        """
        Call every simulation step while corridor is active.
        Checks if the emergency vehicle has cleared and resolves the corridor.
        """
        if self.status not in (EmergencyStatus.CORRIDOR, EmergencyStatus.CLEARING):
            return

        event = self.current_event
        if event is None:
            return

        # Check if the emergency vehicle still exists in the simulation
        emerg_vehicles = [v for v in sim.vehicles if v.is_emergency]
        if not emerg_vehicles:
            self._resolve(sim)

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

    def _resolve(self, sim) -> None:
        """Step 4: restore all overridden intersections."""
        self.status = EmergencyStatus.CLEARING
        event = self.current_event

        if event:
            event.cleared_at_s    = sim.time_s
            event.clearance_time_s = sim.time_s - event.detected_at_s
            self._log(
                f"✅ RESOLVED — Corridor dissolved. "
                f"Total clearance time: {event.clearance_time_s:.1f}s. "
                f"Intersections {', '.join(event.corridor_intersections)} "
                f"returned to adaptive optimisation."
            )
            self.event_log.append(event)
            self.current_event = None

        sim.release_corridor()
        self.status = EmergencyStatus.RESOLVED

        # Back to standby after short delay (simulated)
        self.status = EmergencyStatus.STANDBY

    def _log(self, msg: str) -> None:
        ts  = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self.decision_log.append(entry)
        if len(self.decision_log) > 200:
            self.decision_log.pop(0)
