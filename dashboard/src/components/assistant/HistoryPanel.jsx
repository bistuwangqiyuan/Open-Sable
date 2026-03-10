import { useState, useEffect } from 'react';
import {
  Clock, CheckCircle, XCircle, MessageSquare, Search,
  ChevronDown, Trash2, RotateCcw, ExternalLink,
} from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 16 },
  searchBar: {
    display: 'flex', gap: 8, marginBottom: 16,
  },
  searchInput: {
    flex: 1, padding: '8px 12px 8px 36px', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', background: 'var(--bg-primary)',
    color: 'var(--text)', fontSize: 12, outline: 'none',
  },
  filterBtn: (active) => ({
    padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
    background: active ? 'var(--accent-dim)' : 'var(--bg-hover)',
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    cursor: 'pointer', fontSize: 11, fontWeight: 600,
  }),
  card: {
    padding: '14px 16px', borderRadius: 'var(--radius)', marginBottom: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    cursor: 'pointer', transition: 'border-color .15s',
  },
  cardHeader: {
    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
  },
  statusDot: (status) => ({
    width: 8, height: 8, borderRadius: '50%',
    background: status === 'complete' ? 'var(--green)' :
                status === 'error'    ? 'var(--red)' :
                status === 'running'  ? 'var(--teal)' :
                'var(--text-muted)',
    flexShrink: 0,
  }),
  cardTitle: { fontSize: 14, fontWeight: 700, flex: 1 },
  cardTime: { fontSize: 10, color: 'var(--text-muted)' },
  cardBody: { fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 },
  cardMeta: {
    display: 'flex', gap: 12, marginTop: 8, fontSize: 10, color: 'var(--text-muted)',
  },
  badge: (color) => ({
    padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
    background: color === 'green' ? 'rgba(34,197,94,.15)' :
                color === 'red'   ? 'rgba(239,68,68,.15)' :
                color === 'blue'  ? 'rgba(59,130,246,.15)' :
                'var(--bg-hover)',
    color: color === 'green' ? 'var(--green)' :
           color === 'red'   ? 'var(--red)' :
           color === 'blue'  ? 'var(--teal)' :
           'var(--text-muted)',
  }),
  empty: {
    padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13,
  },
  detail: {
    padding: 16, background: 'var(--bg-tertiary)', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)',
  },
  detailContent: {
    fontSize: 13, color: 'var(--text)', lineHeight: 1.6,
    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    maxHeight: 300, overflowY: 'auto',
  },
};

function relativeTime(ts) {
  const now = Date.now();
  const diff = now - ts;
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return new Date(ts).toLocaleDateString();
}

