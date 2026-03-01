import React from 'react'
import { useSableStore } from '../hooks/useSable.js'

export default function Sidebar({ collapsed = false }) {
  const sessions = useSableStore(s => s.sessions)
  const activeSessionId = useSableStore(s => s.activeSessionId)
  const wsStatus = useSableStore(s => s.wsStatus)
  const newChat = useSableStore(s => s.newChat)
  const selectSession = useSableStore(s => s.selectSession)
  const deleteSession = useSableStore(s => s.deleteSession)
  const openSettings = useSableStore(s => s.openSettings)
  const goHome = useSableStore(s => s.goHome)
  const agents = useSableStore(s => s.agents)
  const activeAgent = useSableStore(s => s.activeAgent)
  const selectAgent = useSableStore(s => s.selectAgent)

  return (
    <div className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo" onClick={goHome} title="Home" style={{ cursor: 'pointer' }}>
          <img src="./logo.png" alt="Sable" />
        </div>
        <button className="new-chat-btn" onClick={newChat}>
          <span>＋</span>
          New chat
        </button>
      </div>

      {agents.length > 1 && (
        <>
          <div className="sidebar-section-label">Agent</div>
          <div className="agent-selector">
            {agents.map(agent => (
              <button
                key={agent.name}
                className={`agent-btn${activeAgent === agent.name ? ' active' : ''}${!agent.running ? ' offline' : ''}`}
                onClick={() => selectAgent(agent.name)}
                title={agent.running ? agent.name : `${agent.name} (offline)`}
              >
                <span className={`agent-dot${agent.running ? ' online' : ''}`} />
                <span className="agent-name">{agent.name}</span>
              </button>
            ))}
          </div>
        </>
      )}

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
