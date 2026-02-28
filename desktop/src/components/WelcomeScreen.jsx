import React, { useRef, useState } from 'react'
import { useSableStore } from '../hooks/useSable.js'
import InputBar from './InputBar.jsx'

const SUGGESTIONS = [
  { icon: '✦', text: 'Tell me what you\'re thinking about right now' },
  { icon: '📊', text: 'Analyze the latest market trends for me' },
  { icon: '🐦', text: 'What should I post on X today?' },
  { icon: '🔍', text: 'Search for recent news about AI' },
  { icon: '💡', text: 'Give me your honest take on something' },
]

export default function WelcomeScreen({ wsStatus }) {
  const sendMessage = useSableStore(s => s.sendMessage)
  const tools = useSableStore(s => s.tools)
  const [input, setInput] = useState('')
  const textareaRef = useRef(null)

  const handleSuggestion = (text) => {
    sendMessage(text)
  }

  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        {/* Logo */}
        <div className="welcome-logo-wrap">
          <img src="./logo.png" alt="OpenSable" className="welcome-logo" />
        </div>

        {/* Tagline */}
        <p className="welcome-tagline">Your autonomous AI agent, ready to think, act, and create.</p>

        {/* Status badge */}
        <div className="welcome-status">
          <span className={`status-badge ${wsStatus}`}>
            <span style={{ fontSize: 8 }}>●</span>
            {wsStatus === 'connected'
              ? `Connected to SableCore${tools.length ? ` · ${tools.length} tools` : ''}`
              : wsStatus === 'connecting'
              ? 'Connecting to SableCore…'
              : 'Disconnected — check gateway'}
          </span>
        </div>

        {/* Suggestions */}
        <div className="welcome-suggestions">
          {SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              className="suggestion-btn"
              onClick={() => handleSuggestion(s.text)}
              disabled={wsStatus !== 'connected'}
            >
              <span className="suggestion-icon">{s.icon}</span>
              <span className="suggestion-text">{s.text}</span>
            </button>
          ))}
        </div>
      </div>

      <InputBar
        input={input}
        setInput={setInput}
        textareaRef={textareaRef}
        wsStatus={wsStatus}
        isWaiting={false}
        autoFocus={true}
      />
    </div>
  )
}

