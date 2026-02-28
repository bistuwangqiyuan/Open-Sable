import React, { useState } from 'react'
import { useSableStore } from '../hooks/useSable.js'

export default function SettingsDialog() {
  const config = useSableStore(s => s.config)
  const closeSettings = useSableStore(s => s.closeSettings)
  const connect = useSableStore(s => s.connect)
  const setConfig = useSableStore(s => s.setConfig)
  const showToast = useSableStore(s => s.showToast)

  const [wsUrl, setWsUrl] = useState(config.wsUrl)
  const [token, setToken] = useState(config.token)

  const handleSave = () => {
    const newConfig = { wsUrl: wsUrl.trim(), token: token.trim() }
    setConfig(newConfig)
    connect(newConfig)
    showToast('Settings saved — reconnecting…')
    closeSettings()
  }

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) closeSettings()
  }

  return (
    <div className="overlay" onClick={handleOverlayClick}>
      <div className="modal">
        <div className="modal-header">
          <span className="modal-title">⚙ Settings</span>
          <button className="modal-close" onClick={closeSettings}>×</button>
        </div>

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
          <input
            className="form-input"
            type="password"
            value={token}
            onChange={e => setToken(e.target.value)}
            placeholder="WEBCHAT_TOKEN from .env"
          />
          <div className="form-hint">Matches WEBCHAT_TOKEN in your SableCore .env file</div>
        </div>

        <div className="form-group" style={{ marginBottom: 0 }}>
          <label className="form-label">About</label>
          <div style={{ fontSize: 12, color: 'var(--text-dim)', lineHeight: 1.7 }}>
            Sable Desktop connects directly to your local SableCore agent.<br/>
            All messages go through the WebSocket gateway — no external servers.
          </div>
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={closeSettings}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave}>Save &amp; Reconnect</button>
        </div>
      </div>
    </div>
  )
}
