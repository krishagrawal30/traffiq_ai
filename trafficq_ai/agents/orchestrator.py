"""
Agent Orchestrator — LangChain-powered coordination layer

Wraps Agent 01/02/03 as LangChain tools with an LLM that produces
explainable natural-language traffic management decisions.
"""

from __future__ import annotations

import json
from typing import Optional

_LANGCHAIN_AVAILABLE = False
try:
    from langchain.agents import AgentExecutor, create_openai_tools_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.tools import StructuredTool
    from langchain_openai import ChatOpenAI, AzureChatOpenAI
    from pydantic import BaseModel, Field
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseModel = object
    Field = lambda **kw: None

from config import settings
from agents.signal_optimizer import SignalOptimizerAgent, SignalRecommendation
from agents.route_recommender import RouteRecommenderAgent, RouteRecommendation
from agents.emergency_priority import EmergencyPriorityAgent, EmergencyEvent

SYSTEM_PROMPT = """You are TRAFFICQ AI, an autonomous traffic management system for Bengaluru's Silk Board corridor — one of India's most congested junctions.

You manage 4 junctions (Silk_Board, Madiwala, HSR_Layout, BTM_Layout) using 3 specialist agents:

• Agent 01 (signal_optimizer) — adjusts green-light timing based on queue lengths and wait times.
• Agent 02 (route_recommender) — monitors corridor congestion and suggests diversions.
• Agent 03 (emergency_priority) — creates green corridors for emergency vehicles.

Your job:
1. Analyse the provided traffic state JSON.
2. Call the appropriate tools.
3. Explain EVERY decision in plain English with specific numbers.
4. Always mention: which junction, which direction, and WHY.

Safety: Minimum green 15s. Emergency ALWAYS overrides standard optimisation.

Bengaluru traffic context:
- Morning peak (8-10 AM): Hosur Road NS direction heaviest (Electronic City → City)
- Evening peak (5:30-8 PM): ORR EW direction heaviest (office return traffic)
- Silk Board is the bottleneck — coordinate with Madiwala and HSR Layout
"""

if _LANGCHAIN_AVAILABLE:
    class SignalOptInput(BaseModel):
        signal_states_json: str = Field(description="JSON array of current signal states")

    class RouteInput(BaseModel):
        signal_states_json: str = Field(description="JSON array of current signal states")

    class EmergencyInput(BaseModel):
        vehicle_type: str = Field(default="ambulance", description="ambulance | fire | police")
        entry_junction: str = Field(default="HSR_Layout", description="Entry junction name")
        entry_approach: str = Field(default="NS_Hosur_Road", description="Entry approach lane")

