import { useRef, useEffect } from 'react';
import { Trash2 } from 'lucide-react';
import { fmtTime } from '../../lib/utils';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  meta: { marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' },
  body: { flex: 1, overflowY: 'auto', padding: 0 },
  item: {
    padding: '10px 16px', borderBottom: '1px solid var(--border)',
    fontSize: 12.5, display: 'flex', gap: 10, alignItems: 'flex-start',
    transition: 'background .1s', cursor: 'default',
  },
  icon: (type) => ({
    width: 28, height: 28, borderRadius: 'var(--radius-sm)', flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
    background: { tool: 'var(--accent-dim)', think: 'var(--yellow-dim)',
                   success: 'var(--green-dim)', error: 'var(--red-dim)',
                   info: 'var(--teal-dim)' }[type] || 'var(--teal-dim)',
    color: { tool: 'var(--accent-light)', think: 'var(--yellow)',
             success: 'var(--green)', error: 'var(--red)',
             info: 'var(--teal)' }[type] || 'var(--teal)',
  }),
  itemTitle: { fontWeight: 600, color: 'var(--text)', marginBottom: 2 },
  detail: {
    color: 'var(--text-muted)', fontSize: 11.5, lineHeight: 1.5,
    overflow: 'hidden', textOverflow: 'ellipsis',
  },
  time: { fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', flexShrink: 0, marginTop: 2 },
  clearBtn: { background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 },
};

export default function ActivityPanel({ activity, onClear }) {
  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>⚡</span>
        <span style={s.title}>Activity</span>
        <span style={s.meta}>{activity.length} events</span>
        <button onClick={onClear} style={s.clearBtn} title="Clear">
          <Trash2 size={14} />
        </button>
      </div>
      <div style={s.body}>
        {activity.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            No activity yet. Send a message to see real-time agent events.
          </div>
        ) : (
          activity.map(a => (
            <div key={a.id} style={s.item}>
              <div style={s.icon(a.type)}>{a.icon}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={s.itemTitle}>{a.title}</div>
                {a.detail && <div style={s.detail}>{a.detail}</div>}
              </div>
              <div style={s.time}>{fmtTime(a.ts)}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
