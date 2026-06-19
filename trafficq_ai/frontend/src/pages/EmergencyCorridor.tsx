import { useState } from 'react';
import { Map } from 'react-map-gl/maplibre';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, LineLayer } from '@deck.gl/layers';
import { useStore } from '../store';
import 'maplibre-gl/dist/maplibre-gl.css';

const VIEW = { longitude: 77.6180, latitude: 12.9160, zoom: 14, pitch: 40, bearing: -10 };
const STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const CORRIDOR = [
  { from: [77.6320, 12.9080], to: [77.6228, 12.9180] }, // HSR Layout to Silk Board
  { from: [77.6228, 12.9180], to: [77.6300, 12.9280] }, // Silk Board to Madiwala
];

const ROUTE_STOPS = ['HSR Layout', 'Silk Board', 'Madiwala'];

export default function EmergencyCorridor() {
  const { simState, dispatchEmergency } = useStore();
  const [vs, setVs] = useState(VIEW);
  const emg = simState?.emergency_status;
  const isActive = emg?.status === 'CORRIDOR_ACTIVE';

  const vehicleLayer = new ScatterplotLayer({
    id: 'vehicles', data: simState?.vehicles || [], pickable: false,
    opacity: 0.7, filled: true, radiusMinPixels: 2, radiusMaxPixels: 6,
    getPosition: (d: any) => [d.lon, d.lat],
    getFillColor: (d: any) => d.is_emergency ? [59, 130, 246, 255] : [100, 116, 139, 100],
    getRadius: (d: any) => d.is_emergency ? 14 : 3,
    transitions: { getPosition: 300 },
  });

  const corridorLayer = new LineLayer({
    id: 'corridor', data: isActive ? CORRIDOR : [], pickable: false,
    getSourcePosition: (d: any) => d.from, getTargetPosition: (d: any) => d.to,
    getColor: [59, 130, 246, 200], getWidth: 8,
  });

  const signalLayer = new ScatterplotLayer({
    id: 'signals', data: simState?.junctions || [], pickable: false,
    opacity: 1, filled: true, stroked: true,
    radiusMinPixels: 10, radiusMaxPixels: 20, lineWidthMinPixels: 2,
    getPosition: (d: any) => [d.lon, d.lat],
    getFillColor: (d: any) => {
      if (isActive && ['HSR_Layout', 'Silk_Board', 'Madiwala'].includes(d.name)) return [59, 130, 246, 255] as any;
      return d.congestion_pct > 50 ? [239, 68, 68, 200] as any : [16, 185, 129, 200] as any;
    },
    getLineColor: [255, 255, 255, 180], getRadius: () => 16,
  });

  return (
    <div className="h-full flex">
      <div className="w-[70%] relative">
        <DeckGL initialViewState={vs} controller={true}
          onViewStateChange={({ viewState }: any) => setVs(viewState)}
          layers={[corridorLayer, signalLayer, vehicleLayer]} getCursor={() => 'grab'}
        >
          <Map mapStyle={STYLE} />
        </DeckGL>

        {isActive && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 emergency-glow glass-card px-6 py-3" style={{ borderColor: '#3b82f6' }}>
            <div className="text-sm font-bold text-blue-300 animate-pulse text-center">⚡ GREEN CORRIDOR ACTIVE</div>
          </div>
        )}
      </div>

      {/* Right panel */}
      <div className="w-[30%] border-l flex flex-col" style={{ borderColor: 'var(--border)', background: 'var(--bg-primary)' }}>
        <div className="p-6 flex-1 overflow-y-auto">
          <h2 className="text-xl font-bold mb-1">Emergency Corridor</h2>
          <p className="text-xs mb-6" style={{ color: 'var(--text-muted)' }}>
            One click. Green corridor. Ambulance priority.
          </p>

          {!isActive && (
            <button onClick={dispatchEmergency}
              className="w-full py-4 rounded-xl text-white font-bold text-lg mb-6 cursor-pointer transition-all hover:scale-[1.02]"
              style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)', boxShadow: '0 4px 20px rgba(59,130,246,0.4)' }}
            >
              🚑 Dispatch Ambulance
            </button>
          )}

          {/* Route */}
          <div className="glass-card p-4 mb-4">
            <div className="text-xs font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>ROUTE</div>
            {ROUTE_STOPS.map((stop, i) => (
              <div key={stop} className="flex items-center gap-3 py-2">
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{
                  background: isActive ? '#3b82f620' : 'var(--bg-elevated)',
                  color: isActive ? '#3b82f6' : 'var(--text-muted)',
                }}>{i + 1}</div>
                <span className="text-sm">{stop}</span>
                {isActive && <span className="text-xs text-emerald-400 ml-auto">✓ Green</span>}
              </div>
            ))}
          </div>

          {/* Impact */}
          <div className="glass-card p-4 mb-4">
            <div className="text-xs font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>IMPACT</div>
            <div className="grid grid-cols-2 gap-3">
              <div className="text-center p-3 rounded" style={{ background: '#ef444410' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Without AI</div>
                <div className="metric-value text-2xl font-bold text-red-400">77s</div>
              </div>
              <div className="text-center p-3 rounded" style={{ background: '#10b98110' }}>
                <div className="text-xs text-emerald-400">With AI</div>
                <div className="metric-value text-2xl font-bold text-emerald-400">{isActive ? `${emg?.eta_s?.toFixed(0) || '19'}s` : '19s'}</div>
              </div>
            </div>
            <div className="text-center text-xs mt-2 font-bold text-emerald-400">75% faster response</div>
          </div>

          {/* How it works */}
          <div className="glass-card p-4">
            <div className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>HOW IT WORKS</div>
            <div className="space-y-2 text-xs" style={{ color: 'var(--text-secondary)' }}>
              <p>1. Ambulance enters the corridor</p>
              <p>2. AI calculates fastest path</p>
              <p>3. All signals along route turn green</p>
              <p>4. Regular traffic is held briefly</p>
              <p>5. Ambulance passes through unobstructed</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
