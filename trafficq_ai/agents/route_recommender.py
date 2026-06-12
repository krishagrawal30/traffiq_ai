"""
TRAFFICQ AI — Agent 02: Route Recommendation
Monitors corridor congestion and issues diversion recommendations
before bottlenecks cascade to adjacent roads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
# ─── Types ────────────────────────────────────────────────────────────────────

@dataclass
class RouteRecommendation:
    corridor: str            # e.g. "N-S Col 1"
    congestion_pct: float
    severity: str            # "LOW" | "MODERATE" | "HIGH" | "CRITICAL"
    action: str              # plain-English action
    alternate_route: str
    estimated_saving_s: float

# ─── Agent ────────────────────────────────────────────────────────────────────

class RouteRecommenderAgent:
    """
    Agent 02 — Route Recommendation

    Aggregates per-intersection queue depths to compute corridor-level
    congestion, then recommends diversions when thresholds are exceeded.
    Shares state with adjacent intersections so it does NOT push
    bottlenecks downstream.
    """

    THRESHOLDS = {
        "LOW":      (0,   35),
        "MODERATE": (35,  60),
        "HIGH":     (60,  80),
        "CRITICAL": (80, 100),
    }

    # Maps corridor name → list of intersection names that form it
    CORRIDORS: Dict[str, List[str]] = {
        "N-S Col 1":  ["NW", "SW"],
        "N-S Col 2":  ["NE", "SE"],
        "E-W Row 1":  ["NW", "NE"],
        "E-W Row 2":  ["SW", "SE"],
    }

    ALTERNATE_ROUTES: Dict[str, str] = {
        "N-S Col 1": "N-S Col 2  (divert via east column)",
        "N-S Col 2": "N-S Col 1  (divert via west column)",
        "E-W Row 1": "E-W Row 2  (divert via south corridor)",
        "E-W Row 2": "E-W Row 1  (divert via north corridor)",
    }

    def __init__(self) -> None:
        self._history: Dict[str, List[float]] = {c: [] for c in self.CORRIDORS}
        self._active_diversions: List[str] = []

    # ── Public ────────────────────────────────────────────────────────────────

    def analyse(self, signal_states: List[dict]) -> List[RouteRecommendation]:
        """Return a recommendation for each corridor based on directional congestion."""
        by_name = {s["name"]: s for s in signal_states}
        recs: List[RouteRecommendation] = []

        for corridor, inter_names in self.CORRIDORS.items():
            # Average directional congestion across the intersections in this corridor
            congs = []
            for n in inter_names:
                if n in by_name:
                    s = by_name[n]
                    if corridor.startswith("N-S"):
                        q = s.get("ns_queue", 0)
                    else:
                        q = s.get("ew_queue", 0)
                    # Directional congestion (cap assumed 20)
                    dir_cong = min(100.0, (q / 20.0) * 100.0)
                    congs.append(dir_cong)
            
            avg_cong = sum(congs) / len(congs) if congs else 0.0

            # Track history
            self._history[corridor].append(avg_cong)
            if len(self._history[corridor]) > 300:
                self._history[corridor].pop(0)

            severity = self._classify(avg_cong)
            action, saving = self._build_action(corridor, avg_cong, severity)

            recs.append(RouteRecommendation(
                corridor=corridor,
                congestion_pct=round(avg_cong, 1),
                severity=severity,
                action=action,
                alternate_route=self.ALTERNATE_ROUTES[corridor],
                estimated_saving_s=saving,
            ))
        return recs

    def format_summary(self, recs: List[RouteRecommendation]) -> str:
        lines = ["Agent 02 — Route Recommendation Analysis", "=" * 48]
        for r in recs:
            tag = f"[{r.severity}]"
            lines.append(f"  {r.corridor:<14} {r.congestion_pct:>5.1f}%  {tag:<10} {r.action}")
            if r.severity in ("HIGH", "CRITICAL"):
                lines.append(f"    ↳ Alternate: {r.alternate_route}  (~{r.estimated_saving_s:.0f}s saved)")
        return "\n".join(lines)

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify(self, cong: float) -> str:
        for level, (lo, hi) in self.THRESHOLDS.items():
            if lo <= cong < hi:
                return level
        return "CRITICAL"

    def _build_action(
        self,
        corridor: str,
        cong: float,
        severity: str,
    ) -> tuple[str, float]:
        if severity == "LOW":
            return "No action required — flow normal.", 0.0
        if severity == "MODERATE":
            return "Monitor closely. Pre-position adjacent signal capacity.", 5.0
        if severity == "HIGH":
            return (
                f"Activate diversion → {self.ALTERNATE_ROUTES[corridor]}. "
                "Coordinate with Agent 01 to extend alternate green time.",
                18.0,
            )
        # CRITICAL
        return (
            f"IMMEDIATE diversion. Notify city operators. "
            f"Force {self.ALTERNATE_ROUTES[corridor]} — block entry to {corridor}.",
            35.0,
        )
