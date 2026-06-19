import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useStore } from './store';
import DigitalTwin from './pages/DigitalTwin';
import AIControlCenter from './pages/AIControlCenter';
import EmergencyCorridor from './pages/EmergencyCorridor';
import ScenarioBattle from './pages/ScenarioBattle';
import AnalyticsScale from './pages/AnalyticsScale';

const NAV = [
  { to: '/', label: 'Digital Twin', icon: '◉' },
  { to: '/ai', label: 'AI Decisions', icon: '⬡' },
  { to: '/emergency', label: 'Emergency', icon: '⚡' },
  { to: '/battle', label: 'Before vs After', icon: '⇄' },
  { to: '/analytics', label: 'Scale', icon: '◈' },
];

export default function App() {
  const { connect, isConnected, phase, activeScenario } = useStore();
  useEffect(() => { connect(); }, [connect]);

  return (
    <BrowserRouter>
      <div className="h-screen w-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
        <header className="h-14 flex items-center justify-between px-6 border-b shrink-0" style={{ borderColor: 'var(--border)', background: 'rgba(10,14,26,0.95)' }}>
          <div className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
            <h1 className="text-lg font-bold tracking-tight">TRAFFICQ</h1>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--bg-elevated)', color: 'var(--text-muted)' }}>
              Digital Twin
            </span>
            {phase !== 'idle' && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{
                background: phase === 'building' ? '#f59e0b20' : '#10b98120',
                color: phase === 'building' ? '#f59e0b' : '#10b981',
                border: `1px solid ${phase === 'building' ? '#f59e0b30' : '#10b98130'}`,
              }}>
                {phase === 'building' ? `⏳ ${activeScenario} — Congestion Building` : `✓ ${activeScenario} — AI Active`}
              </span>
            )}
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map(n => (
              <NavLink key={n.to} to={n.to} end={n.to === '/'}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${
                    isActive ? 'bg-blue-600/20 text-blue-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`
                }
              >
                <span className="text-xs">{n.icon}</span>{n.label}
              </NavLink>
            ))}
          </nav>

          <div className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            Bengaluru · Silk Board
          </div>
        </header>

        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<DigitalTwin />} />
            <Route path="/ai" element={<AIControlCenter />} />
            <Route path="/emergency" element={<EmergencyCorridor />} />
            <Route path="/battle" element={<ScenarioBattle />} />
            <Route path="/analytics" element={<AnalyticsScale />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
