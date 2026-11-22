export default function UserPanel({ users, onAction }) {
  if (!users?.length) return (
    <div style={{ color: '#64748b', fontSize: 13 }}>Waiting for backend…</div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {users.map(user => (
        <div key={user.user_id} style={{
          background: '#1e293b',
          border: `2px solid ${user.conflict_detected ? '#ef4444' : user.color}`,
          borderRadius: 10,
          padding: '12px 14px',
        }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 700, fontSize: 15, color: user.color }}>
              {user.name}
            </span>
            <span style={{
              fontSize: 11, background: '#0f172a',
              borderRadius: 4, padding: '2px 7px', color: '#94a3b8'
            }}>
              {user.vehicle_type?.toUpperCase()}
            </span>
          </div>

          {/* Route path */}
          {user.route?.path && (
            <div style={{ marginTop: 6, fontSize: 13, color: '#cbd5e1', letterSpacing: 1 }}>
              {user.route.path.join(' \u2192 ')}
            </div>
          )}

          {/* ETA row */}
          <div style={{ display: 'flex', gap: 16, marginTop: 8 }}>
            <Stat label="Assigned ETA" value={`${user.assigned_eta_minutes} min`} color={user.color} />
            <Stat label="Personal Best" value={`${user.personal_best_eta_minutes} min`} color="#64748b" />
          </div>

          {/* Warning banner */}
          {user.warning && (
            <div style={{
              marginTop: 8,
              background: user.conflict_detected ? '#450a0a' : '#1a1a2e',
              border: `1px solid ${user.conflict_detected ? '#ef4444' : '#f59e0b'}`,
              borderRadius: 6,
              padding: '6px 10px',
              fontSize: 12,
              color: user.conflict_detected ? '#fca5a5' : '#fde68a',
              lineHeight: 1.5,
            }}>
              {user.warning}
            </div>
          )}

          {/* Departure options — the key UX */}
          {user.departure_options && (
            <div style={{ marginTop: 8 }}>
              <div style={{ fontSize: 10, color: '#475569', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 }}>
                Your options
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <OptionChip
                  label={`Leave ${user.departure_options.leave_early_min} min earlier`}
                  sub="Beat the crowd"
                  color="#22c55e"
                  onClick={() => onAction?.(user.user_id, 'leave_early')}
                />
                <OptionChip
                  label={`Leave ${user.departure_options.leave_late_min} min later`}
                  sub="Let it clear"
                  color="#3b82f6"
                  onClick={() => onAction?.(user.user_id, 'leave_late')}
                />
                {user.route?.path?.length > 2 && (
                  <OptionChip
                    label={`Take ${user.route.path.join('\u2192')}`}
                    sub="Alternate route"
                    color="#a855f7"
                    onClick={() => onAction?.(user.user_id, 'alternate')}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Stat({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#475569', textTransform: 'uppercase', letterSpacing: 0.5 }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 700, color }}>
        {value}
      </div>
    </div>
  )
}

function OptionChip({ label, sub, color, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: '#0f172a',
        border: `1px solid ${color}`,
        borderRadius: 6,
        padding: '5px 9px',
        flex: '1 1 auto',
        minWidth: 0,
        cursor: 'pointer',
        transition: 'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = '#1e293b'}
      onMouseLeave={e => e.currentTarget.style.background = '#0f172a'}
    >
      <div style={{ fontSize: 11, fontWeight: 600, color }}>{label}</div>
      <div style={{ fontSize: 10, color: '#475569' }}>{sub}</div>
    </div>
  )
}
