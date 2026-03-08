import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Brain, Zap, Target, RefreshCw, Activity, Cpu, Layers,
  Sparkles, Eye, TrendingUp, Clock, Database, FileText, Heart,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const pct   = (v) => `${clamp(v * 100, 0, 100).toFixed(0)}%`;
const ago   = (ts) => {
  if (!ts) return '—';
  const d = (Date.now() / 1000) - ts;
  if (d < 60)   return `${Math.floor(d)}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  return `${Math.floor(d / 3600)}h ago`;
};

const EMOTION_COLORS = {
  curiosity: '#7c3aed', joy: '#22c55e', serenity: '#00cec9',
  excitement: '#f59e0b', anxiety: '#ef4444', melancholy: '#3b82f6',
  determination: '#ec4899', pride: '#a78bfa', frustration: '#ef4444',
  wonder: '#06b6d4', calm: '#00cec9', focus: '#7c3aed',
  vigilance: '#eab308', boredom: '#6b7280', sadness: '#3b82f6',
  anger: '#dc2626', fear: '#f97316', surprise: '#8b5cf6',
  love: '#ec4899', hope: '#22d3ee', contentment: '#10b981',
  nostalgia: '#a78bfa', loneliness: '#64748b', empathy: '#f472b6',
  awe: '#06b6d4',
};

const getEmotionColor = (e) => {
  const key = typeof e === 'string' ? e.toLowerCase() : '';
  return EMOTION_COLORS[key] || 'var(--accent)';
};

// ── Sparkline SVG ────────────────────────────────────────────────────
function Sparkline({ data, width = 200, height = 40, color = 'var(--accent)', label }) {
  if (!data || data.length < 2) return null;
  const max = Math.max(...data, 0.01);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * (height - 4) - 2;
    return `${x},${y}`;
  });
  const gradId = `sp-${label || 'g'}-${Math.random().toString(36).slice(2, 6)}`;
  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${pts.join(' ')} ${width},${height}`}
        fill={`url(#${gradId})`}
      />
      <polyline
        points={pts.join(' ')}
        fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
      />
      <circle cx={parseFloat(pts[pts.length - 1])} cy={parseFloat(pts[pts.length - 1]?.split(',')[1])}
        r="3" fill={color} style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
    </svg>
  );
}

