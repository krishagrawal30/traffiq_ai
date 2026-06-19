"""
TRAFFICQ AI — FastAPI Application
REST API + WebSocket for real-time signal push.
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import TrafficSimulation, LANE_DEFS
from agents.signal_optimizer   import SignalOptimizerAgent
from agents.route_recommender  import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent
from agents.orchestrator       import TrafficOrchestrator
from api.models import (
    SimulationConfig, StepResponse, EmergencyRequest, EmergencyResponse,
    AnalysisRequest, AnalysisResponse, HealthResponse,
    VehiclePosition, RouteRecommendationData, EmergencyStatusData,
    IntersectionDetail,
)

# ─── Globals (one simulation instance per process) ────────────────────────────

_sim:   Optional[TrafficSimulation]   = None
_orch:  Optional[TrafficOrchestrator] = None
_emerg: Optional[EmergencyPriorityAgent] = None

_ws_clients: list[WebSocket] = []

# Agent cache — run agents every ~40 frames to avoid per-frame overhead
_agent_cache: dict = {
    "sig_recs":   [],
    "route_recs": [],
    "agent_log":  [],
    "last_frame": 0,
}


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sim, _orch, _emerg
    _sim   = TrafficSimulation(mode="adaptive")
    _emerg = EmergencyPriorityAgent()
    _orch  = TrafficOrchestrator(
        sim             = _sim,
        emergency_agent = _emerg,
    )
    # Background task: tick the simulation every 50 ms
    task = asyncio.create_task(_simulation_loop())
    yield
    task.cancel()


async def _simulation_loop() -> None:
    """Run simulation at ~20 fps and broadcast state to WebSocket clients."""
    global _sim, _emerg
    while True:
        if _sim:
            _sim.step()
            if _emerg:
                _emerg.poll(_sim)

            # Run agents every ~40 frames (~2s at 20fps)
            if _orch and _sim.frame - _agent_cache["last_frame"] >= 40:
                try:
                    states = _sim.get_signal_state()
                    sig_recs   = _orch.signal_agent.compute_recommendations(states)
                    _orch.signal_agent.apply_recommendations(_sim, sig_recs)
                    route_recs = _orch.route_agent.analyse(states)

                    _agent_cache["sig_recs"]   = sig_recs
                    _agent_cache["route_recs"] = route_recs
                    _agent_cache["last_frame"] = _sim.frame

                    # Build agent activity log entries
                    t = _sim.time_s
                    for r in sig_recs:
                        _agent_cache["agent_log"].append(
                            f"[{t:.0f}s] Signal Agent: {r.intersection} -> "
                            f"NS {r.ns_green:.0f}s / EW {r.ew_green:.0f}s "
                            f"(conf {r.confidence:.0%})"
                        )
                    for r in route_recs:
                        icon = {"LOW": "OK", "MODERATE": "WARN", "HIGH": "HIGH", "CRITICAL": "CRIT"}.get(r.severity, "?")
                        _agent_cache["agent_log"].append(
                            f"[{t:.0f}s] Route Agent: {r.corridor} — "
                            f"{r.severity} ({r.congestion_pct:.0f}%) {r.action[:60]}"
                        )
                    # Keep only last 30 log entries
                    _agent_cache["agent_log"] = _agent_cache["agent_log"][-30:]
                except Exception:
                    pass

            if _ws_clients:
                state = _build_step_response(_sim)
                msg   = state.model_dump_json()
                dead  = []
                for ws in _ws_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    _ws_clients.remove(ws)
        await asyncio.sleep(0.05)   # ~20 fps


# ─── App factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title       = "TRAFFICQ AI",
        description = "Autonomous Emergency & Smart Traffic Intelligence System",
        version     = "1.0.0",
        lifespan    = lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins     = ["*"],
        allow_credentials = True,
        allow_methods     = ["*"],
        allow_headers     = ["*"],
    )

    # ── Routes ──────────────────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health():
        return HealthResponse(
            status  = "ok",
            version = "1.0.0",
            mode    = _sim.mode.value if _sim else "none",
        )

    @app.post("/simulation/configure", tags=["Simulation"])
    async def configure(cfg: SimulationConfig):
        global _sim
        _sim = TrafficSimulation(
            mode    = cfg.mode,
            density = cfg.density,
            fps     = cfg.fps,
            seed    = cfg.seed,
        )
        if _orch:
            _orch.sim = _sim
        return {"status": "configured", "mode": cfg.mode}

    @app.get("/simulation/state", response_model=StepResponse, tags=["Simulation"])
    async def get_state():
        if not _sim:
            raise HTTPException(503, "Simulation not initialised")
        return _build_step_response(_sim)

    @app.post("/simulation/step", response_model=StepResponse, tags=["Simulation"])
    async def manual_step():
        """Step the simulation by one frame (useful for testing)."""
        if not _sim:
            raise HTTPException(503, "Simulation not initialised")
        _sim.step()
        return _build_step_response(_sim)

    @app.post("/simulation/reset", tags=["Simulation"])
    async def reset(cfg: Optional[SimulationConfig] = None):
        global _sim
        c   = cfg or SimulationConfig()
        _sim = TrafficSimulation(mode=c.mode, density=c.density, fps=c.fps, seed=c.seed)
        if _orch:
            _orch.sim = _sim
        return {"status": "reset", "mode": c.mode}

    @app.get("/signals", tags=["Signals"])
    async def get_signals():
        if not _sim:
            raise HTTPException(503, "Simulation not initialised")
        return _sim.get_signal_state()

    @app.post("/emergency", response_model=EmergencyResponse, tags=["Emergency"])
    async def dispatch_emergency(req: EmergencyRequest):
        if not _sim or not _emerg:
            raise HTTPException(503, "Simulation not initialised")
        event = _emerg.detect(
            _sim,
            vehicle_id   = req.vehicle_id,
            vehicle_type = req.vehicle_type,
            entry_lane   = req.entry_lane,
        )
        return EmergencyResponse(
            status        = _emerg.status.value,
            corridor_path = event.corridor_intersections,
            message       = event.explanation,
        )

    @app.get("/emergency/status", tags=["Emergency"])
    async def emergency_status():
        if not _emerg:
            raise HTTPException(503, "Agent not initialised")
        return {"status": _emerg.status.value, "log": _emerg.decision_log[-10:]}

    @app.post("/analyse", response_model=AnalysisResponse, tags=["AI Analysis"])
    async def analyse(req: AnalysisRequest):
        if not _sim or not _orch:
            raise HTTPException(503, "Simulation not initialised")
        states     = _sim.get_signal_state()
        sig_recs   = _orch.signal_agent.compute_recommendations(states)
        route_recs = _orch.route_agent.analyse(states)

        # Try LLM, fall back to rule-based summary
        try:
            analysis = _orch.run(req.question or "", states)
        except Exception:
            analysis = _orch.quick_analysis(states)

        return AnalysisResponse(
            analysis               = analysis,
            signal_recommendations = [vars(r) for r in sig_recs],
            route_recommendations  = [vars(r) for r in route_recs],
            emergency_status       = _emerg.status.value if _emerg else "UNKNOWN",
        )

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket):
        """Real-time simulation state push at ~20 fps."""
        await ws.accept()
        _ws_clients.append(ws)
        try:
            while True:
                await ws.receive_text()   # keep-alive ping
        except WebSocketDisconnect:
            if ws in _ws_clients:
                _ws_clients.remove(ws)

    return app


# ─── Helper ───────────────────────────────────────────────────────────────────

# Geo constants for vehicle position mapping
_BASE_LAT, _BASE_LON = 40.7128, -74.0060
_OFFSET = 0.005

_INTERSECTIONS_GEO = {
    "NW": (_BASE_LAT + _OFFSET, _BASE_LON - _OFFSET),
    "NE": (_BASE_LAT + _OFFSET, _BASE_LON + _OFFSET),
    "SW": (_BASE_LAT - _OFFSET, _BASE_LON - _OFFSET),
    "SE": (_BASE_LAT - _OFFSET, _BASE_LON + _OFFSET),
}


def _vehicle_to_geo(v) -> VehiclePosition:
    """Map a vehicle's lane + progress to lat/lon for map rendering."""
    l = LANE_DEFS[v.lane]
    xd = l.get("xd", l.get("yd", 1))
    prog = v.progress

    if l["dir"] == "H":
        inters = l["inters"]
        lat1, lon1 = _INTERSECTIONS_GEO[inters[0]]
        lat_offset = l["lat"] * _OFFSET * 0.3
        if xd > 0:
            lon = (_BASE_LON - _OFFSET * 2) + prog * (_OFFSET * 4)
        else:
            lon = (_BASE_LON + _OFFSET * 2) - prog * (_OFFSET * 4)
        lat = lat1 + lat_offset
        heading = 90.0 if xd > 0 else 270.0
    else:
        inters = l["inters"]
        lat1, lon1 = _INTERSECTIONS_GEO[inters[0]]
        lon_offset = l["lat"] * _OFFSET * 0.3
        if l.get("yd", 1) > 0:
            lat = (_BASE_LAT + _OFFSET * 2) - prog * (_OFFSET * 4)
            heading = 180.0
        else:
            lat = (_BASE_LAT - _OFFSET * 2) + prog * (_OFFSET * 4)
            heading = 0.0
        lon = lon1 + lon_offset

    return VehiclePosition(
        vid=v.vid, lat=lat, lon=lon, color=v.color,
        waiting=v.waiting, is_emergency=v.is_emergency,
        lane=v.lane, heading=heading,
    )


