import React, { useState, useRef, useEffect } from 'react'
import { useSableStore } from '../hooks/useSable.js'

const PROVIDER_ICONS = {
  ollama: '🦙', openai: '🟢', anthropic: '🟠', google: '🔵', gemini: '🔵',
  groq: '⚡', mistral: '🌊', lmstudio: '🖥️', openrouter: '🔀',
  xai: '✖️', deepseek: '🐋', together: '🤝',
}

export default function ModelSelector() {
  const model = useSableStore(s => s.agentModel)
  const modelGroups = useSableStore(s => s.modelGroups)
  const switchModel = useSableStore(s => s.switchModel)
  const requestModels = useSableStore(s => s.requestModels)

  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const totalModels = (modelGroups || []).reduce((sum, g) => sum + (g.models?.length || 0), 0)
  const displayName = model ? (model.length > 22 ? model.slice(0, 20) + '…' : model) : 'No model'

  return (
    <div className="model-selector-wrapper" ref={ref}>
      <button
        className="model-selector-trigger"
        onClick={() => { setOpen(!open); if (!open) requestModels() }}
        title="Switch model"
      >
        <span className="model-selector-icon">🧠</span>
        <span className="model-selector-name">{displayName}</span>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
          width="10" height="10" style={{ opacity: 0.5, transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="model-selector-dropdown">
          <div className="model-selector-header">
            <span>Select Model</span>
            <span className="model-selector-count">({totalModels})</span>
            <button className="model-selector-refresh" onClick={(e) => { e.stopPropagation(); requestModels() }} title="Refresh">
              ↻
            </button>
          </div>

          {totalModels === 0 && (
            <div className="model-selector-empty">
              No models found.<br />Install Ollama or configure an API key.
            </div>
          )}

          {(modelGroups || []).map((group) => (
            <div key={group.provider}>
              <div className="model-selector-group-header">
                <span>{PROVIDER_ICONS[group.provider] || '🔮'}</span>
                <span>{group.name}</span>
                <span className="model-selector-count">({group.models?.length || 0})</span>
              </div>
              {(group.models || []).map((m) => {
                const active = m.name === model
                return (
                  <div
                    key={`${group.provider}:${m.name}`}
                    className={`model-selector-item${active ? ' active' : ''}`}
                    onClick={() => {
                      if (!active) switchModel(m.name, group.provider)
                      setOpen(false)
                    }}
                  >
                    <span className={`model-selector-dot${active ? ' on' : ''}`} />
                    <span className="model-selector-item-name">{m.name}</span>
                    {active && <span className="model-selector-active-label">active</span>}
                  </div>
                )
              })}
            </div>
          ))}

          {totalModels > 0 && (
            <div className="model-selector-footer">
              Click a model to switch instantly.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
