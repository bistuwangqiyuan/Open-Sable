import { useState, useEffect, useCallback, useRef } from 'react';
import {
  TrendingUp, TrendingDown, DollarSign, BarChart2, RefreshCw,
  AlertTriangle, ChevronDown, ChevronRight, ExternalLink,
  Activity, Target, Shield, Zap, PieChart, LineChart,
  Send, MessageSquare, PanelRightClose, PanelRightOpen,
} from 'lucide-react';
import { fmtTime } from '../../lib/utils';
import PolymarketPanel from './PolymarketPanel';

const s = {
  panel: { display: 'flex', flex: 1, overflow: 'hidden' },
  main: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden', minWidth: 0 },
  header: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '12px 16px',
    borderBottom: '1px solid var(--border)', minHeight: 44, flexShrink: 0,
  },
  title: { fontSize: 13, fontWeight: 600 },
  body: { flex: 1, overflowY: 'auto', padding: 0 },
  tabs: {
    display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
    padding: '0 16px', flexShrink: 0,
  },
  tab: (active) => ({
    padding: '10px 16px', border: 'none',
    borderBottom: active ? '2px solid var(--accent)' : '2px solid transparent',
    background: 'transparent',
    color: active ? 'var(--accent-light)' : 'var(--text-muted)',
    cursor: 'pointer', fontSize: 12, fontWeight: 600, transition: 'all .15s',
  }),
  content: { padding: 16, flex: 1, overflowY: 'auto' },
  /* ── Chat sidebar ── */
  chatSide: (open) => ({
    width: open ? 360 : 0, minWidth: open ? 360 : 0,
    borderLeft: open ? '1px solid var(--border)' : 'none',
    display: 'flex', flexDirection: 'column', overflow: 'hidden',
    transition: 'width .2s ease, min-width .2s ease',
    background: 'var(--bg-secondary)',
  }),
  chatHeader: {
    display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px',
    borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  chatMessages: { flex: 1, overflowY: 'auto', padding: 12 },
  chatMsg: (user) => ({
    marginBottom: 12, display: 'flex', gap: 8,
    flexDirection: user ? 'row-reverse' : 'row',
  }),
  chatAvatar: (user) => ({
    width: 26, height: 26, borderRadius: 6, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12,
    background: user ? 'var(--accent-dim)' : 'var(--teal-dim)',
    color: user ? 'var(--accent-light)' : 'var(--teal)',
  }),
  chatBubble: (user) => ({
    maxWidth: '85%', padding: '8px 12px', borderRadius: 10, fontSize: 12.5,
    lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
    ...(user
      ? { background: 'var(--accent)', color: '#fff', borderBottomRightRadius: 3 }
      : { background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderBottomLeftRadius: 3 }),
  }),
  chatTime: { fontSize: 9, color: 'var(--text-muted)', marginTop: 2 },
  chatInput: {
    padding: '10px 14px', borderTop: '1px solid var(--border)', flexShrink: 0,
    display: 'flex', gap: 8,
  },
  chatInputField: {
    flex: 1, padding: '8px 12px', borderRadius: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    color: 'var(--text)', fontSize: 12.5, outline: 'none', fontFamily: 'var(--sans)',
  },
  chatSendBtn: {
    padding: '0 14px', borderRadius: 8, border: 'none',
    background: 'var(--accent)', color: '#fff', cursor: 'pointer',
    display: 'flex', alignItems: 'center',
  },
  chatToggle: {
    background: 'none', border: 'none', color: 'var(--text-muted)',
    cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center',
  },
  statsGrid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: 10, marginBottom: 20,
  },
  statCard: {
    padding: '14px 16px', borderRadius: 'var(--radius)',
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
  },
  statLabel: { fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '.5px' },
  statValue: { fontSize: 22, fontWeight: 800, marginTop: 4 },
  statChange: (positive) => ({
    fontSize: 11, fontWeight: 600, marginTop: 2,
    color: positive ? 'var(--green)' : 'var(--red)',
    display: 'flex', alignItems: 'center', gap: 3,
  }),
  section: { marginBottom: 24 },
  sectionTitle: {
    fontSize: 13, fontWeight: 700, marginBottom: 12,
    display: 'flex', alignItems: 'center', gap: 8,
  },
  orderRow: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '10px 14px',
    background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
    marginBottom: 6, border: '1px solid var(--border)', fontSize: 12,
  },
  badge: (color) => ({
    padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
    background: color === 'green' ? 'rgba(34,197,94,.15)' : color === 'red' ? 'rgba(239,68,68,.15)' : 'rgba(139,92,246,.15)',
    color: color === 'green' ? 'var(--green)' : color === 'red' ? 'var(--red)' : 'var(--accent-light)',
  }),
  signalCard: {
    padding: 14, borderRadius: 'var(--radius)', marginBottom: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
  },
  strategyCard: {
    padding: 14, borderRadius: 'var(--radius)', marginBottom: 8,
    border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
    display: 'flex', gap: 12, alignItems: 'flex-start',
  },
  aggrFrame: {
    width: '100%', border: 'none', borderRadius: 'var(--radius)',
    background: '#0e0f14', minHeight: 500,
  },
  empty: {
    padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13,
  },
  btn: (v) => ({
    padding: '6px 14px', borderRadius: 'var(--radius-sm)', border: 'none',
    cursor: 'pointer', fontSize: 11, fontWeight: 600,
    display: 'flex', alignItems: 'center', gap: 4,
    background: v === 'primary' ? 'var(--accent)' : 'var(--bg-hover)',
    color: v === 'primary' ? '#fff' : 'var(--text-secondary)',
  }),
};