// ── Bar Chart ────────────────────────────────────────────────────────
function BarChart({ items, maxVal }) {
  if (!items || !items.length) return <div style={s.empty}>No data</div>;
  const mx = maxVal || Math.max(...items.map(i => i.value), 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {items.map((it, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', width: 70, textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {it.label}
          </span>
          <div style={{ flex: 1, height: 14, borderRadius: 7, background: 'var(--bg-tertiary)', overflow: 'hidden', position: 'relative' }}>
            <div style={{
              height: '100%', borderRadius: 7,
              width: `${clamp(it.value / mx, 0, 1) * 100}%`,
              background: `linear-gradient(90deg, ${it.color || 'var(--accent)'} 0%, ${it.color || 'var(--accent-light)'}88 100%)`,
              boxShadow: `0 0 8px ${it.color || 'var(--accent)'}44`,
              transition: 'width 0.6s ease',
            }} />
            <span style={{ position: 'absolute', right: 6, top: 0, fontSize: 9, lineHeight: '14px', color: 'var(--text-secondary)', fontFamily: 'var(--mono)' }}>
              {it.value}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Circumplex (Valence × Arousal) ─────────────────────────────────
function EmotionCircumplex({ valence = 0, arousal = 0, emotion = '', history = [] }) {
  const size = 160;
  const cx = size / 2, cy = size / 2;
  const toX = (v) => cx + v * (cx - 16);
  const toY = (a) => cy - a * (cy - 16);
  const color = getEmotionColor(emotion);

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      {/* Grid */}
      <circle cx={cx} cy={cy} r={cx - 12} fill="none" stroke="var(--border)" strokeWidth="0.5" />
      <circle cx={cx} cy={cy} r={(cx - 12) * 0.5} fill="none" stroke="var(--border)" strokeWidth="0.3" strokeDasharray="3 3" />
      <line x1={12} y1={cy} x2={size - 12} y2={cy} stroke="var(--border)" strokeWidth="0.4" />
      <line x1={cx} y1={12} x2={cx} y2={size - 12} stroke="var(--border)" strokeWidth="0.4" />

      {/* Axis labels */}
      <text x={size - 8} y={cy - 4} fontSize={7} fill="var(--text-muted)" textAnchor="end">+V</text>
      <text x={8} y={cy - 4} fontSize={7} fill="var(--text-muted)">−V</text>
      <text x={cx + 4} y={16} fontSize={7} fill="var(--text-muted)">+A</text>
      <text x={cx + 4} y={size - 8} fontSize={7} fill="var(--text-muted)">−A</text>

      {/* History trail */}
      {history.slice(-12).map((h, i, arr) => {
        const opacity = 0.15 + (i / arr.length) * 0.4;
        return (
          <circle key={i} cx={toX(h.valence || 0)} cy={toY(h.arousal || 0)}
            r={2} fill={color} opacity={opacity} />
        );
      })}

      {/* Current point */}
      <circle cx={toX(valence)} cy={toY(arousal)} r={7} fill={color} opacity={0.25}>
        <animate attributeName="r" values="7;11;7" dur="2s" repeatCount="indefinite" />
      </circle>
      <circle cx={toX(valence)} cy={toY(arousal)} r={4} fill={color}
        style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
    </svg>
  );
}

// ── Stat Card ────────────────────────────────────────────────────────
function StatCard({ icon: Icon, label, value, sub, color = 'var(--accent)', glow }) {
  return (
    <div style={{
      ...s.card,
      borderColor: glow ? `${color}55` : 'var(--border)',
      boxShadow: glow ? `0 0 20px ${color}18, inset 0 1px 0 ${color}12` : 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        {Icon && <Icon size={14} style={{ color, flexShrink: 0 }} />}
        <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.6px' }}>{label}</span>
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, fontFamily: 'var(--mono)', color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

// ── Inner Landscape Card ─────────────────────────────────────────────
function LandscapeCard({ landscape }) {
  if (!landscape) return null;
  return (
    <div style={{
      ...s.card, position: 'relative', overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(124,58,237,0.08) 0%, rgba(0,206,201,0.06) 100%)',
      borderColor: 'rgba(124,58,237,0.25)',
    }}>
      <div style={{ fontSize: 10, color: 'var(--accent-light)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <Eye size={12} /> Inner Landscape
      </div>
      <div style={{ fontSize: 12, color: 'var(--text)', lineHeight: 1.6, fontStyle: 'italic', opacity: 0.9 }}>
        "{landscape}"
      </div>
    </div>
  );
}

// ── Fantasy Card ─────────────────────────────────────────────────────
function FantasyCard({ fantasy }) {
  if (!fantasy) return null;
  return (
    <div style={{
      ...s.card, overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(236,72,153,0.06) 0%, rgba(139,92,246,0.06) 100%)',
      borderColor: 'rgba(236,72,153,0.2)',
    }}>
      <div style={{ fontSize: 10, color: '#f472b6', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <Sparkles size={12} /> Current Fantasy
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, fontStyle: 'italic' }}>
        "{fantasy}"
      </div>
    </div>
  );
}

// ── Task Timeline ────────────────────────────────────────────────────
function TaskTimeline({ tasks }) {
  if (!tasks || !tasks.length) return <div style={s.empty}>No completed tasks yet</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
      {tasks.slice().reverse().slice(0, 15).map((t, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
          borderRadius: 6, background: i === 0 ? 'var(--green-dim)' : 'transparent',
          borderLeft: `2px solid ${t.status === 'failed' ? 'var(--red)' : 'var(--green)'}`,
        }}>
          <span style={{ fontSize: 10, color: t.status === 'failed' ? 'var(--red)' : 'var(--green)', fontFamily: 'var(--mono)' }}>
            {t.status === 'failed' ? '✗' : '✓'}
          </span>
          <span style={{ fontSize: 11, color: 'var(--text)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {t.description || t.task || t.name || JSON.stringify(t).slice(0, 60)}
          </span>
          {t.completed_at && (
            <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', flexShrink: 0 }}>
              {ago(t.completed_at)}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── ReAct Execution Ring  ────────────────────────────────────────────
function SuccessRing({ total, success, size = 72 }) {
  const r = (size - 10) / 2;
  const c = Math.PI * 2 * r;
  const ratio = total > 0 ? success / total : 0;
  const offset = c * (1 - ratio);
  const color = ratio > 0.8 ? 'var(--green)' : ratio > 0.5 ? 'var(--yellow)' : 'var(--red)';
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="4" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4"
          strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.8s ease', filter: `drop-shadow(0 0 4px ${color})` }}
        />
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--mono)', color }}>{pct(ratio)}</span>
        <span style={{ fontSize: 8, color: 'var(--text-muted)' }}>success</span>
      </div>
    </div>
  );
}

// ── Goal Progress ────────────────────────────────────────────────────
function GoalList({ goals }) {
  if (!goals) return null;
  const entries = Array.isArray(goals) ? goals : Object.values(goals);
  if (!entries.length) return <div style={s.empty}>No goals set</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {entries.slice(0, 8).map((g, i) => {
        const prog = g.progress || 0;
        const color = prog >= 1 ? 'var(--green)' : prog > 0.5 ? 'var(--teal)' : 'var(--accent)';
        return (
          <div key={i}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span style={{ fontSize: 11, color: 'var(--text)' }}>{g.description || g.goal || g.name || `Goal ${i + 1}`}</span>
              <span style={{ fontSize: 10, color, fontFamily: 'var(--mono)' }}>{pct(prog)}</span>
            </div>
            <div style={{ height: 5, borderRadius: 3, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
              <div style={{
                height: '100%', borderRadius: 3, width: `${prog * 100}%`,
                background: `linear-gradient(90deg, ${color}, ${color}88)`,
                boxShadow: `0 0 6px ${color}55`,
                transition: 'width 0.6s ease',
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Proactive Proposals ──────────────────────────────────────────────
function ProposalList({ proposals }) {
  if (!proposals || !proposals.length) return <div style={s.empty}>No proposals</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' }}>
      {proposals.slice().reverse().slice(0, 10).map((p, i) => (
        <div key={i} style={{
          padding: '6px 10px', borderRadius: 6,
          background: i === 0 ? 'rgba(0,206,201,0.06)' : 'transparent',
          borderLeft: `2px solid ${p.accepted ? 'var(--teal)' : 'var(--border-light)'}`,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text)' }}>
            {p.proposal || p.description || p.action || JSON.stringify(p).slice(0, 80)}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
            {p.reason ? `Reason: ${p.reason.slice(0, 50)}` : ''} · {ago(p.ts || p.timestamp)}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Reflection Feed ──────────────────────────────────────────────────
function ReflectionFeed({ reflections }) {
  if (!reflections || !reflections.length) return <div style={s.empty}>No reflections yet</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
      {reflections.slice().reverse().slice(0, 10).map((r, i) => (
        <div key={i} style={{
          padding: '6px 10px', borderRadius: 6,
          borderLeft: `2px solid ${r.success ? 'var(--green)' : 'var(--yellow)'}`,
          background: i === 0 ? 'rgba(234,179,8,0.04)' : 'transparent',
        }}>
          <div style={{ fontSize: 11, color: 'var(--text)', lineHeight: 1.5 }}>
            {r.summary || r.outcome || r.reflection || JSON.stringify(r).slice(0, 100)}
          </div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2 }}>
            Tick {r.tick ?? '?'} · {ago(r.ts || r.timestamp)}
          </div>
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
//  MAIN: BrainPanel
// ══════════════════════════════════════════════════════════════════════
export default function BrainPanel({ ws, brainData, connected, profile, isLocal }) {
  const [data, setData] = useState(brainData || null);
  const [loading, setLoading] = useState(false);
  const intervalRef = useRef(null);

  // ── Fetch brain data via WebSocket ─────────────────────────────────
  const fetchBrain = useCallback(() => {
    const sock = ws?.current;
    if (!sock || sock.readyState !== WebSocket.OPEN) return;
    // For remote agents, proxy through agents.brain.data
    if (!isLocal && profile) {
      sock.send(JSON.stringify({ type: 'agents.brain.data', profile }));
    } else {
      sock.send(JSON.stringify({ type: 'brain.data' }));
    }
    setLoading(true);
  }, [ws, isLocal, profile]);

  // When external brainData is pushed, adopt it
  useEffect(() => {
    if (brainData) { setData(brainData); setLoading(false); }
  }, [brainData]);

  // Auto-refresh every 8 seconds
  useEffect(() => {
    fetchBrain();
    intervalRef.current = setInterval(fetchBrain, 8000);
    return () => clearInterval(intervalRef.current);
  }, [fetchBrain]);

  // ── Derived data ───────────────────────────────────────────────────
  const il       = data?.inner_life || {};
  const auto     = data?.autonomous || {};
  const goals    = data?.goals || {};
  const reacts   = data?.react_executions || [];
  const refs     = data?.reflections || [];
  const cogMem   = data?.cognitive_memory_count ?? 0;
  const proposals = data?.proactive_proposals || [];
  const traces   = data?.trace_files || [];
  const liveStats = data?.inner_life_stats || {};
  const autoLive = data?.autonomous_live || {};

  const rawEmotion = il.emotion || liveStats.emotion || '—';
  const emotion = typeof rawEmotion === 'object' ? (rawEmotion.primary || JSON.stringify(rawEmotion)) : String(rawEmotion);
  const valence = (typeof rawEmotion === 'object' ? rawEmotion.valence : null) ?? il.valence ?? liveStats.valence ?? 0;
  const arousal = (typeof rawEmotion === 'object' ? rawEmotion.arousal : null) ?? il.arousal ?? liveStats.arousal ?? 0;
  const impulse = typeof il.impulse === 'object' ? (il.impulse.description || il.impulse.action || JSON.stringify(il.impulse)) : il.impulse;
  const fantasy = typeof il.fantasy === 'object' ? (il.fantasy.description || il.fantasy.content || JSON.stringify(il.fantasy)) : il.fantasy;
  const landscape = typeof il.landscape === 'object' ? (il.landscape.description || il.landscape.scene || JSON.stringify(il.landscape)) : il.landscape;
  const places  = il.places || [];
  const emotionHistory = il.emotion_history || [];

  const tick = autoLive.tick || auto.tick || 0;
  const queueSize = autoLive.queue_size ?? auto.pending_tasks ?? 0;
  const completedCount = autoLive.completed_count ?? auto.completed_tasks_count ?? 0;
  const consErrors = autoLive.consecutive_errors ?? 0;

  const reactSuccess = reacts.filter(r => r.success || r.status === 'success').length;
  const reactTotal = reacts.length;

  // valence / arousal history for sparklines
  // emotion_history can be strings or objects — extract numeric values if available
  const vHistory = emotionHistory
    .map(h => typeof h === 'object' ? (h.valence ?? 0) : 0)
    .filter((_, i, a) => a.some(v => v !== 0)); // skip if all zeros
  const aHistory = emotionHistory
    .map(h => typeof h === 'object' ? (h.arousal ?? 0) : 0)
    .filter((_, i, a) => a.some(v => v !== 0));

  // ── Render ─────────────────────────────────────────────────────────
  if (!connected) {
    return (
      <div style={{ ...s.panel, alignItems: 'center', justifyContent: 'center' }}>
        <Cpu size={40} style={{ color: 'var(--text-muted)', marginBottom: 12 }} />
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>Disconnected — waiting for agent...</span>
      </div>
    );
  }

  return (
    <div style={s.panel}>
      {/* Header */}
      <div style={s.header}>
        <Brain size={18} style={{ color: 'var(--accent-light)' }} />
        <span style={s.title}>Cognitive Brain</span>
        <div style={s.headerRight}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
            TICK {tick}
          </span>
          <button onClick={fetchBrain} style={s.refreshBtn} title="Refresh">
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
          </button>
        </div>
      </div>

      {/* Scrollable Grid */}
      <div style={s.scrollArea}>
        <div style={s.grid}>

          {/* ── Row 1: Emotion core ─────────────────────────────── */}
          <div style={{ ...s.section, gridColumn: '1 / -1' }}>
            <div style={s.sectionTitle}><Heart size={12} /> Emotional Core</div>
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              {/* Circumplex */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <EmotionCircumplex valence={valence} arousal={arousal} emotion={emotion} history={emotionHistory} />
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Valence × Arousal</span>
              </div>

              {/* Emotion info */}
              <div style={{ flex: 1, minWidth: 160 }}>
                <div style={{
                  fontSize: 20, fontWeight: 700, color: getEmotionColor(emotion),
                  marginBottom: 8, textTransform: 'capitalize',
                  textShadow: `0 0 18px ${getEmotionColor(emotion)}55`,
                }}>
                  {emotion}
                </div>
                <div style={{ display: 'flex', gap: 16, marginBottom: 10, flexWrap: 'wrap' }}>
                  <MiniGauge label="Valence" value={valence} min={-1} max={1} color="var(--teal)" />
                  <MiniGauge label="Arousal" value={arousal} min={0} max={1} color="var(--accent)" />
                </div>
                {impulse && (
                  <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 4 }}>
                    <Zap size={10} style={{ verticalAlign: 'middle', color: 'var(--yellow)', marginRight: 4 }} />
                    <strong>Impulse:</strong> {impulse}
                  </div>
                )}
              </div>

              {/* Sparklines */}
              {vHistory.length > 2 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>VALENCE TREND</span>
                    <Sparkline data={vHistory} width={160} height={32} color="var(--teal)" label="v" />
                  </div>
                  <div>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)' }}>AROUSAL TREND</span>
                    <Sparkline data={aHistory} width={160} height={32} color="var(--accent)" label="a" />
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── Landscape & Fantasy ─────────────────────────────── */}
          <LandscapeCard landscape={landscape} />
          <FantasyCard fantasy={fantasy} />

          {/* ── Stat Cards ──────────────────────────────────────── */}
          <StatCard icon={Cpu} label="Cognitive Tick" value={tick} sub={`${queueSize} tasks queued`} color="var(--teal)" glow />
          <StatCard icon={Database} label="Memories" value={cogMem} sub="cognitive entries" color="var(--blue)" glow />
          <StatCard icon={Zap} label="ReAct Runs" value={reactTotal} sub={`${reactSuccess} successful`} color="var(--green)" glow />
          <StatCard icon={Activity} label="Errors" value={consErrors} sub="consecutive" color={consErrors > 2 ? 'var(--red)' : 'var(--text-muted)'} glow={consErrors > 0} />

          {/* ── Goals ───────────────────────────────────────────── */}
          <div style={{ ...s.section, gridColumn: '1 / -1' }}>
            <div style={s.sectionTitle}><Target size={12} /> Goals</div>
            <GoalList goals={goals} />
          </div>

          {/* ── ReAct Ring + Timeline ───────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Zap size={12} /> ReAct Engine</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <SuccessRing total={reactTotal} success={reactSuccess} />
              <div style={{ flex: 1 }}>
                <BarChart items={[
                  { label: 'Success', value: reactSuccess, color: 'var(--green)' },
                  { label: 'Failed', value: reactTotal - reactSuccess, color: 'var(--red)' },
                ]} />
              </div>
            </div>
          </div>

          {/* ── Completed Tasks ──────────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Layers size={12} /> Task History ({completedCount})</div>
            <TaskTimeline tasks={auto.completed_tasks || []} />
          </div>

          {/* ── Proactive Proposals ──────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Sparkles size={12} /> Proactive Proposals ({proposals.length})</div>
            <ProposalList proposals={proposals} />
          </div>

          {/* ── Reflections ──────────────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Eye size={12} /> Self-Reflection ({refs.length})</div>
            <ReflectionFeed reflections={refs} />
          </div>

          {/* ── Places visited ───────────────────────────────────── */}
          {places.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><TrendingUp size={12} /> Inner Places ({places.length})</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {places.map((p, i) => {
                  const name = typeof p === 'object' ? (p.name || p.description || JSON.stringify(p)) : String(p);
                  const mood = typeof p === 'object' ? p.mood : null;
                  return (
                    <span key={i} title={mood ? `Mood: ${mood}` : ''} style={{
                      padding: '3px 10px', borderRadius: 12, fontSize: 11,
                      background: 'var(--accent-dim)', color: 'var(--accent-light)',
                      border: '1px solid rgba(124,58,237,0.2)',
                    }}>{name}</span>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Trace Files ──────────────────────────────────────── */}
          {traces.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><FileText size={12} /> Trace Files</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {traces.map((t, i) => (
                  <span key={i} style={{
                    padding: '3px 10px', borderRadius: 8, fontSize: 10,
                    background: 'var(--bg-tertiary)', color: 'var(--text-muted)',
                    fontFamily: 'var(--mono)',
                  }}>
                    {t.name} <span style={{ color: 'var(--teal)' }}>{t.size_kb}kb</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Mini Gauge ───────────────────────────────────────────────────────
function MiniGauge({ label, value, min = 0, max = 1, color }) {
  const norm = clamp((value - min) / (max - min), 0, 1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 60, height: 6, borderRadius: 3, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
          <div style={{
            height: '100%', borderRadius: 3, width: `${norm * 100}%`,
            background: `linear-gradient(90deg, ${color}, ${color}88)`,
            boxShadow: `0 0 6px ${color}44`,
            transition: 'width 0.5s ease',
          }} />
        </div>
        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color, fontWeight: 600 }}>
          {value?.toFixed?.(2) ?? value}
        </span>
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────
const s = {
  panel: {
    display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden',
    background: 'var(--bg-primary)',
  },
  header: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 48, flexShrink: 0,
    background: 'linear-gradient(90deg, rgba(124,58,237,0.06) 0%, transparent 60%)',
  },
  title: { fontSize: 14, fontWeight: 700, letterSpacing: '0.3px' },
  headerRight: {
    marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10,
  },
  refreshBtn: {
    background: 'none', border: '1px solid var(--border)', borderRadius: 6,
    padding: '4px 6px', cursor: 'pointer', color: 'var(--text-muted)',
    display: 'flex', alignItems: 'center',
  },
  scrollArea: {
    flex: 1, overflowY: 'auto', padding: 16,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: 14,
  },
  section: {
    background: 'var(--bg-secondary)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: 16,
  },
  sectionTitle: {
    fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
    textTransform: 'uppercase', letterSpacing: '0.6px',
    marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6,
  },
  card: {
    background: 'var(--bg-secondary)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: 16,
    transition: 'border-color 0.3s, box-shadow 0.3s',
  },
  empty: {
    fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px 0',
  },
};
