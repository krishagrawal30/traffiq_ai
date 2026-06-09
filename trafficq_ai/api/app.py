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

from simulation.engine import TrafficSimulation
from agents.signal_optimizer   import SignalOptimizerAgent
from agents.route_recommender  import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent
from agents.orchestrator       import TrafficOrchestrator
from api.models import (
    SimulationConfig, StepResponse, EmergencyRequest, EmergencyResponse,
    AnalysisRequest, AnalysisResponse, HealthResponse,
)

# ─── Globals (one simulation instance per process) ────────────────────────────

_sim:   Optional[TrafficSimulation]   = None
_orch:  Optional[TrafficOrchestrator] = None
_emerg: Optional[EmergencyPriorityAgent] = None

_ws_clients: list[WebSocket] = []


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
            message       = (
                f"{req.vehicle_type.capitalize()} #{req.vehicle_id} detected. "
                f"Green corridor activated: {' → '.join(event.corridor_intersections)}."
            ),
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

def _build_step_response(sim: TrafficSimulation) -> StepResponse:
    m = sim.get_metrics()
    return StepResponse(
        frame           = m["frame"],
        time_s          = m["time_s"],
        total_vehicles  = m["total_vehicles"],
        waiting_count   = m["waiting_count"],
        avg_wait_s      = round(m["avg_wait_s"], 2),
        throughput_pm   = round(m["throughput_pm"], 1),
        congestion_pct  = round(m["congestion_pct"], 1),
        signal_states   = sim.get_signal_state(),
    )


app = create_app()
