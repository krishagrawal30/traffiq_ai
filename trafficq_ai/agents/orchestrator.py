"""
TRAFFICQ AI — Agent Orchestrator
LangChain-powered orchestration layer that calls Agent 01/02/03 as tools
and uses an LLM to produce explainable natural-language decisions.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# LangChain imports are optional — the orchestrator falls back to
# rule-based quick_analysis() when LangChain is unavailable or broken.
_LANGCHAIN_AVAILABLE = False
try:
    from pydantic import BaseModel, Field
    _LANGCHAIN_AVAILABLE = True
except Exception:
    # Provide lightweight stubs so the rest of the module can load
    BaseModel = object  # type: ignore[misc]
    Field = lambda *a, **kw: None  # type: ignore[assignment]

from config import settings
from agents.signal_optimizer import SignalOptimizerAgent
from agents.route_recommender import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent


# ─── Tool input schemas (only needed when LangChain is available) ─────────────

if _LANGCHAIN_AVAILABLE:
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
      - Current signal states (queue depths, priority scores, phases)
      - Current route congestion
      - Any active emergency

    and returns:
      - A list of tool calls (signal updates, diversions, emergency activation)
      - A plain-English explanation of every decision
    """

    SYSTEM_PROMPT = """You are TRAFFICQ AI, an autonomous traffic management system.
You manage a 2x2 intersection grid (NW, NE, SW, SE) using three specialist agents:

- Agent 01 (signal_optimizer)   -- adjusts green-light timing per intersection.
- Agent 02 (route_recommender)  -- recommends traffic diversions when corridors congest.
- Agent 03 (emergency_priority) -- creates automated green corridors for first responders.

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

        self._llm = self._build_llm()

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, user_message: str, signal_states: List[dict]) -> str:
        """
        Run the orchestrator with a natural-language request and current state.
        Returns the LLM's final plain-English response.
        """
        # Always build the context from the live agents first
        context = self.quick_analysis(signal_states)

        if not self._llm:
            return context

        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Here is the raw data from the simulation right now:\n"
            f"{json.dumps(signal_states, indent=2)}\n\n"
            f"Here are the exact decisions the backend agents just made:\n"
            f"{context}\n\n"
            f"The user is asking: '{user_message}'\n\n"
            f"Please respond as TRAFFICQ AI. Explain the current situation and the agents' decisions "
            f"in a professional, clear, and concise manner without outputting raw JSON. Make sure to "
            f"address the user's specific question."
        )

        try:
            response = self._llm.invoke(prompt)
            return response.content
        except Exception as e:
            # On ANY LLM error (quota, timeout, network), return the clean analysis
            return context

    def quick_analysis(self, signal_states: List[dict]) -> str:
        """
        Structured agent analysis that mirrors the sidebar data exactly.
        Always produces clean, professional output regardless of LLM availability.
        """
        sig_recs   = self.signal_agent.compute_recommendations(signal_states)
        route_recs = self.route_agent.analyse(signal_states)

        lines = []

        # ── Header with timestamp ────────────────────────────────────────
        if self.sim:
            lines.append(f"TRAFFICQ AI Analysis Report  |  T = {self.sim.time_s:.1f}s")
        else:
            lines.append("TRAFFICQ AI Analysis Report")
        lines.append("=" * 50)

        # ── Agent 01: Signal Optimization ────────────────────────────────
        lines.append("")
        lines.append("AGENT 01: Signal Optimization")
        lines.append("-" * 40)
        for r in sig_recs:
            lines.append(f"  [{r.intersection}]  NS = {r.ns_green:.0f}s  |  EW = {r.ew_green:.0f}s  |  Confidence: {r.confidence:.0%}")
            lines.append(f"    > {r.reasoning}")

        # ── Agent 02: Route Recommendations ──────────────────────────────
        lines.append("")
        lines.append("AGENT 02: Route Recommendations")
        lines.append("-" * 40)
        if route_recs:
            for r in route_recs:
                severity_icon = {"LOW": "OK", "MODERATE": "WATCH", "HIGH": "DIVERT", "CRITICAL": "ALERT"}.get(r.severity, "??")
                lines.append(f"  [{r.corridor:<12}]  Congestion: {r.congestion_pct:>5.1f}%  |  Status: {r.severity} ({severity_icon})")
                lines.append(f"    > {r.action}")
                if r.alternate_route and r.severity in ("HIGH", "CRITICAL"):
                    lines.append(f"    > Diverting to: {r.alternate_route}")
        else:
            lines.append("  All corridors flowing normally. No diversions needed.")

        # ── Agent 03: Emergency Priority ─────────────────────────────────
        lines.append("")
        lines.append("AGENT 03: Emergency Priority")
        lines.append("-" * 40)

        status_val = self.emergency_agent.status.value
        evt = self.emergency_agent.current_event

        if status_val in ["CORRIDOR_ACTIVE", "CLEARING"] and evt:
            lines.append(f"  *** ACTIVE EMERGENCY ***")
            lines.append(f"  Vehicle : {evt.vehicle_type.upper()} (ID: {evt.vehicle_id})")
            lines.append(f"  Entry   : {evt.entry_lane}")
            if evt.corridor_intersections:
                path_str = " -> ".join(evt.corridor_intersections)
                lines.append(f"  Route   : {path_str}")
            eta = getattr(self.emergency_agent, 'emergency_eta', 0)
            if eta:
                lines.append(f"  ETA     : {eta:.1f}s")
            lines.append(f"  Status  : GREEN CORRIDOR ACTIVE - All intersections on path overridden")
            if evt.explanation:
                lines.append(f"  AI Note : {evt.explanation[:200]}")

        elif status_val == "RESOLVED" and evt:
            lines.append(f"  Status  : RESOLVED (Emergency Cleared)")
            lines.append(f"  Vehicle : {evt.vehicle_type.upper()} (ID: {evt.vehicle_id})")
            if evt.time_saved is not None and evt.time_saved > 0:
                lines.append(f"  Saved   : {evt.time_saved:.1f}s")
            pct = getattr(self.emergency_agent, 'response_time_improvement_pct', 0)
            if pct and pct > 0:
                lines.append(f"  Improvement: {pct:.1f}% faster than standard flow")
            lines.append(f"  Signals have been returned to adaptive control.")

        else:
            lines.append(f"  Status  : STANDBY")
            lines.append(f"  Monitoring for emergency vehicles...")

        # ── Summary ──────────────────────────────────────────────────────
        lines.append("")
        lines.append("=" * 50)

        # Build a one-line summary
        total_congestion = sum(r.congestion_pct for r in route_recs) / max(len(route_recs), 1) if route_recs else 0
        if status_val in ["CORRIDOR_ACTIVE", "CLEARING"]:
            lines.append(f"PRIORITY: Emergency response in progress. All other traffic yielding.")
        elif total_congestion > 60:
            lines.append(f"WARNING: Network congestion at {total_congestion:.0f}%. Active diversions engaged.")
        elif total_congestion > 30:
            lines.append(f"ADVISORY: Moderate congestion ({total_congestion:.0f}%). Agents optimizing flow.")
        else:
            lines.append(f"STATUS: Network operating normally. Average congestion {total_congestion:.0f}%.")

        return "\n".join(lines)

    # ── Private ───────────────────────────────────────────────────────────────

    def _build_llm(self):
        try:
            if settings.llm_provider == "azure" and settings.azure_openai_api_key:
                from langchain_openai import AzureChatOpenAI
                return AzureChatOpenAI(
                    azure_endpoint    = settings.azure_openai_endpoint,
                    api_key           = settings.azure_openai_api_key,
                    api_version       = settings.azure_openai_api_version,
                    azure_deployment  = settings.azure_openai_deployment,
                    temperature=0,
                )
            elif settings.openai_api_key:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    api_key     = settings.openai_api_key,
                    model       = settings.openai_model,
                    temperature = 0,
                )
        except Exception:
            pass
        return None

