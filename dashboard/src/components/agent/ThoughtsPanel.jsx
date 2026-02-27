import { useState, useEffect, useRef, useCallback } from 'react';
import { RefreshCw, Filter, Brain, Heart, MessageCircle, Zap, AlertTriangle, TrendingUp, Eye, BookOpen } from 'lucide-react';
import { fmtTime } from '../../lib/utils';

// ── Event type config ────────────────────────────────────────────────
const EVENT_META = {
  thought:      { icon: '💭', color: 'var(--accent)',  label: 'Thought' },
  felt:         { icon: '💗', color: 'var(--pink, #ec4899)', label: 'Emotion' },
  posted:       { icon: '📝', color: 'var(--green)',   label: 'Posted' },
  engaged:      { icon: '🤝', color: 'var(--teal)',    label: 'Engaged' },
  reflection:   { icon: '🪞', color: 'var(--yellow)',  label: 'Reflection' },
  error:        { icon: '⚠️', color: 'var(--red)',     label: 'Error' },
  self_healed:  { icon: '🩺', color: 'var(--orange, #f59e0b)', label: 'Self-Heal' },
  trend_joined: { icon: '📈', color: 'var(--blue, #3b82f6)',  label: 'Trend' },
};

const TABS = [
  { id: 'stream',      label: 'Stream',      icon: Zap },
  { id: 'thoughts',    label: 'Thoughts',    icon: Brain },
  { id: 'emotions',    label: 'Emotions',    icon: Heart },
  { id: 'reflections', label: 'Reflections', icon: BookOpen },
  { id: 'decisions',   label: 'Decisions',   icon: Eye },
];

const FILTER_TYPES = ['all', 'thought', 'felt', 'posted', 'engaged', 'reflection', 'error', 'self_healed', 'trend_joined'];

