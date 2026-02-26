import { useState, useRef, useEffect } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { fmtTime } from '../../lib/utils';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600, color: 'var(--text)' },
  meta: { marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' },
  messages: { flex: 1, overflowY: 'auto', padding: 16 },
  empty: {
    display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%',
    flexDirection: 'column', gap: 12,
  },
  msg: (user) => ({
    marginBottom: 16, display: 'flex', gap: 10,
    flexDirection: user ? 'row-reverse' : 'row',
  }),
  avatar: (user) => ({
    width: 32, height: 32, borderRadius: 'var(--radius-sm)', flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14,
    background: user ? 'var(--accent-dim)' : 'var(--teal-dim)',
    color: user ? 'var(--accent-light)' : 'var(--teal)',
  }),
  bubble: (user) => ({
    maxWidth: '80%', padding: '10px 14px', borderRadius: 'var(--radius)',
    fontSize: 13.5, lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    ...(user
      ? { background: 'var(--accent)', color: 'white', borderBottomRightRadius: 4 }
      : { background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderBottomLeftRadius: 4 }),
  }),
  time: (user) => ({
    fontSize: 10, color: 'var(--text-muted)', marginTop: 4,
    textAlign: user ? 'right' : 'left',
  }),
  inputArea: {
    padding: '12px 16px', borderTop: '1px solid var(--border)',
    background: 'var(--bg-secondary)', flexShrink: 0,
  },
  row: { display: 'flex', gap: 8 },
  input: {
    flex: 1, padding: '10px 14px', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    color: 'var(--text)', fontFamily: 'var(--sans)', fontSize: 13.5,
    outline: 'none', resize: 'none',
  },
  sendBtn: {
    padding: '0 18px', borderRadius: 'var(--radius)', border: 'none',
    background: 'var(--accent)', color: 'white', fontWeight: 600, fontSize: 13,
    cursor: 'pointer', display: 'flex', alignItems: 'center',
  },
  clearBtn: {
    background: 'none', border: 'none', color: 'var(--text-muted)',
    cursor: 'pointer', padding: 4,
  },
};

export default function ChatPanel({ messages, streaming, onSend, onClear }) {
  const [input, setInput] = useState('');
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    onSend(text);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div style={s.panel}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>💬</span>
        <span style={s.title}>Chat</span>
        <span style={s.meta}>{messages.length} messages</span>
        <button onClick={onClear} style={s.clearBtn} title="Clear chat">
          <Trash2 size={14} />
        </button>
      </div>

      <div style={s.messages}>
        {messages.length === 0 ? (
          <div style={s.empty}>
            <div style={{ fontSize: 48, opacity: .3 }}>🤖</div>
            <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>Send a message to start chatting</p>
            <p style={{ color: 'var(--text-muted)', fontSize: 11 }}>Use /help for available commands</p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} style={s.msg(m.role === 'user')}>
              <div style={s.avatar(m.role === 'user')}>
                {m.role === 'user' ? '👤' : '🤖'}
              </div>
              <div>
                <div style={s.bubble(m.role === 'user')}>
                  {m.content}
                  {m._streaming && (
                    <span className="typing-dots" style={{ marginLeft: 6 }}>
                      <span>●</span><span>●</span><span>●</span>
                    </span>
                  )}
                </div>
                <div style={s.time(m.role === 'user')}>{fmtTime(m.ts)}</div>
              </div>
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>

      <div style={s.inputArea}>
        <form onSubmit={handleSubmit}>
          <div style={s.row}>
            <textarea
              style={s.input}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message… (/ for commands, Shift+Enter for newline)"
              disabled={streaming}
              rows={1}
            />
            <button
              type="submit"
              style={{ ...s.sendBtn, opacity: streaming || !input.trim() ? 0.5 : 1 }}
              disabled={streaming || !input.trim()}
            >
              <Send size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
