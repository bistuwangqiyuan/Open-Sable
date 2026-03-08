import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Brain, Zap, Target, RefreshCw, Activity, Cpu, Layers,
  Sparkles, Eye, TrendingUp, Clock, Database, FileText, Heart,
  User, Shield, MessageCircle, Wrench, Globe, Radio, BookOpen,
  AlertTriangle, ArrowUpRight, GitBranch, Calendar, Users, Award,
  BookMarked,
} from 'lucide-react';

// ── Helpers ──────────────────────────────────────────────────────────
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const pct   = (v) => `${clamp(v * 100, 0, 100).toFixed(0)}%`;
const ago   = (ts) => {
  if (!ts) return '—';
  const t = typeof ts === 'string' ? new Date(ts).getTime() / 1000 : ts;
  const d = (Date.now() / 1000) - t;
  if (d < 0) return 'just now';
  if (d < 60)   return `${Math.floor(d)}s ago`;
  if (d < 3600) return `${Math.floor(d / 60)}m ago`;
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
  return `${Math.floor(d / 86400)}d ago`;
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
  awe: '#06b6d4', contemplative: '#818cf8', amused: '#34d399',
  analytical: '#60a5fa', playful: '#fbbf24', confused: '#fb923c',
};

const getEmotionColor = (e) => {
  const key = typeof e === 'string' ? e.toLowerCase().split(' ')[0] : '';
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
          <span style={{ fontSize: 10, color: 'var(--text-muted)', width: 90, textAlign: 'right', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
              {typeof it.value === 'number' ? it.value.toFixed(2) : it.value}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Circumplex (Valence x Arousal) ─────────────────────────────────
function EmotionCircumplex({ valence = 0, arousal = 0, emotion = '', history = [] }) {
  const size = 160;
  const cx = size / 2, cy = size / 2;
  const toX = (v) => cx + v * (cx - 16);
  const toY = (a) => cy - a * (cy - 16);
  const color = getEmotionColor(emotion);

  return (
    <svg width={size} height={size} style={{ display: 'block' }}>
      <circle cx={cx} cy={cy} r={cx - 12} fill="none" stroke="var(--border)" strokeWidth="0.5" />
      <circle cx={cx} cy={cy} r={(cx - 12) * 0.5} fill="none" stroke="var(--border)" strokeWidth="0.3" strokeDasharray="3 3" />
      <line x1={12} y1={cy} x2={size - 12} y2={cy} stroke="var(--border)" strokeWidth="0.4" />
      <line x1={cx} y1={12} x2={cx} y2={size - 12} stroke="var(--border)" strokeWidth="0.4" />
      <text x={size - 8} y={cy - 4} fontSize={7} fill="var(--text-muted)" textAnchor="end">+V</text>
      <text x={8} y={cy - 4} fontSize={7} fill="var(--text-muted)">-V</text>
      <text x={cx + 4} y={16} fontSize={7} fill="var(--text-muted)">+A</text>
      <text x={cx + 4} y={size - 8} fontSize={7} fill="var(--text-muted)">-A</text>
      {history.slice(-12).map((h, i, arr) => {
        const opacity = 0.15 + (i / arr.length) * 0.4;
        return (
          <circle key={i} cx={toX(h.valence || 0)} cy={toY(h.arousal || 0)}
            r={2} fill={color} opacity={opacity} />
        );
      })}
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
        &ldquo;{landscape}&rdquo;
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
        &ldquo;{fantasy}&rdquo;
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

// ── ReAct Execution Ring ─────────────────────────────────────────────
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
//  NEW: Personality Radar, Identity, Mood, Monologue, Evolution, Heal
// ══════════════════════════════════════════════════════════════════════

// ── Personality Radar (SVG spider chart) ─────────────────────────────
function PersonalityRadar({ traits }) {
  if (!traits || typeof traits !== 'object') return <div style={s.empty}>No personality data</div>;
  const entries = Object.entries(traits);
  if (!entries.length) return <div style={s.empty}>No traits</div>;

  const size = 240;
  const cx = size / 2, cy = size / 2;
  const maxR = cx - 36;
  const n = entries.length;
  const angleStep = (Math.PI * 2) / n;

  const rings = [0.25, 0.5, 0.75, 1.0];
  const toXY = (angle, r) => ({
    x: cx + Math.cos(angle - Math.PI / 2) * r,
    y: cy + Math.sin(angle - Math.PI / 2) * r,
  });

  const dataPoints = entries.map(([, val], i) => {
    const angle = i * angleStep;
    return toXY(angle, val * maxR);
  });
  const polygon = dataPoints.map(p => `${p.x},${p.y}`).join(' ');

  const traitColors = [
    '#7c3aed', '#22c55e', '#00cec9', '#f59e0b', '#ef4444',
    '#ec4899', '#3b82f6', '#a78bfa', '#06b6d4', '#eab308',
    '#10b981', '#f472b6', '#8b5cf6', '#22d3ee', '#34d399',
  ];

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}
      style={{ display: 'block', margin: '0 auto' }}>
      {rings.map((r, i) => {
        const pts = Array.from({ length: n }, (_, j) => {
          const p = toXY(j * angleStep, r * maxR);
          return `${p.x},${p.y}`;
        }).join(' ');
        return <polygon key={i} points={pts} fill="none" stroke="var(--border)" strokeWidth="0.5" opacity={0.5} />;
      })}
      {entries.map(([,], i) => {
        const p = toXY(i * angleStep, maxR);
        return <line key={i} x1={cx} y1={cy} x2={p.x} y2={p.y} stroke="var(--border)" strokeWidth="0.3" />;
      })}
      <polygon points={polygon} fill="rgba(124,58,237,0.15)" stroke="var(--accent)" strokeWidth="1.5"
        style={{ filter: 'drop-shadow(0 0 8px rgba(124,58,237,0.3))' }} />
      {entries.map(([name, val], i) => {
        const p = dataPoints[i];
        const lp = toXY(i * angleStep, maxR + 18);
        const shortName = name.replace(/_/g, ' ').replace(/^(.)/, (_, c) => c.toUpperCase());
        const displayName = shortName.length > 12 ? shortName.slice(0, 11) + '…' : shortName;
        return (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r={3} fill={traitColors[i % traitColors.length]}
              style={{ filter: `drop-shadow(0 0 3px ${traitColors[i % traitColors.length]})` }} />
            <text x={lp.x} y={lp.y} textAnchor="middle" dominantBaseline="central"
              fontSize={7} fill="var(--text-muted)" fontFamily="var(--mono)">
              {displayName}
            </text>
            <title>{`${name}: ${val.toFixed(2)}`}</title>
          </g>
        );
      })}
      <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
        fontSize={8} fill="var(--text-muted)" fontFamily="var(--mono)">TRAITS</text>
    </svg>
  );
}

// ── Identity Card ────────────────────────────────────────────────────
function IdentityCard({ identity }) {
  if (!identity) return null;
  const voice = identity.voice || {};
  return (
    <div style={{
      ...s.card, overflow: 'hidden',
      background: 'linear-gradient(135deg, rgba(124,58,237,0.06) 0%, rgba(6,182,212,0.04) 100%)',
      borderColor: 'rgba(124,58,237,0.3)',
      boxShadow: '0 0 24px rgba(124,58,237,0.08), inset 0 1px 0 rgba(124,58,237,0.12)',
    }}>
      <div style={{ fontSize: 10, color: 'var(--accent-light)', textTransform: 'uppercase', letterSpacing: '0.6px', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        <User size={12} /> Identity Core
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)', marginBottom: 4,
        textShadow: '0 0 20px rgba(124,58,237,0.3)' }}>
        {identity.name || '—'}
      </div>
      {identity.core_directive && (
        <div style={{ fontSize: 11, color: 'var(--teal)', fontFamily: 'var(--mono)', marginBottom: 12, fontStyle: 'italic' }}>
          &ldquo;{identity.core_directive}&rdquo;
        </div>
      )}
      {voice.description && (
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 10 }}>
          {voice.description}
        </div>
      )}
      {voice.preferred_tones && voice.preferred_tones.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
          {voice.preferred_tones.map((t, i) => (
            <span key={i} style={{
              padding: '2px 8px', borderRadius: 10, fontSize: 9,
              background: 'rgba(0,206,201,0.12)', color: 'var(--teal)',
              border: '1px solid rgba(0,206,201,0.2)', textTransform: 'capitalize',
            }}>{t}</span>
          ))}
        </div>
      )}
      {voice.rules && voice.rules.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
            Voice Rules
          </div>
          {voice.rules.slice(0, 5).map((r, i) => (
            <div key={i} style={{ fontSize: 10, color: 'var(--text-secondary)', padding: '2px 0', display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ color: 'var(--green)', fontSize: 8 }}>▸</span> {r}
            </div>
          ))}
        </div>
      )}
      {voice.forbidden && voice.forbidden.length > 0 && (
        <div>
          <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
            Forbidden
          </div>
          {voice.forbidden.slice(0, 4).map((f, i) => (
            <div key={i} style={{ fontSize: 10, color: 'var(--red)', opacity: 0.7, padding: '2px 0', display: 'flex', alignItems: 'baseline', gap: 4 }}>
              <span style={{ fontSize: 8 }}>✗</span> {f}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Mood Timeline ────────────────────────────────────────────────────
function MoodTimeline({ moods }) {
  if (!moods || !moods.length) return <div style={s.empty}>No mood history</div>;
  const sorted = [...moods].reverse().slice(0, 25);
  const intensities = moods.slice(-30).map(m => m.intensity || 0.5);

  return (
    <div>
      {intensities.length > 2 && (
        <div style={{ marginBottom: 12 }}>
          <span style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Intensity Trend</span>
          <Sparkline data={intensities} width={280} height={36} color="#ec4899" label="mood-int" />
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 260, overflowY: 'auto' }}>
        {sorted.map((m, i) => {
          const eColor = getEmotionColor(m.emotion);
          return (
            <div key={i} style={{
              padding: '6px 10px', borderRadius: 6,
              borderLeft: `3px solid ${eColor}`,
              background: i === 0 ? `${eColor}0a` : 'transparent',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: eColor, textTransform: 'capitalize' }}>
                  {m.emotion || '—'}
                </span>
                {m.intensity != null && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 40, height: 4, borderRadius: 2, background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
                      <div style={{ height: '100%', borderRadius: 2, width: `${(m.intensity || 0) * 100}%`, background: eColor }} />
                    </div>
                    <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                      {(m.intensity || 0).toFixed(2)}
                    </span>
                  </div>
                )}
                <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                  {ago(m.ts)}
                </span>
              </div>
              {m.reason && (
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 2 }}>
                  {m.reason.length > 120 ? m.reason.slice(0, 120) + '…' : m.reason}
                </div>
              )}
              {m.trigger_text && !m.reason && (
                <div style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.4, marginTop: 2, fontStyle: 'italic' }}>
                  trigger: {m.trigger_text.length > 80 ? m.trigger_text.slice(0, 80) + '…' : m.trigger_text}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Inner Monologue Feed ─────────────────────────────────────────────
function InnerMonologueFeed({ entries }) {
  if (!entries || !entries.length) return <div style={s.empty}>No inner monologue yet</div>;
  const [expanded, setExpanded] = useState(null);
  const sorted = [...entries].reverse();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 400, overflowY: 'auto' }}>
      {sorted.map((m, i) => {
        const isOpen = expanded === i;
        const thought = m.thought || '';
        const preview = thought.replace(/^#.*\n/gm, '').trim();
        return (
          <div key={i} style={{
            padding: '8px 12px', borderRadius: 8,
            background: isOpen ? 'rgba(124,58,237,0.06)' : 'var(--bg-tertiary)',
            border: `1px solid ${isOpen ? 'rgba(124,58,237,0.25)' : 'var(--border)'}`,
            cursor: 'pointer', transition: 'all 0.2s',
          }}
            onClick={() => setExpanded(isOpen ? null : i)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <MessageCircle size={11} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <span style={{ fontSize: 10, color: 'var(--accent-light)', fontWeight: 600 }}>
                Session #{m.n || i + 1}
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                {ago(m.ts)}
              </span>
            </div>
            {m.situation && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, fontStyle: 'italic' }}>
                {m.situation.length > 100 ? m.situation.slice(0, 100) + '…' : m.situation}
              </div>
            )}
            <div style={{
              fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6,
              maxHeight: isOpen ? 'none' : 48, overflow: 'hidden',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {isOpen ? thought : (preview.length > 200 ? preview.slice(0, 200) + '…' : preview)}
            </div>
            {!isOpen && thought.length > 200 && (
              <div style={{ fontSize: 9, color: 'var(--accent)', marginTop: 4 }}>Click to expand…</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Evolution Timeline ───────────────────────────────────────────────
function EvolutionTimeline({ entries }) {
  if (!entries || !entries.length) return <div style={s.empty}>No evolution history</div>;
  const sorted = [...entries].reverse();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 300, overflowY: 'auto' }}>
      {sorted.map((evo, i) => {
        const changes = evo.changes || {};
        const traitChanges = changes.personality_traits || {};
        const voiceChanges = changes.voice || {};
        const changedTraits = Object.entries(traitChanges);
        return (
          <div key={i} style={{
            padding: '8px 12px', borderRadius: 8,
            borderLeft: `3px solid ${i === 0 ? 'var(--accent)' : 'var(--border)'}`,
            background: i === 0 ? 'rgba(124,58,237,0.04)' : 'transparent',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <GitBranch size={11} style={{ color: i === 0 ? 'var(--accent)' : 'var(--text-muted)' }} />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                {ago(evo.ts)}
              </span>
              {evo.reason && (
                <span style={{ fontSize: 9, color: 'var(--text-muted)', fontStyle: 'italic', marginLeft: 'auto' }}>
                  {evo.reason}
                </span>
              )}
            </div>
            {changedTraits.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 4 }}>
                {changedTraits.map(([trait, val], j) => (
                  <span key={j} style={{
                    padding: '2px 8px', borderRadius: 10, fontSize: 9,
                    background: 'rgba(124,58,237,0.1)', color: 'var(--accent-light)',
                    fontFamily: 'var(--mono)',
                  }}>
                    {trait.replace(/_/g, ' ')}: {typeof val === 'number' ? val.toFixed(2) : val}
                  </span>
                ))}
              </div>
            )}
            {voiceChanges.description && (
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4, fontStyle: 'italic' }}>
                Voice: {voiceChanges.description.length > 100 ? voiceChanges.description.slice(0, 100) + '…' : voiceChanges.description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Heal Log ─────────────────────────────────────────────────────────
function HealLog({ entries }) {
  if (!entries || !entries.length) return <div style={s.empty}>No self-repair events</div>;
  const sorted = [...entries].reverse();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 250, overflowY: 'auto' }}>
      {sorted.map((h, i) => {
        const result = h.result || {};
        const applied = result.applied;
        const color = applied ? 'var(--green)' : 'var(--yellow)';
        return (
          <div key={i} style={{
            padding: '6px 10px', borderRadius: 6,
            borderLeft: `3px solid ${color}`,
            background: i === 0 ? `${color}08` : 'transparent',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <Wrench size={10} style={{ color, flexShrink: 0 }} />
              <span style={{ fontSize: 10, fontWeight: 600, color }}>
                {result.remedy || h.remedy || 'unknown'}
              </span>
              <span style={{ fontSize: 9, color: applied ? 'var(--green)' : 'var(--yellow)',
                fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                {applied ? 'APPLIED' : 'PENDING'}
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                {ago(h.ts)}
              </span>
            </div>
            {h.context_snippet && (
              <div style={{
                fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)',
                background: 'var(--bg-primary)', borderRadius: 4, padding: '4px 8px',
                marginBottom: 4, maxHeight: 40, overflow: 'hidden',
                whiteSpace: 'pre-wrap', wordBreak: 'break-all',
              }}>
                {h.context_snippet.slice(0, 200)}
              </div>
            )}
            {result.advice && (
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {result.advice.length > 150 ? result.advice.slice(0, 150) + '…' : result.advice}
              </div>
            )}
            {result.actions_taken && result.actions_taken.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3, marginTop: 4 }}>
                {result.actions_taken.map((a, j) => (
                  <span key={j} style={{
                    padding: '1px 6px', borderRadius: 8, fontSize: 8,
                    background: 'rgba(234,179,8,0.12)', color: 'var(--yellow)',
                    fontFamily: 'var(--mono)',
                  }}>{a}</span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── X Activity Stats ─────────────────────────────────────────────────
function XActivityStats({ xState }) {
  if (!xState) return null;
  return (
    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
      <div style={{
        ...s.card, flex: 1, minWidth: 110, textAlign: 'center',
        background: 'linear-gradient(135deg, rgba(29,155,240,0.08) 0%, transparent 100%)',
        borderColor: 'rgba(29,155,240,0.2)',
      }}>
        <Globe size={14} style={{ color: '#1d9bf0', marginBottom: 6 }} />
        <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'var(--mono)', color: '#1d9bf0' }}>
          {xState.posts_today ?? 0}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Posts Today</div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--mono)' }}>
          {xState.posted_count ?? 0} total
        </div>
      </div>
      <div style={{
        ...s.card, flex: 1, minWidth: 110, textAlign: 'center',
        background: 'linear-gradient(135deg, rgba(0,206,201,0.06) 0%, transparent 100%)',
        borderColor: 'rgba(0,206,201,0.2)',
      }}>
        <ArrowUpRight size={14} style={{ color: 'var(--teal)', marginBottom: 6 }} />
        <div style={{ fontSize: 24, fontWeight: 700, fontFamily: 'var(--mono)', color: 'var(--teal)' }}>
          {xState.engagements_today ?? 0}
        </div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Engagements</div>
        <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--mono)' }}>
          {xState.engaged_count ?? 0} total
        </div>
      </div>
    </div>
  );
}

// ── X Reflections (Consciousness) ────────────────────────────────────
function XReflectionsFeed({ reflections }) {
  if (!reflections || !reflections.length) return <div style={s.empty}>No consciousness reflections</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 250, overflowY: 'auto' }}>
      {[...reflections].reverse().map((r, i) => {
        const content = typeof r === 'string' ? r
          : (r.reflection || r.analysis || r.summary || JSON.stringify(r));
        const ts = typeof r === 'object' ? (r.ts || r.timestamp) : null;
        return (
          <div key={i} style={{
            padding: '6px 10px', borderRadius: 6,
            borderLeft: `2px solid ${i === 0 ? 'var(--teal)' : 'var(--border)'}`,
            background: i === 0 ? 'rgba(0,206,201,0.04)' : 'transparent',
          }}>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {typeof content === 'string' && content.length > 200 ? content.slice(0, 200) + '…' : content}
            </div>
            {ts && (
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 2, fontFamily: 'var(--mono)' }}>
                {ago(ts)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Proactive State Summary ──────────────────────────────────────────
function ProactiveStateSummary({ state }) {
  if (!state) return null;
  const recentActions = state.recent_actions || state.actions || [];
  const total = state.total_proposals ?? state.proposals_count ?? 0;
  const accepted = state.total_accepted ?? state.accepted_count ?? 0;
  const ratio = total > 0 ? accepted / total : 0;

  return (
    <div>
      {total > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 12 }}>
          <SuccessRing total={total} success={accepted} size={60} />
          <div>
            <div style={{ fontSize: 12, color: 'var(--text)', fontWeight: 600 }}>
              {accepted}/{total} accepted
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
              Acceptance rate: {pct(ratio)}
            </div>
          </div>
        </div>
      )}
      {recentActions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, maxHeight: 150, overflowY: 'auto' }}>
          {[...recentActions].reverse().slice(0, 8).map((a, i) => (
            <div key={i} style={{
              fontSize: 10, color: 'var(--text-secondary)', padding: '4px 8px',
              borderRadius: 4, background: i === 0 ? 'rgba(0,206,201,0.04)' : 'transparent',
              borderLeft: `2px solid ${a.accepted !== false ? 'var(--teal)' : 'var(--border)'}`,
            }}>
              {a.action || a.description || a.proposal || JSON.stringify(a).slice(0, 80)}
              {a.ts && <span style={{ fontSize: 8, color: 'var(--text-muted)', marginLeft: 6, fontFamily: 'var(--mono)' }}>{ago(a.ts)}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ── Journal Feed (x_consciousness/journal.jsonl) ─────────────────────
function JournalFeed({ entries }) {
  if (!entries || !entries.length) return <div style={s.empty}>No journal entries</div>;
  const [expanded, setExpanded] = useState(null);
  const sorted = [...entries].reverse();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 400, overflowY: 'auto' }}>
      {sorted.map((entry, i) => {
        const isOpen = expanded === i;
        const d = entry.data || {};
        const thought = d.thought || '';
        const situation = d.situation || '';
        const num = d.thought_number ?? entry.thought_number ?? null;
        const preview = thought.replace(/^#.*\n/gm, '').trim();
        return (
          <div key={i} style={{
            padding: '8px 12px', borderRadius: 8,
            background: isOpen ? 'rgba(59,130,246,0.06)' : 'var(--bg-tertiary)',
            border: `1px solid ${isOpen ? 'rgba(59,130,246,0.25)' : 'var(--border)'}`,
            cursor: 'pointer', transition: 'all 0.2s',
          }}
            onClick={() => setExpanded(isOpen ? null : i)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <BookMarked size={11} style={{ color: '#3b82f6', flexShrink: 0 }} />
              <span style={{ fontSize: 10, color: '#60a5fa', fontWeight: 600 }}>
                {num != null ? `Thought #${num}` : (entry.type || 'thought')}
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginLeft: 'auto' }}>
                {ago(entry.ts)}
              </span>
            </div>
            {situation && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, fontStyle: 'italic' }}>
                {situation.length > 120 ? situation.slice(0, 120) + '…' : situation}
              </div>
            )}
            <div style={{
              fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6,
              maxHeight: isOpen ? 'none' : 48, overflow: 'hidden',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word',
            }}>
              {isOpen ? thought : (preview.length > 200 ? preview.slice(0, 200) + '…' : preview)}
            </div>
            {!isOpen && thought.length > 200 && (
              <div style={{ fontSize: 9, color: '#3b82f6', marginTop: 4 }}>Click to expand…</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Calendar View ────────────────────────────────────────────────────
function CalendarView({ events }) {
  if (!events || !events.length) return <div style={s.empty}>No scheduled events</div>;
  const sorted = [...events].sort((a, b) => {
    const ta = new Date(a.date || a.start || a.ts || 0).getTime();
    const tb = new Date(b.date || b.start || b.ts || 0).getTime();
    return ta - tb;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 250, overflowY: 'auto' }}>
      {sorted.map((ev, i) => {
        const dt = ev.date || ev.start || ev.ts || '';
        const isPast = dt && new Date(dt).getTime() < Date.now();
        const color = isPast ? '#6b7280' : '#22c55e';
        return (
          <div key={i} style={{
            padding: '6px 10px', borderRadius: 6,
            borderLeft: `3px solid ${color}`,
            background: isPast ? 'transparent' : 'rgba(34,197,94,0.04)',
            opacity: isPast ? 0.6 : 1,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={10} style={{ color, flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: 'var(--text)', flex: 1 }}>
                {ev.title || ev.summary || ev.description || JSON.stringify(ev).slice(0, 80)}
              </span>
              <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', flexShrink: 0 }}>
                {dt ? new Date(dt).toLocaleDateString() : ''}
              </span>
            </div>
            {ev.description && ev.title && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, marginLeft: 18 }}>
                {ev.description.length > 100 ? ev.description.slice(0, 100) + '…' : ev.description}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Conversations Summary ────────────────────────────────────────────
function ConversationsView({ conversations }) {
  if (!conversations || !conversations.length) return <div style={s.empty}>No conversation history</div>;
  const [openUser, setOpenUser] = useState(null);

  const totalMsgs = conversations.reduce((s, c) => s + (c.total_messages || 0), 0);
  const userColors = ['#7c3aed', '#22c55e', '#00cec9', '#f59e0b', '#ec4899', '#3b82f6', '#ef4444', '#a78bfa'];

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          <Users size={11} style={{ verticalAlign: 'middle', marginRight: 4, color: '#00cec9' }} />
          <span style={{ color: '#00cec9', fontWeight: 600 }}>{conversations.length}</span> users · <span style={{ color: '#7c3aed', fontWeight: 600 }}>{totalMsgs}</span> messages
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 350, overflowY: 'auto' }}>
        {conversations.map((conv, i) => {
          const isOpen = openUser === i;
          const uColor = userColors[i % userColors.length];
          const msgs = conv.last_messages || [];
          return (
            <div key={i} style={{
              padding: '8px 12px', borderRadius: 8,
              background: isOpen ? `${uColor}08` : 'var(--bg-tertiary)',
              border: `1px solid ${isOpen ? `${uColor}33` : 'var(--border)'}`,
              cursor: 'pointer', transition: 'all 0.2s',
            }}
              onClick={() => setOpenUser(isOpen ? null : i)}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 12,
                  background: `linear-gradient(135deg, ${uColor} 0%, ${uColor}88 100%)`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700, color: '#fff', flexShrink: 0,
                }}>
                  {(conv.user_id || '?')[0].toUpperCase()}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>{conv.user_id || 'unknown'}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)' }}>
                    {conv.total_messages || 0} messages
                  </div>
                </div>
                <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)' }}>
                  {msgs.length > 0 ? ago(msgs[msgs.length - 1]?.ts) : ''}
                </span>
              </div>
              {isOpen && msgs.length > 0 && (
                <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {msgs.map((m, j) => (
                    <div key={j} style={{
                      padding: '4px 8px', borderRadius: 6, fontSize: 10,
                      borderLeft: `2px solid ${m.user_message ? uColor : '#22c55e'}`,
                      background: m.user_message ? 'rgba(124,58,237,0.04)' : 'rgba(34,197,94,0.04)',
                    }}>
                      <div style={{ color: m.user_message ? uColor : '#22c55e', fontSize: 9, fontWeight: 600, marginBottom: 2 }}>
                        {m.user_message ? 'User' : 'Agent'}
                      </div>
                      <div style={{ color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                        {(m.user_message || m.agent_response || '').slice(0, 150)}
                        {((m.user_message || m.agent_response || '').length > 150) ? '…' : ''}
                      </div>
                      <div style={{ fontSize: 8, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                        {ago(m.ts)}{m.duration_ms ? ` · ${(m.duration_ms / 1000).toFixed(1)}s` : ''}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Benchmark Cards ──────────────────────────────────────────────────
function BenchmarkCards({ benchmarks }) {
  if (!benchmarks || !benchmarks.length) return <div style={s.empty}>No benchmark data</div>;

  const suiteColors = {
    Reasoning: '#7c3aed', GAIA: '#3b82f6', Coding: '#22c55e',
    Knowledge: '#f59e0b', Safety: '#ef4444', default: '#00cec9',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {benchmarks.map((b, i) => {
        const color = suiteColors[b.suite] || suiteColors.default;
        return (
          <div key={i} style={{
            ...s.card, overflow: 'hidden',
            borderColor: `${color}33`,
            background: `linear-gradient(135deg, ${color}0a 0%, transparent 100%)`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
              <SuccessRing total={b.total || 0} success={b.passed || 0} size={54} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color }}>
                  {b.suite || 'Benchmark'}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  {b.passed ?? 0}/{b.total ?? 0} passed · avg {(b.avg_duration_ms / 1000).toFixed(1)}s
                </div>
                {b.model && (
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--mono)', marginTop: 2 }}>
                    {b.model}
                  </div>
                )}
              </div>
            </div>
            <BarChart items={[
              { label: 'Pass Rate', value: b.pass_rate || 0, color },
              { label: 'Avg Score', value: (b.avg_score || 0) * 100, color: `${color}cc` },
            ]} maxVal={100} />
            {b.started_at && (
              <div style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 6, fontFamily: 'var(--mono)' }}>
                Run: {new Date(b.started_at).toLocaleString()}
              </div>
            )}
          </div>
        );
      })}
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

  const fetchBrain = useCallback(() => {
    const sock = ws?.current;
    if (!sock || sock.readyState !== WebSocket.OPEN) return;
    if (!isLocal && profile) {
      sock.send(JSON.stringify({ type: 'agents.brain.data', profile }));
    } else {
      sock.send(JSON.stringify({ type: 'brain.data' }));
    }
    setLoading(true);
  }, [ws, isLocal, profile]);

  useEffect(() => {
    if (brainData) { setData(brainData); setLoading(false); }
  }, [brainData]);

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

  // New data sources
  const identity       = data?.identity || null;
  const evolutionLog   = data?.evolution_log || [];
  const moodHistory    = data?.mood_history || [];
  const innerMonologue = data?.inner_monologue || [];
  const healLog        = data?.heal_log || [];
  const xAgentState    = data?.x_agent_state || null;
  const proactiveState = data?.proactive_state || null;
  const xReflections   = data?.x_reflections || [];

  // Sources 18-21
  const journal        = data?.journal || [];
  const calendar       = data?.calendar || [];
  const conversations  = data?.conversations || [];
  const benchmarks     = data?.benchmarks || [];

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

  const vHistory = emotionHistory
    .map(h => typeof h === 'object' ? (h.valence ?? 0) : 0)
    .filter((_, i, a) => a.some(v => v !== 0));
  const aHistory = emotionHistory
    .map(h => typeof h === 'object' ? (h.arousal ?? 0) : 0)
    .filter((_, i, a) => a.some(v => v !== 0));

  const personalityTraits = identity?.personality_traits || null;

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
          {identity?.name && (
            <span style={{ fontSize: 11, color: 'var(--teal)', fontWeight: 600, marginRight: 8 }}>
              {identity.name}
            </span>
          )}
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

          {/* ── Emotion core ────────────────────────────────────── */}
          <div style={{ ...s.section, gridColumn: '1 / -1' }}>
            <div style={s.sectionTitle}><Heart size={12} /> Emotional Core</div>
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
                <EmotionCircumplex valence={valence} arousal={arousal} emotion={emotion} history={emotionHistory} />
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Valence x Arousal</span>
              </div>
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

          {/* ── Identity Card ───────────────────────────────────── */}
          {identity && (
            <div style={{ gridColumn: '1 / -1' }}>
              <IdentityCard identity={identity} />
            </div>
          )}

          {/* ── Personality Radar ───────────────────────────────── */}
          {personalityTraits && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Radio size={12} /> Personality Radar</div>
              <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <PersonalityRadar traits={personalityTraits} />
                <div style={{ flex: 1, minWidth: 200 }}>
                  <BarChart items={Object.entries(personalityTraits).map(([k, v]) => ({
                    label: k.replace(/_/g, ' '),
                    value: v,
                    color: v > 0.7 ? '#7c3aed' : v > 0.4 ? '#00cec9' : '#6b7280',
                  }))} maxVal={1} />
                </div>
              </div>
            </div>
          )}

          {/* ── Landscape & Fantasy ─────────────────────────────── */}
          <LandscapeCard landscape={landscape} />
          <FantasyCard fantasy={fantasy} />

          {/* ── Stat Cards ──────────────────────────────────────── */}
          <StatCard icon={Cpu} label="Cognitive Tick" value={tick} sub={`${queueSize} tasks queued`} color="var(--teal)" glow />
          <StatCard icon={Database} label="Memories" value={cogMem} sub="cognitive entries" color="var(--blue)" glow />
          <StatCard icon={Zap} label="ReAct Runs" value={reactTotal} sub={`${reactSuccess} successful`} color="var(--green)" glow />
          <StatCard icon={Activity} label="Errors" value={consErrors} sub="consecutive" color={consErrors > 2 ? 'var(--red)' : 'var(--text-muted)'} glow={consErrors > 0} />

          {/* ── X Activity Stats ────────────────────────────────── */}
          {xAgentState && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Globe size={12} /> X Activity</div>
              <XActivityStats xState={xAgentState} />
            </div>
          )}

          {/* ── Mood Timeline ───────────────────────────────────── */}
          {moodHistory.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Activity size={12} /> Mood Timeline ({moodHistory.length})</div>
              <MoodTimeline moods={moodHistory} />
            </div>
          )}

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
                  { label: 'Success', value: reactSuccess, color: '#22c55e' },
                  { label: 'Failed', value: reactTotal - reactSuccess, color: '#ef4444' },
                ]} />
              </div>
            </div>
          </div>

          {/* ── Completed Tasks ──────────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Layers size={12} /> Task History ({completedCount})</div>
            <TaskTimeline tasks={auto.completed_tasks || []} />
          </div>

          {/* ── Inner Monologue ──────────────────────────────────── */}
          {innerMonologue.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><MessageCircle size={12} /> Inner Monologue ({innerMonologue.length})</div>
              <InnerMonologueFeed entries={innerMonologue} />
            </div>
          )}

          {/* ── Proactive Proposals ──────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Sparkles size={12} /> Proactive Proposals ({proposals.length})</div>
            <ProposalList proposals={proposals} />
          </div>

          {/* ── Proactive State Summary ─────────────────────────── */}
          {proactiveState && (
            <div style={s.section}>
              <div style={s.sectionTitle}><TrendingUp size={12} /> Proactive State</div>
              <ProactiveStateSummary state={proactiveState} />
            </div>
          )}

          {/* ── Reflections ──────────────────────────────────────── */}
          <div style={s.section}>
            <div style={s.sectionTitle}><Eye size={12} /> Self-Reflection ({refs.length})</div>
            <ReflectionFeed reflections={refs} />
          </div>

          {/* ── X Consciousness Reflections ──────────────────────── */}
          {xReflections.length > 0 && (
            <div style={s.section}>
              <div style={s.sectionTitle}><BookOpen size={12} /> X Consciousness ({xReflections.length})</div>
              <XReflectionsFeed reflections={xReflections} />
            </div>
          )}

          {/* ── Evolution Timeline ───────────────────────────────── */}
          {evolutionLog.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><GitBranch size={12} /> Personality Evolution ({evolutionLog.length})</div>
              <EvolutionTimeline entries={evolutionLog} />
            </div>
          )}

          {/* ── Self-Healing Log ─────────────────────────────────── */}
          {healLog.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Wrench size={12} /> Self-Repair Log ({healLog.length})</div>
              <HealLog entries={healLog} />
            </div>
          )}

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

          {/* ── Journal (Consciousness Diary) ──────────────────────── */}
          {journal.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><BookMarked size={12} /> Consciousness Journal ({journal.length})</div>
              <JournalFeed entries={journal} />
            </div>
          )}

          {/* ── Calendar ────────────────────────────────────────── */}
          {calendar.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Calendar size={12} /> Calendar ({calendar.length})</div>
              <CalendarView events={calendar} />
            </div>
          )}

          {/* ── Conversations ───────────────────────────────────── */}
          {conversations.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Users size={12} /> Conversations ({conversations.length} users)</div>
              <ConversationsView conversations={conversations} />
            </div>
          )}

          {/* ── Benchmarks ──────────────────────────────────────── */}
          {benchmarks.length > 0 && (
            <div style={{ ...s.section, gridColumn: '1 / -1' }}>
              <div style={s.sectionTitle}><Award size={12} /> Benchmarks ({benchmarks.length} suites)</div>
              <BenchmarkCards benchmarks={benchmarks} />
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
