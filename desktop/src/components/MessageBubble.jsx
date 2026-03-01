import React, { useState, useCallback, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useSableStore } from '../hooks/useSable.js'
import StdinModal from './StdinModal.jsx'

// ── Video embed helpers ────────────────────────────────────────────────────

function getYouTubeId(url) {
  try {
    const u = new URL(url)
    if (u.hostname === 'youtu.be') return u.pathname.slice(1).split('?')[0]
    if (u.hostname.includes('youtube.com')) {
      if (u.pathname === '/watch') return u.searchParams.get('v')
      const m = u.pathname.match(/\/(?:embed|shorts)\/([^/?]+)/)
      if (m) return m[1]
    }
  } catch {}
  return null
}

function getVideoProvider(url) {
  try {
    const u = new URL(url)
    if (u.hostname.includes('youtube.com') || u.hostname === 'youtu.be') return 'youtube'
    if (u.hostname.includes('vimeo.com')) return 'vimeo'
    if (u.hostname.includes('twitch.tv')) return 'twitch'
  } catch {}
  return null
}

function VideoEmbed({ url, title }) {
  const [expanded, setExpanded] = useState(false)
  const ytId = getYouTubeId(url)

  if (ytId) {
    return (
      <div className="video-preview">
        {!expanded ? (
          <div className="video-thumb" onClick={() => setExpanded(true)}>
            <img
              src={`https://img.youtube.com/vi/${ytId}/mqdefault.jpg`}
              alt={title || 'YouTube video'}
              className="video-thumb-img"
            />
            <div className="video-play-btn">▶</div>
            {title && <div className="video-title">{title}</div>}
          </div>
        ) : (
          <div className="video-iframe-wrap">
            <iframe
              src={`https://www.youtube.com/embed/${ytId}?autoplay=1`}
              title={title || 'YouTube video'}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="video-iframe"
            />
          </div>
        )}
      </div>
    )
  }

  // Generic video link — just show a styled link
  return null
}

// Custom link renderer: if the href is a video URL, embed it; otherwise normal link
function CustomLink({ href, children }) {
  const provider = getVideoProvider(href)
  if (provider === 'youtube') {
    const label = typeof children === 'string' ? children : (children?.[0] ?? href)
    return (
      <>
        <VideoEmbed url={href} title={typeof label === 'string' ? label : undefined} />
        <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
      </>
    )
  }
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
}

// Languages that can be run
const RUNNABLE = new Set(['python', 'python3', 'javascript', 'js', 'bash', 'sh'])

// Code block with optional Run button
function CodeBlock({ code, language }) {
  const runCode     = useSableStore(s => s.runCode)
  const codeResults = useSableStore(s => s.codeResults)
  const [reqId, setReqId]   = useState(null)
  const [copied, setCopied] = useState(false)
  const [stdinModalOpen, setStdinModalOpen] = useState(false)
  const stdinPromiseRef = useRef(null)

  const result   = reqId ? codeResults[reqId] : null
  const running  = result?.running === true
  const canRun   = RUNNABLE.has((language || '').toLowerCase())

  const handleRun = useCallback(() => {
    (async () => {
      const id = `run-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      setReqId(id)
      let stdin = null
      try {
        // If code uses input(), open the multiline modal and await the user's stdin
        if ((code || '').includes('input(')) {
          const p = new Promise(resolve => { stdinPromiseRef.current = resolve; setStdinModalOpen(true) })
          const s = await p
          if (s !== null && s !== undefined) stdin = s
        }
      } catch {}
      runCode(code, language || 'python', id, stdin)
    })()
  }, [code, language, runCode])

  const handleModalConfirm = useCallback((val) => {
    setStdinModalOpen(false)
    if (stdinPromiseRef.current) {
      stdinPromiseRef.current(val)
      stdinPromiseRef.current = null
    }
  }, [])

  const handleModalCancel = useCallback(() => {
    setStdinModalOpen(false)
    if (stdinPromiseRef.current) {
      stdinPromiseRef.current(null)
      stdinPromiseRef.current = null
    }
  }, [])

  const handleCopyCode = useCallback(async () => {
    try { await navigator.clipboard.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch {}
  }, [code])

  return (
    <div className="code-block-wrap">
      <div className="code-block-header">
        {language && <span className="code-lang">{language}</span>}
        <div className="code-block-actions">
          {canRun && (
            <button
              className={`code-run-btn${running ? ' running' : ''}`}
              onClick={handleRun}
              disabled={running}
              title={`Run ${language}`}
            >
              {running ? '⏳' : '▶ Run'}
            </button>
          )}
          <button className="code-copy-btn" onClick={handleCopyCode} title="Copy code">
            {copied ? '✓' : '⎘'}
          </button>
        </div>
      </div>
      <pre className="code-block-pre"><code>{code}</code></pre>
      <StdinModal open={stdinModalOpen} defaultValue={''} onConfirm={handleModalConfirm} onCancel={handleModalCancel} />
      {result && !result.running && (
        <div className={`code-output${result.exit_code !== 0 ? ' error' : ''}`}>
          <span className="code-output-label">
            {result.exit_code === 0 ? '▸ Output' : `▸ Error (exit ${result.exit_code})`}
          </span>
          <pre className="code-output-pre">
            {(result.stdout || result.stderr || '(no output)').trimEnd()}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {}
  }

  if (message.role === 'system') {
    return (
      <div className="message-row system">
        <div className="message-bubble system">{message.content}</div>
      </div>
    )
  }

  const isUser = message.role === 'user'

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="message-avatar assistant">S</div>
      )}
      <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? (
          <span style={{ whiteSpace: 'pre-wrap' }}>{message.content}</span>
        ) : (
          <>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: CustomLink,
                // Override <pre> to capture fenced code blocks with language
                pre({ children }) {
                  const child = React.Children.toArray(children)[0]
                  const className = child?.props?.className || ''
                  const match = /language-(\w+)/.exec(className)
                  const lang = match ? match[1] : ''
                  const codeText = String(child?.props?.children ?? '').replace(/\n$/, '')
                  return <CodeBlock code={codeText} language={lang} />
                },
              }}
            >
              {message.content}
            </ReactMarkdown>
            {message.streaming && <span className="streaming-cursor" />}
          </>
        )}
        {!isUser && !message.streaming && message.content && (
          <button className="msg-copy-btn" onClick={handleCopy} title="Copy">
            {copied ? '✓' : '⎘'}
          </button>
        )}
      </div>
    </div>
  )
}
