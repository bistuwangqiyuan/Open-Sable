'use client';

import { useState, useCallback, useRef } from 'react';

export interface Snapshot {
  id: string;
  timestamp: number;
  label: string;
  prompt?: string;
  files: Record<string, string>;
}

interface UseSnapshotsOptions {
  maxHistory?: number;
}

export function useSnapshots(options: UseSnapshotsOptions = {}) {
  const { maxHistory = 50 } = options;
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);
  const isRestoringRef = useRef(false);

  // Take a snapshot of current files
  const takeSnapshot = useCallback((
    files: Record<string, string>,
    label: string,
    prompt?: string
  ) => {
    // Don't snapshot during restore operations
    if (isRestoringRef.current) return;

    const snapshot: Snapshot = {
      id: `snap_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      timestamp: Date.now(),
      label,
      prompt,
      files: { ...files },
    };

    setSnapshots(prev => {
      // If we're not at the end, discard forward history
      const base = currentIndex >= 0 ? prev.slice(0, currentIndex + 1) : prev;
      const next = [...base, snapshot].slice(-maxHistory);
      return next;
    });

    setCurrentIndex(prev => {
      const base = prev >= 0 ? prev + 1 : 0;
      return Math.min(base, maxHistory - 1);
    });
  }, [currentIndex, maxHistory]);

  // Undo: go to previous snapshot
  const undo = useCallback((): Snapshot | null => {
    if (currentIndex <= 0) return null;
    const prevIndex = currentIndex - 1;
    setCurrentIndex(prevIndex);
    isRestoringRef.current = true;
    setTimeout(() => { isRestoringRef.current = false; }, 100);
    return snapshots[prevIndex];
  }, [currentIndex, snapshots]);

  // Redo: go to next snapshot
  const redo = useCallback((): Snapshot | null => {
    if (currentIndex >= snapshots.length - 1) return null;
    const nextIndex = currentIndex + 1;
    setCurrentIndex(nextIndex);
    isRestoringRef.current = true;
    setTimeout(() => { isRestoringRef.current = false; }, 100);
    return snapshots[nextIndex];
  }, [currentIndex, snapshots]);

  // Restore to a specific snapshot by ID
  const restoreTo = useCallback((id: string): Snapshot | null => {
    const idx = snapshots.findIndex(s => s.id === id);
    if (idx < 0) return null;
    setCurrentIndex(idx);
    isRestoringRef.current = true;
    setTimeout(() => { isRestoringRef.current = false; }, 100);
    return snapshots[idx];
  }, [snapshots]);

  const canUndo = currentIndex > 0;
  const canRedo = currentIndex < snapshots.length - 1;
  const currentSnapshot = currentIndex >= 0 ? snapshots[currentIndex] : null;

  return {
    snapshots,
    currentIndex,
    currentSnapshot,
    takeSnapshot,
    undo,
    redo,
    restoreTo,
    canUndo,
    canRedo,
  };
}
