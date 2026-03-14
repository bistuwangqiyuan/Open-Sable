import React, { useState, useRef, useEffect } from 'react'

const api = typeof window !== 'undefined' && window.sable ? window.sable : null

export default function DashboardPanel({ config, onClose }) {
  const httpBase = (config?.wsUrl || 'ws://localhost:8789')
    .replace(/^ws:\/\//, 'http://')
    .replace(/^wss:\/\//, 'https://')
    .replace(/\/+$/, '')

  const authUrl = (path) => {
    const base = `${httpBase}${path}`
    return config?.token ? `${base}?token=${encodeURIComponent(config.token)}` : base
  }

  const dashUrl = authUrl('/dashboard')
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const wvRef = useRef(null)

  // Attach webview events via ref (React doesn't support webview synthetic events)
  useEffect(() => {
    const wv = wvRef.current
    if (!wv) return
    const onFinish = () => setLoaded(true)
    const onFail = (e) => {
      // error code -3 is aborted navigation (e.g. redirect), not a real error
      if (e.errorCode && e.errorCode !== -3) setError(true)
    }
    wv.addEventListener('did-finish-load', onFinish)
    wv.addEventListener('did-fail-load', onFail)
    return () => {
      wv.removeEventListener('did-finish-load', onFinish)
      wv.removeEventListener('did-fail-load', onFail)
    }
  }, [])

  const openExternal = () => {
    if (api?.openExternal) {
      api.openExternal(dashUrl)
    } else {
      window.open(dashUrl, '_blank')
    }
  }

  const reload = () => {
    setError(false)
    setLoaded(false)
    wvRef.current?.reload()
  }

  return (
    <div className="dashboard-panel">
      <div className="dashboard-topbar">
        <div className="dashboard-topbar-left">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
            <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
            <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
          </svg>
          <span>代理仪表盘</span>
          <span className="dashboard-url-pill">{dashUrl}</span>
        </div>
        <div className="dashboard-topbar-right">
          <button className="dash-btn" onClick={openExternal} title="在浏览器打开">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="13" height="13">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            在浏览器打开
          </button>
          <button className="dash-btn dash-btn-close" onClick={onClose} title="关闭">
            ✕ 关闭
          </button>
        </div>
      </div>

      {error ? (
        <div className="dashboard-error">
          <div className="dashboard-error-icon">⚠</div>
          <div className="dashboard-error-title">无法访问仪表盘</div>
          <div className="dashboard-error-sub">请确认 SableCore 正在 <code>{httpBase}</code> 运行</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center' }}>
            <button className="btn btn-secondary" onClick={reload}>重试</button>
            <button className="btn btn-primary" onClick={openExternal}>在浏览器打开</button>
          </div>
        </div>
      ) : (
        <>
          {!loaded && (
            <div className="dashboard-loading">
              <div className="typing-indicator" style={{ margin: 'auto' }}>
                <div className="typing-dot"/><div className="typing-dot"/><div className="typing-dot"/>
              </div>
              <span>正在加载仪表盘…</span>
            </div>
          )}
          <webview
            ref={wvRef}
            className="dashboard-iframe"
            src={dashUrl}
            style={{ display: loaded ? 'flex' : 'none' }}
          />
        </>
      )}
    </div>
  )
}
