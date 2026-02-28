import React, { useState } from 'react'
import { useSableStore } from '../hooks/useSable.js'

const api = typeof window !== 'undefined' && window.sable ? window.sable : null

const TAB_ICONS = {
  connection: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
      <path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/>
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>
    </svg>
  ),
  dashboard: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
      <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
    </svg>
  ),
  preferences: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
      <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
      <path d="M4.93 4.93a10 10 0 0 0 0 14.14"/>
    </svg>
  ),
  about: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  ),
}

export default function SettingsDialog() {
  const config       = useSableStore(s => s.config)
  const closeSettings = useSableStore(s => s.closeSettings)
  const connect      = useSableStore(s => s.connect)
  const setConfig    = useSableStore(s => s.setConfig)
  const showToast    = useSableStore(s => s.showToast)
  const agentModel   = useSableStore(s => s.agentModel)
  const agentVersion = useSableStore(s => s.agentVersion)
  const tools        = useSableStore(s => s.tools)

  const [tab, setTab]     = useState('connection')
  const [wsUrl, setWsUrl] = useState(config.wsUrl)
  const [token, setToken] = useState(config.token)
  const [showToken, setShowToken] = useState(false)

  const httpBase = (config?.wsUrl || 'ws://localhost:8789')
    .replace(/^ws:\/\//, 'http://')
    .replace(/^wss:\/\//, 'https://')
    .replace(/\/+$/, '')

  // Build authenticated URL helper
  const authUrl = (path) => {
    const base = `${httpBase}${path}`
    return config?.token ? `${base}?token=${encodeURIComponent(config.token)}` : base
  }

  const handleSave = () => {
    const newConfig = { wsUrl: wsUrl.trim(), token: token.trim() }
    setConfig(newConfig)
    connect(newConfig)
    showToast('Settings saved — reconnecting…')
    closeSettings()
  }

  const openDashboard = () => {
    const url = authUrl('/dashboard')
    if (api?.openExternal) api.openExternal(url)
    else window.open(url, '_blank')
  }

  const openMonitor = () => {
    const url = authUrl('/monitor')
    if (api?.openExternal) api.openExternal(url)
    else window.open(url, '_blank')
  }

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) closeSettings()
  }

  return (
    <div className="overlay" onClick={handleOverlayClick}>
      <div className="modal modal-wide">
        <div className="modal-header">
          <span className="modal-title">⚙ Settings</span>
          <button className="modal-close" onClick={closeSettings}>×</button>
        </div>

        {/* ── Tabs ───────────────────────────────────────────── */}
        <div className="settings-tabs">
          {[
            { id: 'connection', label: 'Connection' },
            { id: 'dashboard',  label: 'Dashboard'  },
            { id: 'preferences',label: 'Preferences'},
            { id: 'about',      label: 'About'      },
          ].map(t => (
            <button
              key={t.id}
              className={`settings-tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {TAB_ICONS[t.id]}
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab: Connection ────────────────────────────────── */}
        {tab === 'connection' && (
          <div className="settings-tab-content">
            <div className="form-group">
              <label className="form-label">SableCore Gateway URL</label>
              <input
                className="form-input"
                value={wsUrl}
                onChange={e => setWsUrl(e.target.value)}
                placeholder="ws://localhost:8789"
              />
              <div className="form-hint">WebSocket address of your SableCore instance</div>
            </div>

            <div className="form-group">
              <label className="form-label">Auth Token</label>
              <div className="input-with-action">
                <input
                  className="form-input"
                  type={showToken ? 'text' : 'password'}
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  placeholder="WEBCHAT_TOKEN from .env"
                />
                <button
                  className="input-peek-btn"
                  onClick={() => setShowToken(v => !v)}
                  title={showToken ? 'Hide token' : 'Show token'}
                >
                  {showToken ? '🙈' : '👁'}
                </button>
              </div>
              <div className="form-hint">Matches WEBCHAT_TOKEN in your SableCore .env</div>
            </div>

            <div className="settings-info-row">
              <div className="settings-info-dot connected" />
              <span>HTTP endpoint: <code>{httpBase}</code></span>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={closeSettings}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave}>Save &amp; Reconnect</button>
            </div>
          </div>
        )}

        {/* ── Tab: Dashboard ─────────────────────────────────── */}
        {tab === 'dashboard' && (
          <div className="settings-tab-content">
            <div className="dashboard-links-grid">
              <button className="dash-link-card" onClick={openDashboard}>
                <div className="dash-link-icon">🧠</div>
                <div className="dash-link-body">
                  <div className="dash-link-title">Agent Dashboard</div>
                  <div className="dash-link-sub">Full agent control panel, memory, tools, trading</div>
                </div>
                <div className="dash-link-arrow">→</div>
              </button>

              <button className="dash-link-card" onClick={openMonitor}>
                <div className="dash-link-icon">📊</div>
                <div className="dash-link-body">
                  <div className="dash-link-title">Monitor</div>
                  <div className="dash-link-sub">Live agent thoughts, emotion, X autoposter status</div>
                </div>
                <div className="dash-link-arrow">→</div>
              </button>

              <button className="dash-link-card" onClick={() => {
                const url = authUrl('/dashboard')
                if (api?.openExternal) api.openExternal(url)
                closeSettings()
              }}>
                <div className="dash-link-icon">📋</div>
                <div className="dash-link-body">
                  <div className="dash-link-title">Open Dashboard &amp; Close Settings</div>
                  <div className="dash-link-sub">Opens in system browser with token pre-loaded</div>
                </div>
                <div className="dash-link-arrow">↗</div>
              </button>
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label className="form-label">Dashboard URL</label>
              <div className="copy-row">
                <input className="form-input" readOnly value={authUrl('/dashboard')} />
                <button
                  className="copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(authUrl('/dashboard'))
                    showToast('URL copied!')
                  }}
                >Copy</button>
              </div>
              <div className="form-hint">Use Ctrl+D in the main window to toggle the embedded dashboard</div>
            </div>
          </div>
        )}

        {/* ── Tab: Preferences ────────────────────────────────── */}
        {tab === 'preferences' && (
          <div className="settings-tab-content">
            <div className="pref-section-label">Interface</div>

            <div className="pref-row">
              <div className="pref-row-info">
                <div className="pref-row-title">Compact sidebar by default</div>
                <div className="pref-row-sub">Start with the conversation list hidden. Toggle anytime with Ctrl+B.</div>
              </div>
              <label className="pref-toggle">
                <input
                  type="checkbox"
                  checked={localStorage.getItem('sable-sidebar') === 'collapsed'}
                  onChange={e => {
                    localStorage.setItem('sable-sidebar', e.target.checked ? 'collapsed' : 'open')
                    showToast('Applies on next launch')
                  }}
                />
                <span className="pref-toggle-track" />
              </label>
            </div>

            <div className="pref-section-label" style={{ marginTop: 16 }}>Keyboard shortcuts</div>

            <div className="shortcuts-grid">
              {[
                ['Ctrl+N', 'New chat'],
                ['Ctrl+B', 'Toggle sidebar'],
                ['Ctrl+D', 'Toggle dashboard'],
                ['Enter', 'Send message'],
                ['Shift+Enter', 'New line in message'],
              ].map(([key, desc]) => (
                <div key={key} className="shortcut-row">
                  <kbd className="kbd">{key}</kbd>
                  <span>{desc}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Tab: About ──────────────────────────────────────── */}
        {tab === 'about' && (
          <div className="settings-tab-content">
            <div className="about-hero">
              <img src="./logo.png" alt="OpenSable" style={{ height: 48, marginBottom: 12 }} />
              <div className="about-name">Sable Desktop</div>
              <div className="about-version">
                {agentVersion ? `v${agentVersion}` : ''}{agentModel ? `, ${agentModel}` : ''}
                {!agentVersion && !agentModel ? 'Connecting to SableCore…' : ''}
              </div>
            </div>
            <div className="about-features">
              {[
                ['🧠', 'Autonomous agent with persistent memory and self-reflection'],
                ['🔒', 'Fully local, your data never leaves this machine'],
                ['🔧', `${tools?.length ?? 0} tools available via SableCore gateway`],
                ['🎯', 'Intent-driven desktop control: screenshot, click, type, hotkeys'],
                ['📈', 'Trading tools, market feeds, X autoposter, and web search'],
                ['🔍', 'Codebase RAG, self-aware code assistance over your project'],
                ['🎤', 'Voice input, file attachments, image understanding'],
              ].map(([icon, text]) => (
                <div key={text} className="about-feature-row">
                  <span className="about-feature-icon">{icon}</span>
                  <span>{text}</span>
                </div>
              ))}
            </div>
            <div className="about-footer">
              Gateway: <code>{httpBase || 'not configured'}</code>
              {config?.token ? ' · auth token active' : ' · no auth token'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
