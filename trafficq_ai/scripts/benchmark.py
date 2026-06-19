"""
Benchmark: Compare static vs adaptive modes with cumulative metrics.
Run: python scripts/benchmark.py
"""

from __future__ import annotations
import sys
sys.path.insert(0, ".")

from simulation.engine import TrafficSimulation

def run_comparison(mode: str, frames: int = 1800) -> dict:
    sim = TrafficSimulation(mode=mode, hour=8, fps=10)
    for _ in range(frames):
        sim.step()
    h = sim.history

    avg_wait_mean = sum(h["avg_wait_s"]) / max(len(h["avg_wait_s"]), 1)
    throughput_mean = sum(h["throughput_pm"]) / max(len(h["throughput_pm"]), 1)
    congestion_mean = sum(h["congestion_pct"]) / max(len(h["congestion_pct"]), 1)

    final_wait = h["avg_wait_s"][-1] if h["avg_wait_s"] else 0
    final_thru = h["throughput_pm"][-1] if h["throughput_pm"] else 0
    final_cong = h["congestion_pct"][-1] if h["congestion_pct"] else 0

    return {
        "mode": mode,
        "total_exits": sim.exits,
        "final_avg_wait": final_wait,
        "final_throughput": final_thru,
        "final_congestion": final_cong,
        "avg_wait_mean": avg_wait_mean,
        "throughput_mean": throughput_mean,
        "congestion_mean": congestion_mean,
        "last_60_wait": sum(h["avg_wait_s"][-60:]) / 60,
        "last_60_thru": sum(h["throughput_pm"][-60:]) / 60,
        "last_60_cong": sum(h["congestion_pct"][-60:]) / 60,
    }

print("=== TRAFFICQ AI — Static vs Adaptive Benchmark ===\n")
print(f"{'Metric':<35} {'Static':<15} {'Adaptive':<15} {'Winner':<10}")
print("=" * 75)

static_r = run_comparison("static", 1800)
adaptive_r = run_comparison("adaptive", 1800)

metrics = [
    ("Total Vehicles Exited",      "total_exits",      "{:.0f}",      False, 10),
    ("Final Avg Wait (s)",         "final_avg_wait",   "{:.1f}s",     True,  1),
    ("Final Throughput (/min)",    "final_throughput",  "{:.1f}/min",  False, 1),
    ("Final Congestion (%)",       "final_congestion",  "{:.0f}%",     True,  1),
    ("Overall Avg Wait (mean)",    "avg_wait_mean",    "{:.1f}s",     True,  1),
    ("Overall Throughput (mean)",  "throughput_mean",   "{:.1f}/min",  False, 1),
    ("Overall Congestion (mean)",  "congestion_mean",   "{:.0f}%",     True,  1),
    ("Last 60s Avg Wait",          "last_60_wait",     "{:.1f}s",     True,  1),
    ("Last 60s Throughput",        "last_60_thru",     "{:.1f}/min",  False, 1),
    ("Last 60s Congestion",        "last_60_cong",     "{:.0f}%",     True,  1),
]

for label, key, fmt, lower_better, threshold in metrics:
    sv = static_r[key]
    av = adaptive_r[key]
    diff = av - sv
    if abs(sv) < 0.01:
        pct = 0
    else:
        pct = (diff / sv) * 100

    if abs(pct) < threshold:
        winner = "➡️ Tie"
    elif lower_better:
        winner = "✅ Adaptive" if pct < 0 else "❌ Static"
    else:
        winner = "✅ Adaptive" if pct > 0 else "❌ Static"

    arrow = "↓" if diff < 0 else "↑"
    print(f"{label:<35} {fmt.format(sv):<15} {fmt.format(av):<15} {winner:<10}")

print("=" * 75)

total_improvement = 0
score = 0
if static_r["total_exits"] > 0:
    exit_improvement = (adaptive_r["total_exits"] - static_r["total_exits"]) / static_r["total_exits"] * 100
    score += exit_improvement * 2
if static_r["final_congestion"] > 0:
    cong_improvement = (static_r["final_congestion"] - adaptive_r["final_congestion"]) / static_r["final_congestion"] * 100
    score += cong_improvement

print(f"\nOverall Performance Score: {score:.0f}")
print("(Higher = better. Combines exit throughput + congestion reduction)")