// ── Styles ───────────────────────────────────────────────────────────
const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', background: 'var(--bg-primary)' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  meta: { marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)', display: 'flex', gap: 8, alignItems: 'center' },
  tabBar: {
    display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
    padding: '0 12px', flexShrink: 0, overflowX: 'auto',
  },
  tab: (active) => ({
    padding: '8px 14px', fontSize: 12, fontWeight: active ? 600 : 400,
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
    background: 'none', border: 'none', cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
    transition: 'all .15s',
  }),
  moodBar: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
    background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border)',
    flexShrink: 0, fontSize: 12,
  },
  moodBadge: (intensity) => ({
    padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
    background: `rgba(168,85,247,${0.15 + intensity * 0.3})`,
    color: 'var(--accent-light)',
    border: '1px solid rgba(168,85,247,0.3)',
  }),
  intensityBar: {
    width: 80, height: 6, borderRadius: 3, background: 'var(--bg-tertiary, var(--border))',
    overflow: 'hidden', position: 'relative',
  },
  intensityFill: (v) => ({
    width: `${(v * 100).toFixed(0)}%`, height: '100%',
    borderRadius: 3,
    background: v > 0.7 ? 'var(--red)' : v > 0.4 ? 'var(--yellow)' : 'var(--green)',
    transition: 'width .5s ease',
  }),
  body: { flex: 1, overflowY: 'auto', padding: 0 },
  filterRow: {
    display: 'flex', gap: 4, padding: '8px 16px', flexWrap: 'wrap',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  filterBtn: (active) => ({
    padding: '3px 10px', borderRadius: 12, fontSize: 10.5, fontWeight: active ? 600 : 400,
    background: active ? 'var(--accent-dim)' : 'transparent',
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    cursor: 'pointer', textTransform: 'capitalize',
  }),
  entry: {
    padding: '12px 16px', borderBottom: '1px solid var(--border)',
    fontSize: 12.5, transition: 'background .1s',
  },
  entryHeader: {
    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
  },
  typeIcon: (color) => ({
    width: 26, height: 26, borderRadius: 6, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
    background: `${color}22`, border: `1px solid ${color}44`,
  }),
  entryType: { fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' },
  entryTime: { fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto' },
  entryContent: {
    color: 'var(--text)', lineHeight: 1.65, fontSize: 12.5,
    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    maxHeight: 300, overflow: 'auto',
    padding: '8px 12px', borderRadius: 6,
    background: 'var(--bg-secondary)',
  },
  thoughtFull: {
    color: 'var(--text)', lineHeight: 1.7, fontSize: 13,
    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    padding: '16px', background: 'var(--bg-secondary)',
    borderRadius: 8, margin: '8px 16px',
    border: '1px solid var(--border)',
    maxHeight: 500, overflow: 'auto',
  },
  reflectionCard: {
    margin: '8px 16px', padding: '16px', borderRadius: 8,
    background: 'var(--bg-secondary)', border: '1px solid var(--border)',
  },
  reflectionTitle: { fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text)' },
  reflectionBody: {
    fontSize: 12.5, lineHeight: 1.7, color: 'var(--text-muted)',
    whiteSpace: 'pre-wrap', maxHeight: 400, overflow: 'auto',
  },
  empty: {
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    height: '100%', color: 'var(--text-muted)', gap: 8, fontSize: 13,
  },
  refreshBtn: {
    background: 'none', border: 'none', color: 'var(--text-muted)',
    cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center',
  },
  emotionChip: (color) => ({
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '2px 8px', borderRadius: 10, fontSize: 11,
    background: `${color}22`, color: color, marginRight: 4, marginBottom: 4,
  }),
};

// ── Helper to extract summary from journal entry ──
function summarizeEntry(entry) {
  const data = entry.data || {};
  switch (entry.type) {
    case 'thought':
      return data.thought || '';
    case 'felt':
      return `Mood: ${data.new_mood || data.emotion || '?'} (${(data.intensity ?? '?')}) — ${data.why || ''}`;
    case 'posted':
      return data.tweet || data.text || JSON.stringify(data).slice(0, 200);
    case 'engaged':
      return `${data.action || '?'} @${data.username || '?'} — ${(data.tweet_text || '').slice(0, 120)}`;
    case 'reflection':
      return data.analysis || data.summary || JSON.stringify(data).slice(0, 200);
    case 'error':
      return `[${data.activity || 'unknown'}] ${data.error || JSON.stringify(data).slice(0, 150)}`;
    case 'self_healed':
      return `${data.action || '?'}: ${data.reason || data.error || ''}`;
    case 'trend_joined':
      return `${data.trend || '?'}: ${(data.tweet || '').slice(0, 120)}`;
    default:
      return JSON.stringify(data).slice(0, 200);
  }
}

function fmtDate(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
}

// ── Main Component ───────────────────────────────────────────────────
export default function ThoughtsPanel({ ws, thoughts: data, connected }) {
  const [subTab, setSubTab] = useState('stream');
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const bodyRef = useRef(null);

  const fetchThoughts = useCallback(() => {
    if (!ws?.current || ws.current.readyState !== WebSocket.OPEN) return;
    setLoading(true);
    ws.current.send(JSON.stringify({ type: 'thoughts.list', limit: 500 }));
    setTimeout(() => setLoading(false), 3000);
  }, [ws]);

  // Fetch when panel mounts or when WS connects/reconnects
  useEffect(() => {
    if (connected) fetchThoughts();
  }, [connected, fetchThoughts]);

  // Reset loading when data arrives
  useEffect(() => {
    if (data) setLoading(false);
  }, [data]);

  const journal = data?.journal || [];
  const thoughts = data?.thoughts || [];
  const reflections = data?.reflections || [];
  const mood = data?.mood || {};
  const memStats = data?.memory_stats || {};

  // Filtered + reversed (newest first) journal
  const filteredJournal = (filter === 'all'
    ? journal
    : journal.filter(e => e.type === filter)
  ).slice().reverse();

  // Decisions = posted + engaged + trend_joined (actions the agent took)
  const decisions = journal
    .filter(e => ['posted', 'engaged', 'trend_joined'].includes(e.type))
    .slice()
    .reverse();

  return (
    <div style={s.panel}>
      {/* Header */}
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>🧠</span>
        <span style={s.title}>Agent Consciousness</span>
        <div style={s.meta}>
          <span>{journal.length} events</span>
          <span>•</span>
          <span>{thoughts.length} thoughts</span>
          <span>•</span>
          <span>{reflections.length} reflections</span>
          <button onClick={fetchThoughts} style={s.refreshBtn} title="Refresh">
            <RefreshCw size={14} style={loading ? { animation: 'spin 1s linear infinite' } : {}} />
          </button>
        </div>
      </div>

      {/* Mood bar */}
      {mood.current && mood.current !== 'unknown' && (
        <div style={s.moodBar}>
          <span>💗</span>
          <span style={{ fontWeight: 600 }}>Mood:</span>
          <span style={s.moodBadge(mood.intensity || 0)}>{mood.current}</span>
          <span style={{ color: 'var(--text-muted)' }}>Intensity:</span>
          <div style={s.intensityBar}>
            <div style={s.intensityFill(mood.intensity || 0)} />
          </div>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{((mood.intensity || 0) * 100).toFixed(0)}%</span>
          {memStats.total_memories > 0 && (
            <>
              <span style={{ color: 'var(--border)' }}>|</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {memStats.total_memories} memories
              </span>
            </>
          )}
        </div>
      )}

      {/* Sub-tabs */}
      <div style={s.tabBar}>
        {TABS.map(t => (
          <button key={t.id} style={s.tab(subTab === t.id)} onClick={() => setSubTab(t.id)}>
            <t.icon size={13} />
            {t.label}
            {t.id === 'stream' && <span style={{ opacity: 0.5 }}>({journal.length})</span>}
            {t.id === 'thoughts' && <span style={{ opacity: 0.5 }}>({thoughts.length})</span>}
            {t.id === 'reflections' && <span style={{ opacity: 0.5 }}>({reflections.length})</span>}
          </button>
        ))}
      </div>

      {/* Filter row (only for Stream tab) */}
      {subTab === 'stream' && (
        <div style={s.filterRow}>
          {FILTER_TYPES.map(f => (
            <button key={f} style={s.filterBtn(filter === f)} onClick={() => setFilter(f)}>
              {f === 'all' ? '🔮 All' : `${EVENT_META[f]?.icon || '📌'} ${f}`}
            </button>
          ))}
        </div>
      )}

      {/* Body */}
      <div style={s.body} ref={bodyRef}>
        {subTab === 'stream' && (
          filteredJournal.length === 0 ? (
            <div style={s.empty}>
              <Brain size={32} />
              <span>No events yet</span>
            </div>
          ) : filteredJournal.map((entry, i) => {
            const meta = EVENT_META[entry.type] || { icon: '📌', color: 'var(--text-muted)', label: entry.type };
            const summary = summarizeEntry(entry);
            const isExpanded = expandedIdx === `stream-${i}`;
            return (
              <div key={i} style={s.entry}
                onClick={() => setExpandedIdx(isExpanded ? null : `stream-${i}`)}
              >
                <div style={s.entryHeader}>
                  <div style={s.typeIcon(meta.color)}>
                    <span>{meta.icon}</span>
                  </div>
                  <span style={{ ...s.entryType, color: meta.color }}>{meta.label}</span>
                  <span style={s.entryTime}>{fmtDate(entry.ts)}</span>
                </div>
                <div style={{
                  ...s.entryContent,
                  maxHeight: isExpanded ? 'none' : 80,
                  cursor: 'pointer',
                }}>
                  {summary}
                </div>
              </div>
            );
          })
        )}

        {subTab === 'thoughts' && (
          thoughts.length === 0 ? (
            <div style={s.empty}>
              <Brain size={32} />
              <span>No inner thoughts yet</span>
            </div>
          ) : [...thoughts].reverse().map((t, i) => (
            <div key={i} style={s.thoughtFull}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ fontSize: 16 }}>💭</span>
                <span style={{ fontWeight: 600, fontSize: 13 }}>Thought #{t.n || i + 1}</span>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                  {fmtDate(t.ts)}
                </span>
              </div>
              {t.situation && (
                <div style={{
                  fontSize: 11, color: 'var(--text-muted)', marginBottom: 8,
                  padding: '4px 8px', background: 'var(--bg-primary)', borderRadius: 4,
                }}>
                  Context: {t.situation}
                </div>
              )}
              <div style={{ lineHeight: 1.7, fontSize: 12.5 }}>
                {t.thought}
              </div>
            </div>
          ))
        )}

        {subTab === 'emotions' && (
          <div style={{ padding: 16 }}>
            {/* Current mood */}
            <div style={{
              padding: 16, borderRadius: 8, background: 'var(--bg-secondary)',
              border: '1px solid var(--border)', marginBottom: 16,
            }}>
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>Current Emotional State</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                <span style={{ fontSize: 28 }}>💗</span>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700, textTransform: 'capitalize' }}>
                    {mood.current || 'Unknown'}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Intensity: {((mood.intensity || 0) * 100).toFixed(0)}%
                  </div>
                </div>
              </div>
              <div style={s.intensityBar}>
                <div style={{ ...s.intensityFill(mood.intensity || 0), width: `${((mood.intensity || 0) * 100).toFixed(0)}%` }} />
              </div>
            </div>

            {/* Emotion history from journal */}
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Emotion Timeline</div>
            {journal.filter(e => e.type === 'felt').slice().reverse().map((e, i) => {
              const d = e.data || {};
              return (
                <div key={i} style={{
                  padding: '10px 14px', borderBottom: '1px solid var(--border)',
                  display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: 12,
                }}>
                  <span style={{ fontSize: 16 }}>
                    {(d.intensity || 0) > 0.7 ? '🔥' : (d.intensity || 0) > 0.4 ? '💗' : '🌊'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                      {d.new_mood || d.emotion || '?'}
                      <span style={{
                        fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 6,
                      }}>
                        {((d.intensity || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    {d.why && (
                      <div style={{ color: 'var(--text-muted)', fontSize: 11.5, marginTop: 2 }}>
                        {d.why}
                      </div>
                    )}
                    {d.trigger && (
                      <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2, fontStyle: 'italic' }}>
                        Trigger: {d.trigger.slice(0, 100)}
                      </div>
                    )}
                  </div>
                  <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {fmtDate(e.ts)}
                  </span>
                </div>
              );
            })}
            {journal.filter(e => e.type === 'felt').length === 0 && (
              <div style={s.empty}>
                <Heart size={32} />
                <span>No emotions recorded yet</span>
              </div>
            )}
          </div>
        )}

        {subTab === 'reflections' && (
          reflections.length === 0 ? (
            <div style={s.empty}>
              <BookOpen size={32} />
              <span>No reflections yet</span>
            </div>
          ) : [...reflections].reverse().map((r, i) => (
            <div key={i} style={s.reflectionCard}>
              <div style={s.reflectionTitle}>
                🪞 Reflection — {fmtDate(r.ts)}
              </div>
              <div style={s.reflectionBody}>
                {r.analysis || r.summary || JSON.stringify(r, null, 2)}
              </div>
            </div>
          ))
        )}

        {subTab === 'decisions' && (
          decisions.length === 0 ? (
            <div style={s.empty}>
              <Eye size={32} />
              <span>No decisions recorded yet</span>
            </div>
          ) : decisions.map((entry, i) => {
            const meta = EVENT_META[entry.type] || { icon: '📌', color: 'var(--text-muted)', label: entry.type };
            return (
              <div key={i} style={s.entry}>
                <div style={s.entryHeader}>
                  <div style={s.typeIcon(meta.color)}>
                    <span>{meta.icon}</span>
                  </div>
                  <span style={{ ...s.entryType, color: meta.color }}>{meta.label}</span>
                  <span style={s.entryTime}>{fmtDate(entry.ts)}</span>
                </div>
                <div style={s.entryContent}>
                  {summarizeEntry(entry)}
                </div>
              </div>
            );
          })
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
