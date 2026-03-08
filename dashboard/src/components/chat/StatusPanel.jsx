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
  grid3: { display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, padding: '12px 16px' },
  card: {
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', padding: 12,
    display: 'flex', flexDirection: 'column', gap: 4,
  },
  cardWide: {
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', padding: 12,
    display: 'flex', flexDirection: 'column', gap: 4,
    gridColumn: 'span 2',
  },
  label: {
    fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '.05em', fontWeight: 500,
  },
  value: { fontSize: 20, fontWeight: 700 },
  valueSm: { fontSize: 14, fontWeight: 600 },
  section: { borderTop: '1px solid var(--border)', marginTop: 8 },
  session: {
    padding: '10px 16px', borderBottom: '1px solid var(--border)',
    fontSize: 12.5, cursor: 'pointer', transition: 'background .1s',
  },
  bar: (pct, color) => ({
    height: 6, borderRadius: 3, background: 'var(--bg-primary)',
    overflow: 'hidden', marginTop: 6,
    position: 'relative',
  }),
  barFill: (pct, color) => ({
    height: '100%', borderRadius: 3, width: `${Math.min(pct, 100)}%`,
    background: color, transition: 'width .3s',
  }),
  modelRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 0', fontSize: 12, borderBottom: '1px solid var(--border)',
  },
};

function fmtTokens(n) {
  if (!n) return '0';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toString();
}

function fmtCost(usd) {
  if (!usd) return '$0.00';
  if (usd < 0.01) return '$' + usd.toFixed(4);
  return '$' + usd.toFixed(2);
}

export default function StatusPanel({ stats, sessions, model, activity }) {
  const toolCalls = activity.filter(a => a.type === 'tool').length;
  const errors = activity.filter(a => a.type === 'error').length;
  const tokens = stats.tokens || {};

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

        {/* ── Token Consumption ─────────────────────────────── */}
        <div style={s.section}>
          <div style={s.header}>
            <span style={{ fontSize: 14 }}>🪙</span>
            <span style={s.title}>Token Consumption</span>
            {tokens.tokens_per_min > 0 && (
              <span style={{
                marginLeft: 'auto', fontSize: 11, fontWeight: 600,
                color: tokens.tokens_per_min > 500 ? 'var(--red)' : 'var(--text-muted)',
              }}>
                {tokens.tokens_per_min} tok/min
              </span>
            )}
          </div>
          <div style={s.grid}>
            <div style={s.card}>
              <div style={s.label}>Total Tokens</div>
              <div style={{ ...s.value, color: 'var(--accent-light)' }}>
                {fmtTokens(tokens.total_tokens)}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {fmtTokens(tokens.total_prompt_tokens)} in / {fmtTokens(tokens.total_completion_tokens)} out
              </div>
            </div>
            <div style={s.card}>
              <div style={s.label}>LLM Calls</div>
              <div style={{ ...s.value, color: 'var(--teal)' }}>
                {tokens.call_count || 0}
              </div>
            </div>
            <div style={s.card}>
              <div style={s.label}>Est. Cost</div>
              <div style={{
                ...s.value,
                color: (tokens.total_cost_usd || 0) > 1 ? 'var(--red)' : 'var(--green)',
              }}>
                {fmtCost(tokens.total_cost_usd)}
              </div>
            </div>
            <div style={s.card}>
              <div style={s.label}>Last Hour</div>
              <div style={{ ...s.valueSm, color: 'var(--accent-light)' }}>
                {fmtTokens(tokens.tokens_1h)} tok
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {tokens.calls_1h || 0} calls &middot; {fmtCost(tokens.cost_1h)}
              </div>
            </div>
          </div>

          {/* Prompt vs Completion bar */}
          {(tokens.total_tokens || 0) > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginBottom: 2 }}>
                <span>Prompt ({Math.round((tokens.total_prompt_tokens / tokens.total_tokens) * 100)}%)</span>
                <span>Completion ({Math.round((tokens.total_completion_tokens / tokens.total_tokens) * 100)}%)</span>
              </div>
              <div style={{ height: 6, borderRadius: 3, background: 'var(--bg-primary)', overflow: 'hidden', display: 'flex' }}>
                <div style={{
                  height: '100%',
                  width: `${(tokens.total_prompt_tokens / tokens.total_tokens) * 100}%`,
                  background: 'var(--accent)',
                  transition: 'width .3s',
                }} />
                <div style={{
                  height: '100%',
                  flex: 1,
                  background: 'var(--teal)',
                  transition: 'width .3s',
                }} />
              </div>
            </div>
          )}

          {/* Per-model breakdown */}
          {tokens.by_model && Object.keys(tokens.by_model).length > 0 && (
            <div style={{ padding: '0 16px 12px' }}>
              <div style={{ ...s.label, marginBottom: 6 }}>By Model</div>
              {Object.entries(tokens.by_model)
                .sort((a, b) => b[1].total - a[1].total)
                .map(([name, data]) => (
                  <div key={name} style={s.modelRow}>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text)' }}>
                      {name}
                    </span>
                    <span style={{ display: 'flex', gap: 12, fontSize: 11 }}>
                      <span style={{ color: 'var(--accent-light)' }}>{fmtTokens(data.total)}</span>
                      <span style={{ color: 'var(--text-muted)' }}>{data.calls} calls</span>
                      {data.cost > 0 && (
                        <span style={{ color: 'var(--green)' }}>{fmtCost(data.cost)}</span>
                      )}
                    </span>
                  </div>
                ))}
            </div>
          )}
        </div>

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
