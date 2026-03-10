import { useState, useEffect, useCallback, useRef } from 'react';
import {
  TrendingUp, TrendingDown, Search, RefreshCw, ExternalLink,
  Activity, Target, Zap, BarChart2, Clock, DollarSign,
  ChevronDown, ChevronUp, Filter, Globe, Flame, Star,
  ArrowUpRight, ArrowDownRight, Eye, Volume2,
} from 'lucide-react';

// ─── Styles ──────────────────────────────────────────────────────────────────

const s = {
  container: {
    display: 'flex', flexDirection: 'column', flex: 1,
    gap: 0, overflow: 'hidden', minHeight: 0,
  },
  topBar: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
    background: 'linear-gradient(180deg, rgba(124,58,237,0.04) 0%, transparent 100%)',
  },
  logo: {
    fontSize: 20, display: 'flex', alignItems: 'center', gap: 6,
  },
  logoText: {
    fontSize: 14, fontWeight: 800, letterSpacing: '-0.02em',
    background: 'linear-gradient(135deg, var(--accent-light) 0%, var(--teal) 100%)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
  },
  liveIndicator: {
    display: 'flex', alignItems: 'center', gap: 5, fontSize: 10,
    fontWeight: 700, color: 'var(--green)', textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  liveDot: {
    width: 6, height: 6, borderRadius: '50%', background: 'var(--green)',
    boxShadow: '0 0 8px rgba(34,197,94,0.6)', animation: 'pulse 2s infinite',
  },
  statsRow: {
    display: 'flex', gap: 8, padding: '10px 16px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
    overflowX: 'auto',
  },
  statPill: {
    display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
    borderRadius: 99, background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
    fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap', flexShrink: 0,
  },
  statValue: { color: 'var(--text)', fontWeight: 800, fontFamily: 'var(--font-mono, monospace)' },
  statLabel: { color: 'var(--text-muted)', fontSize: 10 },
  controls: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  searchBox: {
    display: 'flex', alignItems: 'center', gap: 6, flex: 1,
    padding: '7px 12px', borderRadius: 'var(--radius-sm)',
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
  },
  searchInput: {
    border: 'none', outline: 'none', background: 'transparent',
    color: 'var(--text)', fontSize: 12, flex: 1, fontFamily: 'inherit',
  },
  catPill: (active) => ({
    padding: '5px 12px', borderRadius: 99, border: '1px solid',
    borderColor: active ? 'var(--accent)' : 'var(--border)',
    background: active ? 'rgba(124,58,237,0.15)' : 'var(--bg-tertiary)',
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    fontSize: 11, fontWeight: 600, cursor: 'pointer', transition: 'all .15s',
    whiteSpace: 'nowrap', flexShrink: 0,
  }),
  sortBtn: (active) => ({
    padding: '5px 10px', borderRadius: 'var(--radius-sm)',
    border: '1px solid', fontSize: 10, fontWeight: 700, cursor: 'pointer',
    borderColor: active ? 'var(--teal)' : 'var(--border)',
    background: active ? 'rgba(0,206,201,0.1)' : 'transparent',
    color: active ? 'var(--teal)' : 'var(--text-muted)',
    display: 'flex', alignItems: 'center', gap: 4, transition: 'all .15s',
  }),
  grid: {
    flex: 1, overflowY: 'auto', padding: 16, minHeight: 0,
    display: 'flex', flexDirection: 'column', gap: 10,
  },
  card: (expanded) => ({
    background: 'var(--bg-secondary)', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', overflow: 'hidden',
    transition: 'all .2s', cursor: 'pointer', flexShrink: 0,
    ...(expanded ? { borderColor: 'var(--accent)', boxShadow: '0 0 20px rgba(124,58,237,0.08)' } : {}),
  }),
  cardTop: {
    display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 16px',
  },
  cardIcon: (color) => ({
    width: 42, height: 42, borderRadius: 'var(--radius-sm)',
    background: color || 'var(--bg-hover)', display: 'flex',
    alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0,
  }),
  cardBody: { flex: 1, minWidth: 0 },
  cardQuestion: {
    fontSize: 13, fontWeight: 700, lineHeight: 1.35,
    color: 'var(--text)', marginBottom: 8,
    display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
  },
  probBar: {
    display: 'flex', height: 28, borderRadius: 6, overflow: 'hidden',
    background: 'var(--bg-primary)', marginBottom: 8, position: 'relative',
  },
  probYes: (pct) => ({
    width: `${pct}%`, background: 'linear-gradient(90deg, rgba(34,197,94,0.7) 0%, rgba(34,197,94,0.4) 100%)',
    display: 'flex', alignItems: 'center', paddingLeft: 8, fontSize: 11, fontWeight: 800,
    color: '#22c55e', transition: 'width .6s cubic-bezier(0.22, 1, 0.36, 1)',
    textShadow: '0 1px 2px rgba(0,0,0,0.5)',
  }),
  probNo: (pct) => ({
    width: `${pct}%`, background: 'linear-gradient(90deg, rgba(239,68,68,0.4) 0%, rgba(239,68,68,0.7) 100%)',
    display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 8,
    fontSize: 11, fontWeight: 800, color: '#ef4444', transition: 'width .6s cubic-bezier(0.22, 1, 0.36, 1)',
    textShadow: '0 1px 2px rgba(0,0,0,0.5)',
  }),
  cardMeta: {
    display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
  },
  metaItem: {
    display: 'flex', alignItems: 'center', gap: 4, fontSize: 11,
    color: 'var(--text-muted)', fontWeight: 500,
  },
  metaValue: { fontWeight: 700, color: 'var(--text-secondary)' },
  cardExpanded: {
    borderTop: '1px solid var(--border)', padding: '12px 16px',
    background: 'var(--bg-primary)',
  },
  expandedGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
    gap: 8, marginBottom: 12,
  },
  expandedStat: {
    padding: '10px 12px', borderRadius: 'var(--radius-sm)',
    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
  },
  expandedLabel: { fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 2 },
  expandedValue: { fontSize: 14, fontWeight: 800, color: 'var(--text)', fontFamily: 'var(--font-mono, monospace)' },
  description: {
    fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)', marginBottom: 12,
    maxHeight: 80, overflowY: 'auto',
  },
  outcomeRow: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
    background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
    marginBottom: 4, border: '1px solid var(--border)',
  },
  outcomeName: { flex: 1, fontSize: 12, fontWeight: 600 },
  outcomePrice: (val) => ({
    fontSize: 13, fontWeight: 800, fontFamily: 'var(--font-mono, monospace)',
    color: val > 0.6 ? 'var(--green)' : val > 0.4 ? 'var(--text)' : 'var(--red)',
  }),
  viewBtn: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    padding: '6px 14px', borderRadius: 99, fontSize: 11, fontWeight: 700,
    background: 'linear-gradient(135deg, var(--accent) 0%, #6d28d9 100%)',
    color: '#fff', border: 'none', cursor: 'pointer', transition: 'all .15s',
    textDecoration: 'none',
  },
  empty: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', padding: 48, color: 'var(--text-muted)',
    textAlign: 'center', fontSize: 13,
  },
  loadingBar: {
    position: 'absolute', top: 0, left: 0, right: 0, height: 2,
    background: 'linear-gradient(90deg, transparent, var(--accent), transparent)',
    animation: 'progress-slide 1.5s ease infinite',
  },
};

