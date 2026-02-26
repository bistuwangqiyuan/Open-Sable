import { fmtUptime } from '../../lib/utils';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto' },
  grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, padding: '12px 16px' },
  card: {
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', padding: 12,
    display: 'flex', flexDirection: 'column', gap: 4,
  },
  label: {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.05em', fontWeight: 500,
  },
  value: { fontSize: 20, fontWeight: 700 },
  section: { borderTop: '1px solid var(--border)', marginTop: 8 },
  session: {
    padding: '10px 16px', borderBottom: '1px solid var(--border)',
    fontSize: 12.5, cursor: 'pointer', transition: 'background .1s',
  },
};

export default function StatusPanel({ stats, sessions, model, activity }) {
  const toolCalls = activity.filter(a => a.type === 'tool').length;
  const errors = activity.filter(a => a.type === 'error').length;

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>📊</span>
        <span style={s.title}>Status</span>
      </div>
      <div style={s.body}>
        <div style={s.grid}>
          <div style={s.card}>
            <div style={s.label}>Uptime</div>
            <div style={{ ...s.value, color: 'var(--accent-light)' }}>{fmtUptime(stats.uptime_sec)}</div>
          </div>
          <div style={s.card}>
            <div style={s.label}>Clients</div>
            <div style={{ ...s.value, color: 'var(--teal)' }}>{stats.clients || 0}</div>
          </div>
          <div style={s.card}>
            <div style={s.label}>Tool Calls</div>
            <div style={{ ...s.value, color: 'var(--accent-light)' }}>{toolCalls}</div>
          </div>
          <div style={s.card}>
            <div style={s.label}>Errors</div>
            <div style={{ ...s.value, color: errors > 0 ? 'var(--red)' : 'var(--green)' }}>{errors}</div>
          </div>
          <div style={s.card}>
            <div style={s.label}>Nodes</div>
            <div style={{ ...s.value, color: 'var(--teal)' }}>{(stats.nodes || []).length}</div>
          </div>
          <div style={s.card}>
            <div style={s.label}>Sessions</div>
            <div style={s.value}>{sessions.length}</div>
          </div>
        </div>

        {model && (
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
            <div style={s.label}>Active Model</div>
            <div style={{
              marginTop: 6, padding: '8px 12px', background: 'var(--bg-tertiary)',
              border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
              fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--teal)',
            }}>
              {model}
            </div>
          </div>
        )}

        <div style={s.section}>
          <div style={s.header}>
            <span style={{ fontSize: 14 }}>📋</span>
            <span style={s.title}>Sessions</span>
            <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
              {sessions.length}
            </span>
          </div>
          {sessions.length === 0 ? (
            <div style={{ padding: '12px 16px', color: 'var(--text-muted)', fontSize: 12 }}>No sessions</div>
          ) : (
            sessions.map((ses, i) => (
              <div key={i} style={s.session}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontWeight: 600, fontSize: 12 }}>{ses.channel}:{ses.user_id}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{ses.messages} msgs</span>
                </div>
                <div style={{
                  fontSize: 10, color: 'var(--text-muted)', marginTop: 2,
                  fontFamily: 'var(--mono)',
                }}>
                  {ses.id?.slice(0, 24)}…
                </div>
              </div>
            ))
          )}
        </div>

        <div style={{ padding: 16, borderTop: '1px solid var(--border)', textAlign: 'center' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            OpenSable v{stats.version || '1.1.0'}
          </div>
        </div>
      </div>
    </div>
  );
}
