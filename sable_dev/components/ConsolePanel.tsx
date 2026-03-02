'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface ConsoleEntry {
  id: number;
  type: 'log' | 'warn' | 'error' | 'info';
  args: string[];
  timestamp: number;
}

interface ConsolePanelProps {
  isOpen: boolean;
  onToggle: () => void;
  iframeRef?: React.RefObject<HTMLIFrameElement | null>;
}

export default function ConsolePanel({ isOpen, onToggle, iframeRef }: ConsolePanelProps) {
  const [entries, setEntries] = useState<ConsoleEntry[]>([]);
  const [filter, setFilter] = useState<'all' | 'log' | 'warn' | 'error'>('all');
  const scrollRef = useRef<HTMLDivElement>(null);
  const idRef = useRef(0);

  // Listen for console messages from the sandbox iframe
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (event.data?.type === 'sable-console') {
        const { method, args } = event.data;
        if (['log', 'warn', 'error', 'info'].includes(method)) {
          idRef.current += 1;
          setEntries(prev => [...prev.slice(-200), {
            id: idRef.current,
            type: method as ConsoleEntry['type'],
            args: args.map((a: any) => typeof a === 'object' ? JSON.stringify(a, null, 2) : String(a)),
            timestamp: Date.now(),
          }]);
        }
      }
    };

    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current && isOpen) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries, isOpen]);

  const filtered = filter === 'all' ? entries : entries.filter(e => e.type === filter);

  const typeColor = (type: ConsoleEntry['type']) => {
    switch (type) {
      case 'error': return 'text-red-400';
      case 'warn': return 'text-yellow-400';
      case 'info': return 'text-blue-400';
      default: return 'text-gray-300';
    }
  };

  const typeIcon = (type: ConsoleEntry['type']) => {
    switch (type) {
      case 'error': return '✕';
      case 'warn': return '⚠';
      case 'info': return 'ℹ';
      default: return '›';
    }
  };

  const errorCount = entries.filter(e => e.type === 'error').length;
  const warnCount = entries.filter(e => e.type === 'warn').length;

  return (
    <div className={`border-t border-[#2a2a4a] bg-[#0a0a1a] transition-all ${isOpen ? 'h-48' : 'h-8'}`}>
      {/* Console header */}
      <button
        onClick={onToggle}
        className="w-full h-8 px-3 flex items-center justify-between text-xs hover:bg-[#12122a] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-gray-400 font-medium">Console</span>
          {errorCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 text-[10px] font-medium">{errorCount}</span>
          )}
          {warnCount > 0 && (
            <span className="px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400 text-[10px] font-medium">{warnCount}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <svg
            width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor"
            className={`transition-transform ${isOpen ? 'rotate-180' : ''}`}
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </div>
      </button>

      {/* Console content */}
      {isOpen && (
        <div className="flex flex-col h-[calc(100%-2rem)]">
          {/* Filter bar */}
          <div className="flex items-center gap-1 px-2 py-1 border-b border-[#1e1e3a]">
            {(['all', 'log', 'warn', 'error'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                  filter === f ? 'bg-[#2a2a4a] text-gray-200' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
            <div className="flex-1" />
            <button
              onClick={() => setEntries([])}
              className="px-2 py-0.5 rounded text-[10px] text-gray-500 hover:text-gray-300 transition-colors"
              title="Clear console"
            >
              Clear
            </button>
          </div>

          {/* Log entries */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto font-mono text-xs">
            {filtered.length === 0 ? (
              <div className="flex items-center justify-center h-full text-gray-600 text-[11px]">
                No console output yet
              </div>
            ) : (
              filtered.map(entry => (
                <div
                  key={entry.id}
                  className={`flex items-start gap-2 px-3 py-1 border-b border-[#1a1a2e] hover:bg-[#12122a] ${
                    entry.type === 'error' ? 'bg-red-500/5' : entry.type === 'warn' ? 'bg-yellow-500/5' : ''
                  }`}
                >
                  <span className={`flex-shrink-0 w-4 text-center ${typeColor(entry.type)}`}>
                    {typeIcon(entry.type)}
                  </span>
                  <span className={`flex-1 whitespace-pre-wrap break-all ${typeColor(entry.type)}`}>
                    {entry.args.join(' ')}
                  </span>
                  <span className="flex-shrink-0 text-gray-600 text-[10px]">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
