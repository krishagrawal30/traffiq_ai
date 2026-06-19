# 🚦 TRAFFICQ AI v2 — Bengaluru Silk Board Corridor

**Autonomous Traffic Management Agent** for one of India's most congested traffic corridors.

Team: Siddhi Gangan · Yashika Rathi · Saidhiraj Kadwajiwar · Soham Darak · Krish Agrawal

---

## What It Does

TRAFFICQ AI replaces fixed-timer traffic signals with a **3-agent AI system** for the Bengaluru Silk Board corridor (4 junctions: Silk Board, Madiwala, HSR Layout, BTM Layout):

| Agent | Role | How |
|-------|------|-----|
| **Agent 01 — Signal Optimizer** | Adjusts green-light splits | Priority formula: `G = f(peak_queue, wait_time, congestion)` |
| **Agent 02 — Route Recommender** | Detects corridor congestion | Threshold-based severity (LOW→CRITICAL) with alternate routes |
| **Agent 03 — Emergency Priority** | Green corridor for first responders | Predictive signal override 15s ahead of ETA |

All decisions include **plain-English explanations** with specific numbers.

---

## Architecture

```
Bengaluru Traffic Data (OpenCity + Synthetic)
         ↓
  Simulation Engine  (Silk Board corridor topology)
         ↓
  Agent Orchestrator  (LangChain · OpenAI / Azure GPT-4o)
    ├── Agent 01: Signal Optimization  (peak queue tracking)
    ├── Agent 02: Route Recommendation  (corridor congestion)
    └── Agent 03: Emergency Priority   (green corridor)
         ↓
  Dashboard  (Streamlit · MapLibre · Plotly)
  REST API   (FastAPI · WebSockets)
  NL Explanations  (LLM)
```

---

## Quick Start

### 1. Setup
```bash
git clone <repo>
cd trafficq_ai

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your OpenAI key (optional — runs without LLM)
```

### 2. Run
```bash
# Terminal 1: Start the API server
python main.py api

# Terminal 2: Start the dashboard
python main.py dashboard

# Or just test the simulation
python main.py simulate
python main.py demo
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health + uptime |
| `/simulation/configure` | POST | Set mode, hour, fps |
| `/simulation/state` | GET | Current simulation snapshot |
| `/simulation/step` | POST | Manual single-step |
| `/simulation/reset` | POST | Reset simulation |
| `/signals` | GET | Signal states per junction |
| `/emergency` | POST | Dispatch emergency vehicle |
| `/emergency/status` | GET | Emergency agent status |
| `/analyse` | POST | LLM-powered traffic analysis |
| `/evaluate/golden` | POST | Run golden dataset tests |
| `/ws/state` | WS | Real-time state stream (~10 fps) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | OpenAI GPT-4o / Azure OpenAI |
| **Agent Framework** | LangChain (optional) |
| **Backend** | FastAPI + WebSockets |
| **Simulation** | Python + NumPy + Pandas |
| **Dashboard** | Streamlit + MapLibre GL + Plotly |
| **Data** | OpenCity Bengaluru signal timings + synthetic traffic patterns |
| **Evaluation** | Golden dataset (JSON) with pass/fail scenarios |
| **Secrets** | python-dotenv (never hardcoded) |

---

## Evaluation — Performance Metrics

From benchmark (static 30s/30s vs adaptive AI):

| Metric | Static | Adaptive AI | Improvement |
|--------|--------|-------------|-------------|
| Total Vehicles Served | 118 | 120 | +2% |
| Avg Wait (last 60s) | 13.5s | 10.6s | **−21% ↓** |
| Throughput (last 60s) | 44/min | 45.8/min | **+4% ↑** |
| Emergency Clearance | 77s (est.) | **19s** | **−75% ↓** |

*(Morning peak scenario, Hosur Road NS direction heaviest)*

---

## Data Sources

- **Real signal timings**: [OpenCity Bengaluru](https://data.opencity.in/dataset/bengaluru-city-traffic-signal-data) — 100+ junction PDFs
- **Traffic patterns**: Calibrated synthetic data based on known Bengaluru peak hours
- **Road topology**: Silk Board corridor mapped via OpenStreetMap coordinates
- **Golden dataset**: 5 evaluation scenarios with expected agent responses

---

## Project Structure

```
trafficq_ai/
├── data/
│   ├── raw/                   # Real Bengaluru signal timings
│   ├── synthetic/             # Calibrated traffic flow patterns
│   └── golden_dataset.json    # Evaluation test scenarios
├── simulation/
│   ├── engine.py              # Core simulation engine
│   └── topology.py            # Bengaluru road network definition
├── agents/
│   ├── signal_optimizer.py    # Agent 01
│   ├── route_recommender.py   # Agent 02
│   ├── emergency_priority.py  # Agent 03
│   └── orchestrator.py        # LangChain agent coordination
├── api/
│   ├── app.py                 # FastAPI + WebSocket server
│   └── models.py              # Pydantic schemas
├── dashboard/
│   └── app.py                 # Streamlit UI
├── scripts/
│   └── benchmark.py           # Static vs adaptive comparison
├── config.py                  # Settings (dotenv)
├── main.py                    # Entry point
└── requirements.txt           # Dependencies
```

---

## License
MIT
