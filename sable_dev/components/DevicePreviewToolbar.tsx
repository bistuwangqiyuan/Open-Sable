'use client';

import React, { useState } from 'react';

type DeviceMode = 'desktop' | 'tablet' | 'mobile';

interface DevicePreviewToolbarProps {
  deviceMode: DeviceMode;
  onDeviceChange: (mode: DeviceMode) => void;
  sandboxUrl?: string;
  onRefresh?: () => void;
  onOpenExternal?: () => void;
}

const devices: { mode: DeviceMode; label: string; width: string; icon: React.ReactNode }[] = [
  {
    mode: 'desktop',
    label: 'Desktop',
    width: '100%',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    mode: 'tablet',
    label: 'Tablet',
    width: '768px',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    mode: 'mobile',
    label: 'Mobile',
    width: '375px',
    icon: (
      <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
];

export function getDeviceWidth(mode: DeviceMode): string {
  return devices.find(d => d.mode === mode)?.width || '100%';
}

export default function DevicePreviewToolbar({ deviceMode, onDeviceChange, sandboxUrl, onRefresh, onOpenExternal }: DevicePreviewToolbarProps) {
  return (
    <div className="flex items-center gap-2">
      {/* Device toggle buttons */}
      <div className="inline-flex bg-[#12122a] border border-[#2a2a4a] rounded-md p-0.5">
        {devices.map((device) => (
          <button
            key={device.mode}
            onClick={() => onDeviceChange(device.mode)}
            className={`p-1.5 rounded transition-all ${
              deviceMode === device.mode
                ? 'bg-[#2a2a4a] text-gray-100 shadow-sm'
                : 'bg-transparent text-gray-500 hover:text-gray-300'
            }`}
            title={device.label}
          >
            {device.icon}
          </button>
        ))}
      </div>

      {/* Refresh button */}
      {onRefresh && (
        <button
          onClick={onRefresh}
          className="p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-[#1e1e3a] transition-colors"
          title="Refresh preview"
        >
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      )}

      {/* Open in new tab */}
      {sandboxUrl && onOpenExternal && (
        <a
          href={sandboxUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 rounded-md text-gray-500 hover:text-gray-300 hover:bg-[#1e1e3a] transition-colors"
          title="Open in new tab"
        >
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
        </a>
      )}
    </div>
  );
}

export type { DeviceMode };