export default function HistoryPanel({ messages, sessions, onLoadSession }) {
  const [filter, setFilter] = useState('all'); // all | complete | error
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const [history, setHistory] = useState([]);

  // Build task history from sessions + messages
  useEffect(() => {
    const tasks = [];

    // From sessions (if available from gateway)
    if (sessions?.length) {
      sessions.forEach(sess => {
        tasks.push({
          id: sess.session_id || sess.id,
          title: sess.title || sess.session_id || 'Session',
          prompt: sess.last_message || '',
          status: 'complete',
          result: sess.last_response || '',
          tools: sess.tool_count || 0,
          rounds: sess.rounds || 0,
          duration: sess.duration_ms || 0,
          ts: sess.updated_at ? new Date(sess.updated_at).getTime() : Date.now(),
        });
      });
    }

    // From current session messages
    let currentTask = null;
    messages?.forEach(msg => {
      if (msg.role === 'user') {
        currentTask = {
          id: 'msg_' + msg.ts,
          title: msg.content?.slice(0, 80) || 'Task',
          prompt: msg.content || '',
          status: 'complete',
          result: '',
          tools: 0,
          rounds: 1,
          duration: 0,
          ts: msg.ts,
        };
      } else if (msg.role === 'assistant' && currentTask) {
        currentTask.result = msg.content?.slice(0, 500) || '';
        currentTask.duration = msg.ts - currentTask.ts;
        if (msg.content?.startsWith('⚠️')) currentTask.status = 'error';
        tasks.push(currentTask);
        currentTask = null;
      }
    });

    // Sort newest first, deduplicate
    tasks.sort((a, b) => b.ts - a.ts);
    const seen = new Set();
    const unique = tasks.filter(t => {
      if (seen.has(t.id)) return false;
      seen.add(t.id);
      return true;
    });
    setHistory(unique);
  }, [messages, sessions]);

  const filtered = history.filter(task => {
    if (filter !== 'all' && task.status !== filter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      return task.title.toLowerCase().includes(q) || task.prompt.toLowerCase().includes(q);
    }
    return true;
  });

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>📋</span>
        <span style={s.title}>Task History</span>
        <span style={{
          marginLeft: 8, fontSize: 11, color: 'var(--text-muted)',
          background: 'var(--bg-hover)', padding: '2px 8px', borderRadius: 99,
        }}>
          {history.length} tasks
        </span>
      </div>

      <div style={s.body}>
        {/* Search & Filter */}
        <div style={s.searchBar}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              style={s.searchInput}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search task history…"
            />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
          {['all', 'complete', 'error'].map(f => (
            <button key={f} style={s.filterBtn(filter === f)} onClick={() => setFilter(f)}>
              {f === 'all' ? 'All' : f === 'complete' ? '✅ Complete' : '❌ Error'}
            </button>
          ))}
        </div>

        {/* Selected task detail */}
        {selected && (
          <div style={{ marginBottom: 16 }}>
            <button
              style={{ ...s.filterBtn(false), marginBottom: 8 }}
              onClick={() => setSelected(null)}
            >
              ← Back to list
            </button>
            <div style={s.detail}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <div style={s.statusDot(selected.status)} />
                <span style={{ fontSize: 15, fontWeight: 800 }}>{selected.title}</span>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12, fontStyle: 'italic' }}>
                "{selected.prompt}"
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
                Response:
              </div>
              <div style={s.detailContent}>
                {selected.result || 'No response recorded.'}
              </div>
              <div style={s.cardMeta}>
                <span>🔧 {selected.tools} tools</span>
                <span>🔄 {selected.rounds} rounds</span>
                <span>⏱️ {typeof selected.duration === 'number' && selected.duration > 1000 ? `${(selected.duration / 1000).toFixed(1)}s` : `${selected.duration}ms`}</span>
                <span>🕐 {relativeTime(selected.ts)}</span>
              </div>
              {onLoadSession && (
                <button
                  style={{
                    marginTop: 12, padding: '8px 16px', borderRadius: 'var(--radius)',
                    border: 'none', background: 'var(--accent)', color: 'white',
                    fontWeight: 600, fontSize: 12, cursor: 'pointer', width: '100%',
                  }}
                  onClick={() => onLoadSession(selected.id)}
                >
                  💬 Continue this chat
                </button>
              )}
            </div>
          </div>
        )}

        {/* Task list */}
        {!selected && (
          filtered.length === 0 ? (
            <div style={s.empty}>
              <Clock size={32} style={{ opacity: .3, marginBottom: 8 }} />
              <div>No tasks yet</div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                Tasks executed from the Task Launcher will appear here
              </div>
            </div>
          ) : (
            filtered.map(task => (
              <div
                key={task.id}
                style={s.card}
                onClick={() => setSelected(task)}
              >
                <div style={s.cardHeader}>
                  <div style={s.statusDot(task.status)} />
                  <span style={s.cardTitle}>{task.title}</span>
                  <span style={s.cardTime}>{relativeTime(task.ts)}</span>
                </div>
                {task.result && (
                  <div style={s.cardBody}>
                    {task.result.slice(0, 150)}{task.result.length > 150 ? '…' : ''}
                  </div>
                )}
                <div style={s.cardMeta}>
                  <span style={s.badge(task.status === 'complete' ? 'green' : task.status === 'error' ? 'red' : 'blue')}>
                    {task.status}
                  </span>
                  {task.tools > 0 && <span>🔧 {task.tools} tools</span>}
                  {task.rounds > 0 && <span>🔄 {task.rounds} rounds</span>}
                </div>
              </div>
            ))
          )
        )}
      </div>
    </div>
  );
}
