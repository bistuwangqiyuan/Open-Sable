import { useRef, useEffect } from 'react';
import { Trash2 } from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  meta: { marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' },
  body: {
    flex: 1, overflowY: 'auto', padding: '12px 16px',
    fontFamily: 'var(--mono)', fontSize: 12, lineHeight: 1.7,
    color: 'var(--green)', background: 'var(--bg-primary)',
  },
  clearBtn: { background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 },
};

const lineColor = { error: 'var(--red)', info: 'var(--text-muted)', cmd: 'var(--teal)' };

export default function TerminalPanel({ terminal, onClear }) {
  const endRef = useRef(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [terminal]);

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>🖥️</span>
        <span style={s.title}>Terminal / Logs</span>
        <span style={s.meta}>{terminal.length} lines</span>
        <button onClick={onClear} style={s.clearBtn} title="Clear">
          <Trash2 size={14} />
        </button>
      </div>
      <div style={s.body}>
        {terminal.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--mono)', fontSize: 12 }}>
            $ waiting for agent activity…
          </div>
        ) : (
          terminal.map((l, i) => (
            <div key={i} style={{
              whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              color: lineColor[l.cls] || 'var(--green)',
            }}>
              {l.text}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