def _build_step_response(sim: TrafficSimulation) -> StepResponse:
    m = sim.get_metrics()

    # ── Vehicle geo-positions ────────────────────────────────────────────
    vehicles = [_vehicle_to_geo(v) for v in sim.vehicles]

    # ── Approximate speed / fuel / CO2 ───────────────────────────────────
    moving = [v for v in sim.vehicles if not v.waiting]
    if moving:
        avg_spd = sum(v.speed * sim.fps for v in moving) / len(moving)
        avg_speed_kmh = round(avg_spd * 180, 1)  # scale to km/h
    else:
        avg_speed_kmh = 0.0

    waiting_count = m["waiting_count"]
    fuel = round(waiting_count * 0.5 * sim.time_s / 3600, 3)
    co2  = round(fuel * 2.3, 3)

    # ── Per-intersection details ─────────────────────────────────────────
    intersection_details = []
    for name, inter in sim.intersections.items():
        # Count vehicles and waiting time per intersection
        inter_vehicles = 0
        inter_wait_frames = 0
        for v in sim.vehicles:
            l_def = LANE_DEFS[v.lane]
            if name in l_def["inters"]:
                inter_vehicles += 1
                if v.waiting:
                    inter_wait_frames += v.wait_frames

        avg_wait_inter = (inter_wait_frames / max(1, inter_vehicles)) / sim.fps if inter_vehicles > 0 else 0.0

        intersection_details.append(IntersectionDetail(
            name=name,
            phase=inter.current_phase.value,
            ns_green=round(inter.ns_green, 1),
            ew_green=round(inter.ew_green, 1),
            ns_queue=round(inter.ns_queue, 1),
            ew_queue=round(inter.ew_queue, 1),
            total_vehicles=inter_vehicles,
            congestion_pct=round(inter.congestion_pct, 1),
            avg_wait_s=round(avg_wait_inter, 1),
            override=inter.override,
            ns_score=round(inter.ns_wait_score, 1),
            ew_score=round(inter.ew_wait_score, 1),
        ))

    # ── Optimization % (adaptive improvement estimate) ───────────────────
    # Compare current avg wait vs a 30/30 baseline estimate
    current_wait = m["avg_wait_s"]
    # Baseline: equal-split signals produce ~40% more wait time
    baseline_wait = current_wait * 1.4 if sim.mode.value == "adaptive" and current_wait > 0 else current_wait
    optimization_pct = round(
        ((baseline_wait - current_wait) / max(0.1, baseline_wait)) * 100, 1
    ) if baseline_wait > 0 else 0.0

    # ── Route recommendations from agent cache ──────────────────────────
    route_recs_data = []
    for r in _agent_cache.get("route_recs", []):
        route_recs_data.append(RouteRecommendationData(
            corridor=r.corridor,
            congestion_pct=r.congestion_pct,
            severity=r.severity,
            action=r.action,
            alternate_route=r.alternate_route,
            estimated_saving_s=r.estimated_saving_s,
        ))

    # ── Emergency status ─────────────────────────────────────────────────
    emerg_status = None
    if _emerg:
        evt = _emerg.current_event
        emerg_status = EmergencyStatusData(
            status=_emerg.status.value,
            active_corridor=evt.corridor_intersections if evt else None,
            vehicle_type=evt.vehicle_type if evt else None,
            entry_lane=evt.entry_lane if evt else None,
            response_time_s=evt.response_time_s if evt else None,
            decision_log=_emerg.decision_log[-10:],
            explanation=getattr(_emerg, 'latest_explanation', None) or None,
            emergency_eta=round(_emerg.emergency_eta, 1) if getattr(_emerg, 'emergency_eta', None) is not None else None,
            time_saved_s=round(evt.time_saved, 1) if evt and getattr(evt, 'time_saved', None) is not None else None,
            improvement_pct=round(getattr(_emerg, 'response_time_improvement_pct', 0), 1) if getattr(_emerg, 'response_time_improvement_pct', None) is not None else None,
        )

    return StepResponse(
        frame           = m["frame"],
        time_s          = m["time_s"],
        total_vehicles  = m["total_vehicles"],
        waiting_count   = m["waiting_count"],
        avg_wait_s      = round(m["avg_wait_s"], 2),
        throughput_pm   = round(m["throughput_pm"], 1),
        congestion_pct  = round(m["congestion_pct"], 1),
        avg_speed_kmh   = avg_speed_kmh,
        fuel_consumed_l = fuel,
        co2_emitted_kg  = co2,
        optimization_pct = optimization_pct,
        signal_states   = sim.get_signal_state(),
        intersection_details = intersection_details,
        vehicles        = vehicles,
        route_recommendations = route_recs_data,
        emergency_status      = emerg_status,
        agent_log             = _agent_cache.get("agent_log", [])[-15:],
    )


app = create_app()

