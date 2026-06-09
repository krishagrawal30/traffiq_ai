"""
TRAFFICQ AI — Agent 01: Signal Optimization
Computes optimal green-time splits using wait-time scores and issues
per-intersection timing recommendations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

# ─── Output types ─────────────────────────────────────────────────────────────

@dataclass
class SignalRecommendation:
    intersection: str
    ns_green: float          # recommended NS green time (seconds)
    ew_green: float          # recommended EW green time (seconds)
    offset_s: float          # green-wave offset relative to upstream inter
    reasoning: str
    confidence: float        # 0–1


# ─── Agent ────────────────────────────────────────────────────────────────────

class SignalOptimizerAgent:
    """
    Agent 01 — Signal Optimization

    Implements the wait-time formula:
        G(NS) = max(G_min, round( W(NS) / (W(NS)+W(EW)) × C ))

    and adds green-wave coordination by staggering offsets based on the
    average travel time between adjacent intersections.
    """

    CYCLE     = 60.0   # seconds
    MIN_GREEN = 15.0   # seconds (pedestrian safety floor)

    # Approximate travel time (seconds) between adjacent intersections
    TRAVEL_TIME = 12.0

    # Adjacent pairs for green-wave coordination (upstream → downstream)
    GREEN_WAVE_PAIRS = [
        ("NW", "NE"),  # eastbound top row
        ("NE", "NW"),  # westbound top row
        ("NW", "SW"),  # southbound left column
        ("SW", "NW"),  # northbound left column
        ("NE", "SE"),
        ("SE", "NE"),
        ("SW", "SE"),
        ("SE", "SW"),
    ]

    def __init__(self) -> None:
        self._offsets: Dict[str, float] = {n: 0.0 for n in ("NW", "NE", "SW", "SE")}

    # ── Public ────────────────────────────────────────────────────────────────

    def compute_recommendations(
        self,
        signal_states: List[dict],
    ) -> List[SignalRecommendation]:
        """
        Given current signal states (from simulation.get_signal_state()),
        return per-intersection timing recommendations.
        """
        recs: List[SignalRecommendation] = []
        state_by_name = {s["name"]: s for s in signal_states}

        for s in signal_states:
            name     = s["name"]
            ns_score = s["ns_score"]
            ew_score = s["ew_score"]
            total    = ns_score + ew_score

            if total < 0.5:
                ns_g = 30.0
                ew_g = 30.0
                reason = "Queue scores too low — maintaining equal split."
                conf   = 0.5
            else:
                ns_raw = round(ns_score / total * self.CYCLE)
                ns_g   = max(self.MIN_GREEN, min(self.CYCLE - self.MIN_GREEN, float(ns_raw)))
                ew_g   = self.CYCLE - ns_g
                ratio  = ns_score / total
                reason = (
                    f"NS score {ns_score:.1f} vs EW score {ew_score:.1f} "
                    f"→ NS gets {ratio*100:.0f}% of cycle."
                )
                conf = min(0.99, 0.5 + abs(ratio - 0.5))

            offset = self._compute_offset(name)
            recs.append(SignalRecommendation(
                intersection=name,
                ns_green=ns_g,
                ew_green=ew_g,
                offset_s=offset,
                reasoning=reason,
                confidence=conf,
            ))

        return recs

    def apply_recommendations(
        self,
        sim,
        recs: List[SignalRecommendation],
    ) -> None:
        """Push recommended timings into the running simulation."""
        for r in recs:
            inter = sim.intersections.get(r.intersection)
            if inter and not inter.override:
                inter.ns_green = r.ns_green
                inter.ew_green = r.ew_green

    def format_summary(self, recs: List[SignalRecommendation]) -> str:
        lines = ["Agent 01 — Signal Optimization Recommendations", "=" * 52]
        for r in recs:
            lines.append(
                f"  {r.intersection}: NS={r.ns_green:.0f}s  EW={r.ew_green:.0f}s  "
                f"offset={r.offset_s:.0f}s  conf={r.confidence:.0%}"
            )
            lines.append(f"    ↳ {r.reasoning}")
        return "\n".join(lines)

    # ── Private ───────────────────────────────────────────────────────────────

    def _compute_offset(self, name: str) -> float:
        """
        Simple green-wave offset: NW anchors at 0, adjacent intersections
        are offset by the expected inter-intersection travel time.
        """
        offsets = {
            "NW": 0.0,
            "NE": self.TRAVEL_TIME,
            "SW": self.TRAVEL_TIME,
            "SE": self.TRAVEL_TIME * 2,
        }
        return offsets.get(name, 0.0)
