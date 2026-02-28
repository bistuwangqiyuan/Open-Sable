import React, { useEffect, useCallback } from 'react'
import { useSableStore } from './hooks/useSable.js'
import Sidebar from './components/Sidebar.jsx'
import ChatArea from './components/ChatArea.jsx'
import SettingsDialog from './components/SettingsDialog.jsx'

// ─── Window control helpers ────────────────────────────────────────────────
const api = typeof window !== 'undefined' && window.sable ? window.sable : null

export default function App() {
  const connect = useSableStore(s => s.connect)
  const setConfig = useSableStore(s => s.setConfig)
  const config = useSableStore(s => s.config)
  const settingsOpen = useSableStore(s => s.settingsOpen)
  const toast = useSableStore(s => s.toast)
  const newChat = useSableStore(s => s.newChat)

  // ── Init: load config from Electron then connect ──────────────────────────
  useEffect(() => {
    const init = async () => {
      if (api?.getConfig) {
        try {
          const cfg = await api.getConfig()
          setConfig(cfg)
          connect(cfg)
        } catch {
          connect(config)
        }
      } else {
        // Running in browser preview — connect with defaults
        connect(config)
      }
    }
    init()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Keyboard shortcuts ────────────────────────────────────────────────────
  const handleKeyDown = useCallback((e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault()
      newChat()
    }
  }, [newChat])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="app">
      {/* ── Titlebar ─────────────────────────────────────────────────────── */}
      <div className="titlebar">
        <div className="titlebar-status">
          <div className="titlebar-status-dot" />
          SableCore
        </div>
        <div className="titlebar-actions">
          <button className="titlebar-btn" title="Minimize" onClick={() => api?.minimize()}>—</button>
          <button className="titlebar-btn" title="Maximize" onClick={() => api?.maximize()}>□</button>
          <button className="titlebar-btn close" title="Close" onClick={() => api?.close()}>✕</button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="main">
        <Sidebar />
        <ChatArea />
      </div>

      {/* ── Modals / overlays ────────────────────────────────────────────── */}
      {settingsOpen && <SettingsDialog />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
