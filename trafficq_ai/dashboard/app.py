"""
TRAFFICQ AI — Streamlit Dashboard
Real-time visualisation of the multi-agent traffic system with Premium Map.
Run:  streamlit run dashboard/app.py
"""
from __future__ import annotations
import time
import json
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import pandas as pd
import requests

# ─── Configuration ────────────────────────────────────────────────────────────

API_URL = "http://127.0.0.1:8000"
WS_URL  = "ws://127.0.0.1:8000/ws/state"

st.set_page_config(
    page_title = "TRAFFICQ AI",
    page_icon  = "🚦",
    layout     = "wide",
    initial_sidebar_state="expanded"
)

# ─── API Helpers ──────────────────────────────────────────────────────────────

def fetch_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=2).json()
    except:
        return None

def configure_sim(mode, density, fps=20):
    payload = {"mode": mode, "density": density, "fps": fps}
    requests.post(f"{API_URL}/simulation/configure", json=payload)

def dispatch_emergency(vehicle_type, entry_lane, vid):
    payload = {"vehicle_type": vehicle_type, "entry_lane": entry_lane, "vehicle_id": vid}
    requests.post(f"{API_URL}/emergency", json=payload)

# ─── Sidebar Controls ─────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/fluency/64/traffic-light.png", width=48)
    st.title("TRAFFICQ AI")
    st.caption("Autonomous Emergency & Smart Traffic Intelligence")
    
    health = fetch_health()
    if health:
        st.success(f"Backend API: **Online** ({health['mode']})")
    else:
        st.error("Backend API: **Offline** (Ensure FastAPI is running)")
        
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
        if st.button("▶ Apply / Reset", use_container_width=True, type="primary"):
            configure_sim(mode, [ns1, ns2, ew1, ew2])
            st.success("Simulation configured!")
    with col2:
        if st.button("⏹ Stop", use_container_width=True):
            configure_sim("static", [0, 0, 0, 0])

    st.divider()
    st.markdown("**Agent 03 — Emergency Dispatch**")
    e_lane = st.selectbox("Entry lane", ["EB_top", "WB_top", "EB_bot", "WB_bot", "SB_left", "NB_left", "SB_right", "NB_right"], index=0)
    e_type = st.selectbox("Vehicle type", ["ambulance", "fire", "police"])
    if st.button("🚨 Dispatch Emergency Vehicle", use_container_width=True):
        import random
        dispatch_emergency(e_type, e_lane, random.randint(10, 99))
        st.toast(f"Dispatched {e_type} on {e_lane}!", icon="🚨")


# ─── Main Layout ──────────────────────────────────────────────────────────────

st.markdown("## 🚦 TRAFFICQ AI — Live Command Center")

map_col, stats_col = st.columns([2.5, 1])

