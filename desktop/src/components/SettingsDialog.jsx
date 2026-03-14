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
  models: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" width="14" height="14">
      <path d="M12 2a7 7 0 0 0-7 7c0 2.38 1.19 4.47 3 5.74V17a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2v-2.26c1.81-1.27 3-3.36 3-5.74a7 7 0 0 0-7-7z"/>
      <line x1="10" y1="21" x2="14" y2="21"/>
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
  const modelGroups  = useSableStore(s => s.modelGroups)
  const requestModels = useSableStore(s => s.requestModels)
  const switchModel  = useSableStore(s => s.switchModel)
  const importGGUF   = useSableStore(s => s.importGGUF)

  const [tab, setTab]     = useState('connection')
  const [wsUrl, setWsUrl] = useState(config.wsUrl)
  const [token, setToken] = useState(config.token)
  const [showToken, setShowToken] = useState(false)
  const [ggufPath, setGgufPath] = useState('')
  const [ggufName, setGgufName] = useState('')

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
    showToast('设置已保存，正在重连…')
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
          <span className="modal-title">⚙ 设置</span>
          <button className="modal-close" onClick={closeSettings}>×</button>
        </div>

        {/* ── Tabs ───────────────────────────────────────────── */}
        <div className="settings-tabs">
          {[
            { id: 'connection', label: '连接' },
            { id: 'models',     label: '模型'     },
            { id: 'dashboard',  label: '仪表盘'  },
            { id: 'preferences',label: '偏好'},
            { id: 'about',      label: '关于'      },
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
              <label className="form-label">SableCore 网关地址</label>
              <input
                className="form-input"
                value={wsUrl}
                onChange={e => setWsUrl(e.target.value)}
                placeholder="ws://localhost:8789"
              />
              <div className="form-hint">你的 SableCore 实例 WebSocket 地址</div>
            </div>

            <div className="form-group">
              <label className="form-label">鉴权令牌</label>
              <div className="input-with-action">
                <input
                  className="form-input"
                  type={showToken ? 'text' : 'password'}
                  value={token}
                  onChange={e => setToken(e.target.value)}
                  placeholder=".env 中的 WEBCHAT_TOKEN"
                />
                <button
                  className="input-peek-btn"
                  onClick={() => setShowToken(v => !v)}
                  title={showToken ? '隐藏令牌' : '显示令牌'}
                >
                  {showToken ? '🙈' : '👁'}
                </button>
              </div>
              <div className="form-hint">需与你 SableCore .env 的 WEBCHAT_TOKEN 一致</div>
            </div>

            <div className="settings-info-row">
              <div className="settings-info-dot connected" />
              <span>HTTP endpoint: <code>{httpBase}</code></span>
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={closeSettings}>取消</button>
              <button className="btn btn-primary" onClick={handleSave}>保存并重连</button>
            </div>
          </div>
        )}

        {/* ── Tab: Dashboard ─────────────────────────────────── */}        {tab === 'models' && (
          <div className="settings-tab-content">
            <div className="form-group">
              <label className="form-label">当前模型</label>
              <div className="form-hint" style={{ marginBottom: 12 }}>
                {agentModel || '未选择模型'}
                {agentModel && <span style={{ color: '#22c55e', marginLeft: 8 }}>● 已激活</span>}
              </div>
            </div>

            {/* List available models by group */}
            {(modelGroups || []).map(group => (
              <div key={group.provider} className="form-group">
                <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {group.name}
                  <span style={{ fontWeight: 400, opacity: 0.6 }}>({group.models?.length || 0})</span>
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {(group.models || []).map(m => (
                    <div
                      key={m.name}
                      onClick={() => { if (m.name !== agentModel) switchModel(m.name, group.provider) }}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8, padding: '6px 10px',
                        borderRadius: 6, cursor: 'pointer', fontSize: 12,
                        background: m.name === agentModel ? 'rgba(124,58,237,.1)' : 'var(--surface-2, rgba(255,255,255,.03))',
                        border: `1px solid ${m.name === agentModel ? 'var(--accent, #7c3aed)' : 'transparent'}`,
                      }}
                    >
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: m.name === agentModel ? '#22c55e' : 'transparent',
                        border: m.name === agentModel ? 'none' : '1px solid var(--border)',
                      }} />
                      <span style={{ flex: 1 }}>{m.name}</span>
                      {m.name === agentModel && <span style={{ fontSize: 10, color: '#22c55e' }}>当前</span>}
                    </div>
                  ))}
                </div>
              </div>
            ))}

            {(!modelGroups || modelGroups.length === 0) && (
              <div className="form-hint" style={{ textAlign: 'center', padding: '20px 0' }}>
                暂无可用模型。请启动 Ollama 或在 .env 中配置 API Key
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn btn-secondary" onClick={requestModels}>↻ 刷新模型</button>
            </div>

            {/* GGUF Import */}
            <div className="gguf-import-section">
              <div className="gguf-import-title">
                📥 导入 GGUF 模型
              </div>
              <div className="gguf-import-row">
                <input
                  className="gguf-import-input"
                  value={ggufPath}
                  onChange={e => setGgufPath(e.target.value)}
                  placeholder="/path/to/model.gguf（例如 ~/Downloads/Qwen3.5-9B-Q4_K_M.gguf）"
                />
              </div>
              <div className="gguf-import-row">
                <input
                  className="gguf-import-input"
                  value={ggufName}
                  onChange={e => setGgufName(e.target.value)}
                  placeholder="模型名（可选，默认从文件名推断）"
                />
                <button
                  className="gguf-import-btn"
                  disabled={!ggufPath.trim()}
                  onClick={() => {
                    importGGUF(ggufPath.trim(), ggufName.trim())
                    setGgufPath('')
                    setGgufName('')
                  }}
                >
                  导入
                </button>
              </div>
              <div className="gguf-import-hint">
                将 .gguf 文件导入 Ollama，像普通模型一样使用。
                支持 HuggingFace、TheBloke 等来源模型。
                文件保留在本地磁盘，Ollama 仅创建引用。
              </div>
            </div>
          </div>
        )}

        {/* ── Tab: Dashboard (original) ───────────────────── */}        {tab === 'dashboard' && (
          <div className="settings-tab-content">
            <div className="dashboard-links-grid">
              <button className="dash-link-card" onClick={openDashboard}>
                <div className="dash-link-icon">🧠</div>
                <div className="dash-link-body">
                  <div className="dash-link-title">代理仪表盘</div>
                  <div className="dash-link-sub">完整代理控制台：记忆、工具、交易等</div>
                </div>
                <div className="dash-link-arrow">→</div>
              </button>

              <button className="dash-link-card" onClick={openMonitor}>
                <div className="dash-link-icon">📊</div>
                <div className="dash-link-body">
                  <div className="dash-link-title">监控面板</div>
                  <div className="dash-link-sub">实时查看思考、情绪、X 自动发帖状态</div>
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
                  <div className="dash-link-title">打开仪表盘并关闭设置</div>
                  <div className="dash-link-sub">在系统浏览器打开（自动带令牌）</div>
                </div>
                <div className="dash-link-arrow">↗</div>
              </button>
            </div>

            <div className="form-group" style={{ marginTop: 16 }}>
              <label className="form-label">仪表盘地址</label>
              <div className="copy-row">
                <input className="form-input" readOnly value={authUrl('/dashboard')} />
                <button
                  className="copy-btn"
                  onClick={() => {
                    navigator.clipboard.writeText(authUrl('/dashboard'))
                    showToast('链接已复制！')
                  }}
                >复制</button>
              </div>
              <div className="form-hint">在主窗口按 Ctrl+D 可切换内嵌仪表盘</div>
            </div>
          </div>
        )}

        {/* ── Tab: Preferences ────────────────────────────────── */}
        {tab === 'preferences' && (
          <div className="settings-tab-content">
            <div className="pref-section-label">界面</div>

            <div className="pref-row">
              <div className="pref-row-info">
                <div className="pref-row-title">默认折叠侧边栏</div>
                <div className="pref-row-sub">启动时隐藏会话列表，可随时按 Ctrl+B 切换。</div>
              </div>
              <label className="pref-toggle">
                <input
                  type="checkbox"
                  checked={localStorage.getItem('sable-sidebar') === 'collapsed'}
                  onChange={e => {
                    localStorage.setItem('sable-sidebar', e.target.checked ? 'collapsed' : 'open')
                    showToast('将在下次启动时生效')
                  }}
                />
                <span className="pref-toggle-track" />
              </label>
            </div>

            <div className="pref-section-label" style={{ marginTop: 16 }}>快捷键</div>

            <div className="shortcuts-grid">
              {[
                ['Ctrl+N', '新建对话'],
                ['Ctrl+B', '切换侧边栏'],
                ['Ctrl+D', '切换仪表盘'],
                ['Enter', '发送消息'],
                ['Shift+Enter', '消息内换行'],
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
                {!agentVersion && !agentModel ? '正在连接 SableCore…' : ''}
              </div>
            </div>
            <div className="about-features">
              {[
                ['🧠', '具备持久记忆和自我反思的自治代理'],
                ['🔒', '完全本地运行，数据不离开你的机器'],
                ['🔧', `通过 SableCore 网关可用工具：${tools?.length ?? 0} 个`],
                ['🎯', '意图驱动桌面控制：截图、点击、输入、快捷键'],
                ['📈', '交易工具、行情流、X 自动发帖与网页搜索'],
                ['🔍', '代码库 RAG，结合项目上下文进行代码协作'],
                ['🎤', '语音输入、文件附件、图片理解'],
              ].map(([icon, text]) => (
                <div key={text} className="about-feature-row">
                  <span className="about-feature-icon">{icon}</span>
                  <span>{text}</span>
                </div>
              ))}
            </div>
            <div className="about-footer">
              网关：<code>{httpBase || '未配置'}</code>
              {config?.token ? ' · 令牌已启用' : ' · 未配置令牌'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
