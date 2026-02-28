import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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
              components={{ a: CustomLink }}
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
