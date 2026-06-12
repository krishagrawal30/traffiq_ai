# 🚦 TRAFFICQ AI
**Autonomous Emergency & Smart Traffic Intelligence System**
*RCOEM Hackathon 2025 — Use Case 45/50*

> *Traffic that adapts. Cities that breathe.*
---
## Team
Siddhi Gangan · Yashika Rathi · Saidhiraj Kadwajiwar · Soham Darak · Krish Agrawal

---

## What it does
TRAFFICQ AI replaces legacy fixed-timer traffic signals with a **three-agent AI system** that:

| Agent | Role |
|-------|------|
| **Agent 01 — Signal Optimizer**   | Adjusts green-light splits every cycle using priority scores |
| **Agent 02 — Route Recommender**  | Detects corridor congestion and recommends diversions |
| **Agent 03 — Emergency Priority** | Creates automated green corridors for first responders |

All decisions are narrated in plain English by an LLM so city engineers can audit every choice.

---

## Architecture
```
IoT Sensors / Cameras / GPS
          ↓
   Simulation Engine  (pandas · numpy · queue model)
          ↓
   Agent Orchestrator  (LangChain · OpenAI / Azure GPT-4)
    ├── Agent 01: Signal Optimization  (priority formula)
    ├── Agent 02: Route Recommendation (congestion thresholds)
    └── Agent 03: Emergency Priority   (green corridor)
          ↓
   Optimization Decision Engine
    ├── Dashboard  (Streamlit · Plotly)
    ├── REST API   (FastAPI · WebSockets)
    └── NL Explanations (LLM)
```

---

## Quick start

### 1. Clone & install
```bash
git clone https://github.com/your-org/trafficq-ai
cd trafficq-ai
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and add your OpenAI or Azure OpenAI key
```

### 3. Run

| Command | What it does |
|---------|-------------|
| `python main.py demo`      | CLI agent demo with rich terminal output |
| `python main.py simulate`  | Run simulation and print metrics table |
| `python main.py api`       | Start FastAPI server on :8000 |
| `python main.py dashboard` | Launch Streamlit dashboard |
| `python main.py video`     | Generate comparison video |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health`               | GET  | System health check |
| `/simulation/configure` | POST | Set mode, density, FPS |
| `/simulation/state`     | GET  | Current simulation snapshot |
| `/simulation/step`      | POST | Manual single-step |
| `/simulation/reset`     | POST | Reset to fresh state |
| `/signals`              | GET  | Per-intersection signal states |
| `/emergency`            | POST | Dispatch emergency vehicle |
| `/emergency/status`     | GET  | Emergency agent status + log |
| `/analyse`              | POST | LLM-powered traffic analysis |
| `/ws/state`             | WS   | Real-time state stream (~20 fps) |

### Example — dispatch emergency
```bash
curl -X POST http://localhost:8000/emergency \
  -H "Content-Type: application/json" \
  -d '{"vehicle_type":"ambulance","entry_lane":"EB_top","vehicle_id":42}'
```

---

## Core algorithm — priority signal formula

```
G(NS) = max(G_min,  round( P(NS) / (P(NS) + P(EW)) × C ))

where:
  P(d) = (Wait_Time × 0.6) + (Queue_Length × 0.3) + (Emergency × 1000) + (Congestion_Pct × 0.1)
  C    = cycle length (60 s)
  G_min = 15 s  (pedestrian safety floor)
```

Adjacent intersections are offset by the inter-intersection travel time
(≈12 s) to create a coordinated green wave.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| LLM / Reasoning | OpenAI GPT-4o · Azure OpenAI |
| Orchestration   | LangChain · custom tools |
| Backend API     | FastAPI · WebSockets · Uvicorn |
| Simulation      | Python · NumPy · Pandas |
| Dashboard       | Streamlit · Plotly |
| Visualisation   | Matplotlib (video) · Mapbox (prod) |
| Observability   | OpenTelemetry · structured logging |
| Secrets         | python-dotenv · Azure Key Vault pattern |

---

## Simulation results

| Metric | Static signals | TRAFFICQ AI | Improvement |
|--------|---------------|-------------|-------------|
| Avg wait time     | 68 s   | 42 s  | **38% ↓** |
| Emergency clear   | 85+ s  | 12 s  | **86% ↓** |
| Throughput        | 24/min | 58/min| **2.4× ↑** |
| Congestion index  | 67%    | 39%   | **41% ↓** |
| Idle CO₂          | baseline | −29% | **29% ↓** |

---

## Roadmap

| Phase | Description |
|-------|-------------|
| 1 | Pilot: 1–4 intersections with smart sensors |
| 2 | District: 50 nodes, Redis sync, Grafana ops |
| 3 | City-wide: K8s, federated agents, ML preloading |
| 4 | Vehicle-to-city: V2C communication |
| 5 | Digital Twin: full city simulation mirror |

---

## License
MIT — see `LICENSE`