// Mock portfolio data (will be replaced with WS data)
const INITIAL_PORTFOLIO = {
  totalValue: 0,
  cashBalance: 0,
  positionsValue: 0,
  unrealizedPnl: 0,
  realizedPnl: 0,
  pnlPct: 0,
  mode: 'PAPER',
};

const STRATEGIES = [
  { id: 'momentum', name: 'Momentum', desc: 'Trend-following on crypto pairs', status: 'active', winRate: 62, trades: 148 },
  { id: 'mean_reversion', name: 'Mean Reversion', desc: 'Buy dips, sell rallies around moving averages', status: 'active', winRate: 58, trades: 93 },
  { id: 'sentiment', name: 'Sentiment', desc: 'AI-driven social sentiment analysis', status: 'paused', winRate: 54, trades: 41 },
  { id: 'arbitrage', name: 'Arbitrage', desc: 'Cross-exchange spread capture', status: 'inactive', winRate: 71, trades: 22 },
  { id: 'polymarket_edge', name: 'Polymarket Edge', desc: 'Prediction market probability analysis', status: 'inactive', winRate: 0, trades: 0 },
];

export default function TradingPanel({ stats, messages, streaming, sendMessage }) {
  const TABS = [
    { id: 'portfolio', label: '💼 Portfolio' },
    { id: 'polymarket', label: '🔮 Polymarket' },
    { id: 'orders', label: '📋 Orders' },
    { id: 'signals', label: '🎯 Signals' },
    { id: 'strategies', label: '🧠 Strategies' },
    { id: 'charts', label: '📊 Aggr Charts' },
  ];
  const [tab, setTab] = useState('portfolio');
  const [portfolio, setPortfolio] = useState(INITIAL_PORTFOLIO);
  const [positions, setPositions] = useState([]);
  const [orders, setOrders] = useState([]);
  const [signals, setSignals] = useState([]);
  const [strategies, setStrategies] = useState(STRATEGIES);
  const [aggrLoaded, setAggrLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [chatInput, setChatInput] = useState('');
  const polymarketDataRef = useRef([]);
  const aggrRef = useRef(null);
  const chatEndRef = useRef(null);

  // Callback to receive Polymarket data from PolymarketPanel
  const handlePolymarketData = useCallback((data) => {
    polymarketDataRef.current = data || [];
  }, []);

  // Fetch portfolio data via the agent
  const refreshPortfolio = useCallback(() => {
    setRefreshing(true);
    // Send command to get trading status
    if (sendMessage) {
      sendMessage('/trading status');
    }
    setTimeout(() => setRefreshing(false), 2000);
  }, [sendMessage]);

  // Build the aggr URL (same host, /aggr/ path)
  const aggrUrl = (() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    return `/aggr/${token ? '?token=' + encodeURIComponent(token) : ''}`;
  })();

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Build a concise Polymarket summary for the AI context
  const buildPolymarketContext = useCallback(() => {
    const data = polymarketDataRef.current;
    if (!data || data.length === 0) return '';

    const top = data.slice(0, 20);
    const totalVol = data.reduce((s, m) => s + m.volume, 0);
    const totalLiq = data.reduce((s, m) => s + m.liquidity, 0);

    let ctx = `\n\n[POLYMARKET LIVE DATA,  ${data.length} active markets | Total Volume: $${(totalVol / 1e6).toFixed(1)}M | Total Liquidity: $${(totalLiq / 1e6).toFixed(1)}M]\n`;
    ctx += `Top markets by volume:\n`;
    top.forEach((m, i) => {
      const prob = m.isMultiMarket
        ? m.outcomes?.slice(0, 3).map(o => `${o.name}: ${(o.price * 100).toFixed(0)}%`).join(', ')
        : `Yes: ${(m.yesPrice * 100).toFixed(0)}% / No: ${(m.noPrice * 100).toFixed(0)}%`;
      ctx += `${i + 1}. "${m.question}",  ${prob} | Vol: $${m.volume >= 1e6 ? (m.volume / 1e6).toFixed(1) + 'M' : m.volume >= 1e3 ? (m.volume / 1e3).toFixed(0) + 'K' : m.volume.toFixed(0)} | Ends: ${m.endDate ? new Date(m.endDate).toLocaleDateString() : 'Open'}\n`;
    });
    return ctx;
  }, []);

  // Send message with optional Polymarket context injection
  const sendWithContext = useCallback((text) => {
    if (!text || !sendMessage) return;
    const mentionsPoly = /poly(market)?|predict|bet|probab|forecast|mercado/i.test(text);
    const shouldInject = tab === 'polymarket' || mentionsPoly;
    let finalText = text;
    if (shouldInject && polymarketDataRef.current.length > 0) {
      finalText = text + buildPolymarketContext();
    }
    sendMessage(finalText);
  }, [tab, sendMessage, buildPolymarketContext]);

  const handleChatSend = (e) => {
    e?.preventDefault();
    const text = chatInput.trim();
    if (!text || !sendMessage) return;
    sendWithContext(text);
    setChatInput('');
  };

  const handleChatKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleChatSend(e); }
  };

  const formatUSD = (val) => {
    const n = Number(val) || 0;
    return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });
  };

  const formatPct = (val) => {
    const n = Number(val) || 0;
    return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
  };

  return (
    <div style={s.panel}>
    <div style={s.main}>
      <div style={s.header}>
        <span style={{ fontSize: 16 }}>📈</span>
        <span style={s.title}>Sable Trader</span>
        <span style={{
          ...s.badge(portfolio.mode === 'LIVE' ? 'accent' : 'green'),
          marginLeft: 8,
        }}>
          {portfolio.mode}
        </span>
        <div style={{ flex: 1 }} />
        <button
          style={s.btn()}
          onClick={refreshPortfolio}
          title="Refresh trading data"
        >
          <RefreshCw size={13} style={refreshing ? { animation: 'spin 1s linear infinite' } : {}} />
          Refresh
        </button>
        <button
          style={s.chatToggle}
          onClick={() => setChatOpen(p => !p)}
          title={chatOpen ? 'Hide chat' : 'Show chat'}
        >
          {chatOpen ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
        </button>
      </div>

      <div style={s.tabs}>
        {TABS.map(t => (
          <button key={t.id} style={s.tab(tab === t.id)} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      <div style={tab === 'polymarket' ? { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' } : s.content}>
        {/* Polymarket Tab */}
        {tab === 'polymarket' && <PolymarketPanel onDataUpdate={handlePolymarketData} />}

        {/* Portfolio Tab */}
        {tab === 'portfolio' && (
          <div>
            {/* Stats Grid */}
            <div style={s.statsGrid}>
              <div style={s.statCard}>
                <div style={s.statLabel}>Total Value</div>
                <div style={s.statValue}>{formatUSD(portfolio.totalValue)}</div>
              </div>
              <div style={s.statCard}>
                <div style={s.statLabel}>Cash Balance</div>
                <div style={s.statValue}>{formatUSD(portfolio.cashBalance)}</div>
              </div>
              <div style={s.statCard}>
                <div style={s.statLabel}>Positions Value</div>
                <div style={s.statValue}>{formatUSD(portfolio.positionsValue)}</div>
              </div>
              <div style={s.statCard}>
                <div style={s.statLabel}>Unrealized P&L</div>
                <div style={s.statValue}>{formatUSD(portfolio.unrealizedPnl)}</div>
                <div style={s.statChange(portfolio.unrealizedPnl >= 0)}>
                  {portfolio.unrealizedPnl >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                  {formatPct(portfolio.pnlPct)}
                </div>
              </div>
              <div style={s.statCard}>
                <div style={s.statLabel}>Realized P&L</div>
                <div style={s.statValue}>{formatUSD(portfolio.realizedPnl)}</div>
              </div>
              <div style={s.statCard}>
                <div style={s.statLabel}>Open Positions</div>
                <div style={s.statValue}>{positions.length}</div>
              </div>
            </div>

            {/* Positions */}
            <div style={s.section}>
              <div style={s.sectionTitle}>
                <PieChart size={15} /> Open Positions
              </div>
              {positions.length === 0 ? (
                <div style={s.empty}>
                  <DollarSign size={28} style={{ opacity: .3, marginBottom: 8 }} />
                  <div>No open positions</div>
                  <div style={{ fontSize: 11, marginTop: 4 }}>Use the chat to ask Sable to analyze markets or place trades</div>
                </div>
              ) : (
                positions.map((pos, i) => (
                  <div key={i} style={s.orderRow}>
                    <span style={s.badge(pos.side === 'long' ? 'green' : 'red')}>
                      {pos.side.toUpperCase()}
                    </span>
                    <span style={{ fontWeight: 700, flex: 1 }}>{pos.symbol}</span>
                    <span>{pos.quantity}</span>
                    <span style={{ color: 'var(--text-muted)' }}>@ {pos.entryPrice}</span>
                    <span style={{ color: pos.pnl >= 0 ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                      {formatUSD(pos.pnl)}
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* Quick Commands */}
            <div style={s.section}>
              <div style={s.sectionTitle}>
                <Zap size={15} /> Quick Commands
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {[
                  { label: 'Portfolio Status', cmd: '/trading status' },
                  { label: 'Market Analysis', cmd: '/trading analyze BTC' },
                  { label: 'Get Signals', cmd: '/trading signals' },
                  { label: 'Trade History', cmd: '/trading history' },
                  { label: 'Risk Report', cmd: '/trading risk' },
                  { label: '🔮 Polymarket Scan', cmd: '/trading polymarket scan' },
                ].map((q, i) => (
                  <button
                    key={i}
                    style={{
                      padding: '8px 14px', borderRadius: 99,
                      border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
                      color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 11,
                      fontWeight: 600, transition: 'all .15s',
                    }}
                    onClick={() => sendMessage && sendMessage(q.cmd)}
                  >
                    {q.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Orders Tab */}
        {tab === 'orders' && (
          <div>
            <div style={s.section}>
              <div style={s.sectionTitle}><BarChart2 size={15} /> Open Orders</div>
              {orders.length === 0 ? (
                <div style={s.empty}>
                  <BarChart2 size={28} style={{ opacity: .3, marginBottom: 8 }} />
                  <div>No open orders</div>
                  <div style={{ fontSize: 11, marginTop: 4 }}>
                    Orders placed through the agent will appear here
                  </div>
                </div>
              ) : (
                orders.map((ord, i) => (
                  <div key={i} style={s.orderRow}>
                    <span style={s.badge(ord.side === 'buy' ? 'green' : 'red')}>
                      {ord.side.toUpperCase()}
                    </span>
                    <span style={{ fontWeight: 700 }}>{ord.symbol}</span>
                    <span style={{ color: 'var(--text-muted)', flex: 1 }}>
                      {ord.type} · {ord.quantity} @ {ord.price || 'MKT'}
                    </span>
                    <span style={s.badge('accent')}>{ord.status}</span>
                  </div>
                ))
              )}
            </div>

            {/* Exchanges */}
            <div style={s.section}>
              <div style={s.sectionTitle}><Shield size={15} /> Connected Exchanges</div>
              {['Binance', 'Coinbase', 'Alpaca', 'Hyperliquid', 'Jupiter (Solana)', 'Polymarket'].map((ex, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
                  background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-sm)',
                  marginBottom: 4, border: '1px solid var(--border)',
                }}>
                  <span style={{ fontSize: 14 }}>
                    {ex === 'Binance' ? '🟡' : ex === 'Coinbase' ? '🔵' : ex === 'Alpaca' ? '🦙' :
                     ex === 'Hyperliquid' ? '💧' : ex === 'Jupiter (Solana)' ? '🪐' : '🔮'}
                  </span>
                  <span style={{ flex: 1, fontSize: 13, fontWeight: 600 }}>{ex}</span>
                  <span style={{
                    fontSize: 10, fontWeight: 600, color: 'var(--text-muted)',
                    padding: '2px 8px', borderRadius: 99, background: 'var(--bg-hover)',
                  }}>
                    Not connected
                  </span>
                </div>
              ))}
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontStyle: 'italic' }}>
                Configure API keys in Settings → AI Providers / env vars
              </div>
            </div>
          </div>
        )}

        {/* Signals Tab */}
        {tab === 'signals' && (
          <div>
            <div style={s.sectionTitle}><Target size={15} /> Active Signals</div>
            {signals.length === 0 ? (
              <div style={s.empty}>
                <Target size={28} style={{ opacity: .3, marginBottom: 8 }} />
                <div>No active signals</div>
                <div style={{ fontSize: 11, marginTop: 4 }}>
                  Enable strategies to generate trading signals automatically
                </div>
                <button
                  style={{ ...s.btn('primary'), margin: '16px auto 0' }}
                  onClick={() => sendMessage && sendMessage('/trading signals')}
                >
                  <RefreshCw size={12} /> Request Signals
                </button>
              </div>
            ) : (
              signals.map((sig, i) => (
                <div key={i} style={s.signalCard}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={s.badge(sig.direction === 'long' ? 'green' : sig.direction === 'short' ? 'red' : 'accent')}>
                      {sig.direction.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 15, fontWeight: 800 }}>{sig.symbol}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 'auto' }}>
                      {sig.strategy}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Confidence: <strong>{(sig.confidence * 100).toFixed(0)}%</strong> · 
                    Entry: <strong>{sig.entryPrice}</strong> · 
                    Target: <strong>{sig.target}</strong> · 
                    Stop: <strong>{sig.stopLoss}</strong>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Strategies Tab */}
        {tab === 'strategies' && (
          <div>
            <div style={s.sectionTitle}><Activity size={15} /> Trading Strategies</div>
            {strategies.map(strat => (
              <div key={strat.id} style={s.strategyCard}>
                <div style={{
                  width: 40, height: 40, borderRadius: 'var(--radius-sm)',
                  background: strat.status === 'active' ? 'rgba(34,197,94,.15)' : 'var(--bg-hover)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, flexShrink: 0,
                }}>
                  {strat.id === 'momentum' ? '🚀' : strat.id === 'mean_reversion' ? '🔁' :
                   strat.id === 'sentiment' ? '🧠' : strat.id === 'arbitrage' ? '⚡' : '🔮'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 700 }}>{strat.name}</span>
                    <span style={s.badge(
                      strat.status === 'active' ? 'green' : strat.status === 'paused' ? 'accent' : 'red'
                    )}>
                      {strat.status}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{strat.desc}</div>
                  {strat.trades > 0 && (
                    <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                      <span>Win rate: <strong style={{ color: 'var(--green)' }}>{strat.winRate}%</strong></span>
                      <span>Trades: <strong>{strat.trades}</strong></span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Aggr Charts Tab */}
        {tab === 'charts' && (
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
            }}>
              <LineChart size={15} />
              <span style={{ fontSize: 13, fontWeight: 700 }}>Aggr.trade Charts</span>
              <a
                href={aggrUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  marginLeft: 'auto', fontSize: 11, color: 'var(--accent-light)',
                  display: 'flex', alignItems: 'center', gap: 4, textDecoration: 'none',
                }}
              >
                Open Fullscreen <ExternalLink size={11} />
              </a>
            </div>
            <div style={{
              flex: 1, borderRadius: 'var(--radius)',
              border: '1px solid var(--border)', overflow: 'hidden',
              minHeight: 500, position: 'relative',
            }}>
              <iframe
                ref={aggrRef}
                src={aggrUrl}
                style={s.aggrFrame}
                title="Aggr Charts"
                onLoad={() => setAggrLoaded(true)}
                sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
              />
              {!aggrLoaded && (
                <div style={{
                  position: 'absolute', inset: 0, display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  background: 'var(--bg-primary)', color: 'var(--text-muted)', fontSize: 13,
                }}>
                  <RefreshCw size={18} style={{ animation: 'spin 1s linear infinite', marginRight: 8 }} />
                  Loading Aggr Charts…
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>

    {/* ── Chat Sidebar ── */}
    <div style={s.chatSide(chatOpen)}>
      <div style={s.chatHeader}>
        <MessageSquare size={14} style={{ color: 'var(--accent-light)' }} />
        <span style={{ fontSize: 12, fontWeight: 700 }}>Trading Chat</span>
        {streaming && (
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
            boxShadow: '0 0 6px rgba(34,197,94,.6)', marginLeft: 4,
          }} />
        )}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {messages?.length || 0} msgs
        </span>
      </div>

      <div style={s.chatMessages}>
        {(!messages || messages.length === 0) && (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            <div style={{ fontSize: 32, opacity: .3, marginBottom: 8 }}>📈</div>
            Ask the agent about markets, trades, or portfolio
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12, justifyContent: 'center' }}>
              {[
                'Portfolio status',
                'Analyze BTC',
                'Get signals',
                'Market overview',
                '🔮 Top Polymarket bets',
                '🔮 Best prediction opportunities',
              ].map((q, i) => (
                <button key={i} onClick={() => sendWithContext(q)} style={{
                  padding: '5px 10px', borderRadius: 99, fontSize: 10, fontWeight: 600,
                  border: '1px solid var(--border)', background: 'var(--bg-tertiary)',
                  color: 'var(--text-secondary)', cursor: 'pointer',
                }}>{q}</button>
              ))}
            </div>
          </div>
        )}
        {messages?.map((msg, i) => {
          // Strip injected Polymarket context from user messages for display
          const displayContent = msg.role === 'user' && msg.content?.includes('\n\n[POLYMARKET LIVE DATA')
            ? msg.content.split('\n\n[POLYMARKET LIVE DATA')[0]
            : msg.content;
          return (
          <div key={i} style={s.chatMsg(msg.role === 'user')}>
            <div style={s.chatAvatar(msg.role === 'user')}>
              {msg.role === 'user' ? '👤' : '🤖'}
            </div>
            <div>
              <div style={s.chatBubble(msg.role === 'user')}>
                {displayContent}
                {msg.role === 'user' && msg.content?.includes('[POLYMARKET LIVE DATA') && (
                  <span style={{ display: 'block', marginTop: 4, fontSize: 10, opacity: 0.5 }}>📊 + Polymarket data attached</span>
                )}
              </div>
              <div style={{ ...s.chatTime, textAlign: msg.role === 'user' ? 'right' : 'left' }}>
                {fmtTime(msg.ts)}
              </div>
            </div>
          </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>

      <form onSubmit={handleChatSend} style={s.chatInput}>
        <input
          style={s.chatInputField}
          value={chatInput}
          onChange={(e) => setChatInput(e.target.value)}
          onKeyDown={handleChatKey}
          placeholder={tab === 'polymarket' ? 'Ask about predictions, markets, probabilities…' : 'Ask about trading…'}
        />
        <button type="submit" style={s.chatSendBtn} title="Send">
          <Send size={14} />
        </button>
      </form>
    </div>
    </div>
  );
}
