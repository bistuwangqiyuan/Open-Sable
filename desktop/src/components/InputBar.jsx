import React, { useRef, useState, useEffect } from 'react'
import { useSableStore } from '../hooks/useSable.js'

// Shared input bar used in both WelcomeScreen and ChatArea
export default function InputBar({ input, setInput, textareaRef, wsStatus, isWaiting = false, autoFocus = false }) {
  const sendMessage = useSableStore(s => s.sendMessage)
  const fileInputRef = useRef(null)
  const [isRecording, setIsRecording] = useState(false)
  const [attachments, setAttachments] = useState([]) // { name, content, type, size }
  const recognitionRef = useRef(null)

  const canSend = input.trim().length > 0 && !isWaiting && wsStatus === 'connected'
  const disabled = wsStatus !== 'connected'

  // Auto-grow textarea
  useEffect(() => {
    const ta = textareaRef?.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 280) + 'px'
  }, [input, textareaRef])

  // ── File upload ─────────────────────────────────────────────────────────
  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files)
    if (!files.length) return

    const newAttachments = []
    for (const file of files) {
      try {
        if (file.type.startsWith('image/')) {
          // Read as data URL for preview
          const dataUrl = await readAsDataURL(file)
          newAttachments.push({ name: file.name, content: dataUrl, type: 'image', size: file.size })
        } else if (file.size < 500_000) {
          // Read text files up to 500KB
          const text = await readAsText(file)
          newAttachments.push({ name: file.name, content: text, type: 'text', size: file.size })
        } else {
          newAttachments.push({ name: file.name, content: null, type: 'large', size: file.size })
        }
      } catch {
        newAttachments.push({ name: file.name, content: null, type: 'error', size: file.size })
      }
    }

    setAttachments(prev => [...prev, ...newAttachments])
    // Reset file input so same file can be re-selected
    e.target.value = ''
  }

  const removeAttachment = (idx) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx))
  }

  // Build augmented message text with file contents prepended
  const buildFinalText = () => {
    let text = input.trim()
    const textFiles = attachments.filter(a => a.type === 'text' && a.content)
    const imageFiles = attachments.filter(a => a.type === 'image')
    const largeFiles = attachments.filter(a => a.type === 'large' || a.type === 'error')

    const parts = []
    for (const f of textFiles) {
      parts.push(`[Attached file: ${f.name}]\n\`\`\`\n${f.content.slice(0, 8000)}\n\`\`\``)
    }
    for (const f of imageFiles) {
      parts.push(`[Attached image: ${f.name}]`)
    }
    for (const f of largeFiles) {
      parts.push(`[Attached file: ${f.name} (${formatBytes(f.size)}),  too large to embed]`)
    }
    if (parts.length > 0) {
      text = parts.join('\n\n') + (text ? '\n\n' + text : '')
    }
    return text
  }

  const handleSendWithAttachments = () => {
    if (isWaiting || wsStatus !== 'connected') return
    const finalText = buildFinalText()
    if (!finalText) return
    sendMessage(finalText)
    setInput('')
    setAttachments([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendWithAttachments()
    }
  }

  // ── Microphone ──────────────────────────────────────────────────────────
  const SpeechRecognition = typeof window !== 'undefined'
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : null

  const toggleMic = () => {
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser.')
      return
    }

    if (isRecording) {
      recognitionRef.current?.stop()
      setIsRecording(false)
      return
    }

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.lang = 'es-ES' // Spanish default, falls back to browser locale
    recognition.continuous = false
    recognition.interimResults = true

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map(r => r[0].transcript)
        .join('')
      setInput(transcript)
    }

    recognition.onerror = () => setIsRecording(false)
    recognition.onend = () => setIsRecording(false)

    recognition.start()
    setIsRecording(true)
  }

  return (
    <div className="input-area">
      {/* Attachment previews */}
      {attachments.length > 0 && (
        <div className="attachments-row">
          {attachments.map((a, i) => (
            <div key={i} className="attachment-chip">
              <span className="attachment-icon">
                {a.type === 'image' ? '🖼️' : a.type === 'text' ? '📄' : '📎'}
              </span>
              <span className="attachment-name">{a.name}</span>
              {a.type === 'image' && a.content && (
                <img src={a.content} alt={a.name} className="attachment-thumb" />
              )}
              <button
                className="attachment-remove"
                onClick={() => removeAttachment(i)}
                title="Remove"
              >✕</button>
            </div>
          ))}
        </div>
      )}

      <div className="input-wrapper">
        {/* File upload */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="*/*"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <button
          className="input-action-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled}
          title="Attach file"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>

        {/* Mic */}
        <button
          className={`input-action-btn${isRecording ? ' recording' : ''}`}
          onClick={toggleMic}
          disabled={disabled || !SpeechRecognition}
          title={isRecording ? 'Stop recording' : 'Voice input'}
        >
          <svg viewBox="0 0 24 24" fill={isRecording ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/>
            <path d="M19 10v2a7 7 0 01-14 0v-2"/>
            <line x1="12" y1="19" x2="12" y2="23"/>
            <line x1="8" y1="23" x2="16" y2="23"/>
          </svg>
        </button>

        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder={wsStatus === 'connected'
            ? (attachments.length ? 'Add a message… (Enter to send)' : 'Ask Sable anything… (Enter to send)')
            : 'Connecting to SableCore…'}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled}
          autoFocus={autoFocus}
        />

        {/* Send */}
        <button
          className="send-btn"
          onClick={handleSendWithAttachments}
          disabled={(!input.trim() && !attachments.length) || isWaiting || disabled}
          title="Send (Enter)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
          </svg>
        </button>
      </div>
      <div className="input-hint">Shift+Enter for new line &nbsp;·&nbsp; Ctrl+N new chat</div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────────────────────
function readAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = e => resolve(e.target.result)
    reader.onerror = reject
    reader.readAsText(file)
  })
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = e => resolve(e.target.result)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}
