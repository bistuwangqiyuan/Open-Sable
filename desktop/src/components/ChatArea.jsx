import React, { useRef, useEffect, useState, useCallback } from 'react'
import { useSableStore } from '../hooks/useSable.js'
import MessageBubble from './MessageBubble.jsx'
import WelcomeScreen from './WelcomeScreen.jsx'
import InputBar from './InputBar.jsx'

export default function ChatArea() {
  const activeSessionId = useSableStore(s => s.activeSessionId)
  const messages = useSableStore(s => s.messages)
  const streaming = useSableStore(s => s.streaming)
  const streamingSessionId = useSableStore(s => s.streamingSessionId)
  const streamingPhase = useSableStore(s => s.streamingPhase)
  const elapsed = useSableStore(s => s.elapsed)
  const agentProgress = useSableStore(s => s.agentProgress)
  const sessions = useSableStore(s => s.sessions)
  const wsStatus = useSableStore(s => s.wsStatus)

  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const currentMessages = (activeSessionId && messages[activeSessionId]) || []
  const isWaiting = streaming && streamingSessionId === activeSessionId
  const session = sessions.find(s => s.id === activeSessionId)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [currentMessages.length, isWaiting])

  // Welcome screen,  no session selected
  if (!activeSessionId) {
    return (
      <div className="chat-area">
        <WelcomeScreen wsStatus={wsStatus} />
      </div>
    )
  }

  // Elapsed counter label: "⏳ 12s · Thinking…" or "⚡ 47s · Responding…"
  const elapsedLabel = isWaiting
    ? `${streamingPhase === 'responding' ? '⚡' : '⏳'} ${elapsed}s`
    : null

  return (
    <div className="chat-area">
      <div className="chat-topbar">
        <span style={{ fontSize: 14, opacity: 0.5 }}>💬</span>
        <span className="chat-topbar-title">{session?.title || '对话'}</span>
        {isWaiting && (
          <span className={`agent-progress${streamingPhase === 'responding' ? ' responding' : ''}`}>
            <span className="agent-progress-dot" />
            {agentProgress || (streamingPhase === 'responding' ? '正在回复…' : '思考中…')}
            {elapsed > 0 && (
              <span className="elapsed-counter">{elapsedLabel}</span>
            )}
          </span>
        )}
      </div>

      <div className="messages">
        {currentMessages.length === 0 && !isWaiting && (
          <div className="empty-state" style={{ flex: 1, minHeight: 200 }}>
            <div className="empty-state-glyph" style={{ fontSize: 32 }}>✦</div>
            <p>对 Sable 说点什么吧…</p>
          </div>
        )}
        {currentMessages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isWaiting && currentMessages[currentMessages.length - 1]?.role !== 'assistant' && streamingPhase === 'thinking' && (
          <div className="message-row assistant">
            <div className="message-avatar assistant">S</div>
            <div className="typing-indicator">
              <div className="typing-dot" />
              <div className="typing-dot" />
              <div className="typing-dot" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <InputBar
        input={input}
        setInput={setInput}
        textareaRef={textareaRef}
        wsStatus={wsStatus}
        isWaiting={isWaiting}
        autoFocus={true}
      />
    </div>
  )
}
