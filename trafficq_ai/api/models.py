"""TRAFFICQ AI — API Pydantic models for Bengaluru traffic management."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class SimulationConfig(BaseModel):
    mode: str = Field("adaptive", description="'static' or 'adaptive'")
    hour: int = Field(8, description="Hour of day (0-23) for traffic pattern")
    fps: int = Field(10, description="Frames per second")
    seed: int = Field(42, description="Random seed")


class SignalStateData(BaseModel):
    name: str
    phase: str
    ns_green: float
    ew_green: float
    ns_queue: float
    ew_queue: float
    sw_queue: float
    ne_queue: float
    ns_score: float
    ew_score: float
    override: bool
    congestion: float
    total_queue: float


class JunctionInfo(BaseModel):
    name: str
    lat: float
    lon: float
    congestion_pct: float
    phase: str
    queue_ns: float
    queue_ew: float


class VehiclePosition(BaseModel):
    vid: int
    junction: str
    approach: str
    progress: float
    waiting: bool
    is_emergency: bool
    color: str
    vehicle_type: str = "car"
    lat: float = 12.918
    lon: float = 77.622


class RouteRecData(BaseModel):
    corridor: str
    congestion_pct: float
    severity: str
    action: str
    alternate_route: str
    estimated_saving_s: float
    affected_junctions: list[str]


class EmergencyStatusData(BaseModel):
    status: str
    active_corridor: Optional[list[str]] = None
    vehicle_type: Optional[str] = None
    entry_junction: Optional[str] = None
    eta_s: Optional[float] = None
    explanation: Optional[str] = None
    decision_log: list[str] = []


class AgentLogEntry(BaseModel):
    time_s: float
    agent: str
    message: str
    severity: str = "info"


class StepResponse(BaseModel):
    frame: int
    time_s: float
    hour: int
    total_vehicles: int
    waiting_count: int
    avg_wait_s: float
    throughput_pm: float
    congestion_pct: float
    signal_states: list[SignalStateData]
    junctions: list[JunctionInfo]
    vehicles: list[VehiclePosition]
    route_recommendations: list[RouteRecData] = []
    emergency_status: Optional[EmergencyStatusData] = None
    agent_log: list[AgentLogEntry] = []


class EmergencyRequest(BaseModel):
    vehicle_type: str = Field("ambulance", description="ambulance | fire | police")
    entry_junction: str = Field("HSR_Layout", description="HSR_Layout | BTM_Layout | Madiwala | Silk_Board")
    entry_approach: str = Field("NS_Hosur_Road", description="Approach lane name")


class EmergencyResponse(BaseModel):
    status: str
    corridor_path: list[str]
    message: str


class AnalysisRequest(BaseModel):
    question: Optional[str] = Field(
        "Analyse current traffic state and recommend optimisations.",
        description="Natural-language question for the LLM agent",
    )


class AnalysisResponse(BaseModel):
    analysis: str
    signal_recommendations: list[dict]
    route_recommendations: list[dict]
    emergency_status: str


class HealthResponse(BaseModel):
    status: str
    version: str
    mode: str
    hour: int
    uptime_s: float
