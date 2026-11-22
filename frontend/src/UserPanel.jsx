export default function UserPanel({ user, allUsers, onAction }) {
  if (!user) return null

  const otherUsers = (allUsers ?? []).filter(u => u.user_id !== user.user_id)

  return (
    <div style={{
      background: 'white', borderRadius: 16,
      boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
      overflow: 'hidden',
    }}>
      {/* Coloured top strip */}
      <div style={{ height: 4, background: user.color }} />

      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Name + vehicle */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16, color: '#111827' }}>{user.name}</div>
            <div style={{ fontSize: 12, color: '#6b7280', marginTop: 1 }}>
              {user.origin} → {user.destination}
            </div>
          </div>
          <span style={{
            fontSize: 11, background: '#f3f4f6',
            borderRadius: 20, padding: '3px 10px',
            color: '#374151', fontWeight: 700,
          }}>
            {user.vehicle_type?.toUpperCase()}
          </span>
        </div>

        {/* Route breadcrumb */}
        {user.route?.path && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 4,
            background: '#f9fafb', borderRadius: 8, padding: '7px 10px',
          }}>
            {user.route.path.map((node, i) => (
              <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                {i > 0 && <span style={{ color: '#9ca3af', fontSize: 11 }}>▶</span>}
                <span style={{
                  background: i === 0 ? user.color : i === user.route.path.length - 1 ? '#111827' : '#e5e7eb',
                  color: (i === 0 || i === user.route.path.length - 1) ? 'white' : '#374151',
                  borderRadius: 6, padding: '2px 8px',
                  fontWeight: 700, fontSize: 12,
                }}>{node}</span>
              </span>
            ))}
          </div>
        )}

        {/* ETA */}
        <div style={{ display: 'flex', gap: 0, background: '#f9fafb', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ flex: 1, padding: '10px 14px', borderRight: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.5 }}>Your ETA</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: user.color, marginTop: 2 }}>
              {user.assigned_eta_minutes} <span style={{ fontSize: 12, fontWeight: 500, color: '#6b7280' }}>min</span>
            </div>
          </div>
          <div style={{ flex: 1, padding: '10px 14px' }}>
            <div style={{ fontSize: 10, color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.5 }}>Best case</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: '#9ca3af', marginTop: 2 }}>
              {user.personal_best_eta_minutes} <span style={{ fontSize: 12, fontWeight: 500 }}>min</span>
            </div>
          </div>
        </div>

        {/* AI Profile insight */}
        <AIProfile userId={user.user_id} color={user.color} />

        {/* Warning */}
        {user.warning && (
          <div style={{
            background: user.conflict_detected ? '#fef2f2' : '#fffbeb',
            border: `1px solid ${user.conflict_detected ? '#fca5a5' : '#fde68a'}`,
            borderRadius: 10, padding: '8px 12px',
            fontSize: 12, color: user.conflict_detected ? '#991b1b' : '#92400e',
            lineHeight: 1.6,
          }}>
            {user.warning}
          </div>
        )}

        {/* Action chips */}
        {user.departure_options && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Your options
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <ActionBtn icon="⏰" label={`Leave ${user.departure_options.leave_early_min} min earlier`} sub="Beat the crowd" color="#16a34a" bg="#f0fdf4" onClick={() => onAction?.(user.user_id, 'leave_early')} />
              <ActionBtn icon="☕" label={`Leave ${user.departure_options.leave_late_min} min later`} sub="Let it clear" color="#2563eb" bg="#eff6ff" onClick={() => onAction?.(user.user_id, 'leave_late')} />
            </div>
            {user.route?.path?.length > 2 && (
              <ActionBtn icon="↗" label="Take alternate route" sub={user.route.path.join(' → ')} color="#7c3aed" bg="#f5f3ff" onClick={() => onAction?.(user.user_id, 'alternate')} full />
            )}
          </div>
        )}

        {/* Others on same road */}
        {otherUsers.length > 0 && (
          <div style={{ borderTop: '1px solid #f3f4f6', paddingTop: 10 }}>
            <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
              Others on network
            </div>
            {otherUsers.map(u => (
              <div key={u.user_id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '4px 0',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: u.color }} />
                  <span style={{ fontSize: 12, color: '#374151', fontWeight: 600 }}>{u.name}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 11, color: '#6b7280' }}>{u.route?.path?.join('→')}</span>
                  {u.conflict_detected && <span style={{ fontSize: 10, color: '#dc2626', fontWeight: 700 }}>⚠</span>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ── AI Profile widget — fetches server-side learned profile ──
import { useEffect, useState } from 'react'
const API = 'http://localhost:8001'

function AIProfile({ userId, color }) {
  const [profile, setProfile] = useState(null)
  useEffect(() => {
    fetch(`${API}/profile/${userId}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setProfile(d))
      .catch(() => {})
  }, [userId])

  if (!profile) return null

  return (
    <div style={{
      background: '#fafafa', border: '1px solid #e5e7eb',
      borderRadius: 10, padding: '8px 12px',
    }}>
      <div style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>
        🤖 AI Profile
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {profile.preferred_departure && (
          <Tag label={`Leaves ~${profile.preferred_departure}`} color={color} />
        )}
        {profile.avg_speed_factor && (
          <Tag label={`Drives ${profile.avg_speed_factor > 1 ? 'faster' : 'slower'} than avg`} color={color} />
        )}
        {profile.usual_route && (
          <Tag label={`Usual: ${profile.usual_route}`} color={color} />
        )}
        {profile.trips_logged != null && (
          <Tag label={`${profile.trips_logged} trips logged`} color="#6b7280" />
        )}
      </div>
    </div>
  )
}

function Tag({ label, color }) {
  return (
    <span style={{
      fontSize: 11, background: `${color}15`,
      color, borderRadius: 20, padding: '2px 8px', fontWeight: 600,
    }}>
      {label}
    </span>
  )
}

function ActionBtn({ icon, label, sub, color, bg, onClick, full }) {
  return (
    <button onClick={onClick} style={{
      flex: full ? '1 1 100%' : '1 1 0',
      background: bg, border: `1.5px solid ${color}25`,
      borderRadius: 10, padding: '8px 10px', cursor: 'pointer',
      textAlign: 'left', display: 'flex', alignItems: 'flex-start', gap: 7,
      transition: 'transform 0.1s, box-shadow 0.1s',
    }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = `0 3px 10px ${color}25` }}
      onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = '' }}
    >
      <span style={{ fontSize: 16, marginTop: 1 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, color }}>{label}</div>
        {sub && <div style={{ fontSize: 10, color: '#9ca3af', marginTop: 1 }}>{sub}</div>}
      </div>
    </button>
  )
}
