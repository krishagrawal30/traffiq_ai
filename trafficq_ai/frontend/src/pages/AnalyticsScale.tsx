import { motion } from 'framer-motion';

const INTEGRATIONS = [
  { name: 'CCTV Cameras', desc: 'Real-time video feeds for vehicle counting', status: 'Planned', color: '#3b82f6' },
  { name: 'IoT Sensors', desc: 'Inductive loop detectors at junctions', status: 'Planned', color: '#8b5cf6' },
  { name: 'Smart Traffic Lights', desc: 'Direct signal control via API', status: 'Ready', color: '#10b981' },
  { name: 'Google Maps API', desc: 'Live traffic layer and routing data', status: 'Planned', color: '#f59e0b' },
  { name: 'Emergency Services', desc: 'Automatic dispatch integration', status: 'Prototype', color: '#06b6d4' },
  { name: 'Public Transit', desc: 'BMTC bus priority signaling', status: 'Planned', color: '#ec4899' },
];


export default function AnalyticsScale() {
  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="mb-8">
        <h2 className="text-2xl font-bold">Analytics & Scalability</h2>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Architecture designed for city-scale deployment across 500+ junctions
        </p>
      </div>

      {/* Scale metrics */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Current Junctions', value: '4', sub: 'Silk Board Corridor' },
          { label: 'Scalable To', value: '500+', sub: 'City-wide deployment' },
          { label: 'Processing Latency', value: '<50ms', sub: 'Real-time decisions' },
          { label: 'Data Throughput', value: '10K+', sub: 'Events per second' },
        ].map((m, i) => (
          <motion.div key={m.label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }} className="glass-card p-5 text-center"
          >
            <div className="text-xs font-semibold tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>{m.label}</div>
            <div className="metric-value text-3xl font-bold text-white">{m.value}</div>
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{m.sub}</div>
          </motion.div>
        ))}
      </div>

      {/* Integrations */}
      <h3 className="text-lg font-bold mb-4">Ecosystem Integrations</h3>
      <div className="grid grid-cols-3 gap-4 mb-8">
        {INTEGRATIONS.map((intg, i) => (
          <motion.div key={intg.name} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }} className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold">{intg.name}</span>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{
                background: `${intg.color}20`, color: intg.color, border: `1px solid ${intg.color}30`
              }}>{intg.status}</span>
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{intg.desc}</div>
          </motion.div>
        ))}
      </div>

      {/* Performance benchmarks */}
      <h3 className="text-lg font-bold mb-4">Simulated Impact Benchmarks</h3>
      <div className="glass-card p-6 mb-4">
        <div className="overflow-hidden rounded-lg">
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: 'var(--bg-elevated)' }}>
                <th className="text-left p-3 text-xs font-semibold" style={{ color: 'var(--text-muted)' }}>Metric</th>
                <th className="text-right p-3 text-xs font-semibold text-red-400">Static Signals</th>
                <th className="text-right p-3 text-xs font-semibold text-emerald-400">TRAFFICQ AI</th>
                <th className="text-right p-3 text-xs font-semibold" style={{ color: 'var(--accent-cyan)' }}>Improvement</th>
              </tr>
            </thead>
            <tbody>
              {[
                { metric: 'Total Vehicles Served', stat: '118', adaptive: '120', imp: '+2%' },
                { metric: 'Avg Wait (last 60s)', stat: '13.5s', adaptive: '10.6s', imp: '-21% ↓' },
                { metric: 'Throughput (last 60s)', stat: '44/min', adaptive: '45.8/min', imp: '+4% ↑' },
                { metric: 'Emergency Clearance', stat: '77s', adaptive: '19s', imp: '-75% ↓' },
              ].map(row => (
                <tr key={row.metric} className="border-t" style={{ borderColor: 'var(--border)' }}>
                  <td className="p-3 text-xs" style={{ color: 'var(--text-secondary)' }}>{row.metric}</td>
                  <td className="p-3 text-right metric-value text-red-400">{row.stat}</td>
                  <td className="p-3 text-right metric-value text-emerald-400">{row.adaptive}</td>
                  <td className="p-3 text-right metric-value font-bold" style={{ color: 'var(--accent-cyan)' }}>{row.imp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
