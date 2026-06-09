"""
TRAFFICQ AI — Streamlit Dashboard
Real-time visualisation of the multi-agent traffic system.
Run:  streamlit run dashboard/app.py
"""
from __future__ import annotations
import time
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from simulation.engine import TrafficSimulation, LANE_DEFS
from agents.signal_optimizer   import SignalOptimizerAgent
from agents.route_recommender  import RouteRecommenderAgent
from agents.emergency_priority import EmergencyPriorityAgent

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title = "TRAFFICQ AI",
    page_icon  = "🚦",
    layout     = "wide",
)

# ─── Session state ────────────────────────────────────────────────────────────

if "sim"   not in st.session_state:
    st.session_state.sim        = None
    st.session_state.sig_agent  = SignalOptimizerAgent()
    st.session_state.rte_agent  = RouteRecommenderAgent()
    st.session_state.emg_agent  = EmergencyPriorityAgent()
    st.session_state.running    = False
    st.session_state.frame_log  = []
    st.session_state.emerg_log  = []

# ─── Sidebar controls ─────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/64/traffic-light.png", width=48)
    st.title("TRAFFICQ AI")
    st.caption("Autonomous Emergency & Smart Traffic Intelligence")
    st.divider()

    mode = st.selectbox("Signal mode", ["adaptive", "static"])
    scenario = st.selectbox("Scenario", ["Morning Rush", "Midday Flow", "Evening Rush", "Late Night"])
    SCENARIOS = {
        "Morning Rush": [75, 70, 50, 55],
        "Midday Flow":  [38, 35, 42, 38],
        "Evening Rush": [55, 60, 82, 85],
        "Late Night":   [10, 12, 15, 12],
    }
    density = SCENARIOS[scenario]

    st.divider()
    ns1 = st.slider("N-S Col 1 density", 0, 100, density[0])
    ns2 = st.slider("N-S Col 2 density", 0, 100, density[1])
    ew1 = st.slider("E-W Row 1 density", 0, 100, density[2])
    ew2 = st.slider("E-W Row 2 density", 0, 100, density[3])

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ Start", use_container_width=True, type="primary"):
            st.session_state.sim = TrafficSimulation(
                mode=mode, density=[ns1, ns2, ew1, ew2]
            )
            st.session_state.running   = True
            st.session_state.frame_log = []
    with col2:
        if st.button("⏹ Stop", use_container_width=True):
            st.session_state.running = False

    st.divider()
    st.markdown("**Agent 03 — Emergency**")
    e_lane = st.selectbox("Entry lane", list(LANE_DEFS.keys()), index=0)
    e_type = st.selectbox("Vehicle type", ["ambulance", "fire", "police"])
    if st.button("🚨 Dispatch Emergency", use_container_width=True):
        sim = st.session_state.sim
        if sim:
            event = st.session_state.emg_agent.detect(
                sim, vehicle_id=999, vehicle_type=e_type, entry_lane=e_lane
            )
            st.session_state.emerg_log.append(
                f"🚨 {e_type.upper()} dispatched — corridor: {' → '.join(event.corridor_intersections)}"
            )

# ─── Main layout ──────────────────────────────────────────────────────────────

st.markdown("## 🚦 TRAFFICQ AI — Live Dashboard")

kpi0, kpi1, kpi2, kpi3, kpi4 = st.columns(5)
sig_col, agent_col = st.columns([3, 2])
chart_col1, chart_col2 = st.columns(2)
log_col1, log_col2 = st.columns(2)

# ─── Simulation Step ──────────────────────────────────────────────────────────

sim = st.session_state.sim

if st.session_state.running and sim:
    # Step simulation + poll emergency agent
    for _ in range(2):
        sim.step()
    st.session_state.emg_agent.poll(sim)

    metrics = sim.get_metrics()
    states  = sim.get_signal_state()

    # Log a frame snapshot
    st.session_state.frame_log.append(metrics)
    if len(st.session_state.frame_log) > 300:
        st.session_state.frame_log.pop(0)

    # ── Agent 01 recommendations ──────────────────────────────────────────────
    sig_recs   = st.session_state.sig_agent.compute_recommendations(states)
    route_recs = st.session_state.rte_agent.analyse(states)
    st.session_state.sig_agent.apply_recommendations(sim, sig_recs)

elif sim:
    metrics = sim.get_metrics()
    states  = sim.get_signal_state()
    sig_recs   = st.session_state.sig_agent.compute_recommendations(states)
    route_recs = st.session_state.rte_agent.analyse(states)
else:
    metrics = {"total_vehicles": 0, "waiting_count": 0, "avg_wait_s": 0.0, "congestion_pct": 0.0, "throughput_pm": 0.0}
    states = []
    sig_recs = []
    route_recs = []

# ── KPIs ─────────────────────────────────────────────────────────────────
with kpi0: st.metric("Vehicles",    metrics["total_vehicles"])
with kpi1: st.metric("Waiting",     metrics["waiting_count"])
with kpi2: st.metric("Avg wait",    f"{metrics['avg_wait_s']:.1f}s")
with kpi3: st.metric("Congestion",  f"{metrics['congestion_pct']:.0f}%")
with kpi4: st.metric("Throughput",  f"{metrics['throughput_pm']:.0f}/min")

# ── Signal status ─────────────────────────────────────────────────────────
if states:
    with sig_col:
        st.markdown("### Signal State — Agent 01")
        df_sig = pd.DataFrame(states)[
            ["name","phase","ns_green","ew_green","ns_queue","ew_queue","congestion","override"]
        ]
        df_sig.columns = ["Intersection","Phase","NS Green (s)","EW Green (s)",
                          "NS Queue","EW Queue","Congestion %","Override"]
        st.dataframe(df_sig, use_container_width=True, hide_index=True)

# ── Agent status panels ───────────────────────────────────────────────────
with agent_col:
    st.markdown("### Agent Status")
    for r in route_recs:
        colour = {"LOW":"🟢","MODERATE":"🟡","HIGH":"🟠","CRITICAL":"🔴"}.get(r.severity,"⚪")
        st.write(f"{colour} **{r.corridor}** — {r.congestion_pct:.0f}% {r.severity}")
    st.divider()
    emg = st.session_state.emg_agent
    st.write(f"🚨 Agent 03: **{emg.status.value}**")
    for msg in st.session_state.emerg_log[-3:]:
        st.caption(msg)

# ── History charts ────────────────────────────────────────────────────────
if len(st.session_state.frame_log) > 2:
    df_h = pd.DataFrame(st.session_state.frame_log)
    with chart_col1:
        fig = px.line(df_h, y="avg_wait_s", title="Avg Wait Time (s)",
                      labels={"avg_wait_s":"seconds","index":"frame"})
        fig.update_layout(height=220, margin=dict(l=0,r=0,t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)
    with chart_col2:
        fig = px.line(df_h, y="congestion_pct", title="Congestion Index (%)",
                      color_discrete_sequence=["#ef4444"],
                      labels={"congestion_pct":"%","index":"frame"})
        fig.update_layout(height=220, margin=dict(l=0,r=0,t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)

if st.session_state.running:
    time.sleep(0.05)
    st.rerun()
