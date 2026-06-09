"""
TRAFFICQ AI — Agent Orchestrator
LangChain-powered orchestration layer that calls Agent 01/02/03 as tools
and uses an LLM to produce explainable natural-language decisions.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic import BaseModel, Field

from config import settings
from agents.signal_optimizer import SignalOptimizerAgent
from agents.route_recommender import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent


# ─── Tool input schemas ───────────────────────────────────────────────────────

class SignalOptInput(BaseModel):
    signal_states_json: str = Field(
        description="JSON string of current signal states from simulation.get_signal_state()"
    )

class RouteInput(BaseModel):
    signal_states_json: str = Field(
        description="JSON string of current signal states"
    )

class EmergencyInput(BaseModel):
    vehicle_type: str  = Field(default="ambulance", description="Type of emergency vehicle")
    entry_lane:   str  = Field(default="EB_top",    description="Entry lane key")
    vehicle_id:   int  = Field(default=999,         description="Vehicle identifier")


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class TrafficOrchestrator:
    """
    LangChain agent that wraps the three sub-agents as callable tools.

    The LLM reasons over:
      - Current signal states (queue depths, wait scores, phases)
      - Current route congestion
      - Any active emergency

    and returns:
      - A list of tool calls (signal updates, diversions, emergency activation)
      - A plain-English explanation of every decision
    """

    SYSTEM_PROMPT = """You are TRAFFICQ AI, an autonomous traffic management system.
You manage a 2×2 intersection grid (NW, NE, SW, SE) using three specialist agents:

• Agent 01 (signal_optimizer)   — adjusts green-light timing per intersection.
• Agent 02 (route_recommender)  — recommends traffic diversions when corridors congest.
• Agent 03 (emergency_priority) — creates automated green corridors for first responders.

Your job:
1. Analyse the provided traffic state.
2. Call the appropriate tools.
3. Explain every decision in plain English so city engineers can audit it.

Safety constraints:
- Minimum green time: 15 seconds (pedestrians must cross safely).
- Never issue conflicting green phases at the same intersection.
- Emergency priority ALWAYS overrides standard optimisation.
"""

    def __init__(
        self,
        sim=None,
        signal_agent:    Optional[SignalOptimizerAgent]   = None,
        route_agent:     Optional[RouteRecommenderAgent]  = None,
        emergency_agent: Optional[EmergencyPriorityAgent] = None,
    ) -> None:
        self.sim             = sim
        self.signal_agent    = signal_agent    or SignalOptimizerAgent()
        self.route_agent     = route_agent     or RouteRecommenderAgent()
        self.emergency_agent = emergency_agent or EmergencyPriorityAgent()

        self._llm      = self._build_llm()
        self._tools    = self._build_tools()
        self._executor = self._build_executor()

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, user_message: str, signal_states: List[dict]) -> str:
        """
        Run the orchestrator with a natural-language request and current state.
        Returns the LLM's final plain-English response.
        """
        state_str = json.dumps(signal_states, indent=2)
        result = self._executor.invoke({
            "input": user_message,
            "state": state_str,
        })
        return result.get("output", "No response generated.")

    def quick_analysis(self, signal_states: List[dict]) -> str:
        """
        Fast path: no LLM call — just run all three agents and summarise.
        Useful when LLM is not configured.
        """
        sig_recs   = self.signal_agent.compute_recommendations(signal_states)
        route_recs = self.route_agent.analyse(signal_states)

        lines = []
        lines.append("── Agent 01: Signal Optimization ──")
        for r in sig_recs:
            lines.append(f"  {r.intersection}: NS={r.ns_green:.0f}s  EW={r.ew_green:.0f}s  [{r.confidence:.0%}]")
            lines.append(f"    {r.reasoning}")

        lines.append("\n── Agent 02: Route Recommendations ──")
        for r in route_recs:
            lines.append(f"  {r.corridor:<14} {r.congestion_pct:>5.1f}%  [{r.severity}]  {r.action}")

        lines.append(f"\n── Agent 03: Emergency ──")
        lines.append(f"  Status: {self.emergency_agent.status.value}")

        return "\n".join(lines)

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_llm(self):
        try:
            if settings.llm_provider == "azure" and settings.azure_openai_api_key:
                return AzureChatOpenAI(
                    azure_endpoint    = settings.azure_openai_endpoint,
                    api_key           = settings.azure_openai_api_key,
                    api_version       = settings.azure_openai_api_version,
                    azure_deployment  = settings.azure_openai_deployment,
                    temperature=0,
                )
            elif settings.openai_api_key:
                return ChatOpenAI(
                    api_key     = settings.openai_api_key,
                    model       = settings.openai_model,
                    temperature = 0,
                )
        except Exception:
            pass
        return None

    def _build_tools(self) -> List:
        def _signal_opt(signal_states_json: str) -> str:
            states = json.loads(signal_states_json)
            recs   = self.signal_agent.compute_recommendations(states)
            if self.sim:
                self.signal_agent.apply_recommendations(self.sim, recs)
            return self.signal_agent.format_summary(recs)

        def _route_rec(signal_states_json: str) -> str:
            states = json.loads(signal_states_json)
            recs   = self.route_agent.analyse(states)
            return self.route_agent.format_summary(recs)

        def _emergency(vehicle_type: str, entry_lane: str, vehicle_id: int) -> str:
            if self.sim is None:
                return "No simulation attached to orchestrator."
            event = self.emergency_agent.detect(
                self.sim,
                vehicle_id   = vehicle_id,
                vehicle_type = vehicle_type,
                entry_lane   = entry_lane,
            )
            return self.emergency_agent.format_summary()

        return [
            StructuredTool(
                name        = "signal_optimizer",
                description = "Compute and apply optimal signal timing for all intersections.",
                func        = _signal_opt,
                args_schema = SignalOptInput,
            ),
            StructuredTool(
                name        = "route_recommender",
                description = "Analyse corridor congestion and recommend diversions.",
                func        = _route_rec,
                args_schema = RouteInput,
            ),
            StructuredTool(
                name        = "emergency_priority",
                description = "Activate an emergency green corridor for a first-responder vehicle.",
                func        = _emergency,
                args_schema = EmergencyInput,
            ),
        ]

    def _build_executor(self) -> Optional[AgentExecutor]:
        if self._llm is None:
            return None
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human",  "Current signal state:\n{state}\n\nRequest: {input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        agent = create_openai_tools_agent(self._llm, self._tools, prompt)
        return AgentExecutor(agent=agent, tools=self._tools, verbose=True)
