import { useStore } from '../store';
import { motion } from 'framer-motion';

export default function AIControlCenter() {
  const { simState, phase } = useStore();
  const signals = simState?.signal_states || [];
  const routes = simState?.route_recommendations || [];
  const emg = simState?.emergency_status;

  // Generate human-readable insights
  const insights = [];

  if (phase === 'idle' || phase === 'building') {
    insights.push({
      type: 'system',
      icon: '⏸️',
      title: 'AI is currently observing',
      text: 'The AI agents are monitoring traffic but have not applied any optimizations yet. Click "Apply AI Optimization" on the Digital Twin to activate the agents.'
    });
  } else {
    // 1. Emergency Agent
    if (emg && emg.status !== 'STANDBY') {
      insights.push({
        type: 'emergency',
        icon: '🚑',
        title: 'Emergency Override Active',
        text: `Critical priority granted to ${emg.vehicle_type}. A green corridor has been created along ${emg.active_corridor?.join(', ')}. All cross-traffic signals have been preemptively turned red to guarantee a ${emg.eta_s?.toFixed(0)}s clear passage.`
      });
    }

    // 2. Signal Optimizer Agent
    const congestedSignals = signals.filter(s => s.congestion > 50 && !s.override);
    if (congestedSignals.length > 0) {
      congestedSignals.forEach(sig => {
        const total = sig.ns_green + sig.ew_green;
        const nsPct = Math.round((sig.ns_green / total) * 100);
        const heavier = nsPct > 50 ? 'North-South' : 'East-West';
        const lighter = nsPct > 50 ? 'East-West' : 'North-South';
        const moreTime = Math.max(sig.ns_green, sig.ew_green).toFixed(0);
        
        insights.push({
          type: 'signal',
          icon: '🚦',
          title: `Adaptive Timing at ${sig.name.replace('_', ' ')}`,
          text: `Detected ${sig.congestion.toFixed(0)}% congestion. The AI dynamically stole green time from the lighter ${lighter} approach and granted ${moreTime}s to the heavier ${heavier} approach to forcefully flush the queue.`
        });
      });
    } else if (!emg || emg.status === 'STANDBY') {
      insights.push({
        type: 'signal',
        icon: '✅',
        title: 'Traffic Flow is Stable',
        text: 'All junctions are currently experiencing normal flow. The AI is maintaining standard 30s/30s balanced signal splits to prevent unnecessary waiting.'
      });
    }

    // 3. Route Recommender Agent
    const activeRoutes = routes.filter(r => r.severity === 'HIGH' || r.severity === 'CRITICAL');
    activeRoutes.forEach(r => {
      insights.push({
        type: 'route',
        icon: '🗺️',
        title: `Rerouting: ${r.corridor.split('(')[0].trim()}`,
        text: `Severe bottleneck detected. The AI has actively diverted incoming traffic via ${r.alternate_route}. This proactive rerouting is estimated to save commuters ${r.estimated_saving_s} seconds of delay.`
      });
    });
  }

  return (
    <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold mb-2">Agent Activity Log</h2>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Real-time, explainable AI decisions translated into plain English.
        </p>
      </div>

      <div className="space-y-4">
        {insights.map((insight, i) => (
          <motion.div 
            key={`${insight.title}-${i}`} 
            initial={{ opacity: 0, x: -10 }} 
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-card p-5 border-l-4"
            style={{ 
              borderLeftColor: 
                insight.type === 'emergency' ? '#3b82f6' : 
                insight.type === 'signal' ? '#10b981' : 
                insight.type === 'route' ? '#f59e0b' : '#64748b'
            }}
          >
            <div className="flex items-start gap-4">
              <div className="text-2xl pt-1">{insight.icon}</div>
              <div>
                <h3 className="text-sm font-bold mb-1 text-white">{insight.title}</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                  {insight.text}
                </p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
