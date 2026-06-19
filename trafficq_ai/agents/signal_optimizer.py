"""
Agent 01 — Signal Optimization Agent (Bengaluru Silk Board Corridor)

Adjusts green-light splits per junction using a priority formula:
  G(direction) = round(P(direction) / ΣP × C)

Where P(direction) = Wait_Time × 0.5 + Queue_Length × 0.3 + Congestion × 0.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

CYCLE_S = 60.0
MIN_GREEN_S = 10.0

@dataclass
class SignalRecommendation:
    junction: str
    ns_green: float
    ew_green: float
    reasoning: str
    confidence: float
    estimated_impact: str

class SignalOptimizerAgent:
    def __init__(self):
        self._decision_log: list[str] = []

    def compute_recommendations(self, signal_states: list[dict]) -> list[SignalRecommendation]:
        recs: list[SignalRecommendation] = []
        for s in signal_states:
            name = s["name"]
            ns_wait = s.get("ns_score", 0)
            ew_wait = s.get("ew_score", 0)
            ns_queue = s.get("ns_queue", 0)
            ew_queue = s.get("ew_queue", 0)
            ns_cong = ns_queue / max(25, 1) * 100
            ew_cong = ew_queue / max(25, 1) * 100

            wait_factor = 0.5
            queue_factor = 0.3
            cong_factor = 0.2

            p_ns = ns_wait * wait_factor + ns_queue * queue_factor + ns_cong * cong_factor
            p_ew = ew_wait * wait_factor + ew_queue * queue_factor + ew_cong * cong_factor
            total = p_ns + p_ew

            if total < 1.0:
                ns_g = 30.0
                ew_g = 30.0
                reason = f"Low traffic at {name} — maintaining balanced 30s/30s split"
                conf = 0.3
            else:
                ns_raw = round(p_ns / total * CYCLE_S)
                ns_g = max(MIN_GREEN_S, min(CYCLE_S - MIN_GREEN_S, float(ns_raw)))
                ew_g = CYCLE_S - ns_g
                ratio = p_ns / total
                ns_label = f"NS gets {ratio*100:.0f}% of cycle"
                ew_label = f"EW gets {(1-ratio)*100:.0f}% of cycle"
                dominance = "NS" if ratio > 0.55 else "EW" if ratio < 0.45 else "balanced"
                reason = (
                    f"{name}: NS wait score {ns_wait:.1f}s (queue {ns_queue:.0f}), "
                    f"EW wait score {ew_wait:.1f}s (queue {ew_queue:.0f}). "
                    f"{ns_label}, {ew_label}. Signal dominance: {dominance}."
                )
                conf = min(0.95, 0.5 + abs(ratio - 0.5))

            impact = self._estimate_impact(ns_g, ew_g, ns_queue, ew_queue)
            rec = SignalRecommendation(
                junction=name,
                ns_green=ns_g,
                ew_green=ew_g,
                reasoning=reason,
                confidence=round(conf, 2),
                estimated_impact=impact,
            )
            self._decision_log.append(reason)
            recs.append(rec)
        return recs

    def apply_recommendations(self, sim, recs: list[SignalRecommendation]):
        for r in recs:
            sim.set_signal_timings(r.junction, r.ns_green, r.ew_green)

    @staticmethod
    def _estimate_impact(ns_g: float, ew_g: float, ns_q: float, ew_q: float) -> str:
        if ns_q > 30 or ew_q > 30:
            return "High — expected to clear >85% of queued vehicles this cycle"
        if ns_q > 15 or ew_q > 15:
            return "Moderate — gradual queue reduction expected"
        return "Low — maintaining flow on clear approaches"

    def get_log(self) -> list[str]:
        return self._decision_log[-20:]
