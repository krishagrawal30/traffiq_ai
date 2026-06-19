"""
TRAFFICQ AI — Core Traffic Simulation Engine (Bengaluru Silk Board Corridor)

Discrete-event simulation calibrated to real Bengaluru traffic patterns.
Supports static (fixed-timer) and adaptive (AI-driven) signal modes.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from .topology import build_topology

# ─── Enums ────────────────────────────────────────────────────────────────────

class SignalPhase(str, Enum):
    NS = "NS"
    EW = "EW"
    SW = "SW"
    NE = "NE"

class SimMode(str, Enum):
    STATIC   = "static"
    ADAPTIVE = "adaptive"
    INCIDENT = "incident"

# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class SignalState:
    name: str
    phase: SignalPhase = SignalPhase.NS
    phase_timer: float = 0.0
    ns_green: float = 30.0
    ew_green: float = 30.0
    sw_green: float = 0.0
    ne_green: float = 0.0
    ns_queue: float = 0.0
    ew_queue: float = 0.0
    sw_queue: float = 0.0
    ne_queue: float = 0.0
    ns_wait_score: float = 0.0
    ew_wait_score: float = 0.0
    sw_wait_score: float = 0.0
    ne_wait_score: float = 0.0
    override: bool = False
    corridor_phase: SignalPhase = SignalPhase.NS
    override_priority: int = 0
    congestion_pct: float = 0.0
    peak_ns_queue: float = 0.0
    peak_ew_queue: float = 0.0

    @property
    def active_phase(self) -> SignalPhase:
        return self.corridor_phase if self.override else self.phase

    @property
    def total_queue(self) -> float:
        return self.ns_queue + self.ew_queue + self.sw_queue + self.ne_queue

@dataclass
class Vehicle:
    vid: int
    vehicle_type: str = "car"
    junction: str = ""
    approach: str = ""
    progress: float = 0.0
    speed: float = 0.0
    waiting: bool = False
    wait_frames: int = 0
    is_emergency: bool = False
    color: str = "#3B8BD4"
    route: list[str] = field(default_factory=list)
    passed_signal: bool = False

# ─── Simulation Engine ────────────────────────────────────────────────────────

class TrafficSimulation:
    CYCLE = 60.0
    MIN_GREEN = 10.0

    def __init__(
        self,
        mode: str = "static",
        hour: int = 8,
        fps: int = 10,
        seed: int = 42,
    ):
        self.mode = SimMode(mode)
        self.hour = hour
        self.fps = fps
        self.rng = random.Random(seed)
        self.frame = 0
        self.time_s = 0.0

        self._topology = build_topology()
        self.signals: dict[str, SignalState] = {}
        self._init_signals()

        self.vehicles: list[Vehicle] = []
        self._vid_counter = 0
        self._spawn_timers: dict[str, int] = {}
        self._spawn_rates: dict[str, float] = {}

        self._compute_spawn_rates()

        self.exits = 0
        self._exit_ts: list[int] = []
        self._cum_wait_frames = 0

        self.history: dict[str, list[float]] = {
            "avg_wait_s": [],
            "throughput_pm": [],
            "congestion_pct": [],
            "waiting_count": [],
            "total_vehicles": [],
        }

    def _init_signals(self):
        for name in self._topology:
            phase = SignalPhase.NS if name in ("HSR_Layout", "Silk_Board", "Madiwala") else SignalPhase.EW
            offsets = {"Silk_Board": 0, "Madiwala": 5, "HSR_Layout": 3, "BTM_Layout": 8}
            self.signals[name] = SignalState(
                name=name,
                phase=phase,
                phase_timer=offsets.get(name, 0),
                ns_green=30.0, ew_green=30.0,
            )

    def _compute_spawn_rates(self):
        patterns = {
            "Silk_Board_NS_Hosur_Road":  (8, 70),
            "Silk_Board_EW_ORR":          (4, 28),
            "Silk_Board_SW_Bannerghatta": (5, 35),
            "Madiwala_NS_Hosur_Road":     (6, 50),
            "HSR_Layout_NS_Hosur_Road":   (5, 42),
            "BTM_Layout_NS_Bannerghatta": (4, 30),
        }
        for key, (low, high) in patterns.items():
            spread = high - low
            peak_center = 8.5
            dist_from_peak = abs(self.hour - peak_center)
            if self.hour < 6 or self.hour >= 22:
                factor = 0.1
            elif self.hour >= 17 and self.hour <= 19:
                factor = 0.85
            elif dist_from_peak <= 1.5:
                factor = 0.9 + 0.1 * math.cos(dist_from_peak * math.pi / 1.5)
            elif dist_from_peak <= 4:
                factor = 0.5 + 0.4 * math.cos((dist_from_peak - 1.5) * math.pi / 2.5)
            else:
                factor = 0.2 + 0.3 * math.cos((dist_from_peak - 4) * math.pi / 3)
            self._spawn_rates[key] = low + spread * max(0.1, factor)

    def step(self):
        self.frame += 1
        self.time_s = self.frame / self.fps
        self._spawn_vehicles()
        if self.frame % 10 == 0:
            self._compute_wait_scores()
        self._update_signals()
        self._update_vehicles()
        self._record_metrics()

    def _create_vehicle(self, junction: str, approach: str, is_emergency: bool = False,
                        color: str = "#3B8BD4", route: Optional[list[str]] = None, vehicle_type: str = "car") -> int:
        vid = self._vid_counter
        self._vid_counter += 1
        spd_scale = 0.8 if is_emergency else (0.15 + self.rng.random() * 0.1)
        self.vehicles.append(Vehicle(
            vid=vid, junction=junction, approach=approach,
            progress=0.0, speed=spd_scale / (self.fps * 3),
            is_emergency=is_emergency, color=color,
            route=route or [], vehicle_type=vehicle_type,
        ))
        return vid

    def _spawn_vehicles(self):
        if len(self.vehicles) >= 300:
            return
        spawn_configs = [
            ("Silk_Board", "NS_Hosur_Road"),
            ("Silk_Board", "EW_ORR"),
            ("Silk_Board", "SW_Bannerghatta"),
            ("Silk_Board", "NE_Central_Silk_Board"),
            ("Madiwala", "NS_Hosur_Road"),
            ("Madiwala", "EW_BC_Road"),
            ("HSR_Layout", "NS_Hosur_Road"),
            ("HSR_Layout", "EW_HSR_Sector1"),
            ("BTM_Layout", "NS_Bannerghatta"),
            ("BTM_Layout", "EW_BTM_Main"),
        ]
        for junction, approach in spawn_configs:
            key = f"{junction}_{approach}"
            rate = self._spawn_rates.get(key, 30)
            timer_key = f"{junction}_{approach}"
            t = self._spawn_timers.get(timer_key, 0)
            t += 1
            threshold = int(max(3, 60 - rate * 0.7))
            if t >= threshold:
                self._spawn_timers[timer_key] = 0
                color = self.rng.choice(["#3B8BD4", "#1D9E75", "#D85A30", "#7F77DD", "#F59E0B"])
                self._create_vehicle(junction, approach, color=color)
            else:
                self._spawn_timers[timer_key] = t

    APPROACH_QUEUE_MAP = {
        "NS_Hosur_Road": ("ns_queue", "ns_wait_score"),
        "NS_Bannerghatta": ("ns_queue", "ns_wait_score"),
        "SW_Bannerghatta": ("ns_queue", "ns_wait_score"),
        "EW_ORR": ("ew_queue", "ew_wait_score"),
        "EW_BC_Road": ("ew_queue", "ew_wait_score"),
        "EW_HSR_Sector1": ("ew_queue", "ew_wait_score"),
        "EW_BTM_Main": ("ew_queue", "ew_wait_score"),
        "NE_Central_Silk_Board": ("ew_queue", "ew_wait_score"),
    }

    def _compute_wait_scores(self):
        for sig in self.signals.values():
            sig.ns_wait_score = 0.0
            sig.ew_wait_score = 0.0
            sig.sw_wait_score = 0.0
            sig.ne_wait_score = 0.0
            sig.ns_queue = 0.0
            sig.ew_queue = 0.0
            sig.sw_queue = 0.0
            sig.ne_queue = 0.0

        for v in self.vehicles:
            if not v.waiting:
                continue
            sig = self.signals.get(v.junction)
            if not sig:
                continue
            mapping = self.APPROACH_QUEUE_MAP.get(v.approach)
            if mapping:
                q_attr, w_attr = mapping
                setattr(sig, q_attr, getattr(sig, q_attr) + 1)
                wait_sec = v.wait_frames / self.fps
                setattr(sig, w_attr, getattr(sig, w_attr) + wait_sec)

        for sig in self.signals.values():
            sig.congestion_pct = min(100.0, sig.total_queue / 50.0 * 100)
            # Track peak queues during current phase's red interval
            if sig.active_phase == SignalPhase.NS:
                sig.peak_ew_queue = max(sig.peak_ew_queue, sig.ew_queue + sig.ne_queue)
            else:
                sig.peak_ns_queue = max(sig.peak_ns_queue, sig.ns_queue + sig.sw_queue)

    APPROACH_PHASE_MAP = {
        "NS_Hosur_Road": SignalPhase.NS,
        "NS_Bannerghatta": SignalPhase.NS,
        "SW_Bannerghatta": SignalPhase.NS,
        "EW_ORR": SignalPhase.EW,
        "EW_BC_Road": SignalPhase.EW,
        "EW_HSR_Sector1": SignalPhase.EW,
        "EW_BTM_Main": SignalPhase.EW,
        "NE_Central_Silk_Board": SignalPhase.EW,
    }

    def _can_proceed(self, junction: str, approach: str) -> bool:
        sig = self.signals.get(junction)
        if not sig:
            return True
        if sig.override:
            return True
        needed = self.APPROACH_PHASE_MAP.get(approach, SignalPhase.NS)
        return sig.active_phase == needed

    def _update_signals(self):
        dt = 1.0 / self.fps
        for sig in self.signals.values():
            if sig.override:
                continue
            sig.phase_timer += dt
            duration = self._current_green(sig)
            if sig.phase_timer >= duration:
                prev = sig.phase
                if self.mode == SimMode.ADAPTIVE:
                    self._recalculate_split(sig, prev)
                sig.phase = SignalPhase.EW if sig.phase == SignalPhase.NS else SignalPhase.NS
                sig.phase_timer = 0.0

    def _current_green(self, sig: SignalState) -> float:
        return sig.ns_green if sig.phase == SignalPhase.NS else sig.ew_green

    def _recalculate_split(self, sig: SignalState, prev_phase: SignalPhase):
        peak_ns = max(sig.peak_ns_queue, 1)
        peak_ew = max(sig.peak_ew_queue, 1)
        ratio = peak_ns / (peak_ns + peak_ew)
        ns_raw = round(ratio * self.CYCLE)
        sig.ns_green = max(self.MIN_GREEN, min(self.CYCLE - self.MIN_GREEN, float(ns_raw)))
        sig.ew_green = self.CYCLE - sig.ns_green
        sig.peak_ns_queue = 0.0
        sig.peak_ew_queue = 0.0

    def _update_vehicles(self):
        keep = []
        approach_queues = {}
        for v in self.vehicles:
            approach_queues.setdefault((v.junction, v.approach), []).append(v)

        for (junc, app), queue in approach_queues.items():
            queue.sort(key=lambda x: x.progress, reverse=True)
            head_progress = 1.0
            
            for v in queue:
                sig = self.signals.get(v.junction)
                if not sig:
                    v.progress += v.speed
                    keep.append(v)
                    continue

                if v.progress >= 0.35:
                    v.passed_signal = True

                must_stop = not v.passed_signal and not self._can_proceed(v.junction, v.approach)
                
                max_progress = min(head_progress - 0.025, 0.35 if must_stop else 1.0)
                
                if v.progress + v.speed > max_progress:
                    v.progress = max(v.progress, max_progress)
                    v.waiting = True
                    v.wait_frames += 1
                    self._cum_wait_frames += 1
                else:
                    v.waiting = False
                    v.progress += v.speed

                if v.progress >= 1.0:
                    self.exits += 1
                    self._exit_ts.append(self.frame)
                    continue

                head_progress = v.progress
                if v.progress < 1.5:
                    keep.append(v)
                    
        self.vehicles = keep

    def _record_metrics(self):
        total = len(self.vehicles)
        waiting = sum(1 for v in self.vehicles if v.waiting)
        cong = waiting / max(total, 1) * 100
        wait_frames_list = [v.wait_frames for v in self.vehicles if v.waiting]
        avg_wait = (sum(wait_frames_list) / len(wait_frames_list) / self.fps) if wait_frames_list else 0.0
        recent_exits = sum(1 for t in self._exit_ts if self.frame - t < 60 * self.fps)
        throughput_pm = recent_exits / 60.0 * 60
        self.history["avg_wait_s"].append(avg_wait)
        self.history["throughput_pm"].append(throughput_pm)
        self.history["congestion_pct"].append(cong)
        self.history["waiting_count"].append(waiting)
        self.history["total_vehicles"].append(total)

    # ─── Public API ───────────────────────────────────────────────────────────

    def get_metrics(self) -> dict:
        h = self.history
        return {
            "avg_wait_s": h["avg_wait_s"][-1] if h["avg_wait_s"] else 0.0,
            "throughput_pm": h["throughput_pm"][-1] if h["throughput_pm"] else 0.0,
            "congestion_pct": h["congestion_pct"][-1] if h["congestion_pct"] else 0.0,
            "waiting_count": h["waiting_count"][-1] if h["waiting_count"] else 0,
            "total_vehicles": h["total_vehicles"][-1] if h["total_vehicles"] else 0,
            "frame": self.frame,
            "time_s": self.time_s,
            "hour": self.hour,
        }

    def get_signal_state(self) -> list[dict]:
        out = []
        for sig in self.signals.values():
            out.append({
                "name": sig.name,
                "phase": sig.active_phase.value,
                "ns_green": sig.ns_green,
                "ew_green": sig.ew_green,
                "ns_queue": round(sig.ns_queue, 2),
                "ew_queue": round(sig.ew_queue, 2),
                "sw_queue": round(sig.sw_queue, 2),
                "ne_queue": round(sig.ne_queue, 2),
                "ns_score": round(sig.ns_wait_score, 2),
                "ew_score": round(sig.ew_wait_score, 2),
                "override": sig.override,
                "congestion": round(sig.congestion_pct, 1),
                "total_queue": round(sig.total_queue, 1),
            })
        return out

    def dispatch_emergency(self, junction: str = "HSR_Layout", approach: str = "NS_Hosur_Road",
                           vehicle_type: str = "ambulance") -> int:
        route = []
        if junction == "HSR_Layout":
            route = ["HSR_Layout", "Silk_Board", "Madiwala"]
        elif junction == "BTM_Layout":
            route = ["BTM_Layout", "Silk_Board"]
        elif junction == "Madiwala":
            route = ["Madiwala"]
        else:
            route = [junction]
        vid = self._create_vehicle(junction, approach, is_emergency=True, color="#EF4444",
                                    route=route, vehicle_type=vehicle_type)
        return vid

    def release_corridor(self):
        for sig in self.signals.values():
            sig.override = False
            sig.override_priority = 0

    def set_signal_timings(self, name: str, ns_green: float, ew_green: float):
        sig = self.signals.get(name)
        if sig and not sig.override:
            sig.ns_green = ns_green
            sig.ew_green = ew_green
