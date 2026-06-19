"""
TRAFFICQ AI v2 — Bengaluru Silk Board Corridor
Entry point for running all components.
"""

from __future__ import annotations

import sys
import os


def run_api():
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)


def run_dashboard():
    os.system(f'cd frontend && npm run dev')


def run_simulate():
    from simulation.engine import TrafficSimulation
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    import time

    console = Console()
    console.print("\n[bold cyan]TRAFFICQ AI v2 — Bengaluru Simulation[/bold cyan]\n")

    sim = TrafficSimulation(mode="adaptive", hour=8)
    table = Table(title="Simulation Metrics", show_header=True)
    table.add_column("Frame", style="dim")
    table.add_column("Vehicles", justify="right")
    table.add_column("Waiting", justify="right")
    table.add_column("Avg Wait (s)", justify="right")
    table.add_column("Congestion", justify="right")
    table.add_column("Throughput", justify="right")

    for frame in range(600):
        sim.step()
        if frame % 60 == 0:
            m = sim.get_metrics()
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


def run_demo():
    from simulation.engine import TrafficSimulation
    from agents.orchestrator import TrafficOrchestrator
    from agents.emergency_priority import EmergencyPriorityAgent
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]TRAFFICQ AI v2 — Agent Demo[/bold cyan]\n"
        "Bengaluru Silk Board Corridor · Multi-Agent System",
        border_style="cyan",
    ))

    sim = TrafficSimulation(mode="adaptive", hour=8)
    emg = EmergencyPriorityAgent()
    orch = TrafficOrchestrator(sim=sim, emergency_agent=emg)

    for _ in range(200):
        sim.step()

    states = sim.get_signal_state()
    console.print("\n[bold yellow]Agent 01 + 02 quick analysis:[/bold yellow]")
    console.print(orch.quick_analysis(states))

    console.print("\n[bold red]Dispatching emergency vehicle from HSR Layout → Madiwala...[/bold red]")
    event = emg.detect(sim, vehicle_type="ambulance", entry_junction="HSR_Layout")
    console.print(event.explanation)

    for _ in range(150):
        sim.step()
        emg.poll(sim)

    console.print(f"\n[bold green]Emergency status: {emg.status.value}[/bold green]")
    console.print(Panel.fit("[bold green]Demo complete.[/bold green]", border_style="green"))


COMMANDS = {
    "api": run_api,
    "dashboard": run_dashboard,
    "simulate": run_simulate,
    "demo": run_demo,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Choose from: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[cmd]()
