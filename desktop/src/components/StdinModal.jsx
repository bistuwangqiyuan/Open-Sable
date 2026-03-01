import React, { useState, useEffect } from 'react'

export default function StdinModal({ open, defaultValue = '', onConfirm, onCancel }) {
  const [value, setValue] = useState(defaultValue)

  useEffect(() => {
    setValue(defaultValue || '')
  }, [defaultValue, open])

  if (!open) return null

  return (
    <div className="stdin-modal-backdrop">
      <div className="stdin-modal">
        <div className="stdin-modal-header">Provide simulated stdin (use Enter for new lines)</div>
        <textarea
          className="stdin-modal-textarea"
          value={value}
          onChange={e => setValue(e.target.value)}
          placeholder={'Example:\n3\n+\n4'}
        />
        <div className="stdin-modal-actions">
          <button className="stdin-modal-btn cancel" onClick={() => onCancel && onCancel()}>Cancel</button>
          <button className="stdin-modal-btn confirm" onClick={() => onConfirm && onConfirm(value)}>Run</button>
        </div>
      </div>
    </div>
  )
}
