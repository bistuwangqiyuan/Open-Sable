import React, { useState, useEffect } from 'react'
import { useSableStore } from '../hooks/useSable'

const ACTION_LABELS = {
  browser_navigate: 'Web Browsing',
  file_write: 'Write File',
  file_delete: 'Delete File',
  system_command: 'Run System Command',
  email_send: 'Send Email',
  email_read: 'Read Email',
  calendar_write: 'Modify Calendar',
}

const ACTION_ICONS = {
  browser_navigate: '🌐',
  file_write: '📝',
  file_delete: '🗑️',
  system_command: '⚙️',
  email_send: '📧',
  email_read: '📬',
  calendar_write: '📅',
}

export default function PermissionDialog() {
  const pending = useSableStore(s => s.pendingPermission)
  const respond = useSableStore(s => s.respondPermission)
  const [remember, setRemember] = useState(false)
  const [countdown, setCountdown] = useState(60)

  useEffect(() => {
    if (!pending) return
    setCountdown(60)
    setRemember(false)
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          // Auto-deny on timeout
          respond(pending.requestId, false)
          clearInterval(interval)
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [pending?.requestId])

  if (!pending) return null

  const label = ACTION_LABELS[pending.action] || pending.action
  const icon = ACTION_ICONS[pending.action] || '🔐'
  const toolArgs = pending.arguments || {}
  const argEntries = Object.entries(toolArgs).filter(([, v]) => v !== undefined && v !== null && v !== '')

  return (
    <div className="permission-overlay">
      <div className="permission-dialog">
        <div className="permission-header">
          <span className="permission-icon">{icon}</span>
          <span className="permission-title">Permission Required</span>
          <span className="permission-countdown">{countdown}s</span>
        </div>

        <div className="permission-body">
          <p className="permission-question">
            Sable wants to use <strong>{label}</strong>
          </p>
          <div className="permission-tool">
            <code>{pending.tool}</code>
          </div>
          {argEntries.length > 0 && (
            <div className="permission-args">
              {argEntries.map(([k, v]) => (
                <div key={k} className="permission-arg">
                  <span className="permission-arg-key">{k}:</span>
                  <span className="permission-arg-val">{String(v)}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <label className="permission-remember">
          <input
            type="checkbox"
            checked={remember}
            onChange={e => setRemember(e.target.checked)}
          />
          Always allow this action
        </label>

        <div className="permission-actions">
          <button
            className="permission-btn deny"
            onClick={() => respond(pending.requestId, false)}
          >
            Deny
          </button>
          <button
            className="permission-btn allow"
            onClick={() => respond(pending.requestId, true, remember)}
          >
            Allow
          </button>
        </div>
      </div>
    </div>
  )
}
