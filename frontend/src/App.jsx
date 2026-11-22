import { useState, useEffect, useCallback } from 'react'
import TrafficMap from './Map.jsx'
import UserPanel from './UserPanel.jsx'
import { useTrafficSocket } from './useWebSocket.js'

const API = 'http://localhost:8001'

export default function App() {
  const { state, connected } = useTrafficSocket()
  const [crowdSize, setCrowdSize] = useState(8)
  const [actionFeedback, setActionFeedback] = useState(null)

  const users = state?.users ?? []
  const namedUsers = users.filter(u => !u.is_background)
  const conflictActive = namedUsers.some(u => u.conflict_detected)

  // Called when a user clicks an option chip
  const handleAction = useCallback(async (userId, action) => {
    const res = await fetch(`${API}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, action }),
    })
    if (res.ok) {
      setActionFeedback({ userId, action })
      setTimeout(() => setActionFeedback(null), 3000)
    }
  }, [])

  // Set crowd size
  const handleCrowdChange = useCallback(async (n) => {
    setCrowdSize(n)
    await fetch(`${API}/crowd`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: n }),
    })
  }, [])

  return (
    <div style={{
      display: 'grid',
      gridTemplateRows: 'auto 1fr',
      gridTemplateColumns: '1fr 320px',
      height: '100vh',
      gap: 0,
      background: '#0f172a',
    }}>
      {/* Header */}
      <div style={{
        gridColumn: '1 / -1',
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        padding: '10px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div>
          <span style={{ fontWeight: 800, fontSize: 18, color: '#f1f5f9' }}>
            Adaptive Traffic Routing
          </span>
          <span style={{ marginLeft: 12, fontSize: 12, color: '#64748b' }}>
            Multi-user conflict resolver · real-time
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Data source badge */}
          <div style={{
            background: state?.data_source === 'tomtom' ? '#052e16' : '#1c1917',
            border: `1px solid ${state?.data_source === 'tomtom' ? '#22c55e' : '#78716c'}`,
            borderRadius: 6,
            padding: '3px 10px',
            fontSize: 11,
            color: state?.data_source === 'tomtom' ? '#86efac' : '#a8a29e',
            fontWeight: 600,
          }}>
            {state?.data_source === 'tomtom' ? '🟢 TomTom Live' : '🟡 Simulated'}
          </div>

          {/* Total users on network */}
          {state?.total_users && (
            <div style={{ fontSize: 12, color: '#64748b' }}>
              {state.total_users} users on network
            </div>
          )}

          {/* Incident count */}
          {state?.incidents?.length > 0 && (
            <div style={{
              background: '#431407', border: '1px solid #f97316',
              borderRadius: 6, padding: '3px 10px',
              fontSize: 11, color: '#fdba74', fontWeight: 600,
            }}>
              ⚠ {state.incidents.length} incident{state.incidents.length > 1 ? 's' : ''}
            </div>
          )}

          {conflictActive && (
            <div style={{
              background: '#7f1d1d', border: '1px solid #ef4444',
              borderRadius: 6, padding: '4px 12px',
              fontSize: 12, color: '#fca5a5', fontWeight: 600,
            }}>
              CONFLICT DETECTED — REROUTING
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: connected ? '#22c55e' : '#ef4444',
            }} />
            <span style={{ fontSize: 12, color: '#64748b' }}>
              {connected ? 'WS Live' : 'Reconnecting…'}
            </span>
          </div>
        </div>
      </div>

      {/* Map */}
      <div style={{ position: 'relative', overflow: 'hidden' }}>
        <TrafficMap worldState={state} />
        {/* Legend */}
        <div style={{
          position: 'absolute', bottom: 16, left: 16,
          background: 'rgba(15,23,42,0.85)',
          borderRadius: 8, padding: '8px 12px',
          fontSize: 11, color: '#94a3b8',
          display: 'flex', flexDirection: 'column', gap: 4,
          backdropFilter: 'blur(4px)',
          zIndex: 1000,
        }}>
          <div style={{ fontWeight: 700, color: '#f1f5f9', marginBottom: 2 }}>Road Density</div>
          {[['#22c55e','Free flow'],['#f59e0b','Moderate'],['#ef4444','Congested']].map(([c,l]) => (
            <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 24, height: 4, background: c, borderRadius: 2 }} />
              {l}
            </div>
          ))}
          <div style={{ marginTop: 4, borderTop: '1px solid #334155', paddingTop: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444', boxShadow: '0 0 6px #ef4444' }} />
              Traffic signal
            </div>
          </div>
        </div>
      </div>

      {/* Sidebar */}
      <div style={{
        background: '#1e293b',
        borderLeft: '1px solid #334155',
        padding: 16,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}>
        {/* Crowd size slider */}
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
            Simulate Traffic Load
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input
              type="range" min={0} max={50} value={crowdSize}
              onChange={e => handleCrowdChange(Number(e.target.value))}
              style={{ flex: 1, accentColor: '#3b82f6' }}
            />
            <span style={{ fontSize: 13, color: '#f1f5f9', minWidth: 32 }}>
              {crowdSize + 2}
            </span>
          </div>
          <div style={{ fontSize: 11, color: '#475569', marginTop: 2 }}>
            users total on network
          </div>
        </div>

        <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 1 }}>
          Named Users
        </div>
        <UserPanel users={namedUsers} onAction={handleAction} />

        {/* Action feedback toast */}
        {actionFeedback && (
          <div style={{
            background: '#052e16', border: '1px solid #22c55e',
            borderRadius: 6, padding: '6px 10px',
            fontSize: 12, color: '#86efac',
          }}>
            ✓ {actionFeedback.action.replace('_', ' ')} applied for {actionFeedback.userId} — re-routing everyone now
          </div>
        )}

        {/* Segment stats */}
        {state?.segments && (
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
              Segment Stats
            </div>
            {Object.entries(state.segments).map(([id, seg]) => (
              <div key={id} style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: 12, color: '#64748b',
                padding: '4px 0', borderBottom: '1px solid #0f172a',
              }}>
                <span>{id}</span>
                <span style={{ color: seg.density > 0.6 ? '#ef4444' : seg.density > 0.3 ? '#f59e0b' : '#22c55e' }}>
                  {Math.round(seg.density * 100)}% · {seg.vehicle_count}v
                </span>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 'auto', fontSize: 11, color: '#334155', textAlign: 'center' }}>
          Updates every 2s · Backend ws://localhost:8001
        </div>
      </div>
    </div>
  )
}