class TrafficOrchestrator:
    def __init__(self, sim=None, signal_agent=None, route_agent=None, emergency_agent=None):
        self.sim = sim
        self.signal_agent = signal_agent or SignalOptimizerAgent()
        self.route_agent = route_agent or RouteRecommenderAgent()
        self.emergency_agent = emergency_agent or EmergencyPriorityAgent()

        self._llm = self._build_llm()
        self._tools = self._build_tools()
        self._executor = self._build_executor()

    def run(self, user_message: str, signal_states: list[dict]) -> str:
        if not _LANGCHAIN_AVAILABLE or not self._executor:
            return self.quick_analysis(signal_states)
        try:
            state_str = json.dumps(signal_states, indent=2)
            result = self._executor.invoke({
                "input": user_message,
                "state": state_str,
            })
            return result.get("output", "No response generated.")
        except Exception as e:
            return f"[LLM fallback] {e}\n\n" + self.quick_analysis(signal_states)

    def quick_analysis(self, signal_states: list[dict]) -> str:
        sig_recs = self.signal_agent.compute_recommendations(signal_states)
        route_recs = self.route_agent.analyse(signal_states)

        lines = ["── TRAFFICQ AI — Real-Time Analysis ──\n"]

        lines.append("≡ Agent 01: Signal Optimization")
        for r in sig_recs:
            lines.append(f"  ◆ {r.junction}: NS={r.ns_green:.0f}s EW={r.ew_green:.0f}s [confidence: {r.confidence:.0%}]")
            lines.append(f"    {r.reasoning}")
            lines.append(f"    Impact: {r.estimated_impact}")

        lines.append("\n≡ Agent 02: Route Recommendations")
        for r in route_recs:
            icon = {"LOW": "✓", "MODERATE": "△", "HIGH": "!", "CRITICAL": "⊘"}.get(r.severity, "?")
            lines.append(f"  {icon} {r.corridor}: {r.congestion_pct:.0f}% [{r.severity}]")
            lines.append(f"    {r.action}")
            if r.severity in ("HIGH", "CRITICAL"):
                lines.append(f"    Alternate: {r.alternate_route} (~{r.estimated_saving_s:.0f}s saved)")

        lines.append(f"\n≡ Agent 03: Emergency")
        lines.append(f"  Status: {self.emergency_agent.status.value}")
        if self.emergency_agent.current_event:
            e = self.emergency_agent.current_event
            lines.append(f"  Active: {e.vehicle_type} #{e.vehicle_id} → {' → '.join(e.corridor_path)}")

        return "\n".join(lines)

    def _build_llm(self):
        if not _LANGCHAIN_AVAILABLE:
            return None
        try:
            if settings.llm_provider == "azure" and settings.azure_openai_api_key:
                return AzureChatOpenAI(
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_key=settings.azure_openai_api_key,
                    api_version=settings.azure_openai_api_version,
                    azure_deployment=settings.azure_openai_deployment,
                    temperature=0,
                )
            elif settings.openai_api_key:
                return ChatOpenAI(
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    temperature=0,
                )
        except Exception:
            pass
        return None

    def _build_tools(self) -> list:
        if not _LANGCHAIN_AVAILABLE:
            return []

        def _signal_opt(signal_states_json: str) -> str:
            states = json.loads(signal_states_json)
            recs = self.signal_agent.compute_recommendations(states)
            if self.sim:
                self.signal_agent.apply_recommendations(self.sim, recs)
            lines = ["Signal Optimization Results:"]
            for r in recs:
                lines.append(f"  {r.junction}: NS={r.ns_green:.0f}s EW={r.ew_green:.0f}s — {r.reasoning}")
            return "\n".join(lines)

        def _route_rec(signal_states_json: str) -> str:
            states = json.loads(signal_states_json)
            recs = self.route_agent.analyse(states)
            lines = ["Route Recommendation Results:"]
            for r in recs:
                lines.append(f"  [{r.severity}] {r.corridor}: {r.congestion_pct:.0f}% — {r.action}")
            return "\n".join(lines)

        def _emergency(vehicle_type: str, entry_junction: str, entry_approach: str) -> str:
            if self.sim is None:
                return "No simulation attached."
            event = self.emergency_agent.detect(
                self.sim,
                vehicle_type=vehicle_type,
                entry_junction=entry_junction,
                entry_approach=entry_approach,
            )
            return event.explanation

        return [
            StructuredTool(
                name="signal_optimizer",
                description="Compute and apply optimal signal timing. Input: JSON of signal states.",
                func=_signal_opt,
                args_schema=SignalOptInput,
            ),
            StructuredTool(
                name="route_recommender",
                description="Analyse corridor congestion and recommend diversions. Input: JSON of signal states.",
                func=_route_rec,
                args_schema=RouteInput,
            ),
            StructuredTool(
                name="emergency_priority",
                description="Activate green corridor for emergency vehicle.",
                func=_emergency,
                args_schema=EmergencyInput,
            ),
        ]

    def _build_executor(self):
        if not _LANGCHAIN_AVAILABLE or self._llm is None:
            return None
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Current traffic state:\n{state}\n\nRequest: {input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        agent = create_openai_tools_agent(self._llm, self._tools, prompt)
        return AgentExecutor(agent=agent, tools=self._tools, verbose=True)
