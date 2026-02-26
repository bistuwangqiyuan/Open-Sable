import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Play, Send, Loader, CheckCircle, XCircle, AlertTriangle,
  ChevronRight, Eye, Brain, Cog, MessageSquare, Lightbulb,
  ArrowRight, Sparkles, FileText, Globe, Code, Folder,
} from 'lucide-react';

const s = {
  panel: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  /* ── Launcher (home) ── */
  launcher: {
    flex: 1, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', padding: 32, gap: 24,
    overflowY: 'auto',
  },
  heroTitle: {
    fontSize: 26, fontWeight: 800, textAlign: 'center',
    background: 'linear-gradient(135deg, var(--accent-light), var(--teal))',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
  },
  heroSub: {
    fontSize: 13, color: 'var(--text-muted)', textAlign: 'center', maxWidth: 500,
    lineHeight: 1.6,
  },
  inputWrap: {
    width: '100%', maxWidth: 600, position: 'relative',
  },
  input: {
    width: '100%', padding: '14px 50px 14px 18px', borderRadius: 12,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    color: 'var(--text)', fontSize: 14, outline: 'none',
    transition: 'border-color .15s',
  },
  sendBtn: {
    position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
    width: 36, height: 36, borderRadius: 8, border: 'none',
    background: 'var(--accent)', color: '#fff', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  examples: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
    gap: 10, width: '100%', maxWidth: 600,
  },
  exampleCard: {
    padding: '14px 16px', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    cursor: 'pointer', transition: 'border-color .15s, background .15s',
    display: 'flex', gap: 10, alignItems: 'flex-start',
  },
  exampleIcon: {
    width: 32, height: 32, borderRadius: 8,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 16, flexShrink: 0, background: 'var(--accent-dim)',
  },
  exampleTitle: { fontSize: 12, fontWeight: 700, marginBottom: 2 },
  exampleDesc: { fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.3 },

  /* ── Execution view ── */
  execHeader: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  execBody: { flex: 1, overflowY: 'auto', padding: 16 },
  thoughtStream: { marginBottom: 16 },
  thought: (type) => ({
    display: 'flex', gap: 10, padding: '8px 12px', marginBottom: 4,
    borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.5,
    background: type === 'observation' ? 'rgba(34,197,94,.06)' :
                type === 'reasoning'   ? 'rgba(139,92,246,.06)' :
                type === 'decision'    ? 'rgba(245,158,11,.06)' :
                type === 'action'      ? 'rgba(59,130,246,.06)' :
                type === 'error'       ? 'rgba(239,68,68,.06)' :
                'var(--bg-tertiary)',
    border: `1px solid ${
      type === 'observation' ? 'rgba(34,197,94,.15)' :
      type === 'reasoning'   ? 'rgba(139,92,246,.15)' :
      type === 'decision'    ? 'rgba(245,158,11,.15)' :
      type === 'action'      ? 'rgba(59,130,246,.15)' :
      type === 'error'       ? 'rgba(239,68,68,.15)' :
      'var(--border)'
    }`,
  }),
  thoughtIcon: (type) => ({
    width: 22, height: 22, borderRadius: 6, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: type === 'observation' ? 'var(--green)' :
           type === 'reasoning'   ? 'var(--accent-light)' :
           type === 'decision'    ? 'var(--yellow)' :
           type === 'action'      ? 'var(--teal)' :
           type === 'error'       ? 'var(--red)' : 'var(--text-muted)',
  }),
  permission: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
    background: 'rgba(245,158,11,.08)', border: '1px solid rgba(245,158,11,.2)',
    borderRadius: 'var(--radius)', marginBottom: 8,
  },
  permBtn: (approve) => ({
    padding: '6px 14px', borderRadius: 'var(--radius-sm)', border: 'none',
    cursor: 'pointer', fontSize: 11, fontWeight: 700,
    background: approve ? 'var(--green)' : 'var(--red)',
    color: '#fff',
  }),
  backBtn: {
    padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
    background: 'var(--bg-hover)', color: 'var(--text-secondary)',
    cursor: 'pointer', fontSize: 11, fontWeight: 600,
    display: 'flex', alignItems: 'center', gap: 4,
  },
  statusBadge: (status) => ({
    padding: '3px 10px', borderRadius: 99, fontSize: 10, fontWeight: 700,
    background: status === 'running' ? 'rgba(59,130,246,.15)' :
                status === 'complete' ? 'rgba(34,197,94,.15)' :
                status === 'error'   ? 'rgba(239,68,68,.15)' :
                'var(--bg-hover)',
    color: status === 'running' ? 'var(--teal)' :
           status === 'complete' ? 'var(--green)' :
           status === 'error'   ? 'var(--red)' :
           'var(--text-muted)',
  }),
};

