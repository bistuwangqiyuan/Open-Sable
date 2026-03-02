import React, { useEffect, useCallback, useState, useRef } from 'react'

// ─── Sun / Moon SVG icons for the theme toggle ────────────────────────────
const SunIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="4"/>
    <line x1="12" y1="2" x2="12" y2="5"/>
    <line x1="12" y1="19" x2="12" y2="22"/>
    <line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/>
    <line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/>
    <line x1="2" y1="12" x2="5" y2="12"/>
    <line x1="19" y1="12" x2="22" y2="12"/>
    <line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/>
    <line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/>
  </svg>
)
const MoonIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
)
import { useSableStore } from './hooks/useSable.js'
import Sidebar from './components/Sidebar.jsx'
import ChatArea from './components/ChatArea.jsx'
import SettingsDialog from './components/SettingsDialog.jsx'
import DashboardPanel from './components/DashboardPanel.jsx'
import DevStudioPanel from './components/DevStudioPanel.jsx'

// ─── Window control helpers ────────────────────────────────────────────────
const api = typeof window !== 'undefined' && window.sable ? window.sable : null

export default function App() {
  const connect = useSableStore(s => s.connect)
  const setConfig = useSableStore(s => s.setConfig)
  const config = useSableStore(s => s.config)
  const settingsOpen = useSableStore(s => s.settingsOpen)
  const toast = useSableStore(s => s.toast)
  const newChat = useSableStore(s => s.newChat)

  // ── Theme: dark (default) / light ─────────────────────────────────────────
  const [isDark, setIsDark] = useState(
    () => localStorage.getItem('sable-theme') !== 'light'
  )
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem('sable-sidebar') === 'collapsed'
  )
  const [dashboardOpen, setDashboardOpen] = useState(false)
  const [devStudioOpen, setDevStudioOpen] = useState(false)

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed(v => {
      const next = !v
      localStorage.setItem('sable-sidebar', next ? 'collapsed' : 'open')
      return next
    })
  }, [])
  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.remove('light-theme')
    } else {
      document.documentElement.classList.add('light-theme')
    }
    localStorage.setItem('sable-theme', isDark ? 'dark' : 'light')
  }, [isDark])

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
    if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
      e.preventDefault()
      toggleSidebar()
    }
    // Ctrl+Shift+D → Dev Studio (check first — more specific)
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'd') {
      e.preventDefault()
      setDevStudioOpen(v => !v)
      setDashboardOpen(false)
      return
    }
    // Ctrl+D → Dashboard
    if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'd') {
      e.preventDefault()
      setDashboardOpen(v => !v)
      setDevStudioOpen(false)
    }
  }, [newChat, toggleSidebar])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])

  return (
    <div className="app">
      {/* ── Titlebar ─────────────────────────────────────────────────────── */}
      <div className="titlebar">
        <div className="titlebar-left">
          <button
            className="sidebar-toggle-btn"
            onClick={toggleSidebar}
            title={sidebarCollapsed ? 'Show sidebar (Ctrl+B)' : 'Hide sidebar (Ctrl+B)'}
            style={{ WebkitAppRegion: 'no-drag' }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
              {sidebarCollapsed
                ? <><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></>
                : <><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="3" x2="9" y2="21"/></>
              }
            </svg>
          </button>
          <div className="titlebar-status">
            <div className="titlebar-status-dot" />
            SableCore
          </div>
        </div>

        {/* ── Day / Night toggle ──────────────────────────────────────── */}
        <div className="theme-toggle" style={{ WebkitAppRegion: 'no-drag' }}>
          <input
            type="checkbox"
            id="theme-check"
            checked={!isDark}
            onChange={() => setIsDark(d => !d)}
          />
          <label
            htmlFor="theme-check"
            className="theme-toggle-label"
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            <div className="theme-box">
              <div className="theme-ball" />
              <div className="theme-scenary">
                <span className="theme-icon theme-moon"><MoonIcon /></span>
                <span className="theme-icon theme-sun"><SunIcon /></span>
              </div>
            </div>
          </label>
        </div>

        <div className="titlebar-actions" style={{ WebkitAppRegion: 'no-drag' }}>
          <button
            className={`titlebar-btn ${devStudioOpen ? 'active' : ''}`}
            title="Dev Studio (Ctrl+Shift+D)"
            onClick={() => { setDevStudioOpen(v => !v); setDashboardOpen(false) }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="13" height="13">
              <polyline points="16 18 22 12 16 6" />
              <polyline points="8 6 2 12 8 18" />
            </svg>
          </button>
          <button
            className={`titlebar-btn ${dashboardOpen ? 'active' : ''}`}
            title="Agent Dashboard (Ctrl+D)"
            onClick={() => { setDashboardOpen(v => !v); setDevStudioOpen(false) }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="13" height="13">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
            </svg>
          </button>
          <button className="titlebar-btn" title="Minimize" onClick={() => api?.minimize()}>—</button>
          <button className="titlebar-btn" title="Maximize" onClick={() => api?.maximize()}>□</button>
          <button className="titlebar-btn close" title="Close" onClick={() => api?.close()}>✕</button>
        </div>
      </div>

      {/* ── Main content ─────────────────────────────────────────────────── */}
      <div className="main">
        <Sidebar collapsed={sidebarCollapsed} onOpenDevStudio={() => { setDevStudioOpen(true); setDashboardOpen(false) }} />
        {devStudioOpen
          ? <DevStudioPanel onClose={() => setDevStudioOpen(false)} />
          : dashboardOpen
            ? <DashboardPanel config={config} onClose={() => setDashboardOpen(false)} />
            : <ChatArea />
        }
      </div>

      {/* ── Modals / overlays ────────────────────────────────────────────── */}
      {settingsOpen && <SettingsDialog />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
