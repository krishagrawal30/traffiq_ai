"""
TRAFFICQ AI — Streamlit Dashboard (Bengaluru Silk Board)
"""

from __future__ import annotations

import time
import json
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import requests

API_URL = "http://127.0.0.1:8000"
WS_URL = "ws://127.0.0.1:8000/ws/state"

st.set_page_config(
    page_title="TRAFFICQ AI — Bengaluru",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def fetch(endpoint: str, timeout: int = 3):
    try:
        r = requests.get(f"{API_URL}{endpoint}", timeout=timeout)
        return r.json() if r.ok else None
    except Exception:
        return None

def post(endpoint: str, data: dict):
    try:
        return requests.post(f"{API_URL}{endpoint}", json=data, timeout=3)
    except Exception:
        return None

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
        <div style='display:flex;align-items:center;gap:10px;margin-bottom:8px'>
            <span style='font-size:32px'>🚦</span>
            <div>
                <div style='font-size:20px;font-weight:700'>TRAFFICQ AI</div>
                <div style='font-size:11px;color:#94a3b8'>Bengaluru · Silk Board Corridor</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    health = fetch("/health")
    if health:
        blk = "🟢" if health["status"] == "ok" else "🔴"
        st.markdown(f"**Backend:** {blk} Online · Hour {health['hour']}:00 · v{health['version']}")
    else:
        st.error("🔴 Backend Offline — Start FastAPI first")
        st.stop()

    st.divider()

    mode = st.selectbox("Signal Mode", ["adaptive", "static"],
                        help="Adaptive = AI adjusts green times. Static = fixed 30s/30s.")
    scenario = st.selectbox("Scenario", ["Morning Rush (8 AM)", "Midday (1 PM)",
                                          "Evening Rush (6 PM)", "Late Night (10 PM)"])
    scenario_map = {
        "Morning Rush (8 AM)": 8,
        "Midday (1 PM)": 13,
        "Evening Rush (6 PM)": 18,
        "Late Night (10 PM)": 22,
    }
    hour = scenario_map[scenario]

    st.divider()
    st.markdown("#### ⚙️ Controls")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶ Apply", type="primary", width='stretch'):
            post("/simulation/configure", {"mode": mode, "hour": hour})
            time.sleep(0.3)
            st.rerun()
    with col2:
        if st.button("⏹ Pause", width='stretch'):
            post("/simulation/configure", {"mode": "static", "hour": hour})
            st.info("Paused (static mode)")

    if st.button("🔄 Refresh Dashboard", type="secondary", width='stretch'):
        st.rerun()

    auto_refresh = st.checkbox("Auto-refresh every 3s", value=False,
                                help="When OFF, click Refresh to update KPIs. Map updates live either way.")

    st.divider()
    st.markdown("#### 🚨 Emergency Dispatch")
    e_junction = st.selectbox("Entry Point", ["HSR_Layout", "BTM_Layout", "Madiwala", "Silk_Board"])
    e_type = st.selectbox("Vehicle", ["ambulance", "fire", "police"])
    approach_map = {
        "HSR_Layout": "NS_Hosur_Road",
        "BTM_Layout": "NS_Bannerghatta",
        "Madiwala": "NS_Hosur_Road",
        "Silk_Board": "NS_Hosur_Road",
    }
    if st.button("🚨 Dispatch", width='stretch', type="secondary"):
        resp = post("/emergency", {
            "vehicle_type": e_type,
            "entry_junction": e_junction,
            "entry_approach": approach_map.get(e_junction, "NS_Hosur_Road"),
        })
        if resp and resp.ok:
            data = resp.json()
            st.success(f"Path: {' → '.join(data['corridor_path'])}")
        else:
            st.error("Dispatch failed")

    st.divider()
    st.markdown("#### 📊 Golden Dataset")
    if st.button("Run Evaluation", width='stretch'):
        result = post("/evaluate/golden", {})
        if result and result.ok:
            st.success("Evaluation complete")

# ─── MAIN DASHBOARD ───────────────────────────────────────────────────────────

st.markdown("## 🚦 TRAFFICQ AI — Live Command Center")
st.caption(f"Bengaluru Silk Board Corridor · {datetime.now().strftime('%H:%M:%S')}")

state = fetch("/simulation/state")

if not state:
    st.warning("Waiting for simulation data...")
    time.sleep(0.5)
    st.rerun()

# ─── TOP ROW: KPI CARDS ──────────────────────────────────────────────────────

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    c = state["congestion_pct"]
    color = "#22c55e" if c < 35 else "#eab308" if c < 60 else "#ef4444"
    st.markdown(f"""
        <div style='background:#1e293b;padding:16px;border-radius:12px;border-left:4px solid {color}'>
            <div style='color:#94a3b8;font-size:13px'>🚦 Congestion</div>
            <div style='color:{color};font-size:28px;font-weight:700'>{c:.0f}%</div>
            <div style='color:#64748b;font-size:10px;margin-top:2px'>% vehicles waiting</div>
        </div>
    """, unsafe_allow_html=True)
with k2:
    w = state["avg_wait_s"]
    color = "#22c55e" if w < 20 else "#eab308" if w < 45 else "#ef4444"
    st.markdown(f"""
        <div style='background:#1e293b;padding:16px;border-radius:12px;border-left:4px solid {color}'>
            <div style='color:#94a3b8;font-size:13px'>⏱ Avg Wait</div>
            <div style='color:{color};font-size:28px;font-weight:700'>{w:.1f}s</div>
            <div style='color:#64748b;font-size:10px;margin-top:2px'>lower = better</div>
        </div>
    """, unsafe_allow_html=True)
with k3:
    t = state["throughput_pm"]
    st.markdown(f"""
        <div style='background:#1e293b;padding:16px;border-radius:12px;border-left:4px solid #3b82f6'>
            <div style='color:#94a3b8;font-size:13px'>📊 Throughput</div>
            <div style='color:#3b82f6;font-size:28px;font-weight:700'>{t:.0f}/min</div>
            <div style='color:#64748b;font-size:10px;margin-top:2px'>vehicles cleared / minute</div>
        </div>
    """, unsafe_allow_html=True)
with k4:
    v = state["total_vehicles"]
    st.markdown(f"""
        <div style='background:#1e293b;padding:16px;border-radius:12px;border-left:4px solid #a78bfa'>
            <div style='color:#94a3b8;font-size:13px'>🚗 Active Vehicles</div>
            <div style='color:#a78bfa;font-size:28px;font-weight:700'>{v}</div>
            <div style='color:#64748b;font-size:10px;margin-top:2px'>on corridor right now</div>
        </div>
    """, unsafe_allow_html=True)
with k5:
    waiting = state["waiting_count"]
    pct = (waiting / max(v, 1)) * 100 if v > 0 else 0
    st.markdown(f"""
        <div style='background:#1e293b;padding:16px;border-radius:12px;border-left:4px solid #f59e0b'>
            <div style='color:#94a3b8;font-size:13px'>🔴 % Waiting</div>
            <div style='color:#f59e0b;font-size:28px;font-weight:700'>{pct:.0f}%</div>
            <div style='color:#64748b;font-size:10px;margin-top:2px'>stopped at red lights</div>
        </div>
    """, unsafe_allow_html=True)

# ─── HOW TO READ THIS ─────────────────────────────────────────────────────────

with st.expander("📖 How to read this dashboard", expanded=False):
    st.markdown("""
    | Section | What to look for |
    |---------|------------------|
    | **Map** | 4 junctions (dots) colored by congestion 🟢<35% 🟡35-60% 🔴>60%. Tiny dots = vehicles. Red glow = emergency corridor. |
    | **KPI Cards** | Congestion % = proportion of vehicles waiting at red lights. Avg Wait = how long they've been stopped. Throughput = how many pass per minute. |
    | **Agent Cards** | Each agent explains its reasoning. Agent 01 = signal splits, Agent 02 = congestion alerts, Agent 03 = emergency status. |
    | **Activity Log** | Real-time text feed of every agent decision. |
    """)

# ─── MAP + SIGNALS ROW ────────────────────────────────────────────────────────

map_col, sig_col = st.columns([2.2, 1])

with map_col:
    junction_geo = {
        "Silk_Board": [77.6228, 12.9180],
        "Madiwala": [77.6200, 12.9330],
        "HSR_Layout": [77.6240, 12.9080],
        "BTM_Layout": [77.6100, 12.9080],
    }

    junctions_data = state.get("junctions", [])
    junction_congestion = {j["name"]: j["congestion_pct"] for j in junctions_data}
    junction_phases = {j["name"]: j["phase"] for j in junctions_data}
    junction_q_ns = {j["name"]: j["queue_ns"] for j in junctions_data}
    junction_q_ew = {j["name"]: j["queue_ew"] for j in junctions_data}

    emerg = state.get("emergency_status", {}) or {}
    active_corridor = emerg.get("active_corridor", []) if emerg else []

    corridor_geojson = []
    if active_corridor and len(active_corridor) >= 2:
        coords = []
        for node in active_corridor:
            if node in junction_geo:
                coords.append(junction_geo[node])
        if len(coords) >= 2:
            corridor_geojson = [{
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"corridor": "active"},
            }]

    road_lines = [
        [[77.6240, 12.9080], [77.6228, 12.9180]],
        [[77.6228, 12.9180], [77.6200, 12.9330]],
        [[77.6100, 12.9080], [77.6228, 12.9180]],
    ]

    junctions_geojson = []
    for name, coords in junction_geo.items():
        cp = junction_congestion.get(name, 0)
        color = "#22c55e" if cp < 35 else "#eab308" if cp < 60 else "#ef4444"
        size = 10 + (cp / 100) * 16
        phase = junction_phases.get(name, "NS")
        junctions_geojson.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coords},
            "properties": {"name": name, "congestion": cp, "color": color,
                           "size": size, "phase": phase,
                           "q_ns": junction_q_ns.get(name, 0),
                           "q_ew": junction_q_ew.get(name, 0)},
        })

    # Build vehicle geojson for initial render (will be updated via WS)
    init_vehicles = state.get("vehicles", [])
    vehicles_geojson = []
    for v in init_vehicles:
        vcolor = v.get("color", "#3B8BD4")
        vsize = 7 if v.get("is_emergency") else 3
        vcolor = "#EF4444" if v.get("is_emergency") else vcolor
        vehicles_geojson.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [v["lon"], v["lat"]]},
            "properties": {"color": vcolor, "size": vsize,
                           "emergency": v.get("is_emergency", False)},
        })

    map_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
        <script src="https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.js"></script>
        <link href="https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.css" rel="stylesheet" />
        <style>
            body {{ margin: 0; padding: 0; }}
            #map {{ width: 100%; height: 520px; border-radius: 12px; }}
            .map-overlay {{
                position: absolute; top: 10px; left: 10px;
                background: rgba(15,23,42,0.85); backdrop-filter: blur(8px);
                color: #f8fafc; padding: 8px 14px; border-radius: 8px;
                font-size: 12px; z-index: 10;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .map-legend {{
                position: absolute; bottom: 10px; left: 10px;
                background: rgba(15,23,42,0.85); backdrop-filter: blur(8px);
                color: #f8fafc; padding: 6px 12px; border-radius: 8px;
                font-size: 11px; z-index: 10;
                border: 1px solid rgba(255,255,255,0.1);
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="map-overlay" id="stats">
            🚦 TRAFFICQ AI · Bengaluru Silk Board Corridor
        </div>
        <div class="map-legend">
            🟢 <35% &nbsp; 🟡 35-60% &nbsp; 🔴 >60% &nbsp; · &nbsp; dots = vehicles
        </div>
        <script>
            const map = new maplibregl.Map({{
                container: 'map',
                style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                center: [77.6228, 12.920],
                zoom: 13.5,
                pitch: 0,
                bearing: 0
            }});

            const junctions = {json.dumps(junctions_geojson)};
            const roads = {json.dumps(road_lines)};
            const corridor = {json.dumps(corridor_geojson)};
            const initVehicles = {json.dumps(vehicles_geojson)};
            const wsUrl = "{WS_URL}";

            map.on('load', () => {{
                map.addSource('roads', {{
                    type: 'geojson',
                    data: {{
                        type: 'FeatureCollection',
                        features: roads.map(r => ({{
                            type: 'Feature',
                            geometry: {{ type: 'LineString', coordinates: r }},
                            properties: {{}}
                        }}))
                    }}
                }});
                map.addLayer({{
                    id: 'roads-layer', type: 'line',
                    source: 'roads',
                    paint: {{ 'line-width': 6, 'line-color': '#1e293b', 'line-opacity': 0.8 }}
                }});

                map.addSource('junctions', {{
                    type: 'geojson',
                    data: {{ type: 'FeatureCollection', features: junctions }}
                }});
                map.addLayer({{
                    id: 'junctions-layer', type: 'circle',
                    source: 'junctions',
                    paint: {{
                        'circle-radius': ['get', 'size'],
                        'circle-color': ['get', 'color'],
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#0f172a',
                        'circle-opacity': 0.85
                    }}
                }});
                map.addLayer({{
                    id: 'junctions-label', type: 'symbol',
                    source: 'junctions',
                    layout: {{
                        'text-field': ['get', 'name'],
                        'text-offset': [0, 1.8],
                        'text-size': 11,
                        'text-font': ['Open Sans Bold', 'Arial Unicode MS Bold']
                    }},
                    paint: {{ 'text-color': '#f8fafc', 'text-halo-color': '#0f172a', 'text-halo-width': 2 }}
                }});

                // Vehicle layer (tiny dots)
                map.addSource('vehicles', {{
                    type: 'geojson',
                    data: {{ type: 'FeatureCollection', features: initVehicles }}
                }});
                map.addLayer({{
                    id: 'vehicles-layer', type: 'circle',
                    source: 'vehicles',
                    paint: {{
                        'circle-radius': ['get', 'size'],
                        'circle-color': ['get', 'color'],
                        'circle-stroke-width': 1,
                        'circle-stroke-color': '#ffffff',
                        'circle-stroke-opacity': 0.3,
                        'circle-opacity': 0.8
                    }}
                }});

                if (corridor.length > 0) {{
                    map.addSource('corridor', {{
                        type: 'geojson',
                        data: {{ type: 'FeatureCollection', features: corridor }}
                    }});
                    map.addLayer({{
                        id: 'corridor-glow', type: 'line',
                        source: 'corridor',
                        paint: {{
                            'line-width': 14, 'line-color': '#ef4444',
                            'line-opacity': 0.3, 'line-blur': 8
                        }}
                    }});
                    map.addLayer({{
                        id: 'corridor-core', type: 'line',
                        source: 'corridor',
                        paint: {{
                            'line-width': 4, 'line-color': '#10b981',
                            'line-opacity': 0.9, 'line-dasharray': [2, 1]
                        }}
                    }});
                }}

                // WebSocket
                let ws = new WebSocket(wsUrl);
                ws.onmessage = (event) => {{
                    const data = JSON.parse(event.data);
                    updateMap(data);
                }};
                ws.onclose = () => setTimeout(() => ws = new WebSocket(wsUrl), 2000);
            }});

            function updateMap(data) {{
                if (!map.isStyleLoaded()) return;
                const newJunctions = (data.junctions || []).map(j => ({{
                    type: 'Feature',
                    geometry: {{ type: 'Point', coordinates: [j.lon, j.lat] }},
                    properties: {{
                        name: j.name, congestion: j.congestion_pct,
                        color: j.congestion_pct < 35 ? '#22c55e' : j.congestion_pct < 60 ? '#eab308' : '#ef4444',
                        size: 10 + (j.congestion_pct / 100) * 16,
                        phase: j.phase,
                        q_ns: j.queue_ns, q_ew: j.queue_ew
                    }}
                }}));
                try {{
                    map.getSource('junctions').setData({{ type: 'FeatureCollection', features: newJunctions }});
                }} catch(e) {{}}

                // Update vehicles
                const newVehicles = (data.vehicles || []).map(v => ({{
                    type: 'Feature',
                    geometry: {{ type: 'Point', coordinates: [v.lon, v.lat] }},
                    properties: {{
                        color: v.is_emergency ? '#EF4444' : (v.color || '#3B8BD4'),
                        size: v.is_emergency ? 7 : 3,
                        emergency: v.is_emergency,
                    }}
                }}));
                try {{
                    map.getSource('vehicles').setData({{ type: 'FeatureCollection', features: newVehicles }});
                }} catch(e) {{}}
            }}
        </script>
    </body>
    </html>
    """

    components.html(map_html, height=530)

with sig_col:
    st.markdown("#### Traffic Signals")
    df_sig = pd.DataFrame(state["signal_states"])
    if not df_sig.empty:
        display = df_sig[["name", "phase", "ns_queue", "ew_queue", "ns_green", "ew_green", "override"]].copy()
        display.columns = ["Junction", "Phase", "NS Q", "EW Q", "NS(s)", "EW(s)", "OVR"]
        display["OVR"] = display["OVR"].apply(lambda x: "🔴" if x else "—")
        def color_phase(p):
            return f"🟢 {p}" if p == "NS" else f"🔵 {p}"
        display["Phase"] = display["Phase"].apply(color_phase)
        st.dataframe(display, hide_index=True, width='stretch', height=210)

    st.markdown("#### 🚦 Congestion by Junction")
    if junctions_data:
        df_j = pd.DataFrame(junctions_data)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_j["name"], y=df_j["congestion_pct"],
            marker_color=df_j["congestion_pct"].apply(
                lambda c: "#22c55e" if c < 35 else "#eab308" if c < 60 else "#ef4444"
            ),
            text=df_j["congestion_pct"].apply(lambda c: f"{c:.0f}%"),
            textposition="outside",
        ))
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=180, margin=dict(l=10, r=10, t=5, b=20),
            yaxis_title="Congestion %", xaxis_title="",
            font=dict(color="#94a3b8"),
            yaxis=dict(range=[0, 105], gridcolor="#1e293b"),
        )
        st.plotly_chart(fig, width='stretch')

# ─── AGENT INTELLIGENCE ROW ───────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 🧠 Agent Intelligence — Explainable AI Decisions")
st.caption("Each agent shows its current recommendation and the reasoning behind it.")

agt1, agt2, agt3 = st.columns(3)

with agt1:
    st.markdown("""
        <div style='background:#1e293b;border-radius:12px;padding:16px;border-top:3px solid #3b82f6'>
            <div style='font-size:16px;font-weight:600;margin-bottom:4px'>Agent 01 — Signal Optimizer</div>
            <div style='color:#94a3b8;font-size:12px;margin-bottom:12px'>Adjusts green-light splits per junction</div>
        </div>
    """, unsafe_allow_html=True)

    sig_recs = fetch("/analyse")
    if sig_recs and sig_recs.get("signal_recommendations"):
        for rec in sig_recs["signal_recommendations"]:
            c = "🟢" if rec.get("confidence", 0) > 0.7 else "🟡" if rec.get("confidence", 0) > 0.4 else "🔴"
            st.markdown(f"""
                <div style='background:#0f172a;border-radius:8px;padding:10px;margin-bottom:6px;border-left:3px solid #3b82f6'>
                    <div style='font-size:14px;font-weight:600'>{c} {rec.get('junction','')}</div>
                    <div style='font-size:12px;color:#94a3b8'>
                        NS: <b>{rec.get('ns_green',0):.0f}s</b> · EW: <b>{rec.get('ew_green',0):.0f}s</b>
                        · Confidence: {rec.get('confidence',0):.0%}
                    </div>
                    <div style='font-size:11px;color:#64748b;margin-top:4px'>{rec.get('reasoning','')[:120]}</div>
                    <div style='font-size:11px;color:#22c55e;margin-top:2px'>{rec.get('estimated_impact','')}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.caption("No signal recommendations yet — simulation running...")

with agt2:
    st.markdown("""
        <div style='background:#1e293b;border-radius:12px;padding:16px;border-top:3px solid #f59e0b'>
            <div style='font-size:16px;font-weight:600;margin-bottom:4px'>Agent 02 — Route Recommender</div>
            <div style='color:#94a3b8;font-size:12px;margin-bottom:12px'>Detects congestion & suggests diversions</div>
        </div>
    """, unsafe_allow_html=True)

    route_recs = state.get("route_recommendations", [])
    if route_recs:
        for r in route_recs:
            icon_map = {"LOW": "🟢", "MODERATE": "🟡", "HIGH": "🟠", "CRITICAL": "🔴"}
            icon = icon_map.get(r["severity"], "⚪")
            border = "#22c55e" if r["severity"] == "LOW" else "#eab308" if r["severity"] == "MODERATE" else "#ef4444"
            st.markdown(f"""
                <div style='background:#0f172a;border-radius:8px;padding:10px;margin-bottom:6px;border-left:3px solid {border}'>
                    <div style='font-size:14px;font-weight:600'>{icon} {r['corridor']}</div>
                    <div style='font-size:12px;color:#94a3b8'>Congestion: <b>{r['congestion_pct']:.0f}%</b> · Severity: {r['severity']}</div>
                    <div style='font-size:11px;color:#64748b;margin-top:4px'>{r['action'][:90]}</div>
            """, unsafe_allow_html=True)
            if r["severity"] in ("HIGH", "CRITICAL"):
                st.markdown(f"""
                    <div style='font-size:11px;color:#22c55e;margin-top:2px'>
                        ↳ Alternate: {r['alternate_route']} (~{r['estimated_saving_s']:.0f}s saved)
                    </div>
                """, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.caption("No routing advisories — all corridors nominal.")

with agt3:
    st.markdown("""
        <div style='background:#1e293b;border-radius:12px;padding:16px;border-top:3px solid #ef4444'>
            <div style='font-size:16px;font-weight:600;margin-bottom:4px'>Agent 03 — Emergency Priority</div>
            <div style='color:#94a3b8;font-size:12px;margin-bottom:12px'>Green corridor for first responders</div>
        </div>
    """, unsafe_allow_html=True)

    emg = state.get("emergency_status", {}) or {}
    if emg and emg.get("status") == "CORRIDOR_ACTIVE":
        st.error(f"""
            🚨 **{emg.get('vehicle_type','vehicle').upper()} ACTIVE**
            Entry: {emg.get('entry_junction','?')}
            Path: {' → '.join(emg.get('active_corridor',[]))}
            ETA: {emg.get('eta_s', '?')}s
        """)
        if emg.get("explanation"):
            st.info(emg["explanation"])
    elif emg and emg.get("status") in ("STANDBY", "RESOLVED"):
        st.success("✅ Monitoring for emergency vehicles...")
        if emg.get("decision_log"):
            with st.expander("Recent emergency log"):
                for line in emg["decision_log"][-5:]:
                    st.caption(line)
    else:
        st.info("📡 Standby — no active emergency")

    st.markdown("#### 📋 Agent Activity Log")
    logs = state.get("agent_log", [])
    log_html = "<div style='height:160px;overflow-y:auto;background:#0f172a;padding:8px;border-radius:8px;font-size:11px;font-family:monospace;color:#a5b4fc'>"
    for log_entry in logs:
        sev_icon = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}
        icon = sev_icon.get(log_entry.get("severity", "info"), "ℹ️")
        log_html += f"<div style='margin-bottom:3px;border-bottom:1px solid #1e293b;padding-bottom:2px'>{icon} [{log_entry.get('time_s',0):.0f}s] {log_entry.get('agent','')}: {log_entry.get('message','')[:70]}</div>"
    log_html += "</div>"
    st.markdown(log_html, unsafe_allow_html=True)

# ─── QUEUE BREAKDOWN ──────────────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 📊 Queue Distribution by Junction")
st.caption("Number of vehicles waiting at each approach per junction. Higher bars = more congestion in that direction.")

df_sig = pd.DataFrame(state["signal_states"])
if not df_sig.empty:
    df_q = df_sig.melt(
        id_vars=["name"],
        value_vars=["ns_queue", "ew_queue", "sw_queue", "ne_queue"],
        var_name="approach", value_name="queue"
    )
    df_q["approach"] = df_q["approach"].str.upper().str.replace("_QUEUE", "")
    fig_q = px.bar(
        df_q, x="name", y="queue", color="approach",
        barmode="group",
        color_discrete_map={
            "NS": "#3b82f6", "EW": "#22c55e",
            "SW": "#f59e0b", "NE": "#a78bfa",
        },
    )
    fig_q.update_layout(
        title="Vehicles Queued per Approach", height=250,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"), margin=dict(l=10, r=10, t=30, b=20),
        yaxis=dict(gridcolor="#1e293b"), xaxis=dict(gridcolor="#1e293b"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_q, width='stretch')

# ─── AUTO-REFRESH (optional) ──────────────────────────────────────────────────

if auto_refresh and fetch("/health"):
    time.sleep(3.0)
    st.rerun()
