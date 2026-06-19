import { useStore } from '../store';
import { motion } from 'framer-motion';

export default function ScenarioBattle() {
  const { simState, beforeMetrics, phase, startScenario, applyOptimization } = useStore();

  const hasData = phase === 'optimized' && beforeMetrics && simState;

  const comparisons = hasData ? [
    { label: 'Average Wait', before: `${beforeMetrics.avg_wait_s.toFixed(1)}s`, after: `${simState.avg_wait_s.toFixed(1)}s`,
      beforeVal: beforeMetrics.avg_wait_s, afterVal: simState.avg_wait_s, lowerBetter: true },
    { label: 'Congestion', before: `${beforeMetrics.congestion_pct.toFixed(0)}%`, after: `${simState.congestion_pct.toFixed(0)}%`,
      beforeVal: beforeMetrics.congestion_pct, afterVal: simState.congestion_pct, lowerBetter: true },
    { label: 'Throughput', before: `${(beforeMetrics.throughput_pm * 60).toFixed(0)}/hr`, after: `${(simState.throughput_pm * 60).toFixed(0)}/hr`,
      beforeVal: beforeMetrics.throughput_pm * 60, afterVal: simState.throughput_pm * 60, lowerBetter: false },
  ] : [];

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="max-w-3xl mx-auto">
        <h2 className="text-2xl font-bold text-center mb-2">Before vs After</h2>
        <p className="text-sm text-center mb-8" style={{ color: 'var(--text-muted)' }}>
          Static signals vs AI-optimized signals — same traffic, same roads
        </p>

        {/* If no data yet, prompt to run demo */}
        {!hasData && (
          <div className="glass-card p-8 text-center mb-8">
            <div className="text-lg mb-2" style={{ color: 'var(--text-muted)' }}>No comparison data yet</div>
            <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
              Go to Digital Twin → Pick a scenario → Let congestion build → Click "Apply AI Optimization"
            </p>
            <div className="flex gap-3 justify-center">
              <button onClick={() => startScenario('Morning Rush', 8)}
                className="px-4 py-2 rounded-lg cursor-pointer text-sm font-medium"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
              >
                Start Morning Rush
              </button>
              {phase === 'building' && (
                <button onClick={applyOptimization}
                  className="px-4 py-2 rounded-lg cursor-pointer text-sm font-medium text-white"
                  style={{ background: '#3b82f6' }}
                >
                  Apply AI Now
                </button>
              )}
            </div>
          </div>
        )}

        {/* Comparison bars */}
        {hasData && (
          <div className="space-y-6 mb-8">
            {comparisons.map(c => {
              const imp = c.lowerBetter
                ? ((c.beforeVal - c.afterVal) / Math.max(c.beforeVal, 0.01) * 100)
                : ((c.afterVal - c.beforeVal) / Math.max(c.beforeVal, 0.01) * 100);
              const maxVal = Math.max(c.beforeVal, c.afterVal, 1);
              return (
                <div key={c.label} className="glass-card p-5">
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-sm font-bold">{c.label}</span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${imp > 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                      {imp > 0 ? '↓' : '↑'} {Math.abs(imp).toFixed(0)}%
                    </span>
                  </div>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span style={{ color: 'var(--text-muted)' }}>Static Signals</span>
                        <span className="metric-value font-bold text-red-400">{c.before}</span>
                      </div>
                      <div className="h-4 rounded-full overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                        <motion.div animate={{ width: `${(c.beforeVal / maxVal) * 100}%` }} className="h-full rounded-full bg-red-500/50" />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span style={{ color: 'var(--text-muted)' }}>TRAFFICQ AI</span>
                        <span className="metric-value font-bold text-emerald-400">{c.after}</span>
                      </div>
                      <div className="h-4 rounded-full overflow-hidden" style={{ background: 'var(--bg-elevated)' }}>
                        <motion.div animate={{ width: `${(c.afterVal / maxVal) * 100}%` }} className="h-full rounded-full bg-emerald-500/50" />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Emergency benchmark — only show when data exists */}
        {hasData && (
          <div className="glass-card p-6 mt-6">
            <h3 className="text-sm font-bold mb-4 text-center">Emergency Response</h3>
            <div className="grid grid-cols-2 gap-6">
              <div className="text-center p-4 rounded-xl" style={{ background: '#ef444410', border: '1px solid #ef444420' }}>
                <div className="text-xs" style={{ color: 'var(--text-muted)' }}>Without AI</div>
                <div className="metric-value text-4xl font-bold text-red-400 my-2">77s</div>
                <div className="text-xs text-red-400/70">Stuck in traffic</div>
              </div>
              <div className="text-center p-4 rounded-xl" style={{ background: '#10b98110', border: '1px solid #10b98120' }}>
                <div className="text-xs text-emerald-400">With AI Corridor</div>
                <div className="metric-value text-4xl font-bold text-emerald-400 my-2">19s</div>
                <div className="text-xs text-emerald-400/70">75% faster</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