const EXAMPLES = [
  { icon: '📁', title: 'Organize Files', desc: 'Sort my Downloads folder by file type', prompt: 'Organize my ~/Downloads folder by file type into subfolders' },
  { icon: '📝', title: 'Summarize Document', desc: 'Create a summary of a long document', prompt: 'Summarize the most recent document in my ~/Documents folder' },
  { icon: '🔍', title: 'Research Topic', desc: 'Deep-dive research on any subject', prompt: 'Research the latest developments in AI agents and give me a comprehensive summary' },
  { icon: '💻', title: 'Code Review', desc: 'Review and improve code quality', prompt: 'Review the staged git changes in my current project and provide feedback' },
  { icon: '🌐', title: 'Web Scraping', desc: 'Extract data from websites', prompt: 'Scrape the top stories from Hacker News and summarize them' },
  { icon: '📊', title: 'Data Analysis', desc: 'Analyze CSV or JSON data', prompt: 'Analyze the data in my most recent CSV file and create a summary report' },
];

const THOUGHT_ICONS = {
  observation: Eye,
  reasoning: Brain,
  decision: Lightbulb,
  action: Cog,
  error: XCircle,
  info: MessageSquare,
};

export default function TaskPanel({ streaming, messages, activity, sendMessage }) {
  const [view, setView] = useState('launcher'); // launcher | executing
  const [taskPrompt, setTaskPrompt] = useState('');
  const [thoughts, setThoughts] = useState([]);
  const [taskStatus, setTaskStatus] = useState('idle'); // idle | running | complete | error
  const bottomRef = useRef(null);

  // Convert activity items into thought stream
  useEffect(() => {
    if (!activity?.length) return;
    const latest = activity[0]; // activity is reverse-chronological
    if (!latest) return;

    const typeMap = {
      'think': 'reasoning',
      'tool': 'action',
      'success': 'observation',
      'error': 'error',
      'info': 'info',
    };

    const thoughtType = typeMap[latest.type] || 'info';
    const newThought = {
      id: latest.id,
      type: thoughtType,
      icon: latest.icon,
      title: latest.title,
      detail: latest.detail,
      ts: latest.ts,
    };

    setThoughts(prev => {
      if (prev.some(t => t.id === newThought.id)) return prev;
      return [...prev, newThought].slice(-100);
    });
  }, [activity]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [thoughts]);

  // Track task status from streaming state
  useEffect(() => {
    if (view === 'executing') {
      if (streaming) setTaskStatus('running');
      else if (taskStatus === 'running') setTaskStatus('complete');
    }
  }, [streaming, view, taskStatus]);

  const launchTask = useCallback((prompt) => {
    if (!prompt?.trim()) return;
    setView('executing');
    setThoughts([]);
    setTaskStatus('running');
    sendMessage(prompt);
  }, [sendMessage]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (taskPrompt.trim()) {
      launchTask(taskPrompt);
      setTaskPrompt('');
    }
  };

  const goBack = () => {
    setView('launcher');
    setTaskStatus('idle');
    setThoughts([]);
  };

  const ThoughtIcon = (type) => THOUGHT_ICONS[type] || MessageSquare;

  // ── Launcher View ──
  if (view === 'launcher') {
    return (
      <div style={s.panel}>
        <div style={s.launcher}>
          <div>
            <Sparkles size={40} style={{ color: 'var(--accent-light)', marginBottom: 8 }} />
          </div>
          <div style={s.heroTitle}>What can I help you with?</div>
          <div style={s.heroSub}>
            Launch a task and watch the agent work. Sable can organize files, research topics,
            write documents, review code, scrape websites, and much more.
          </div>

          <form onSubmit={handleSubmit} style={s.inputWrap}>
            <input
              style={s.input}
              value={taskPrompt}
              onChange={(e) => setTaskPrompt(e.target.value)}
              placeholder="Describe a task for the agent…"
              autoFocus
            />
            <button type="submit" style={s.sendBtn} title="Launch Task">
              <Play size={16} />
            </button>
          </form>

          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)' }}>
            Try these examples
          </div>
          <div style={s.examples}>
            {EXAMPLES.map((ex, i) => (
              <div
                key={i}
                style={s.exampleCard}
                onClick={() => launchTask(ex.prompt)}
              >
                <div style={s.exampleIcon}>{ex.icon}</div>
                <div>
                  <div style={s.exampleTitle}>{ex.title}</div>
                  <div style={s.exampleDesc}>{ex.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // ── Execution View ──
  return (
    <div style={s.panel}>
      <div style={s.execHeader}>
        <button style={s.backBtn} onClick={goBack}>
          ← Back
        </button>
        <span style={{ fontSize: 14, fontWeight: 700, flex: 1 }}>Task Execution</span>
        <span style={s.statusBadge(taskStatus)}>
          {taskStatus === 'running' && <><Loader size={10} style={{ animation: 'spin 1s linear infinite', marginRight: 4 }} /> Running</>}
          {taskStatus === 'complete' && <><CheckCircle size={10} style={{ marginRight: 4 }} /> Complete</>}
          {taskStatus === 'error' && <><XCircle size={10} style={{ marginRight: 4 }} /> Error</>}
          {taskStatus === 'idle' && 'Idle'}
        </span>
      </div>

      <div style={s.execBody}>
        {/* Thought Stream */}
        <div style={s.thoughtStream}>
          {thoughts.map(t => {
            const Icon = ThoughtIcon(t.type);
            return (
              <div key={t.id} style={s.thought(t.type)}>
                <div style={s.thoughtIcon(t.type)}>
                  <Icon size={14} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, marginBottom: 2 }}>
                    {t.icon} {t.title}
                  </div>
                  {t.detail && (
                    <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
                      {t.detail}
                    </div>
                  )}
                </div>
                <span style={{ fontSize: 10, color: 'var(--text-muted)', flexShrink: 0 }}>
                  {t.ts ? new Date(t.ts * 1000).toLocaleTimeString() : ''}
                </span>
              </div>
            );
          })}

          {taskStatus === 'running' && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
              color: 'var(--text-muted)', fontSize: 12,
            }}>
              <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} />
              Agent is working…
            </div>
          )}

          {taskStatus === 'complete' && messages.length > 0 && (
            <div style={{
              marginTop: 16, padding: 16, borderRadius: 'var(--radius)',
              border: '1px solid rgba(34,197,94,.2)', background: 'rgba(34,197,94,.04)',
            }}>
              <div style={{
                fontSize: 12, fontWeight: 700, color: 'var(--green)',
                marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <CheckCircle size={14} /> Task Complete
              </div>
              <div style={{
                fontSize: 13, color: 'var(--text)', lineHeight: 1.6,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word',
              }}>
                {messages[messages.length - 1]?.content?.slice(0, 2000) || 'Done.'}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