with map_col:
    # Premium MapLibre HTML Component featuring Uber-like dynamic path visualization
    MAP_HTML = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>TRAFFICQ AI Live Map</title>
        <meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
        <script src="https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.js"></script>
        <link href="https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.css" rel="stylesheet" />
        <style>
            body { margin: 0; padding: 0; background-color: #0b0f19; font-family: 'Inter', sans-serif; }
            #map { position: absolute; top: 0; bottom: 0; width: 100%; border-radius: 12px; }
            .overlay-panel {
                position: absolute;
                top: 15px;
                left: 15px;
                background: rgba(15, 23, 42, 0.85);
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255,255,255,0.1);
                color: #f8fafc;
                padding: 12px 18px;
                border-radius: 8px;
                font-size: 13px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                z-index: 10;
            }
            .emerg-panel {
                position: absolute;
                bottom: 25px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(220, 38, 38, 0.9);
                backdrop-filter: blur(10px);
                color: white;
                padding: 10px 20px;
                border-radius: 30px;
                font-weight: 600;
                font-size: 14px;
                box-shadow: 0 0 15px rgba(220, 38, 38, 0.6);
                display: none;
                z-index: 10;
                transition: all 0.3s ease;
                white-space: nowrap;
            }
            .emerg-panel.active { display: block; animation: pulse 2s infinite; }
            @keyframes pulse {
                0% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0.7); }
                70% { box-shadow: 0 0 0 10px rgba(220, 38, 38, 0); }
                100% { box-shadow: 0 0 0 0 rgba(220, 38, 38, 0); }
            }
            .kpi-row { display: flex; gap: 15px; margin-top: 5px; }
            .kpi-item { display: flex; flex-direction: column; }
            .kpi-val { font-size: 18px; font-weight: bold; color: #38bdf8; }
            .kpi-lbl { font-size: 10px; color: #94a3b8; text-transform: uppercase; }
            .node-label {
                background: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(56, 189, 248, 0.4);
                color: #e2e8f0;
                padding: 6px 10px;
                border-radius: 6px;
                font-size: 11px;
                pointer-events: none;
                box-shadow: 0 2px 4px rgba(0,0,0,0.5);
                backdrop-filter: blur(4px);
                line-height: 1.3;
                min-width: 100px;
            }
            .node-label.override {
                border-color: #ef4444;
                box-shadow: 0 0 10px rgba(239, 68, 68, 0.6);
            }
            .node-header {
                font-weight: bold;
                color: #38bdf8;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                margin-bottom: 3px;
                padding-bottom: 2px;
                display: flex;
                justify-content: space-between;
            }
            .node-stat { display: flex; justify-content: space-between; gap: 8px; }
            .node-stat-val { font-weight: 600; }
        </style>
    </head>
    <body>
        <div id="map"></div>
        <div class="overlay-panel" id="stats">Connecting to simulation...</div>
        <div class="emerg-panel" id="emerg-alert">🚨 REROUTING: GREEN CORRIDOR ACTIVE</div>

        <script>
            // Use Carto dark matter for a sleek, premium base map
            const map = new maplibregl.Map({
                container: 'map',
                style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
                center: [-74.0060, 40.7128],
                zoom: 15.5,
                pitch: 45,
                bearing: 0
            });

            // WebSocket URL injected via Python string replacement
            const wsUrl = 'INJECT_WS_URL_HERE';
            let ws;
            
            // Map coordinates for intersections
            const BASE_LAT = 40.7128;
            const BASE_LON = -74.0060;
            const OFFSET = 0.005;
            const INTERSECTIONS = {
                "NW": [BASE_LON - OFFSET, BASE_LAT + OFFSET],
                "NE": [BASE_LON + OFFSET, BASE_LAT + OFFSET],
                "SW": [BASE_LON - OFFSET, BASE_LAT - OFFSET],
                "SE": [BASE_LON + OFFSET, BASE_LAT - OFFSET],
            };
            const nodeMarkers = {};

            function connectWebSocket() {
                ws = new WebSocket(wsUrl);
                ws.onopen = () => {
                    document.getElementById('stats').innerHTML = "Connected to Agent Subsystem.";
                };
                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    updateMap(data);
                    updateUI(data);
                };
                ws.onclose = () => {
                    document.getElementById('stats').innerHTML = "Connection lost. Reconnecting...";
                    setTimeout(connectWebSocket, 1000);
                };
            }

            map.on('load', () => {
                // 1. Add Intersection Nodes
                map.addSource('intersections', {
                    type: 'geojson',
                    data: { type: 'FeatureCollection', features: [] }
                });
                map.addLayer({
                    id: 'intersections-layer',
                    type: 'circle',
                    source: 'intersections',
                    paint: {
                        'circle-radius': 12,
                        'circle-color': '#1e293b',
                        'circle-stroke-width': 2,
                        'circle-stroke-color': '#475569'
                    }
                });

                // 2. Add Road Network Background
                map.addSource('roads-bg', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
                map.addLayer({
                    id: 'roads-bg-layer',
                    type: 'line',
                    source: 'roads-bg',
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: { 'line-width': 8, 'line-color': '#1e293b' }
                }, 'intersections-layer');

                // 3. Add Premium Dynamic Emergency Corridor (Uber-style)
                map.addSource('corridor-path', {
                    type: 'geojson',
                    data: { type: 'FeatureCollection', features: [] }
                });
                
                // Glow effect for corridor
                map.addLayer({
                    id: 'corridor-glow',
                    type: 'line',
                    source: 'corridor-path',
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: {
                        'line-width': 12,
                        'line-color': '#ef4444',
                        'line-opacity': 0.3,
                        'line-blur': 8
                    }
                });
                
                // Solid core line for corridor
                map.addLayer({
                    id: 'corridor-core',
                    type: 'line',
                    source: 'corridor-path',
                    layout: { 'line-cap': 'round', 'line-join': 'round' },
                    paint: {
                        'line-width': 4,
                        'line-color': '#10b981', // Green for green corridor
                        'line-opacity': 0.9,
                        'line-dasharray': [2, 1] // Animated dashed line effect
                    }
                });

                // 4. Add Vehicles
                map.addSource('vehicles', {
                    type: 'geojson',
                    data: { type: 'FeatureCollection', features: [] }
                });
                
                // Regular vehicles
                map.addLayer({
                    id: 'vehicles-layer',
                    type: 'circle',
                    source: 'vehicles',
                    filter: ['!=', ['get', 'is_emergency'], true],
                    paint: {
                        'circle-radius': ['case', ['==', ['get', 'waiting'], true], 4, 3],
                        'circle-color': ['get', 'color'],
                        'circle-opacity': 0.8
                    }
                });
                
                // Emergency vehicles with glow
                map.addLayer({
                    id: 'emergency-vehicles',
                    type: 'circle',
                    source: 'vehicles',
                    filter: ['==', ['get', 'is_emergency'], true],
                    paint: {
                        'circle-radius': 8,
                        'circle-color': '#ef4444',
                        'circle-stroke-width': 3,
                        'circle-stroke-color': '#ffffff'
                    }
                });

                // Initialize static features
                initStaticMapFeatures();
                
                // Initialize markers
                for (const [key, coords] of Object.entries(INTERSECTIONS)) {
                    const el = document.createElement('div');
                    el.className = 'node-label';
                    el.id = 'node-label-' + key;
                    nodeMarkers[key] = new maplibregl.Marker({element: el, anchor: 'bottom-left', offset: [15, -15]})
                        .setLngLat(coords)
                        .addTo(map);
                }

                connectWebSocket();
                
                // Animate dashed line
                let dashOffset = 0;
                function animateDashArray() {
                    if (map.getLayer('corridor-core')) {
                        dashOffset = (dashOffset - 0.1) % 3;
                        map.setPaintProperty('corridor-core', 'line-dasharray', [2, 1]);
                    }
                    requestAnimationFrame(animateDashArray);
                }
                animateDashArray();
            });

            function initStaticMapFeatures() {
                // Intersections
                const intFeatures = Object.keys(INTERSECTIONS).map(k => ({
                    type: 'Feature',
                    properties: { name: k },
                    geometry: { type: 'Point', coordinates: INTERSECTIONS[k] }
                }));
                map.getSource('intersections').setData({ type: 'FeatureCollection', features: intFeatures });

                // Simple grid roads
                const roadFeatures = [
                    { type: 'Feature', geometry: { type: 'LineString', coordinates: [ [BASE_LON - OFFSET, BASE_LAT + OFFSET*2], [BASE_LON - OFFSET, BASE_LAT - OFFSET*2] ] } },
                    { type: 'Feature', geometry: { type: 'LineString', coordinates: [ [BASE_LON + OFFSET, BASE_LAT + OFFSET*2], [BASE_LON + OFFSET, BASE_LAT - OFFSET*2] ] } },
                    { type: 'Feature', geometry: { type: 'LineString', coordinates: [ [BASE_LON - OFFSET*2, BASE_LAT + OFFSET], [BASE_LON + OFFSET*2, BASE_LAT + OFFSET] ] } },
                    { type: 'Feature', geometry: { type: 'LineString', coordinates: [ [BASE_LON - OFFSET*2, BASE_LAT - OFFSET], [BASE_LON + OFFSET*2, BASE_LAT - OFFSET] ] } }
                ];
                map.getSource('roads-bg').setData({ type: 'FeatureCollection', features: roadFeatures });
            }

            function updateMap(data) {
                if (!map.isStyleLoaded()) return;

                // Update vehicles
                const vFeatures = data.vehicles.map(v => ({
                    type: 'Feature',
                    geometry: { type: 'Point', coordinates: [v.lon, v.lat] },
                    properties: {
                        vid: v.vid,
                        color: v.color,
                        waiting: v.waiting,
                        is_emergency: v.is_emergency
                    }
                }));
                map.getSource('vehicles').setData({ type: 'FeatureCollection', features: vFeatures });

                // Update Green Corridor path
                const emerg = data.emergency_status;
                const emergPanel = document.getElementById('emerg-alert');
                
                if (emerg && (emerg.status === 'CORRIDOR_ACTIVE' || emerg.status === 'CLEARING') && emerg.active_corridor && emerg.active_corridor.length >= 2) {
                    const pathCoords = emerg.active_corridor.map(node => INTERSECTIONS[node]);
                    
                    // Construct smooth line for the corridor
                    const corridorFeature = {
                        type: 'Feature',
                        geometry: { type: 'LineString', coordinates: pathCoords },
                        properties: {}
                    };
                    map.getSource('corridor-path').setData({ type: 'FeatureCollection', features: [corridorFeature] });
                    
                    emergPanel.classList.add('active');
                    emergPanel.style.background = 'rgba(220, 38, 38, 0.9)'; // Red
                    emergPanel.style.boxShadow = '0 0 15px rgba(220, 38, 38, 0.6)';
                    let bannerText = `🚨 AI REROUTING: GREEN CORRIDOR ACTIVE [${emerg.active_corridor.join(' → ')}]`;
                    if (emerg.emergency_eta) {
                        bannerText += ` | ETA: ${emerg.emergency_eta.toFixed(1)}s`;
                    }
                    emergPanel.innerHTML = bannerText;
                } else {
                    map.getSource('corridor-path').setData({ type: 'FeatureCollection', features: [] });
                    emergPanel.classList.remove('active');
                    
                    if (emerg && emerg.status === 'RESOLVED' && emerg.time_saved_s) {
                         emergPanel.classList.add('active');
                         emergPanel.style.background = 'rgba(16, 185, 129, 0.9)'; // Green
                         emergPanel.style.boxShadow = '0 0 15px rgba(16, 185, 129, 0.6)';
                         emergPanel.innerHTML = `✅ EMERGENCY CLEARED | Saved ${emerg.time_saved_s.toFixed(1)}s (${emerg.improvement_pct.toFixed(1)}%)`;
                    }
                }
                
                // Update Node Overlays
                if (data.intersection_details) {
                    data.intersection_details.forEach(node => {
                        const marker = nodeMarkers[node.name];
                        if (marker) {
                            const el = marker.getElement();
                            if (node.override) {
                                el.classList.add('override');
                            } else {
                                el.classList.remove('override');
                            }
                            
                            const color = node.congestion_pct > 80 ? '#ef4444' : (node.congestion_pct > 50 ? '#f59e0b' : '#10b981');
                            
                            el.innerHTML = `
                                <div class="node-header">
                                    <span>NODE ${node.name}</span>
                                    <span style="color: ${node.override ? '#ef4444' : '#94a3b8'}; font-size: 9px; padding-left: 5px;">
                                        ${node.override ? 'OVERRIDE' : node.phase}
                                    </span>
                                </div>
                                <div class="node-stat"><span>Split:</span> <span class="node-stat-val">${node.ns_green.toFixed(0)}s / ${node.ew_green.toFixed(0)}s</span></div>
                                <div class="node-stat"><span>Vehicles:</span> <span class="node-stat-val">${node.total_vehicles}</span></div>
                                <div class="node-stat"><span>Wait:</span> <span class="node-stat-val">${node.avg_wait_s.toFixed(1)}s</span></div>
                                <div class="node-stat"><span>Congest:</span> <span class="node-stat-val" style="color: ${color}">${node.congestion_pct.toFixed(0)}%</span></div>
                            `;
                        }
                    });
                }
            }

            function updateUI(data) {
                const html = `
                    <div style="font-weight: 600; margin-bottom: 8px;">TRAFFICQ AI Engine</div>
                    <div class="kpi-row">
                        <div class="kpi-item">
                            <span class="kpi-val">${data.total_vehicles}</span>
                            <span class="kpi-lbl">Vehicles</span>
                        </div>
                        <div class="kpi-item">
                            <span class="kpi-val">${data.avg_speed_kmh.toFixed(1)}</span>
                            <span class="kpi-lbl">Avg km/h</span>
                        </div>
                        <div class="kpi-item">
                            <span class="kpi-val" style="color: ${data.congestion_pct > 60 ? '#ef4444' : '#38bdf8'}">${data.congestion_pct.toFixed(0)}%</span>
                            <span class="kpi-lbl">Congestion</span>
                        </div>
                        <div class="kpi-item">
                            <span class="kpi-val" style="color: #10b981;">+${(data.optimization_pct || 0).toFixed(1)}%</span>
                            <span class="kpi-lbl">Optimization</span>
                        </div>
                    </div>
                `;
                document.getElementById('stats').innerHTML = html;
            }
        </script>
    </body>
    </html>
    """.replace("INJECT_WS_URL_HERE", WS_URL)
    
    components.html(MAP_HTML, height=600)

    st.markdown("---")
    st.markdown("### 🧠 AI Traffic Analysis & Orchestrator")
    
    # Initialize session state for AI analysis
    if "ai_analysis" not in st.session_state:
        st.session_state.ai_analysis = None
    if "ai_question" not in st.session_state:
        st.session_state.ai_question = "Analyze the current traffic state and recommend optimizations."
        
    col_q, col_btn = st.columns([3, 1])
    with col_q:
        q = st.text_input("Ask the Traffic Orchestrator:", value=st.session_state.ai_question, label_visibility="collapsed")
    with col_btn:
        if st.button("Analyze with LLM", type="primary", use_container_width=True):
            with st.spinner("LLM is analyzing current grid state..."):
                try:
                    resp = requests.post(f"{API_URL}/analyse", json={"question": q}, timeout=45)
                    if resp.status_code == 200:
                        st.session_state.ai_analysis = resp.json().get("analysis", "")
                        st.session_state.ai_question = q
                except Exception as e:
                    st.error(f"Error fetching analysis: {e}")
                    
    if st.session_state.ai_analysis:
        st.markdown("**Orchestrator Decision & Analysis:**")
        st.code(st.session_state.ai_analysis, language="markdown")


with stats_col:
    st.markdown("### Agent Intelligence")
    
    # We fetch the latest state from the REST API to render the Streamlit UI side of things
    state = None
    try:
        resp = requests.get(f"{API_URL}/simulation/state", timeout=2)
        if resp.status_code == 200:
            state = resp.json()
    except:
        pass
        
    if state:
        st.markdown("##### 🚦 Intersection Metrics (Agent 1)")
        df_sig = pd.DataFrame(state.get("intersection_details", []))
        if not df_sig.empty:
            df_sig = df_sig[["name", "phase", "ns_green", "ew_green", "total_vehicles", "avg_wait_s", "congestion_pct", "override"]]
            df_sig.columns = ["Node", "Phase", "NS(s)", "EW(s)", "Vehicles", "Wait(s)", "Congest(%)", "OVR"]
            st.dataframe(df_sig, hide_index=True, use_container_width=True)
            
        st.markdown("##### 🗺️ Route Recommendations (Agent 2)")
        if state.get("route_recommendations"):
            for r in state["route_recommendations"]:
                col_icon = {"LOW":"🟢","MODERATE":"🟡","HIGH":"🟠","CRITICAL":"🔴"}.get(r["severity"],"⚪")
                st.caption(f"{col_icon} **{r['corridor']}**: {r['action']}")
        else:
            st.caption("No active routing advisories.")
            
        st.markdown("##### 🚨 Emergency Priority (Agent 3)")
        emg = state.get("emergency_status")
        if emg and emg["status"] in ["CORRIDOR_ACTIVE", "CLEARING"]:
            st.error(f"**ACTIVE:** {emg['vehicle_type'].upper()} entering from {emg.get('entry_lane', 'unknown')}", icon="🚨")
            if emg.get("active_corridor"):
                path_str = " → ".join(emg['active_corridor'])
                st.success(f"**AI Reroute Path:** {path_str}", icon="🗺️")
            if emg.get("emergency_eta"):
                st.caption(f"**ETA to destination:** {emg['emergency_eta']}s")
            if emg.get("explanation"):
                st.info(emg["explanation"])
            if emg.get("improvement_pct"):
                st.caption(f"**Optimization:** {emg['improvement_pct']}% faster response ({emg['time_saved_s']}s saved)")
        elif emg and emg["status"] == "RESOLVED":
            st.success(f"**RESOLVED:** {emg.get('vehicle_type', 'Vehicle').upper()} cleared.", icon="✅")
            if emg.get("time_saved_s"):
                st.caption(f"**Time Saved:** {emg['time_saved_s']}s ({emg['improvement_pct']}% improvement)")
        else:
            st.info("Monitoring for emergency vehicles...", icon="📡")
            
        st.markdown("##### 🧠 Agent Action Log")
        log_html = "<div style='height: 200px; overflow-y: auto; background-color: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #334155; font-family: monospace; font-size: 0.85em; color: #a5b4fc;'>"
        for log in reversed(state.get("agent_log", [])):
            log_html += f"<div style='margin-bottom: 4px; border-bottom: 1px solid #1e293b; padding-bottom: 2px;'>{log}</div>"
        log_html += "</div>"
        if state.get("agent_log"):
            st.markdown(log_html, unsafe_allow_html=True)
        else:
            st.caption("No agent activity recorded yet.")

# Trigger auto-refresh loop for Streamlit to fetch REST data periodically
if fetch_health():
    time.sleep(1.0)
    st.rerun()
