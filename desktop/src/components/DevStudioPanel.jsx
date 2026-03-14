import React, { useState, useRef, useEffect } from 'react'

const api = typeof window !== 'undefined' && window.sable ? window.sable : null

// Code / IDE icon
const CodeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <polyline points="16 18 22 12 16 6" />
    <polyline points="8 6 2 12 8 18" />
  </svg>
)

export default function DevStudioPanel({ onClose }) {
  const devUrl = 'http://localhost:5700'
  const [loaded, setLoaded] = useState(false)
  const [error, setError] = useState(false)
  const wvRef = useRef(null)

  useEffect(() => {
    const wv = wvRef.current
    if (!wv) return
    const onFinish = () => setLoaded(true)
    const onFail = (e) => {
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
      api.openExternal(devUrl)
    } else {
      window.open(devUrl, '_blank')
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
          <CodeIcon />
          <span>开发工作台</span>
          <span className="dashboard-url-pill">{devUrl}</span>
        </div>
        <div className="dashboard-topbar-right">
          <button className="dash-btn" onClick={openExternal} title="在浏览器打开">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="13" height="13">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
            在浏览器打开
          </button>
          <button className="dash-btn" onClick={reload} title="重新加载">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="13" height="13">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            重新加载
          </button>
          <button className="dash-btn dash-btn-close" onClick={onClose} title="关闭">
            ✕ 关闭
          </button>
        </div>
      </div>

      {error ? (
        <div className="dashboard-error">
          <div className="dashboard-error-icon">⚠</div>
          <div className="dashboard-error-title">无法访问开发工作台</div>
          <div className="dashboard-error-sub">
            请确认 Sable Dev 正在 <code>{devUrl}</code> 运行
            <br />
            <code style={{ fontSize: 11, marginTop: 4, display: 'inline-block' }}>
              cd sable_dev && npm run dev
            </code>
          </div>
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
              <span>正在加载开发工作台…</span>
            </div>
          )}
          <webview
            ref={wvRef}
            className="dashboard-iframe"
            src={devUrl}
            style={{ display: loaded ? 'flex' : 'none' }}
          />
        </>
      )}
    </div>
  )
}
