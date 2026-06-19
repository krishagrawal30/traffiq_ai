# 🚦 How to Run TRAFFICQ AI

To run the full TRAFFICQ AI project with the live MapLibre dashboard, you need to start two separate processes.

You will need to open **two separate terminal windows** (Command Prompt or PowerShell) and make sure both are in the project folder:
`c:\Users\soham\OneDrive\Desktop\Codes\Capgemini\traffiq_ai\trafficq_ai`

---

### Step 1: Start the Backend AI & API Server
In your **first terminal**, run the following command. This starts the simulation engine and the FastAPI server that hosts the AI Agents.

```powershell
python main.py api
```
*Wait until you see `Application startup complete.` or `Uvicorn running on http://0.0.0.0:8000` before proceeding to Step 2.*

---

### Step 2: Start the Frontend Dashboard
In your **second terminal**, run the following command to launch the Streamlit frontend.

```powershell
python main.py dashboard
```
*(Alternatively, you can run: `python -m streamlit run dashboard/app.py`)*

---

### Step 3: Open the Dashboard
Once the second command is running, it should automatically open a browser window. If it doesn't, manually open your web browser and go to:
**[http://localhost:8501](http://localhost:8501)**

### 💡 Tips for Using the Dashboard
1. Click the **"▶ Apply / Reset"** button in the sidebar to sync the dashboard with the simulation.
2. Under "Agent 03 — Emergency Dispatch", select an entry lane and click **"🚨 Dispatch Emergency Vehicle"** to see the AI dynamically reroute traffic and clear a green corridor!
3. Watch the intersection nodes on the map update in real-time with signal splits and wait times.
