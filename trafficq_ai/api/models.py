"""TRAFFICQ AI — API Pydantic models."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class SimulationConfig(BaseModel):
    mode:    str       = Field("adaptive", description="'static' or 'adaptive'")
    density: List[int] = Field([65,60,40,45], description="[NS_col1, NS_col2, EW_row1, EW_row2] 0–100")
    fps:     int       = Field(20,            description="Simulation frames per second")
    seed:    int       = Field(42,            description="Random seed")


class StepResponse(BaseModel):
    frame:           int
    time_s:          float
    total_vehicles:  int
    waiting_count:   int
    avg_wait_s:      float
    throughput_pm:   float
    congestion_pct:  float
    signal_states:   List[dict]


class EmergencyRequest(BaseModel):
    vehicle_type: str = Field("ambulance", description="ambulance | fire | police")
    entry_lane:   str = Field("EB_top",    description="Which lane the vehicle enters from")
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
