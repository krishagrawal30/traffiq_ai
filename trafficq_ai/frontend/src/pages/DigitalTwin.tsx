import { useMemo, useState } from 'react';
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, LineLayer, TextLayer } from '@deck.gl/layers';
import { useStore } from '../store';
import 'maplibre-gl/dist/maplibre-gl.css';

const VIEW = { longitude: 77.6180, latitude: 12.9160, zoom: 14, pitch: 45, bearing: -10 };
const STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const CLR: Record<string, [number, number, number, number]> = {
  '#3B8BD4': [59, 139, 212, 220], '#1D9E75': [29, 158, 117, 220],
  '#D85A30': [216, 90, 48, 220],  '#7F77DD': [127, 119, 221, 220],
  '#F59E0B': [245, 158, 11, 220], '#EF4444': [239, 68, 68, 255],
};

const ROADS = [
  { from: [77.6240, 12.8960], to: [77.6228, 12.9180] },
  { from: [77.6228, 12.9180], to: [77.6200, 12.9330] },
  { from: [77.6100, 12.9080], to: [77.6228, 12.9180] },
  { from: [77.6100, 12.9080], to: [77.6020, 12.9080] },
  { from: [77.6140, 12.9180], to: [77.6228, 12.9180] },
  { from: [77.6228, 12.9180], to: [77.6300, 12.9280] },
  { from: [77.6240, 12.9080], to: [77.6320, 12.9080] },
  { from: [77.6200, 12.9330], to: [77.6120, 12.9330] },
];

const SCENARIOS = [
  { label: 'Morning Rush', hour: 8, desc: '8 AM peak traffic' },
  { label: 'Evening Peak', hour: 18, desc: '6 PM all directions' },
  { label: 'Road Accident', hour: 9, desc: 'Creates route diversion' },
];

