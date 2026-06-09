"""
TRAFFICQ AI — Entry Point
Usage
-----
  python main.py api          # start FastAPI server
  python main.py dashboard    # start Streamlit dashboard
  python main.py simulate     # run a CLI simulation and print metrics
  python main.py video        # generate comparison video
  python main.py demo         # quick agent demo in terminal
"""
from __future__ import annotations
import sys
import os

def run_api():
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)

def run_dashboard():
    os.system("streamlit run dashboard/app.py")

def run_simulate():
    from simulation.engine import TrafficSimulation
    from agents.signal_optimizer  import SignalOptimizerAgent
    from agents.route_recommender import RouteRecommenderAgent
    from rich.console import Console
    from rich.table   import Table
    from rich.live    import Live
    import time

    console = Console()
    console.print("\n[bold cyan]TRAFFICQ AI — CLI Simulation[/bold cyan]\n")

    sim   = TrafficSimulation(mode="adaptive", density=[70, 65, 40, 45])
    sig_a = SignalOptimizerAgent()
    rte_a = RouteRecommenderAgent()

    table = Table(title="Simulation Metrics", show_header=True)
    table.add_column("Frame",       style="dim")
    table.add_column("Vehicles",    justify="right")
    table.add_column("Waiting",     justify="right")
    table.add_column("Avg Wait (s)",justify="right")
    table.add_column("Congestion",  justify="right")
    table.add_column("Throughput",  justify="right")

    for frame in range(600):
        sim.step()
        if frame % 60 == 0:
            m = sim.get_metrics()
            states = sim.get_signal_state()
            recs   = sig_a.compute_recommendations(states)
            sig_a.apply_recommendations(sim, recs)
            table.add_row(
                str(frame),
                str(m["total_vehicles"]),
                str(m["waiting_count"]),
                f"{m['avg_wait_s']:.1f}",
                f"{m['congestion_pct']:.0f}%",
                f"{m['throughput_pm']:.0f}/min",
            )

    console.print(table)
    console.print("\n[bold green]Simulation complete.[/bold green]")

def run_video():
    sys.path.insert(0, os.path.dirname(__file__))
    from visualization.generate_video import main as gen
    gen()

def run_demo():
    from simulation.engine         import TrafficSimulation
    from agents.orchestrator       import TrafficOrchestrator
    from agents.emergency_priority import EmergencyPriorityAgent
    from rich.console import Console
    from rich.panel   import Panel

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]TRAFFICQ AI — Agent Demo[/bold cyan]\n"
        "Initialising multi-agent system …",
        border_style="cyan",
    ))

    sim   = TrafficSimulation(mode="adaptive", density=[70, 65, 38, 42])
    emg   = EmergencyPriorityAgent()
    orch  = TrafficOrchestrator(sim=sim, emergency_agent=emg)

    # Warm up
    for _ in range(200):
        sim.step()

    states = sim.get_signal_state()
    console.print("\n[bold yellow]Agent 01 + 02 quick analysis:[/bold yellow]")
    console.print(orch.quick_analysis(states))

    console.print("\n[bold red]Dispatching emergency vehicle …[/bold red]")
    event = emg.detect(sim, vehicle_id=42, vehicle_type="ambulance", entry_lane="EB_top")
    console.print(emg.format_summary())

    for _ in range(100):
        sim.step()
        emg.poll(sim)

    console.print(f"\n[bold green]Emergency status: {emg.status.value}[/bold green]")
    console.print(Panel.fit("[bold green]Demo complete.[/bold green]", border_style="green"))

# ─── Dispatcher ───────────────────────────────────────────────────────────────

COMMANDS = {
    "api":       run_api,
    "dashboard": run_dashboard,
    "simulate":  run_simulate,
    "video":     run_video,
    "demo":      run_demo,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Choose from: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[cmd]()
