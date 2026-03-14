import React, { useState, useEffect } from 'react'
import { useSableStore } from '../hooks/useSable'

const ACTION_LABELS = {
  browser_navigate: '网页浏览',
  file_write: '写入文件',
  file_delete: '删除文件',
  system_command: '执行系统命令',
  email_send: '发送邮件',
  email_read: '读取邮件',
  calendar_write: '修改日历',
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
          <span className="permission-title">需要授权</span>
          <span className="permission-countdown">{countdown}s</span>
        </div>

        <div className="permission-body">
          <p className="permission-question">
            Sable 请求执行：<strong>{label}</strong>
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
          始终允许此操作
        </label>

        <div className="permission-actions">
          <button
            className="permission-btn deny"
            onClick={() => respond(pending.requestId, false)}
          >
            拒绝
          </button>
          <button
            className="permission-btn allow"
            onClick={() => respond(pending.requestId, true, remember)}
          >
            允许
          </button>
        </div>
      </div>
    </div>
  )
}
