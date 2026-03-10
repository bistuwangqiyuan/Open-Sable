import React, { useState, useEffect, useRef } from 'react'
import { useSableStore } from '../hooks/useSable.js'

const BOOT_STAGES = [
  'Connecting to SableCore',
  'Initializing neural pathways',
  'Loading tool registry',
  'Warming up models',
  'Syncing sessions',
]

export default function LoadingOverlay() {
  const wsStatus = useSableStore(s => s.wsStatus)
  const [stageIdx, setStageIdx] = useState(0)
  const [attempt, setAttempt] = useState(0)
  const [dismissed, setDismissed] = useState(false)
  const [fadeOut, setFadeOut] = useState(false)
  const stableTimer = useRef(null)
  const wasEverConnected = useRef(false)

  // Track reconnect attempts
  useEffect(() => {
    if (wsStatus === 'disconnected') {
      setAttempt(a => a + 1)
    }
  }, [wsStatus])

  // Only dismiss after connection is STABLE for 2 seconds
  useEffect(() => {
    if (wsStatus === 'connected') {
      stableTimer.current = setTimeout(() => {
        wasEverConnected.current = true
        setFadeOut(true)
        setTimeout(() => setDismissed(true), 600)
      }, 1500)
    } else {
      // Connection dropped,  cancel the stable timer
      clearTimeout(stableTimer.current)
      // Only re-show if we haven't fully dismissed yet
      if (!wasEverConnected.current) {
        setFadeOut(false)
        setDismissed(false)
      }
    }
    return () => clearTimeout(stableTimer.current)
  }, [wsStatus])

  // Cycle boot-stage messages
  useEffect(() => {
    if (dismissed) return
    const iv = setInterval(() => {
      setStageIdx(i => (i + 1) % BOOT_STAGES.length)
    }, 2600)
    return () => clearInterval(iv)
  }, [dismissed])

  // Once fully dismissed, never come back in this session
  if (dismissed) return null

  return (
    <div className={`loading-overlay ${fadeOut ? 'fade-out' : ''}`}>
      <div className="loading-content">
        {/* ── Animated ring + logo ───────────────────────────────── */}
        <div className="loading-logo-wrap">
          <div className="loading-ring" />
          <img src="./logo.png" alt="Sable" className="loading-logo" />
        </div>

        {/* ── Status line ────────────────────────────────────────── */}
        <div className="loading-status">
          {fadeOut
            ? <span className="loading-connected">Connected</span>
            : <span className="loading-text">{BOOT_STAGES[stageIdx]}</span>
          }
        </div>

        {/* ── Progress bar ───────────────────────────────────────── */}
        {!fadeOut && (
          <div className="loading-bar-track">
            <div className="loading-bar-fill" />
          </div>
        )}

        {/* ── Attempt counter ────────────────────────────────────── */}
        {!fadeOut && attempt > 1 && (
          <div className="loading-sub">
            Attempt {attempt} &middot; SableCore is still booting
          </div>
        )}
      </div>
    </div>
  )
}
