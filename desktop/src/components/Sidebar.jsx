import React from 'react'
import { useSableStore } from '../hooks/useSable.js'

export default function Sidebar() {
  const sessions = useSableStore(s => s.sessions)
  const activeSessionId = useSableStore(s => s.activeSessionId)
  const wsStatus = useSableStore(s => s.wsStatus)
  const newChat = useSableStore(s => s.newChat)
  const selectSession = useSableStore(s => s.selectSession)
  const deleteSession = useSableStore(s => s.deleteSession)
  const openSettings = useSableStore(s => s.openSettings)
  const goHome = useSableStore(s => s.goHome)

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo" onClick={goHome} title="Home" style={{ cursor: 'pointer' }}>
          <img src="./logo.png" alt="Sable" />
        </div>
        <button className="new-chat-btn" onClick={newChat}>
          <span>＋</span>
          New chat
        </button>
      </div>

      {sessions.length > 0 && (
        <div className="sidebar-section-label">Recent</div>
      )}

      <div className="sessions-list">
        {sessions.map(session => (
          <div
            key={session.id}
            className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
            onClick={() => selectSession(session.id)}
          >
            <span className="session-icon">💬</span>
            <span className="session-title">{session.title || 'New chat'}</span>
            <button
              className="session-delete"
              onClick={(e) => { e.stopPropagation(); deleteSession(session.id) }}
              title="Delete"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'center' }}>
          <span className={`status-badge ${wsStatus}`}>
            <span style={{ fontSize: 8 }}>●</span>
            {wsStatus === 'connected' ? 'Connected' : wsStatus === 'connecting' ? 'Connecting…' : 'Disconnected'}
          </span>
        </div>
        <button className="settings-btn" onClick={openSettings}>
          <span>⚙</span>
          Settings
        </button>
      </div>
    </div>
  )
}
