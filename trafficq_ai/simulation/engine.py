"""
TRAFFICQ AI — Core Traffic Simulation Engine
Discrete-event simulation of a 2×2 intersection grid.

Modes
-----
static   : All signals run fixed 30 s NS / 30 s EW cycles (legacy approach).
adaptive : Agent 01 recalculates green splits every cycle using wait-time scores.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ─── Enums ────────────────────────────────────────────────────────────────────

class SignalPhase(str, Enum):
    NS = "NS"   # North-South green / East-West red
    EW = "EW"   # East-West green / North-South red


class SimMode(str, Enum):
    STATIC   = "static"
    ADAPTIVE = "adaptive"


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Intersection:
    """Single intersection with two-phase traffic signal."""
    name: str
    phase: SignalPhase = SignalPhase.NS
    phase_timer: float = 0.0       # seconds elapsed in current phase
    ns_green: float = 30.0         # seconds of NS green per cycle
    ew_green: float = 30.0         # seconds of EW green per cycle
    ns_queue: float = 0.0          # vehicles queued on N-S approaches
    ew_queue: float = 0.0          # vehicles queued on E-W approaches
    ns_wait_score: float = 0.0     # cumulative wait score (queue × time)
    ew_wait_score: float = 0.0
    override: bool = False         # True when Agent 03 holds this signal
    corridor_phase: SignalPhase = SignalPhase.EW  # phase forced during override

    # ── derived ──────────────────────────────────────────────────────────────
    @property
    def current_phase(self) -> SignalPhase:
        return self.corridor_phase if self.override else self.phase

    @property
    def total_queue(self) -> float:
        return self.ns_queue + self.ew_queue

    @property
    def congestion_pct(self) -> float:
        cap = 20.0
        return min(100.0, self.total_queue / cap * 100)


@dataclass
class Vehicle:
    """Single vehicle travelling through the grid."""
    vid: int
    lane: str
    progress: float          # 0.0 (entry) → 1.0 (exit)
    speed: float             # progress units per step
    waiting: bool = False
    wait_frames: int = 0     # frames spent waiting
    is_emergency: bool = False
    color: str = "#3B8BD4"
    next_stop_idx: int = 0   # index into lane's stop list


# ─── Lane definitions ─────────────────────────────────────────────────────────

LANE_COLORS = ["#3B8BD4", "#1D9E75", "#D85A30", "#7F77DD", "#F59E0B"]

LANE_DEFS: Dict[str, dict] = {
    #          direction  lateral    x/y-dir  intersections     stop-progresses  density-idx
    "EB_top":  dict(dir="H", lat=0.28,  xd=+1, inters=["NW","NE"], stops=[0.22,0.72], di=2),
    "WB_top":  dict(dir="H", lat=-0.28, xd=-1, inters=["NE","NW"], stops=[0.78,0.28], di=2),
    "EB_bot":  dict(dir="H", lat=0.28,  xd=+1, inters=["SW","SE"], stops=[0.22,0.72], di=3),
    "WB_bot":  dict(dir="H", lat=-0.28, xd=-1, inters=["SE","SW"], stops=[0.78,0.28], di=3),
    "SB_left": dict(dir="V", lat=-0.28, yd=+1, inters=["NW","SW"], stops=[0.22,0.72], di=0),
    "NB_left": dict(dir="V", lat=+0.28, yd=-1, inters=["SW","NW"], stops=[0.78,0.28], di=0),
    "SB_right":dict(dir="V", lat=-0.28, yd=+1, inters=["NE","SE"], stops=[0.22,0.72], di=1),
    "NB_right":dict(dir="V", lat=+0.28, yd=-1, inters=["SE","NE"], stops=[0.78,0.28], di=1),
}


# ─── Simulation Engine ────────────────────────────────────────────────────────

class TrafficSimulation:
    """
    2×2 intersection grid traffic simulation.

    Parameters
    ----------
    mode     : 'static' or 'adaptive'
    density  : [NS_col1, NS_col2, EW_row1, EW_row2] as 0–100 values
    fps      : simulation frames per second
    seed     : random seed for reproducibility
    """

    CYCLE     = 60.0   # total signal cycle length (seconds)
    MIN_GREEN = 15.0   # minimum green time (pedestrian safety)

    def __init__(
        self,
        mode: str = "static",
        density: Optional[List[int]] = None,
        fps: int = 20,
        seed: int = 42,
    ) -> None:
        self.mode    = SimMode(mode)
        self.density = density or [65, 60, 40, 45]
        self.fps     = fps
        self.rng     = random.Random(seed)
        self.frame   = 0
        self.time_s  = 0.0

        # ── Intersections ────────────────────────────────────────────────────
        offsets = {"NW": 0.0, "NE": fps * 15, "SW": fps * 8, "SE": fps * 22}
        self.intersections: Dict[str, Intersection] = {}
        for name, timer_offset in offsets.items():
            phase = SignalPhase.NS if name in ("NW", "NE") else SignalPhase.EW
            self.intersections[name] = Intersection(
                name=name,
                phase=phase,
                phase_timer=timer_offset / fps,   # convert to seconds
            )

        # ── Vehicles ─────────────────────────────────────────────────────────
        self.vehicles: List[Vehicle] = []
        self._vid_counter = 0
        self._spawn_timers: Dict[str, int] = {
            lk: self.rng.randint(0, 50) for lk in LANE_DEFS
        }
        self._corridor_lanes: set = set()

        # ── Metrics ──────────────────────────────────────────────────────────
        self.exits      = 0
        self._exit_ts: List[int] = []   # frame numbers of exits
        self._cum_wait_veh_frames = 0   # total vehicle-frames spent waiting

        self.history: Dict[str, List[float]] = {
            "avg_wait_s":    [],
            "throughput_pm": [],
            "congestion_pct":[],
            "waiting_count": [],
            "total_vehicles":[],
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def step(self) -> None:
        """Advance simulation by one frame."""
        self.frame  += 1
        self.time_s  = self.frame / self.fps

        self._spawn_vehicles()
        if self.frame % 10 == 0:
            self._compute_wait_scores()
        self._update_signals()
        self._update_vehicles()
        self._record_metrics()

    def dispatch_emergency(self, lane: str = "EB_top") -> int:
        """
        Agent 03: spawn emergency vehicle and activate green corridor.
        Returns the vehicle id of the emergency vehicle.
        """
        l  = LANE_DEFS[lane]
        start = 0.0 if l.get("xd", l.get("yd", 1)) > 0 else 1.0
        vid = self._create_vehicle(lane, start, is_emergency=True, color="#EF4444")

        # Force EW green on all intersections along the corridor
        self._corridor_lanes = {lane}
        for iname in l["inters"]:
            inter = self.intersections[iname]
            inter.override        = True
            inter.corridor_phase  = SignalPhase.EW if l["dir"] == "H" else SignalPhase.NS
        return vid

    def release_corridor(self, lane: str | None = None) -> None:
        """Agent 03: release signal overrides after emergency clears.
        
        If lane is None, release ALL overridden intersections.
        If lane is specified, release only the intersections on that lane.
        """
        self._corridor_lanes = set()
        if lane is None:
            # Release all overridden intersections
            for inter in self.intersections.values():
                inter.override = False
        else:
            for iname in LANE_DEFS[lane]["inters"]:
                inter         = self.intersections[iname]
                inter.override = False

    def get_metrics(self) -> dict:
        """Return current-frame metrics snapshot."""
        h = self.history
        return {
            "avg_wait_s":     h["avg_wait_s"][-1]     if h["avg_wait_s"]     else 0.0,
            "throughput_pm":  h["throughput_pm"][-1]  if h["throughput_pm"]  else 0.0,
            "congestion_pct": h["congestion_pct"][-1] if h["congestion_pct"] else 0.0,
            "waiting_count":  h["waiting_count"][-1]  if h["waiting_count"]  else 0,
            "total_vehicles": h["total_vehicles"][-1]  if h["total_vehicles"] else 0,
            "frame":          self.frame,
            "time_s":         self.time_s,
        }

    def get_signal_state(self) -> List[dict]:
        """Return list of signal state dicts (one per intersection)."""
        out = []
        for name, inter in self.intersections.items():
            out.append({
                "name":       name,
                "phase":      inter.current_phase.value,
                "ns_green":   inter.ns_green,
                "ew_green":   inter.ew_green,
                "ns_queue":   round(inter.ns_queue, 2),
                "ew_queue":   round(inter.ew_queue, 2),
                "ns_score":   round(inter.ns_wait_score, 2),
                "ew_score":   round(inter.ew_wait_score, 2),
                "override":   inter.override,
                "congestion": round(inter.congestion_pct, 1),
            })
        return out

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _create_vehicle(
        self,
        lane: str,
        start: float,
        is_emergency: bool = False,
        color: str = "#3B8BD4",
    ) -> int:
        vid = self._vid_counter
        self._vid_counter += 1
        spd_scale = 2.5 if is_emergency else (1.2 + self.rng.random() * 0.8)
        self.vehicles.append(
            Vehicle(
                vid=vid, lane=lane, progress=start,
                speed=spd_scale / (self.fps * 4),
                is_emergency=is_emergency, color=color,
            )
        )
        return vid

    def _spawn_vehicles(self) -> None:
        if len(self.vehicles) >= 90:
            return
        for lk, ldata in LANE_DEFS.items():
            d    = self.density[ldata["di"]]
            rate = max(14, 112 - d)
            self._spawn_timers[lk] += 1
            if self._spawn_timers[lk] < rate:
                continue

            xd    = ldata.get("xd", ldata.get("yd", 1))
            start = 0.0 if xd > 0 else 1.0
            clear = all(
                abs(v.progress - start) > 0.06
                for v in self.vehicles if v.lane == lk
            )
            if clear:
                col = self.rng.choice(LANE_COLORS)
                self._create_vehicle(lk, start, color=col)
                self._spawn_timers[lk] = 0

    def _compute_wait_scores(self) -> None:
        for inter in self.intersections.values():
            inter.ns_wait_score = 0.0
            inter.ew_wait_score = 0.0
            inter.ns_queue      = 0.0
            inter.ew_queue      = 0.0

        for v in self.vehicles:
            if not v.waiting:
                continue
            l      = LANE_DEFS[v.lane]
            xd     = l.get("xd", l.get("yd", 1))
            score  = 1.0 + v.wait_frames * 0.04

            for iname, stop in zip(l["inters"], l["stops"]):
                dist = (stop - v.progress) * xd
                if -0.05 <= dist <= 0.20:
                    inter = self.intersections[iname]
                    if l["dir"] == "V":
                        inter.ns_wait_score += score
                        inter.ns_queue      += 1
                    else:
                        inter.ew_wait_score += score
                        inter.ew_queue      += 1
                    break

    def _can_proceed(self, lane_key: str, iname: str) -> bool:
        l     = LANE_DEFS[lane_key]
        inter = self.intersections[iname]
        if inter.override:
            return lane_key in self._corridor_lanes
        need = SignalPhase.EW if l["dir"] == "H" else SignalPhase.NS
        return inter.phase == need

    def _update_signals(self) -> None:
        dt = 1.0 / self.fps
        for inter in self.intersections.values():
            if inter.override:
                continue
            inter.phase_timer += dt
            duration = inter.ns_green if inter.phase == SignalPhase.NS else inter.ew_green
            if inter.phase_timer >= duration:
                inter.phase       = SignalPhase.EW if inter.phase == SignalPhase.NS else SignalPhase.NS
                inter.phase_timer = 0.0
                # Adaptive recalculation on NS start
                if self.mode == SimMode.ADAPTIVE and inter.phase == SignalPhase.NS:
                    self._recalculate_split(inter)

    def _recalculate_split(self, inter: Intersection) -> None:
        """Agent 01 wait-time formula: G_NS = max(MIN_G, round(W_NS/(W_NS+W_EW)·C))"""
        total = inter.ns_wait_score + inter.ew_wait_score
        if total > 1.0:
            ns_raw = round(inter.ns_wait_score / total * self.CYCLE)
            inter.ns_green = max(self.MIN_GREEN, min(self.CYCLE - self.MIN_GREEN, ns_raw))
            inter.ew_green = self.CYCLE - inter.ns_green
        else:
            inter.ns_green = 30.0
            inter.ew_green = 30.0

    def _update_vehicles(self) -> None:
        keep: List[Vehicle] = []
        for v in self.vehicles:
            l  = LANE_DEFS[v.lane]
            xd = l.get("xd", l.get("yd", 1))

            stop = False
            for iname, sp in zip(l["inters"], l["stops"]):
                dist = (sp - v.progress) * xd
                if 0 < dist < 0.18:
                    if not self._can_proceed(v.lane, iname):
                        if dist < 0.04:
                            stop = True
                        else:
                            v.speed = max(0.0004, v.speed * 0.86)
                elif dist <= 0:
                    if v.next_stop_idx <= l["inters"].index(iname):
                        v.next_stop_idx += 1
                    spd_scale = 2.5 if v.is_emergency else (1.2 + self.rng.random() * 0.8)
                    v.speed = spd_scale / (self.fps * 4)

            if stop:
                v.waiting      = True
                v.wait_frames += 1
                self._cum_wait_veh_frames += 1
            else:
                v.waiting   = False
                v.progress += xd * v.speed

            if -0.08 < v.progress < 1.08:
                keep.append(v)
            else:
                self.exits += 1
                self._exit_ts.append(self.frame)
                if v.is_emergency:
                    # Auto-release corridor when emergency vehicle exits
                    self.release_corridor(v.lane)

        self.vehicles = keep

    def _record_metrics(self) -> None:
        total   = len(self.vehicles)
        waiting = sum(1 for v in self.vehicles if v.waiting)
        cong    = waiting / max(total, 1) * 100

        wait_frames = [v.wait_frames for v in self.vehicles if v.waiting]
        avg_wait    = (sum(wait_frames) / len(wait_frames) / self.fps) if wait_frames else 0.0

        recent_exits  = sum(1 for t in self._exit_ts if self.frame - t < 60 * self.fps)
        throughput_pm = recent_exits / 60.0 * 60

        self.history["avg_wait_s"].append(avg_wait)
        self.history["throughput_pm"].append(throughput_pm)
        self.history["congestion_pct"].append(cong)
        self.history["waiting_count"].append(waiting)
        self.history["total_vehicles"].append(total)
