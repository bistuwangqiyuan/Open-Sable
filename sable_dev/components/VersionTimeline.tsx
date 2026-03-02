'use client';

import { useState } from 'react';
import { Snapshot } from '@/hooks/useSnapshots';

interface VersionTimelineProps {
  snapshots: Snapshot[];
  currentIndex: number;
  onRestore: (id: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export default function VersionTimeline({
  snapshots,
  currentIndex,
  onRestore,
  isOpen,
  onClose,
}: VersionTimelineProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  if (!isOpen) return null;

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDate = (ts: number) => {
    const d = new Date(ts);
    const today = new Date();
    if (d.toDateString() === today.toDateString()) return 'Today';
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  // Group snapshots by date
  const groups: { date: string; items: (Snapshot & { idx: number })[] }[] = [];
  snapshots.forEach((snap, idx) => {
    const date = formatDate(snap.timestamp);
    const last = groups[groups.length - 1];
    if (last && last.date === date) {
      last.items.push({ ...snap, idx });
    } else {
      groups.push({ date, items: [{ ...snap, idx }] });
    }
  });
  groups.reverse();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-[560px] max-w-[90vw] max-h-[80vh] bg-[#0e0e20] border border-[#2a2a4a] rounded-2xl flex flex-col shadow-2xl animate-in zoom-in-95 fade-in duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a4a]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-purple-400">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-200">Version History</h3>
              <p className="text-[11px] text-gray-500">{snapshots.length} version{snapshots.length !== 1 ? 's' : ''} saved</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-[#2a2a4a] text-gray-400 hover:text-gray-200 transition-colors"
          >
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4 min-h-0">
          {groups.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm">
              <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="mb-2 opacity-50">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p>No versions yet</p>
              <p className="text-xs text-gray-600 mt-1">Versions are created on each AI edit</p>
            </div>
          ) : (
            groups.map(group => (
              <div key={group.date} className="mb-4">
                <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  {group.date}
                </div>
                <div className="space-y-1">
                  {group.items.map(snap => {
                    const isCurrent = snap.idx === currentIndex;
                    const isHovered = hoveredId === snap.id;

                    return (
                      <button
                        key={snap.id}
                        onClick={() => !isCurrent && onRestore(snap.id)}
                        onMouseEnter={() => setHoveredId(snap.id)}
                        onMouseLeave={() => setHoveredId(null)}
                        className={`w-full text-left px-3 py-2 rounded-lg transition-all group ${
                          isCurrent
                            ? 'bg-purple-500/15 border border-purple-500/30'
                            : 'hover:bg-[#1a1a3a] border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          {/* Timeline dot */}
                          <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            isCurrent ? 'bg-purple-400' : 'bg-gray-600 group-hover:bg-gray-400'
                          }`} />
                          <span className={`text-xs font-medium truncate flex-1 ${
                            isCurrent ? 'text-purple-300' : 'text-gray-300'
                          }`}>
                            {snap.label}
                          </span>
                          <span className="text-[10px] text-gray-500 flex-shrink-0">
                            {formatTime(snap.timestamp)}
                          </span>
                        </div>
                        {snap.prompt && (
                          <p className="text-[11px] text-gray-500 mt-1 ml-4 truncate">
                            "{snap.prompt}"
                          </p>
                        )}
                        {isCurrent && (
                          <span className="text-[10px] text-purple-400 ml-4 mt-1 block">Current</span>
                        )}
                        {!isCurrent && isHovered && (
                          <span className="text-[10px] text-gray-400 ml-4 mt-1 block">Click to restore</span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-[#2a2a4a] flex items-center justify-between">
          <span className="text-[11px] text-gray-500">Click a version to restore it</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a3a] hover:bg-[#2a2a4a] text-xs text-gray-300 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
