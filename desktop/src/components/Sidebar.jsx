import React from 'react'
import { useSableStore } from '../hooks/useSable.js'

export default function Sidebar({ collapsed = false, onOpenDevStudio, onToggle }) {
  const sessions = useSableStore(s => s.sessions)
  const activeSessionId = useSableStore(s => s.activeSessionId)
  const wsStatus = useSableStore(s => s.wsStatus)
  const booting = useSableStore(s => s.booting)
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
        <div className="sidebar-header-row">
          <div className="sidebar-logo" onClick={goHome} title="首页" style={{ cursor: 'pointer' }}>
            <img src="./logo.png" alt="Sable" />
          </div>
          <button className="sidebar-close-btn" onClick={onToggle} title="收起侧边栏 (Ctrl+B)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>
        <button className="new-chat-btn" onClick={newChat}>
          <span>＋</span>
          新建对话
        </button>
      </div>

      {agents.length > 1 && (
        <>
          <div className="sidebar-section-label">代理</div>
          <div className="agent-selector">
            {agents.map(agent => (
              <button
                key={agent.name}
                className={`agent-btn${activeAgent === agent.name ? ' active' : ''}${!agent.running ? ' offline' : ''}`}
                onClick={() => selectAgent(agent.name)}
                title={agent.running ? agent.name : `${agent.name}（离线）`}
              >
                <span className={`agent-dot${agent.running ? ' online' : ''}`} />
                <span className="agent-name">{agent.name}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {sessions.length > 0 && (
        <div className="sidebar-section-label">最近会话</div>
      )}

      <div className="sessions-list">
        {sessions.map(session => (
          <div
            key={session.id}
            className={`session-item ${activeSessionId === session.id ? 'active' : ''}`}
            onClick={() => selectSession(session.id)}
          >
            <span className="session-icon">💬</span>
            <span className="session-title">{session.title || '新建对话'}</span>
            <button
              className="session-delete"
              onClick={(e) => { e.stopPropagation(); deleteSession(session.id) }}
              title="删除"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'center' }}>
          <span className={`status-badge ${booting ? 'connecting' : wsStatus}`}>
            <span style={{ fontSize: 8 }}>●</span>
            {wsStatus === 'connected' ? '已连接' : booting ? '启动中…' : wsStatus === 'connecting' ? '连接中…' : '已断开'}
          </span>
        </div>
        <button className="settings-btn dev-studio-btn" onClick={onOpenDevStudio} title="开发工作台 (Ctrl+Shift+D)">
          <span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
          </span>
          开发工作台
        </button>
        <button className="settings-btn" onClick={openSettings}>
          <span>⚙</span>
          设置
        </button>
      </div>
    </div>
  )
}
