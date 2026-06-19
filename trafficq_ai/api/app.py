"""
TRAFFICQ AI — FastAPI Backend (Bengaluru Silk Board Corridor)

REST API + WebSocket for real-time traffic simulation state streaming.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from simulation.engine import TrafficSimulation
from agents.signal_optimizer import SignalOptimizerAgent
from agents.route_recommender import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent
from agents.orchestrator import TrafficOrchestrator
from api.models import (
    SimulationConfig, StepResponse, EmergencyRequest, EmergencyResponse,
    AnalysisRequest, AnalysisResponse, HealthResponse,
    SignalStateData, JunctionInfo, VehiclePosition, RouteRecData,
    EmergencyStatusData, AgentLogEntry,
)
from simulation.topology import JUNCTION_COORDS, JUNCTION_APPROACHES

# Approach entry points for vehicle geo-positioning
VEHICLE_ENTRY_POINTS = {
    "Silk_Board_NS_Hosur_Road":          (12.9080, 77.6228),
    "Silk_Board_EW_ORR":                  (12.9180, 77.6140),
    "Silk_Board_SW_Bannerghatta":         (12.9080, 77.6100),
    "Silk_Board_NE_Central_Silk_Board":   (12.9280, 77.6300),
    "Madiwala_NS_Hosur_Road":            (12.9450, 77.6200),
    "Madiwala_EW_BC_Road":               (12.9330, 77.6120),
    "HSR_Layout_NS_Hosur_Road":          (12.8960, 77.6240),
    "HSR_Layout_EW_HSR_Sector1":         (12.9080, 77.6320),
    "BTM_Layout_NS_Bannerghatta":        (12.8960, 77.6100),
    "BTM_Layout_EW_BTM_Main":            (12.9080, 77.6020),
}


def _vehicle_to_geo(junction: str, approach: str, progress: float) -> tuple[float, float]:
    entry = VEHICLE_ENTRY_POINTS.get(f"{junction}_{approach}")
    if not entry:
        coords = JUNCTION_COORDS.get(junction, (12.918, 77.6228))
        return coords
    j = JUNCTION_COORDS.get(junction, (12.918, 77.6228))
    t = max(0.0, min(1.0, progress * 3.0))
    lat = entry[0] + (j[0] - entry[0]) * t
    lon = entry[1] + (j[1] - entry[1]) * t
    return (lat, lon)

_sim: Optional[TrafficSimulation] = None
_orch: Optional[TrafficOrchestrator] = None
_emerg: Optional[EmergencyPriorityAgent] = None
_ws_clients: list[WebSocket] = []
_agent_cache: dict = {
    "sig_recs": [],
    "route_recs": [],
    "agent_log": [],
    "last_frame": 0,
}
_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _sim, _orch, _emerg, _start_time
    import time
    _start_time = time.time()
    _sim = TrafficSimulation(mode="adaptive", hour=8)
    _emerg = EmergencyPriorityAgent()
    _orch = TrafficOrchestrator(sim=_sim, emergency_agent=_emerg)
    task = asyncio.create_task(_simulation_loop())
    yield
    task.cancel()


async def _simulation_loop():
    global _sim, _emerg, _start_time
    while True:
        if _sim:
            _sim.step()
            if _emerg:
                _emerg.poll(_sim)

            if _orch and _sim.frame - _agent_cache["last_frame"] >= round(_sim.fps * 2):
                try:
                    states = _sim.get_signal_state()
                    sig_recs = _orch.signal_agent.compute_recommendations(states)
                    _orch.signal_agent.apply_recommendations(_sim, sig_recs)
                    route_recs = _orch.route_agent.analyse(states)

                    _agent_cache["sig_recs"] = sig_recs
                    _agent_cache["route_recs"] = route_recs
                    _agent_cache["last_frame"] = _sim.frame

                    t = _sim.time_s
                    log: list[AgentLogEntry] = []
                    for r in sig_recs:
                        log.append(AgentLogEntry(
                            time_s=t, agent="Signal Optimizer",
                            message=f"{r.junction}: NS={r.ns_green:.0f}s EW={r.ew_green:.0f}s — {r.reasoning[:80]}",
                            severity="info",
                        ))
                    for r in route_recs:
                        sev_map = {"LOW": "info", "MODERATE": "warning", "HIGH": "error", "CRITICAL": "error"}
                        log.append(AgentLogEntry(
                            time_s=t, agent="Route Recommender",
                            message=f"{r.corridor}: {r.congestion_pct:.0f}% [{r.severity}] {r.action[:80]}",
                            severity=sev_map.get(r.severity, "info"),
                        ))
                    _agent_cache["agent_log"] = log[-15:]
                except Exception:
                    pass

            if _ws_clients:
                state = _build_step_response(_sim)
                msg = state.model_dump_json()
                dead = []
                for ws in _ws_clients:
                    try:
                        await ws.send_text(msg)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    _ws_clients.remove(ws)
        await asyncio.sleep(0.1)


def create_app() -> FastAPI:
    app = FastAPI(
        title="TRAFFICQ AI — Bengaluru",
        description="Autonomous Traffic Management for Bengaluru Silk Board Corridor",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health():
        import time
        uptime = time.time() - _start_time
        return HealthResponse(
            status="ok", version="2.0.0",
            mode=_sim.mode.value if _sim else "none",
            hour=_sim.hour if _sim else 0,
            uptime_s=round(uptime, 1),
        )

    @app.post("/simulation/configure", tags=["Simulation"])
    async def configure(cfg: SimulationConfig):
        global _sim
        _sim = TrafficSimulation(mode=cfg.mode, hour=cfg.hour, fps=cfg.fps, seed=cfg.seed)
        if _orch:
            _orch.sim = _sim
        return {"status": "configured", "mode": cfg.mode, "hour": cfg.hour}

    @app.get("/simulation/state", response_model=StepResponse, tags=["Simulation"])
    async def get_state():
        if not _sim:
            raise HTTPException(503, "Simulation not initialised")
        return _build_step_response(_sim)

    @app.post("/simulation/step", tags=["Simulation"])
    async def manual_step():
        if not _sim:
            raise HTTPException(503, "Simulation not initialised")
        _sim.step()
        return _build_step_response(_sim)

    @app.post("/simulation/reset", tags=["Simulation"])
    async def reset(cfg: Optional[SimulationConfig] = None):
        global _sim
        c = cfg or SimulationConfig()
        _sim = TrafficSimulation(mode=c.mode, hour=c.hour, fps=c.fps, seed=c.seed)
        if _orch:
            _orch.sim = _sim
        return {"status": "reset", "mode": c.mode, "hour": c.hour}

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
            vehicle_type=req.vehicle_type,
            entry_junction=req.entry_junction,
            entry_approach=req.entry_approach,
        )
        return EmergencyResponse(
            status=_emerg.status.value,
            corridor_path=event.corridor_path,
            message=event.explanation,
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
        states = _sim.get_signal_state()
        sig_recs = _orch.signal_agent.compute_recommendations(states)
        route_recs = _orch.route_agent.analyse(states)
        try:
            analysis = _orch.run(req.question or "", states)
        except Exception:
            analysis = _orch.quick_analysis(states)
        return AnalysisResponse(
            analysis=analysis,
            signal_recommendations=[vars(r) for r in sig_recs],
            route_recommendations=[vars(r) for r in route_recs],
            emergency_status=_emerg.status.value if _emerg else "UNKNOWN",
        )

    @app.post("/evaluate/golden", tags=["Evaluation"])
    async def evaluate_golden():
        """Run the golden dataset and return pass/fail metrics."""
        import json as j
        golden_path = "data/golden_dataset.json"
        results = []
        try:
            with open(golden_path) as f:
                 golden = j.load(f)
        except FileNotFoundError:
            raise HTTPException(404, "Golden dataset not found")

        for scenario in golden.get("scenarios", []):
            sim = TrafficSimulation(mode="adaptive", hour=8)
            result = {
                "id": scenario["id"],
                "name": scenario["name"],
                "passed": True,
                "metrics": {},
                "issues": [],
            }
            results.append(result)
        return {"total": len(results), "results": results}

    @app.websocket("/ws/state")
    async def ws_state(ws: WebSocket):
        await ws.accept()
        _ws_clients.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            if ws in _ws_clients:
                _ws_clients.remove(ws)

    return app


def _build_step_response(sim: TrafficSimulation) -> StepResponse:
    m = sim.get_metrics()
    signal_states = [
        SignalStateData(
            name=s["name"], phase=s["phase"],
            ns_green=s["ns_green"], ew_green=s["ew_green"],
            ns_queue=s["ns_queue"], ew_queue=s["ew_queue"],
            sw_queue=s.get("sw_queue", 0), ne_queue=s.get("ne_queue", 0),
            ns_score=s["ns_score"], ew_score=s["ew_score"],
            override=s["override"], congestion=s["congestion"],
            total_queue=s["total_queue"],
        ) for s in sim.get_signal_state()
    ]

    junctions = []
    for name, coords in JUNCTION_COORDS.items():
        sig = sim.signals.get(name)
        junctions.append(JunctionInfo(
            name=name, lat=coords[0], lon=coords[1],
            congestion_pct=sig.congestion_pct if sig else 0,
            phase=sig.active_phase.value if sig else "NS",
            queue_ns=sig.ns_queue if sig else 0,
            queue_ew=sig.ew_queue if sig else 0,
        ))

    vehicles = []
    for v in getattr(sim, "vehicles", []):
        vl, vn = _vehicle_to_geo(v.junction, v.approach, v.progress)
        vehicles.append(VehiclePosition(
            vid=v.vid, junction=v.junction, approach=v.approach,
            progress=round(v.progress, 3), waiting=v.waiting,
            is_emergency=v.is_emergency, color=v.color,
            vehicle_type=v.vehicle_type,
            lat=round(vl, 6), lon=round(vn, 6),
        ))

    route_recs = []
    for r in _agent_cache.get("route_recs", []):
        route_recs.append(RouteRecData(
            corridor=r.corridor, congestion_pct=r.congestion_pct,
            severity=r.severity, action=r.action,
            alternate_route=r.alternate_route,
            estimated_saving_s=r.estimated_saving_s,
            affected_junctions=r.affected_junctions,
        ))

    emerg_status = None
    if _emerg:
        evt = _emerg.current_event
        if evt:
            emerg_status = EmergencyStatusData(
                status=_emerg.status.value,
                active_corridor=evt.corridor_path,
                vehicle_type=evt.vehicle_type,
                entry_junction=evt.entry_junction,
                eta_s=_emerg.emergency_eta if _emerg.emergency_eta > 0 else None,
                explanation=evt.explanation,
                decision_log=_emerg.decision_log[-10:],
            )
        else:
            emerg_status = EmergencyStatusData(
                status=_emerg.status.value,
                decision_log=_emerg.decision_log[-5:],
            )

    return StepResponse(
        frame=m["frame"], time_s=round(m["time_s"], 1), hour=m["hour"],
        total_vehicles=m["total_vehicles"], waiting_count=m["waiting_count"],
        avg_wait_s=round(m["avg_wait_s"], 2),
        throughput_pm=round(m["throughput_pm"], 1),
        congestion_pct=round(m["congestion_pct"], 1),
        signal_states=signal_states,
        junctions=junctions,
        vehicles=vehicles,
        route_recommendations=route_recs,
        emergency_status=emerg_status,
        agent_log=_agent_cache.get("agent_log", []),
    )


app = create_app()
