"""TRAFFICQ AI — API Pydantic models."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class SimulationConfig(BaseModel):
    mode:    str       = Field("adaptive", description="'static' or 'adaptive'")
    density: List[int] = Field([65, 60, 40, 45], description="[NS_col1, NS_col2, EW_row1, EW_row2] 0–100")
    fps:     int       = Field(20, description="Simulation frames per second")
    seed:    int       = Field(42, description="Random seed")


class VehiclePosition(BaseModel):
    vid: int
    lat: float
    lon: float
    color: str = "#3B82F6"
    waiting: bool = False
    is_emergency: bool = False
    lane: str = ""
    heading: float = 0.0


class IntersectionDetail(BaseModel):
    """Per-node metrics for map overlays."""
    name: str
    phase: str
    ns_green: float
    ew_green: float
    ns_queue: float
    ew_queue: float
    total_vehicles: int
    congestion_pct: float
    avg_wait_s: float
    override: bool = False
    ns_score: float = 0.0
    ew_score: float = 0.0


class RouteRecommendationData(BaseModel):
    corridor: str
    congestion_pct: float
    severity: str
    action: str
    alternate_route: str
    estimated_saving_s: float


class EmergencyStatusData(BaseModel):
    status: str
    active_corridor: Optional[List[str]] = None
    vehicle_type: Optional[str] = None
    entry_lane: Optional[str] = None
    response_time_s: Optional[float] = None
    decision_log: List[str] = []
    explanation: Optional[str] = None
    emergency_eta: Optional[float] = None
    time_saved_s: Optional[float] = None
    improvement_pct: Optional[float] = None


class StepResponse(BaseModel):
    frame:           int
    time_s:          float
    total_vehicles:  int
    waiting_count:   int
    avg_wait_s:      float
    throughput_pm:   float
    congestion_pct:  float
    avg_speed_kmh:   float = 0.0
    fuel_consumed_l: float = 0.0
    co2_emitted_kg:  float = 0.0
    optimization_pct: float = 0.0
    signal_states:   List[dict]
    intersection_details: List[IntersectionDetail] = []
    vehicles:        List[VehiclePosition] = []
    route_recommendations: List[RouteRecommendationData] = []
    emergency_status: Optional[EmergencyStatusData] = None
    agent_log:       List[str] = []


class EmergencyRequest(BaseModel):
    vehicle_type: str = Field("ambulance", description="ambulance | fire | police")
    entry_lane:   str = Field("EB_top", description="Which lane the vehicle enters from")
    vehicle_id:   int = Field(999)


class EmergencyResponse(BaseModel):
    status:        str
    corridor_path: List[str]
    message:       str


class AnalysisRequest(BaseModel):
    question: Optional[str] = Field(
        "Analyse current traffic state and recommend optimisations.",
        description="Natural-language question for the LLM agent",
    )


class AnalysisResponse(BaseModel):
    analysis: str
    signal_recommendations: List[dict]
    route_recommendations:  List[dict]
    emergency_status:       str


class HealthResponse(BaseModel):
    status:  str
    version: str
    mode:    str