// ─── Categories ──────────────────────────────────────────────────────────────

const CATEGORIES = [
  { id: 'all', label: 'All Markets', icon: '🌐' },
  { id: 'crypto', label: 'Crypto', icon: '₿' },
  { id: 'politics', label: 'Politics', icon: '🏛️' },
  { id: 'sports', label: 'Sports', icon: '⚽' },
  { id: 'pop-culture', label: 'Pop Culture', icon: '🎬' },
  { id: 'science', label: 'Science', icon: '🔬' },
  { id: 'business', label: 'Business', icon: '📊' },
];

const CATEGORY_ICONS = {
  crypto: '₿', politics: '🏛️', sports: '⚽', 'pop-culture': '🎬',
  science: '🔬', business: '📊', tech: '💻', world: '🌍',
  entertainment: '🎬', finance: '💰', default: '🔮',
};

const SORT_OPTIONS = [
  { id: 'volume', label: 'Volume' },
  { id: 'liquidity', label: 'Liquidity' },
  { id: 'newest', label: 'Newest' },
  { id: 'ending', label: 'Ending Soon' },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatVolume(v) {
  if (!v && v !== 0) return '$0';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function formatLiquidity(v) {
  if (!v && v !== 0) return '$0';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function timeUntil(dateStr) {
  if (!dateStr) return 'Open';
  const diff = new Date(dateStr) - Date.now();
  if (diff <= 0) return 'Ended';
  const days = Math.floor(diff / 86400000);
  if (days > 365) return `${Math.floor(days / 365)}y`;
  if (days > 30) return `${Math.floor(days / 30)}mo`;
  if (days > 0) return `${days}d`;
  const hrs = Math.floor(diff / 3600000);
  if (hrs > 0) return `${hrs}h`;
  return `${Math.floor(diff / 60000)}m`;
}

function extractTagLabels(tags) {
  if (!tags) return '';
  if (!Array.isArray(tags)) return String(tags || '');
  return tags.map(t => (typeof t === 'object' && t !== null) ? (t.label || t.slug || '') : String(t || '')).join(' ');
}

function getCategoryIcon(tags) {
  if (!tags) return CATEGORY_ICONS.default;
  const t = extractTagLabels(tags).toLowerCase();
  for (const [k, v] of Object.entries(CATEGORY_ICONS)) {
    if (t.includes(k)) return v;
  }
  return CATEGORY_ICONS.default;
}

function matchesCategory(market, cat) {
  if (cat === 'all') return true;
  const tags = extractTagLabels(market.tags).toLowerCase();
  const q = (market.question || '').toLowerCase();
  const desc = (market.description || '').toLowerCase();
  const combined = `${tags} ${q} ${desc}`;

  const matchers = {
    crypto: /\bcrypto|bitcoin|btc|ethereum|eth|solana|sol\b|defi|nft|blockchain|token/i,
    politics: /\bpolitics|president|election|senate|congress|vote|democrat|republican|trump|biden\b/i,
    sports: /\bsports|nba|nfl|mlb|soccer|football|tennis|ufc|fight|championship|super bowl\b/i,
    'pop-culture': /\bpop.?culture|movie|tv|music|celebrity|oscar|grammy|award|entertainment\b/i,
    science: /\bscience|space|nasa|ai|artificial|climate|research|physics|medical\b/i,
    business: /\bbusiness|company|stock|market|economy|gdp|fed|interest.rate|earnings\b/i,
  };

  return matchers[cat] ? matchers[cat].test(combined) : false;
}

// ─── API ─────────────────────────────────────────────────────────────────────

const API_BASE = '/api/polymarket';

async function fetchMarkets({ limit = 100, offset = 0, order = 'volume', active = true } = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    active: String(active),
    closed: 'false',
    order,
    ascending: 'false',
  });

  const resp = await fetch(`${API_BASE}/events?${params}`);
  if (!resp.ok) throw new Error(`API ${resp.status}`);
  return resp.json();
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function PolymarketPanel({ onDataUpdate }) {
  const [markets, setMarkets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [sort, setSort] = useState('volume');
  const [expanded, setExpanded] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const timerRef = useRef(null);
  const scrollRef = useRef(null);

  // ── Fetch data ──
  const loadMarkets = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const data = await fetchMarkets({ limit: 100, order: sort === 'newest' ? 'startDate' : sort === 'ending' ? 'endDate' : sort });
      // Gamma API returns an array of events, each with markets
      const processed = (Array.isArray(data) ? data : []).map(event => {
        const m = event.markets?.[0] || {};

        // outcomes / outcomePrices come as JSON strings in the Gamma API
        const parseField = (v) => {
          if (Array.isArray(v)) return v;
          if (typeof v === 'string') { try { return JSON.parse(v); } catch { return []; } }
          return [];
        };

        const outcomes = parseField(m.outcomes || event.outcomes);
        const outcomePrices = parseField(m.outcomePrices || event.outcomePrices)
          .map(p => parseFloat(p) || 0);

        // Multi-outcome events: each sub-market = one candidate/option
        const allMarkets = event.markets || [];
        const isMultiMarket = allMarkets.length > 1;

        let allOutcomes;
        if (isMultiMarket) {
          // Each sub-market = one candidate/option
          allOutcomes = allMarkets
            .map(sm => {
              const smPrices = parseField(sm.outcomePrices);
              const yp = parseFloat(smPrices[0]) || 0;
              return {
                name: sm.groupItemTitle || sm.question?.replace(/^Will\s+/i, '').split(/\s+(win|be)\b/i)[0] || 'Unknown',
                price: yp,
                volume: parseFloat(sm.volumeNum || sm.volume || 0),
                image: sm.image || sm.icon,
              };
            })
            .filter(o => o.price > 0.001)
            .sort((a, b) => b.price - a.price);
        } else {
          allOutcomes = outcomes.map((name, i) => ({
            name: typeof name === 'string' ? name : name?.value || `Outcome ${i + 1}`,
            price: outcomePrices[i] ?? 0,
          }));
        }

        // For binary markets: YES price is the first outcome price
        const yesPrice = isMultiMarket
          ? (allOutcomes[0]?.price ?? 0.5)
          : (outcomePrices[0] ?? parseFloat(m.bestAsk || m.lastTradePrice || 0.5));
        const noPrice = isMultiMarket
          ? (allOutcomes.length > 1 ? allOutcomes[1]?.price : (1 - yesPrice))
          : (outcomePrices[1] ?? (1 - yesPrice));

        return {
          id: event.id || m.conditionId || m.id,
          conditionId: m.conditionId || event.conditionId,
          slug: event.slug || m.slug,
          question: event.title || m.question || event.question || 'Unknown',
          description: event.description || m.description || '',
          yesPrice,
          noPrice,
          volume: parseFloat(event.volume || m.volume || m.volumeNum || 0),
          liquidity: parseFloat(event.liquidity || m.liquidityNum || 0),
          volume24hr: parseFloat(event.volume24hr || m.volume24hr || 0),
          endDate: event.endDate || m.endDate || m.end_date_iso,
          startDate: event.startDate || m.startDate,
          active: m.active !== false,
          closed: event.closed || m.closed || false,
          tags: event.tags || m.tags || [],
          outcomes: allOutcomes,
          isMultiMarket,
          competitive: event.competitive || 0,
          icon: getCategoryIcon(event.tags || m.tags),
          markets: allMarkets,
          image: event.image || m.image || event.icon,
          commentCount: event.commentCount || 0,
        };
      }).filter(m => !m.closed && m.active);

      setMarkets(processed);
      setLastUpdate(new Date());
      // Expose data to parent for trading chat context
      onDataUpdate?.(processed);
    } catch (e) {
      console.error('Polymarket fetch error:', e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sort, onDataUpdate]);

  // Initial load + auto-refresh every 30s
  useEffect(() => {
    loadMarkets();
    timerRef.current = setInterval(() => loadMarkets(true), 30000);
    return () => clearInterval(timerRef.current);
  }, [loadMarkets]);

  // ── Filter + sort ──
  const filtered = markets
    .filter(m => {
      if (category !== 'all' && !matchesCategory(m, category)) return false;
      if (search) {
        const q = search.toLowerCase();
        return m.question.toLowerCase().includes(q) || m.description.toLowerCase().includes(q);
      }
      return true;
    })
    .sort((a, b) => {
      if (sort === 'volume') return b.volume - a.volume;
      if (sort === 'liquidity') return b.liquidity - a.liquidity;
      if (sort === 'newest') return new Date(b.startDate || 0) - new Date(a.startDate || 0);
      if (sort === 'ending') {
        const aEnd = a.endDate ? new Date(a.endDate).getTime() : Infinity;
        const bEnd = b.endDate ? new Date(b.endDate).getTime() : Infinity;
        return aEnd - bEnd;
      }
      return 0;
    });

  // ── Aggregate stats ──
  const totalVolume = markets.reduce((sum, m) => sum + m.volume, 0);
  const totalLiquidity = markets.reduce((sum, m) => sum + m.liquidity, 0);
  const totalMarkets = markets.length;
  const highConviction = markets.filter(m => m.yesPrice > 0.85 || m.yesPrice < 0.15).length;

  return (
    <div style={s.container}>
      {loading && <div style={s.loadingBar} />}

      {/* ── Header ── */}
      <div style={s.topBar}>
        <div style={s.logo}>
          <span>🔮</span>
          <span style={s.logoText}>POLYMARKET SCANNER</span>
        </div>
        <div style={s.liveIndicator}>
          <span style={s.liveDot} />
          LIVE
        </div>
        <span style={{ flex: 1 }} />
        {lastUpdate && (
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
        )}
        <button
          onClick={() => loadMarkets()}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--text-muted)', display: 'flex', padding: 4,
          }}
          title="Refresh"
        >
          <RefreshCw size={14} style={loading ? { animation: 'spin 1s linear infinite' } : {}} />
        </button>
      </div>

      {/* ── Stats Row ── */}
      <div style={s.statsRow}>
        <div style={s.statPill}>
          <DollarSign size={12} style={{ color: 'var(--green)' }} />
          <span style={s.statLabel}>Volume</span>
          <span style={s.statValue}>{formatVolume(totalVolume)}</span>
        </div>
        <div style={s.statPill}>
          <Activity size={12} style={{ color: 'var(--teal)' }} />
          <span style={s.statLabel}>Liquidity</span>
          <span style={s.statValue}>{formatLiquidity(totalLiquidity)}</span>
        </div>
        <div style={s.statPill}>
          <BarChart2 size={12} style={{ color: 'var(--accent-light)' }} />
          <span style={s.statLabel}>Markets</span>
          <span style={s.statValue}>{totalMarkets}</span>
        </div>
        <div style={s.statPill}>
          <Flame size={12} style={{ color: 'var(--red)' }} />
          <span style={s.statLabel}>High Conviction</span>
          <span style={s.statValue}>{highConviction}</span>
        </div>
      </div>

      {/* ── Search + Category + Sort ── */}
      <div style={s.controls}>
        <div style={s.searchBox}>
          <Search size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <input
            style={s.searchInput}
            placeholder="Search prediction markets…"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0, fontSize: 14 }}
            >×</button>
          )}
        </div>
        <div style={{ display: 'flex', gap: 4, overflowX: 'auto' }}>
          {SORT_OPTIONS.map(o => (
            <button key={o.id} style={s.sortBtn(sort === o.id)} onClick={() => setSort(o.id)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Category Pills ── */}
      <div style={{ display: 'flex', gap: 6, padding: '8px 16px', borderBottom: '1px solid var(--border)', overflowX: 'auto', flexShrink: 0 }}>
        {CATEGORIES.map(c => (
          <button key={c.id} style={s.catPill(category === c.id)} onClick={() => setCategory(c.id)}>
            {c.icon} {c.label}
          </button>
        ))}
      </div>

      {/* ── Markets Grid ── */}
      <div style={s.grid} ref={scrollRef}>
        {error && (
          <div style={{ ...s.empty, color: 'var(--red)' }}>
            <Zap size={28} style={{ opacity: 0.4, marginBottom: 8 }} />
            <div style={{ fontWeight: 700 }}>Connection Error</div>
            <div style={{ fontSize: 11, marginTop: 4, color: 'var(--text-muted)' }}>{error}</div>
            <button
              onClick={() => loadMarkets()}
              style={{ ...s.viewBtn, marginTop: 12 }}
            >
              <RefreshCw size={12} /> Retry
            </button>
          </div>
        )}

        {!error && !loading && filtered.length === 0 && (
          <div style={s.empty}>
            <Target size={28} style={{ opacity: 0.3, marginBottom: 8 }} />
            <div>No markets found</div>
            <div style={{ fontSize: 11, marginTop: 4 }}>
              {search ? 'Try a different search term' : 'No active markets in this category'}
            </div>
          </div>
        )}

        {!error && filtered.map(market => {
          const isExpanded = expanded === market.id;
          const yesPct = Math.round(market.yesPrice * 100);
          const noPct = 100 - yesPct;
          const isMultiOutcome = market.isMultiMarket || market.outcomes.length > 2;
          const slug = market.slug || market.conditionId || market.id;

          return (
            <div key={market.id} style={s.card(isExpanded)} onClick={() => setExpanded(isExpanded ? null : market.id)}>
              <div style={s.cardTop}>
                {/* Event image or icon */}
                {market.image ? (
                  <div style={{
                    width: 42, height: 42, borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden', flexShrink: 0, border: '1px solid var(--border)',
                    background: 'var(--bg-hover)',
                  }}>
                    <img
                      src={market.image}
                      alt=""
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      onError={e => { e.target.style.display = 'none'; }}
                    />
                  </div>
                ) : (
                  <div style={s.cardIcon(
                    yesPct > 70 ? 'rgba(34,197,94,0.12)' :
                    yesPct < 30 ? 'rgba(239,68,68,0.12)' :
                    'var(--bg-hover)'
                  )}>
                    {market.icon}
                  </div>
                )}
                <div style={s.cardBody}>
                  <div style={s.cardQuestion}>{market.question}</div>

                  {/* Binary probability bar */}
                  {!isMultiOutcome && (
                    <div style={s.probBar}>
                      <div style={s.probYes(yesPct)}>
                        {yesPct > 12 && `YES ${yesPct}¢`}
                      </div>
                      <div style={s.probNo(noPct)}>
                        {noPct > 12 && `NO ${noPct}¢`}
                      </div>
                    </div>
                  )}

                  {/* Multi-outcome: ranked list of top candidates */}
                  {isMultiOutcome && (
                    <div style={{ marginBottom: 8 }}>
                      {market.outcomes.slice(0, 5).map((out, i) => (
                        <div key={i} style={{
                          display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3,
                        }}>
                          <span style={{
                            fontSize: 10, fontWeight: 800, color: 'var(--text-muted)',
                            width: 14, textAlign: 'right', flexShrink: 0,
                          }}>#{i + 1}</span>
                          <span style={{
                            flex: 1, fontSize: 11, fontWeight: 600, color: 'var(--text)',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>{out.name}</span>
                          <div style={{
                            width: 60, height: 6, borderRadius: 3, background: 'var(--bg-primary)',
                            overflow: 'hidden', flexShrink: 0,
                          }}>
                            <div style={{
                              width: `${Math.min(out.price * 100, 100)}%`, height: '100%', borderRadius: 3,
                              background: i === 0
                                ? 'linear-gradient(90deg, var(--green), rgba(34,197,94,0.5))'
                                : i < 3
                                  ? 'linear-gradient(90deg, var(--accent), rgba(124,58,237,0.4))'
                                  : 'var(--bg-hover)',
                              transition: 'width .6s ease',
                            }} />
                          </div>
                          <span style={{
                            fontSize: 11, fontWeight: 800, fontFamily: 'var(--font-mono, monospace)',
                            color: i === 0 ? 'var(--green)' : 'var(--text-secondary)',
                            width: 32, textAlign: 'right', flexShrink: 0,
                          }}>{Math.round(out.price * 100)}¢</span>
                        </div>
                      ))}
                      {market.outcomes.length > 5 && (
                        <span style={{ fontSize: 10, color: 'var(--text-muted)', paddingLeft: 22, marginTop: 2, display: 'block' }}>
                          +{market.outcomes.length - 5} more options
                        </span>
                      )}
                    </div>
                  )}

                  <div style={s.cardMeta}>
                    <span style={s.metaItem}>
                      <DollarSign size={11} />
                      <span style={s.metaValue}>{formatVolume(market.volume)}</span>
                      <span>vol</span>
                    </span>
                    <span style={s.metaItem}>
                      <Activity size={11} />
                      <span style={s.metaValue}>{formatLiquidity(market.liquidity)}</span>
                      <span>liq</span>
                    </span>
                    <span style={s.metaItem}>
                      <Clock size={11} />
                      <span style={s.metaValue}>{timeUntil(market.endDate)}</span>
                    </span>
                    {market.volume24hr > 0 && (
                      <span style={s.metaItem}>
                        <TrendingUp size={11} style={{ color: 'var(--teal)' }} />
                        <span style={{ ...s.metaValue, color: 'var(--teal)' }}>{formatVolume(market.volume24hr)}</span>
                        <span>24h</span>
                      </span>
                    )}
                    {market.commentCount > 0 && (
                      <span style={s.metaItem}>
                        💬 {market.commentCount}
                      </span>
                    )}
                    <span style={{ flex: 1 }} />
                    {isExpanded
                      ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} />
                      : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />
                    }
                  </div>
                </div>
              </div>

              {/* ── Expanded Details ── */}
              {isExpanded && (
                <div style={s.cardExpanded} onClick={e => e.stopPropagation()}>
                  {market.description && (
                    <div style={s.description}>{market.description}</div>
                  )}

                  <div style={s.expandedGrid}>
                    {!isMultiOutcome && (
                      <>
                        <div style={s.expandedStat}>
                          <div style={s.expandedLabel}>YES Price</div>
                          <div style={{ ...s.expandedValue, color: 'var(--green)' }}>{yesPct}¢</div>
                        </div>
                        <div style={s.expandedStat}>
                          <div style={s.expandedLabel}>NO Price</div>
                          <div style={{ ...s.expandedValue, color: 'var(--red)' }}>{noPct}¢</div>
                        </div>
                      </>
                    )}
                    {isMultiOutcome && (
                      <div style={s.expandedStat}>
                        <div style={s.expandedLabel}>Leader</div>
                        <div style={{ ...s.expandedValue, color: 'var(--green)' }}>
                          {market.outcomes[0]?.name} ({Math.round(market.outcomes[0]?.price * 100)}¢)
                        </div>
                      </div>
                    )}
                    <div style={s.expandedStat}>
                      <div style={s.expandedLabel}>Total Volume</div>
                      <div style={s.expandedValue}>{formatVolume(market.volume)}</div>
                    </div>
                    <div style={s.expandedStat}>
                      <div style={s.expandedLabel}>Liquidity</div>
                      <div style={s.expandedValue}>{formatLiquidity(market.liquidity)}</div>
                    </div>
                    <div style={s.expandedStat}>
                      <div style={s.expandedLabel}>Ends</div>
                      <div style={s.expandedValue}>{timeUntil(market.endDate)}</div>
                    </div>
                    <div style={s.expandedStat}>
                      <div style={s.expandedLabel}>Markets</div>
                      <div style={s.expandedValue}>{market.markets?.length || 1}</div>
                    </div>
                  </div>

                  {/* All outcomes (for multi-outcome markets) */}
                  {market.outcomes.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6 }}>
                        {isMultiOutcome ? `TOP OUTCOMES (${market.outcomes.length} total)` : 'OUTCOMES'}
                      </div>
                      {market.outcomes.slice(0, isMultiOutcome ? 15 : 10).map((out, i) => (
                        <div key={i} style={s.outcomeRow}>
                          <span style={{
                            width: 8, height: 8, borderRadius: '50%',
                            background: out.price > 0.5 ? 'var(--green)' : out.price > 0.3 ? 'var(--accent)' : 'var(--red)',
                          }} />
                          <span style={s.outcomeName}>{out.name}</span>
                          <span style={s.outcomePrice(out.price)}>
                            {Math.round(out.price * 100)}¢
                          </span>
                          <div style={{
                            width: 60, height: 4, borderRadius: 2, background: 'var(--bg-primary)',
                            overflow: 'hidden',
                          }}>
                            <div style={{
                              width: `${out.price * 100}%`, height: '100%', borderRadius: 2,
                              background: out.price > 0.5
                                ? 'linear-gradient(90deg, var(--green), rgba(34,197,94,0.5))'
                                : 'linear-gradient(90deg, var(--accent), rgba(124,58,237,0.5))',
                              transition: 'width .6s ease',
                            }} />
                          </div>
                        </div>
                      ))}
                      {market.outcomes.length > 15 && isMultiOutcome && (
                        <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: '6px 0', fontStyle: 'italic' }}>
                          +{market.outcomes.length - 15} more,  view all on Polymarket
                        </div>
                      )}
                    </div>
                  )}

                  {/* Action buttons */}
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <a
                      href={`https://polymarket.com/event/${slug}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={s.viewBtn}
                      onClick={e => e.stopPropagation()}
                    >
                      <ExternalLink size={11} /> View on Polymarket
                    </a>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                      ID: {(market.conditionId || market.id || '').slice(0, 12)}…
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}

        {/* Loading skeletons */}
        {loading && markets.length === 0 && Array.from({ length: 6 }).map((_, i) => (
          <div key={i} style={{
            ...s.card(false), padding: 16, animation: 'pulse 1.5s ease infinite',
          }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{ width: 42, height: 42, borderRadius: 8, background: 'var(--bg-hover)' }} />
              <div style={{ flex: 1 }}>
                <div style={{ height: 14, background: 'var(--bg-hover)', borderRadius: 4, marginBottom: 8, width: '80%' }} />
                <div style={{ height: 28, background: 'var(--bg-hover)', borderRadius: 6, marginBottom: 8 }} />
                <div style={{ display: 'flex', gap: 12 }}>
                  <div style={{ height: 10, background: 'var(--bg-hover)', borderRadius: 4, width: 60 }} />
                  <div style={{ height: 10, background: 'var(--bg-hover)', borderRadius: 4, width: 50 }} />
                  <div style={{ height: 10, background: 'var(--bg-hover)', borderRadius: 4, width: 40 }} />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
