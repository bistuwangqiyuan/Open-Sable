import { useState, useEffect, useRef } from 'react';

const STAGES = [
  'Connecting to SableCore',
  'Initializing neural pathways',
  'Loading tool registry',
  'Warming up models',
  'Syncing sessions',
];

export default function LoadingOverlay({ connected }) {
  const [stageIdx, setStageIdx] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [fadeOut, setFadeOut] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const stableTimer = useRef(null);
  const wasEverStable = useRef(false);

  // Track reconnect attempts
  useEffect(() => {
    if (!connected) {
      setAttempt(a => a + 1);
    }
  }, [connected]);

  // Only dismiss after connection is STABLE for 1.5s
  useEffect(() => {
    if (connected) {
      stableTimer.current = setTimeout(() => {
        wasEverStable.current = true;
        setFadeOut(true);
        setTimeout(() => setDismissed(true), 600);
      }, 1500);
    } else {
      clearTimeout(stableTimer.current);
      if (!wasEverStable.current) {
        setFadeOut(false);
        setDismissed(false);
      }
    }
    return () => clearTimeout(stableTimer.current);
  }, [connected]);

  // Cycle messages
  useEffect(() => {
    if (dismissed) return;
    const iv = setInterval(() => setStageIdx(i => (i + 1) % STAGES.length), 2600);
    return () => clearInterval(iv);
  }, [dismissed]);

  if (dismissed) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 9999,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg, #0d0f11)',
      opacity: fadeOut ? 0 : 1,
      transition: 'opacity 0.6s ease-out',
      pointerEvents: fadeOut ? 'none' : 'auto',
    }}>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        gap: 'clamp(14px, 3vh, 24px)',
        padding: 'clamp(16px, 4vw, 40px)',
        userSelect: 'none',
        maxWidth: '90vw',
      }}>
        {/* Spinner */}
        <div style={{
          position: 'relative',
          width: 'clamp(60px, 12vmin, 96px)',
          height: 'clamp(60px, 12vmin, 96px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            position: 'absolute', inset: 0,
            border: 'clamp(2px, 0.4vmin, 3px) solid transparent',
            borderTopColor: 'var(--accent, #6c5ce7)',
            borderRightColor: 'var(--accent, #6c5ce7)',
            borderRadius: '50%',
            animation: 'dash-spin 1.2s linear infinite',
          }} />
          <span style={{ fontSize: 'clamp(22px, 4vmin, 32px)' }}>&#9889;</span>
        </div>

        {/* Status */}
        <div style={{
          fontSize: 'clamp(13px, 2vmin, 16px)',
          fontWeight: 500,
          color: 'var(--text-secondary, #8b8fa3)',
          textAlign: 'center',
          minHeight: '1.4em',
          lineHeight: 1.4,
        }}>
          {fadeOut ? (
            <span style={{ color: 'var(--green, #22d3a5)', fontWeight: 600 }}>Connected</span>
          ) : (
            <span style={{ animation: 'dash-fade 2.6s ease-in-out infinite' }}>{STAGES[stageIdx]}</span>
          )}
        </div>

        {/* Progress bar */}
        {!fadeOut && (
          <div style={{
            width: 'clamp(140px, 30vw, 240px)',
            height: 'clamp(2px, 0.4vmin, 4px)',
            background: 'var(--bg-alt, #1a1d23)',
            borderRadius: 4, overflow: 'hidden',
          }}>
            <div style={{
              width: '40%', height: '100%',
              background: 'var(--accent, #6c5ce7)',
              borderRadius: 4,
              animation: 'dash-bar 1.5s ease-in-out infinite',
            }} />
          </div>
        )}

        {/* Attempt counter */}
        {!fadeOut && attempt > 1 && (
          <div style={{
            fontSize: 'clamp(10px, 1.6vmin, 12px)',
            color: 'var(--text-muted, #555)',
            opacity: 0.65,
            textAlign: 'center',
            lineHeight: 1.4,
          }}>
            Attempt {attempt} &middot; SableCore is still booting
          </div>
        )}
      </div>

      <style>{`
        @keyframes dash-spin { to { transform: rotate(360deg); } }
        @keyframes dash-fade { 0%,100% { opacity: .45; } 50% { opacity: 1; } }
        @keyframes dash-bar {
          0% { transform: translateX(-100%); }
          50% { transform: translateX(150%); }
          100% { transform: translateX(250%); }
        }
      `}</style>
    </div>
  );
}