export default function DigitalTwin() {
  const { simState, phase, startScenario, applyOptimization, resetDemo, beforeMetrics } = useStore();
  const [vs, setVs] = useState(VIEW);

  const vehicleLayer = useMemo(() => {
    if (!simState?.vehicles?.length) return null;
    return new ScatterplotLayer({
      id: 'vehicles', data: simState.vehicles, pickable: false,
      opacity: 0.9, filled: true, stroked: true,
      radiusMinPixels: 5, radiusMaxPixels: 12, lineWidthMinPixels: 1,
      getPosition: (d: any) => [d.lon, d.lat],
      getFillColor: (d: any) => d.is_emergency ? [59, 130, 246, 255] : (CLR[d.color] || [180, 180, 200, 200]),
      getLineColor: (d: any) => d.is_emergency ? [255, 255, 255, 255] : [0, 0, 0, 80],
      getRadius: (d: any) => d.is_emergency ? 18 : (d.waiting ? 8 : 10),
      transitions: { getPosition: 300 },
    });
  }, [simState?.vehicles]);

  const signalLayer = useMemo(() => {
    if (!simState?.junctions?.length) return null;
    return new ScatterplotLayer({
      id: 'signals', data: simState.junctions, pickable: false,
      opacity: 1, filled: true, stroked: true,
      radiusMinPixels: 10, radiusMaxPixels: 22, lineWidthMinPixels: 2,
      getPosition: (d: any) => [d.lon, d.lat],
      getFillColor: (d: any) => {
        if (d.congestion_pct > 70) return [239, 68, 68, 220];
        if (d.congestion_pct > 40) return [245, 158, 11, 220];
        return [16, 185, 129, 220];
      },
      getLineColor: [255, 255, 255, 180],
      getRadius: () => 18,
    });
  }, [simState?.junctions]);

  const signalTextLayer = useMemo(() => {
    if (!simState?.signal_states?.length || !simState?.junctions?.length) return null;
    const jMap: Record<string, any> = {};
    simState.junctions.forEach(j => { jMap[j.name] = j; });

    return new TextLayer({
      id: 'signal-texts',
      data: simState.signal_states.filter(s => jMap[s.name]),
      getPosition: (d: any) => [jMap[d.name].lon, jMap[d.name].lat],
      getText: (d: any) => `${jMap[d.name].name.replace(/_/g, ' ').toUpperCase()}\n${d.phase === 'NS' ? '[GO]' : '[STOP]'} NS: ${Math.round(d.ns_green)}s\n${d.phase === 'EW' ? '[GO]' : '[STOP]'} EW: ${Math.round(d.ew_green)}s`,
      getSize: 14,
      getColor: [255, 255, 255, 255],
      getAlignmentBaseline: 'center',
      getTextAnchor: 'middle',
      getPixelOffset: [0, -45],
      fontWeight: 'bold',
      outlineWidth: 2,
      outlineColor: [0, 0, 0, 255],
    });
  }, [simState?.signal_states, simState?.junctions]);

  const roadLayer = useMemo(() => {
    const cong = simState?.congestion_pct ?? 0;
    return new LineLayer({
      id: 'roads', data: ROADS, pickable: false,
      getSourcePosition: (d: any) => d.from,
      getTargetPosition: (d: any) => d.to,
      getColor: cong > 60 ? [239, 68, 68, 140] : cong > 30 ? [245, 158, 11, 100] : [16, 185, 129, 70],
      getWidth: 4,
    });
  }, [simState?.congestion_pct]);

  const rerouteTextLayer = useMemo(() => {
    if (!simState?.route_recommendations?.length) return null;
    const active = simState.route_recommendations.filter(r => r.severity === 'HIGH' || r.severity === 'CRITICAL');
    if (active.length === 0) return null;

    const uniqueRoutes = Array.from(new Set(active.map(r => r.alternate_route))).join(' | ');

    return new TextLayer({
      id: 'reroute-texts',
      data: [{ text: `⚠️ DIVERSION ACTIVE\nUse ${uniqueRoutes}`, pos: [77.6180, 12.9240] }],
      getPosition: (d: any) => d.pos,
      getText: (d: any) => d.text,
      getSize: 16,
      getColor: [245, 158, 11, 255],
      getAlignmentBaseline: 'center',
      getTextAnchor: 'middle',
      fontWeight: 'bold',
      outlineWidth: 3,
      outlineColor: [0, 0, 0, 255],
    });
  }, [simState?.route_recommendations]);

  return (
    <div className="h-full w-full relative">
      <DeckGL
        initialViewState={vs} controller={true}
        onViewStateChange={({ viewState }: any) => setVs(viewState)}
        layers={[roadLayer, signalLayer, vehicleLayer, signalTextLayer, rerouteTextLayer].filter(Boolean)}
        getCursor={() => 'grab'}
      >
        <Map mapStyle={STYLE} />
      </DeckGL>

      {/* ── STEP 1: Pick a scenario (idle state) ── */}
      {phase === 'idle' && (
        <div className="absolute inset-0 flex items-center justify-center z-20" style={{ background: 'rgba(10,14,26,0.7)' }}>
          <div className="glass-card p-8 max-w-lg text-center">
            <h2 className="text-2xl font-bold mb-2">Bengaluru Traffic Digital Twin</h2>
            <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>Choose a traffic scenario to begin the demo</p>
            <div className="flex gap-3 justify-center">
              {SCENARIOS.map(s => (
                <button key={s.label} onClick={() => startScenario(s.label, s.hour)}
                  className="px-6 py-4 rounded-xl cursor-pointer transition-all hover:scale-105"
                  style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
                >
                  <div className="text-sm font-bold text-white">{s.label}</div>
                  <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{s.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── STEP 2: Congestion building — show "Optimize" button ── */}
      {phase === 'building' && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 glass-card px-6 py-4 text-center" style={{ borderColor: '#f59e0b40' }}>
          <div className="text-sm font-bold text-amber-400 mb-1">⏳ Traffic is building up — No AI optimization</div>
          <div className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>Fixed 30s/30s signals — watch congestion grow</div>
          <button onClick={applyOptimization}
            className="px-8 py-3 rounded-xl text-white font-bold cursor-pointer transition-all hover:scale-105"
            style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', boxShadow: '0 4px 20px rgba(59,130,246,0.4)' }}
          >
            🧠 Apply AI Optimization
          </button>
        </div>
      )}

      {/* ── STEP 3: Optimized — show before/after ── */}
      {phase === 'optimized' && beforeMetrics && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 glass-card px-6 py-4" style={{ borderColor: '#10b98140' }}>
          <div className="text-sm font-bold text-emerald-400 mb-3 text-center">✓ AI Optimization Active</div>
          <div className="flex gap-6 items-center">
            <div className="text-center">
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Wait Before</div>
              <div className="metric-value text-xl font-bold text-red-400 line-through">{beforeMetrics.avg_wait_s.toFixed(1)}s</div>
            </div>
            <div className="text-lg text-emerald-400">→</div>
            <div className="text-center">
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Wait Now</div>
              <div className="metric-value text-xl font-bold text-emerald-400">{(simState?.avg_wait_s ?? 0).toFixed(1)}s</div>
            </div>
            <div className="w-px h-10" style={{ background: 'var(--border)' }} />
            <div className="text-center">
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Congestion Before</div>
              <div className="metric-value text-xl font-bold text-red-400 line-through">{beforeMetrics.congestion_pct.toFixed(0)}%</div>
            </div>
            <div className="text-lg text-emerald-400">→</div>
            <div className="text-center">
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Now</div>
              <div className="metric-value text-xl font-bold text-emerald-400">{(simState?.congestion_pct ?? 0).toFixed(0)}%</div>
            </div>
            <div className="w-px h-10" style={{ background: 'var(--border)' }} />
            <button onClick={resetDemo} className="text-xs px-3 py-1.5 rounded-lg cursor-pointer" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
              Reset
            </button>
          </div>
        </div>
      )}

      {/* ── Live stats bar (always visible) ── */}
      <div className="absolute bottom-4 left-4 flex gap-2 z-10">
        {[
          { label: 'Vehicles', val: simState?.total_vehicles ?? 0, color: '#f1f5f9' },
          { label: 'Passing / min', val: (simState?.throughput_pm ?? 0).toFixed(0), color: '#3b82f6' },
          { label: 'Waiting', val: simState?.waiting_count ?? 0, color: (simState?.waiting_count ?? 0) > 20 ? '#ef4444' : '#10b981' },
          { label: 'Congestion', val: `${(simState?.congestion_pct ?? 0).toFixed(0)}%`, color: (simState?.congestion_pct ?? 0) > 60 ? '#ef4444' : '#10b981' },
          { label: 'Avg Wait', val: `${(simState?.avg_wait_s ?? 0).toFixed(1)}s`, color: (simState?.avg_wait_s ?? 0) > 10 ? '#f59e0b' : '#10b981' },
        ].map(m => (
          <div key={m.label} className="glass-card px-4 py-2">
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{m.label}</div>
            <div className="metric-value text-lg font-bold" style={{ color: m.color }}>{m.val}</div>
          </div>
        ))}
      </div>

      {/* Junction legend */}
      <div className="absolute bottom-4 right-4 glass-card px-3 py-2 z-10">
        {simState?.junctions?.map(j => (
          <div key={j.name} className="flex items-center gap-2 py-0.5">
            <div className="w-2.5 h-2.5 rounded-full" style={{
              background: j.congestion_pct > 70 ? '#ef4444' : j.congestion_pct > 40 ? '#f59e0b' : '#10b981'
            }} />
            <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>{j.name.replace('_', ' ')}</span>
            <span className="text-xs font-mono ml-auto pl-3" style={{
              color: j.congestion_pct > 70 ? '#ef4444' : j.congestion_pct > 40 ? '#f59e0b' : '#10b981'
            }}>{j.congestion_pct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
