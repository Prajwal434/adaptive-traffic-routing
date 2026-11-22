import { useState, useEffect, useCallback } from 'react'
import TrafficMap from './Map.jsx'
import UserPanel from './UserPanel.jsx'
import { useTrafficSocket } from './useWebSocket.js'

const API = 'http://localhost:8001'

const USER_META = {
  user_1: { label: 'Priya', emoji: '👩', color: '#3b82f6' },
  user_2: { label: 'Ravi',  emoji: '🚛', color: '#ef4444' },
}

export default function App() {
  const { state, connected } = useTrafficSocket()
  const [crowdSize, setCrowdSize]       = useState(8)
  const [actionFeedback, setActionFeedback] = useState(null)
  const [sysStatus, setSysStatus]       = useState(null)
  const [activeUser, setActiveUser]     = useState('user_1')  // which user's POV we show

  // Poll /status every 5s
  useEffect(() => {
    const poll = async () => {
      try { const r = await fetch(`${API}/status`); if (r.ok) setSysStatus(await r.json()) }
      catch (_) {}
    }
    poll(); const id = setInterval(poll, 5000); return () => clearInterval(id)
  }, [])

  const users     = state?.users ?? []
  const namedUsers = users.filter(u => !u.is_background)
  const activeUserData = namedUsers.find(u => u.user_id === activeUser)
  const conflictActive = namedUsers.some(u => u.conflict_detected)
  const isLive = sysStatus?.data_source === 'tomtom'

  const handleAction = useCallback(async (userId, action) => {
    const res = await fetch(`${API}/action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, action }),
    })
    if (res.ok) { setActionFeedback({ userId, action }); setTimeout(() => setActionFeedback(null), 3000) }
  }, [])

  const handleCrowdChange = useCallback(async (n) => {
    setCrowdSize(n)
    await fetch(`${API}/crowd`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count: n }),
    })
  }, [])

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>

      {/* MAP — full screen */}
      <TrafficMap worldState={state} activeUserId={activeUser} />

      {/* ── TOP BAR ── */}
      <div style={{
        position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'white', borderRadius: 24, padding: '8px 16px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.18)',
        zIndex: 1000, whiteSpace: 'nowrap',
      }}>
        <span style={{ fontWeight: 700, fontSize: 15, color: '#1f2328' }}>Adaptive Traffic</span>
        <Divider />
        <LiveDot active={isLive} label={isLive ? 'TomTom Live' : 'Simulated'} color={isLive ? '#16a34a' : '#d97706'} />
        <Divider />
        <LiveDot active={connected} label={connected ? 'Connected' : 'Reconnecting…'} color={connected ? '#3b82f6' : '#ef4444'} />
        {sysStatus?.total_users > 0 && <><Divider /><span style={{ fontSize: 12, color: '#6b7280' }}>{sysStatus.total_users} on network</span></>}
        {conflictActive && <><Divider /><span style={{ fontSize: 12, fontWeight: 700, color: '#dc2626' }}>⚠ Conflict — rerouting</span></>}
      </div>

      {/* ── USER SWITCHER ── */}
      <div style={{
        position: 'absolute', top: 68, left: '50%', transform: 'translateX(-50%)',
        display: 'flex', gap: 8, zIndex: 1000,
      }}>
        {namedUsers.map(u => {
          const meta = USER_META[u.user_id] ?? { label: u.name, emoji: '👤', color: u.color }
          const isActive = activeUser === u.user_id
          return (
            <button
              key={u.user_id}
              onClick={() => setActiveUser(u.user_id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 7,
                background: isActive ? meta.color : 'white',
                color: isActive ? 'white' : '#374151',
                border: `2px solid ${meta.color}`,
                borderRadius: 20, padding: '6px 14px',
                fontWeight: 700, fontSize: 13, cursor: 'pointer',
                boxShadow: isActive ? `0 2px 8px ${meta.color}60` : '0 1px 4px rgba(0,0,0,0.1)',
                transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: 16 }}>{meta.emoji}</span>
              {meta.label}
              {u.conflict_detected && <span style={{ fontSize: 10, background: isActive ? 'rgba(255,255,255,0.3)' : '#fee2e2', color: isActive ? 'white' : '#dc2626', borderRadius: 10, padding: '1px 6px' }}>!</span>}
            </button>
          )
        })}
      </div>

      {/* ── ACTION FEEDBACK TOAST ── */}
      {actionFeedback && (
        <div style={{
          position: 'absolute', top: 120, left: '50%', transform: 'translateX(-50%)',
          background: '#16a34a', color: 'white', borderRadius: 20, padding: '7px 18px',
          fontSize: 13, fontWeight: 600, boxShadow: '0 2px 8px rgba(0,0,0,0.2)', zIndex: 1001,
        }}>
          ✓ Applied — routes updating now
        </div>
      )}

      {/* ── ACTIVE USER CARD (right panel) ── */}
      {activeUserData && (
        <div style={{
          position: 'absolute', top: 120, right: 12,
          width: 300, zIndex: 1000,
        }}>
          <UserPanel
            user={activeUserData}
            allUsers={namedUsers}
            onAction={handleAction}
          />
        </div>
      )}

      {/* ── MAP LEGEND (bottom-left) ── */}
      <div style={{
        position: 'absolute', bottom: 24, left: 16,
        background: 'white', borderRadius: 12, padding: '10px 14px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.12)', zIndex: 1000, fontSize: 12, color: '#374151',
      }}>
        <div style={{ fontWeight: 600, marginBottom: 6, color: '#111827' }}>Road traffic</div>
        {[['#22c55e','Free flow'],['#f59e0b','Moderate'],['#ef4444','Heavy']].map(([c,l]) => (
          <div key={l} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <div style={{ width: 28, height: 5, background: c, borderRadius: 3 }} />
            <span>{l}</span>
          </div>
        ))}
      </div>

      {/* ── TRAFFIC LOAD SLIDER (bottom-center) ── */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        background: 'white', borderRadius: 12, padding: '10px 18px',
        boxShadow: '0 2px 10px rgba(0,0,0,0.12)', zIndex: 1000, minWidth: 220,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: '#111827' }}>Simulate traffic load</span>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{crowdSize + 2} users</span>
        </div>
        <input type="range" min={0} max={50} value={crowdSize}
          onChange={e => handleCrowdChange(Number(e.target.value))}
          style={{ width: '100%', accentColor: '#3b82f6', cursor: 'pointer' }} />
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#9ca3af', marginTop: 2 }}>
          <span>Quiet</span><span>Rush hour</span>
        </div>
      </div>

      {/* ── SEGMENT STATS (bottom-right, collapsed) ── */}
      {state?.segments && (
        <SegmentOverlay segments={state.segments} />
      )}
    </div>
  )
}

function Divider() {
  return <div style={{ width: 1, height: 16, background: '#e5e7eb' }} />
}

function LiveDot({ active, label, color }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, boxShadow: active ? `0 0 0 2px ${color}30` : 'none' }} />
      <span style={{ fontSize: 12, color, fontWeight: 600 }}>{label}</span>
    </div>
  )
}

function SegmentOverlay({ segments }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{
      position: 'absolute', bottom: 24, right: 12,
      background: 'white', borderRadius: 12,
      boxShadow: '0 2px 10px rgba(0,0,0,0.12)',
      zIndex: 1000, overflow: 'hidden', minWidth: 160,
    }}>
      <button onClick={() => setOpen(o => !o)} style={{
        width: '100%', padding: '9px 14px', background: 'none', border: 'none',
        cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        fontSize: 12, fontWeight: 600, color: '#111827',
      }}>
        Road segments <span>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 14px 10px' }}>
          {Object.entries(segments).map(([id, seg]) => (
            <div key={id} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0', borderTop: '1px solid #f3f4f6' }}>
              <span style={{ color: '#6b7280' }}>{id}</span>
              <span style={{ fontWeight: 600, color: seg.density > 0.6 ? '#dc2626' : seg.density > 0.3 ? '#d97706' : '#16a34a' }}>
                {Math.round(seg.density * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
