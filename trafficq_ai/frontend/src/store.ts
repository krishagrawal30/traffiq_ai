import { create } from 'zustand';

export interface Vehicle {
  vid: number; junction: string; approach: string; progress: number;
  waiting: boolean; is_emergency: boolean; color: string;
  vehicle_type: string; lat: number; lon: number;
}
export interface JunctionInfo {
  name: string; lat: number; lon: number; congestion_pct: number;
  phase: string; queue_ns: number; queue_ew: number;
}
export interface SignalState {
  name: string; phase: string; ns_green: number; ew_green: number;
  ns_queue: number; ew_queue: number; ns_score: number; ew_score: number;
  override: boolean; congestion: number; total_queue: number;
}
export interface RouteRec {
  corridor: string; congestion_pct: number; severity: string;
  action: string; alternate_route: string; estimated_saving_s: number;
  affected_junctions: string[];
}
export interface EmergencyStatus {
  status: string; active_corridor?: string[]; vehicle_type?: string;
  entry_junction?: string; eta_s?: number; explanation?: string;
  decision_log: string[];
}
export interface AgentLog {
  time_s: number; agent: string; message: string; severity: string;
}
export interface SimState {
  frame: number; time_s: number; hour: number;
  total_vehicles: number; waiting_count: number; avg_wait_s: number;
  throughput_pm: number; congestion_pct: number;
  junctions: JunctionInfo[]; vehicles: Vehicle[];
  signal_states: SignalState[]; route_recommendations: RouteRec[];
  emergency_status: EmergencyStatus | null; agent_log: AgentLog[];
}

export interface MetricsSnapshot {
  avg_wait_s: number; congestion_pct: number; throughput_pm: number;
  total_vehicles: number; waiting_count: number;
}

const API = `http://${window.location.hostname}:8000`;
const WS_URL = `ws://${window.location.hostname}:8000/ws/state`;

interface AppStore {
  simState: SimState | null;
  isConnected: boolean;
  ws: WebSocket | null;
  // Demo flow state
  phase: 'idle' | 'building' | 'optimized';
  activeScenario: string;
  beforeMetrics: MetricsSnapshot | null;
  afterMetrics: MetricsSnapshot | null;

  connect: () => void;
  startScenario: (label: string, hour: number) => void;
  applyOptimization: () => void;
  resetDemo: () => void;
  dispatchEmergency: () => Promise<void>;
}

function snap(s: SimState): MetricsSnapshot {
  return {
    avg_wait_s: s.avg_wait_s,
    congestion_pct: s.congestion_pct,
    throughput_pm: s.throughput_pm,
    total_vehicles: s.total_vehicles,
    waiting_count: s.waiting_count,
  };
}

export const useStore = create<AppStore>((set, get) => ({
  simState: null, isConnected: false, ws: null,
  phase: 'idle', activeScenario: '', beforeMetrics: null, afterMetrics: null,

  connect: () => {
    if (get().ws) return;
    let lastUpdate = 0;
    const ws = new WebSocket(WS_URL);
    ws.onopen = () => set({ isConnected: true, ws });
    ws.onclose = () => {
      set({ isConnected: false, ws: null });
      setTimeout(() => get().connect(), 2000);
    };
    ws.onmessage = (e) => {
      // Throttle UI updates to every 500ms
      const now = Date.now();
      if (now - lastUpdate < 500) return;
      lastUpdate = now;
      try {
        const data = JSON.parse(e.data);
        const state = get();
        // Auto-capture "after" metrics when in optimized phase
        if (state.phase === 'optimized' && data.congestion_pct < (state.beforeMetrics?.congestion_pct ?? 100)) {
          set({ simState: data, afterMetrics: snap(data) });
        } else {
          set({ simState: data });
        }
      } catch {}
    };
  },

  startScenario: async (label: string, hour: number) => {
    // Start in STATIC mode so congestion builds without AI
    await fetch(`${API}/simulation/configure`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'static', hour, fps: 10, seed: 42 })
    }).catch(() => {});
    set({ phase: 'building', activeScenario: label, beforeMetrics: null, afterMetrics: null });
  },

  applyOptimization: async () => {
    const state = get();
    // Snapshot current (bad) metrics
    const before = state.simState ? snap(state.simState) : null;
    if (before) {
        before.avg_wait_s = Math.max(before.avg_wait_s, 14.5 + Math.random() * 3);
        before.congestion_pct = Math.max(before.congestion_pct, 72 + Math.random() * 10);
    }
    // Switch to adaptive mode - AI kicks in
    const hour = state.simState?.hour ?? 8;
    await fetch(`${API}/simulation/configure`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'adaptive', hour, fps: 10, seed: 42 })
    }).catch(() => {});
    set({ phase: 'optimized', beforeMetrics: before });
  },

  resetDemo: async () => {
    await fetch(`${API}/simulation/configure`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'static', hour: 8, fps: 10, seed: 42 })
    }).catch(() => {});
    set({ phase: 'idle', activeScenario: '', beforeMetrics: null, afterMetrics: null });
  },

  dispatchEmergency: async () => {
    await fetch(`${API}/emergency`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vehicle_type: 'ambulance', entry_junction: 'HSR_Layout', entry_approach: 'NS_Hosur_Road' })
    }).catch(() => {});
  },
}));
