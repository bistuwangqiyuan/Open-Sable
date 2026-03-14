import React, { useRef, useState } from 'react'
import { useSableStore } from '../hooks/useSable.js'
import InputBar from './InputBar.jsx'

const ChatIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
  </svg>
)
const ChartIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <line x1="18" y1="20" x2="18" y2="10"/>
    <line x1="12" y1="20" x2="12" y2="4"/>
    <line x1="6" y1="20" x2="6" y2="14"/>
  </svg>
)
const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" width="14" height="14">
    <path d="M4 4l16 16M4 20L20 4"/>
  </svg>
)
const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" width="14" height="14">
    <circle cx="11" cy="11" r="8"/>
    <line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
)
const BulbIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <path d="M9 18h6M10 22h4M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"/>
  </svg>
)
const CodeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="14" height="14">
    <polyline points="16 18 22 12 16 6"/>
    <polyline points="8 6 2 12 8 18"/>
  </svg>
)

const SUGGESTIONS = [
  { icon: <ChatIcon />,   text: '你现在最想解决什么问题？' },
  { icon: <ChartIcon />,  text: '分析最新市场趋势' },
  { icon: <XIcon />,      text: '今天我在 X 上该发什么？' },
  { icon: <SearchIcon />, text: '搜索近期热点新闻' },
  { icon: <BulbIcon />,   text: '给我一个直截了当的判断' },
  { icon: <CodeIcon />,   text: '帮我写代码或做代码评审' },
]

export default function WelcomeScreen({ wsStatus }) {
  const sendMessage = useSableStore(s => s.sendMessage)
  const tools      = useSableStore(s => s.tools)
  const activeAgent = useSableStore(s => s.activeAgent)
  const booting    = useSableStore(s => s.booting)
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)

  const agentLabel = activeAgent ? activeAgent.charAt(0).toUpperCase() + activeAgent.slice(1) : 'Sable'

  return (
    <div className="welcome-screen">
      <div className="welcome-content">

        {/* ── Logo + headline ─────────────────────────────────────── */}
        <div className="welcome-hero">
          <img src="./logo.png" alt="OpenSable" className="welcome-logo" />
          <h1 className="welcome-title">我可以帮你做什么？</h1>
          <div className="welcome-status">
            <span className={`status-badge ${wsStatus}`}>
              <span style={{ fontSize: 8 }}>●</span>
              {wsStatus === 'connected'
                ? `${agentLabel} · ${tools.length} 个工具可用`
                : booting
                ? '启动中…'
                : wsStatus === 'connecting'
                ? '连接中…'
                : '连接断开，请检查网关'}
            </span>
          </div>
        </div>

        {/* ── Big input,  first, like Claude ────────────────────── */}
        <div className="welcome-input-wrap">
          <InputBar
            input={input}
            setInput={setInput}
            textareaRef={textareaRef}
            wsStatus={wsStatus}
            isWaiting={false}
            autoFocus={true}
          />
        </div>

        {/* ── Suggestion chip grid ───────────────────────────────── */}
        <div className="welcome-suggestions">
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              className="suggestion-btn"
              onClick={() => sendMessage(s.text)}
              disabled={wsStatus !== 'connected'}
            >
              <span className="suggestion-icon">{s.icon}</span>
              <span className="suggestion-text">{s.text}</span>
            </button>
          ))}
        </div>

      </div>
    </div>
  )
}

