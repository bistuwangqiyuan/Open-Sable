'use client';

import { useState, useRef, useCallback } from 'react';

interface ImportProjectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImport: (files: Record<string, string>) => void;
}

export default function ImportProjectModal({ isOpen, onClose, onImport }: ImportProjectModalProps) {
  const [tab, setTab] = useState<'zip' | 'github'>('zip');
  const [githubUrl, setGithubUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleZipUpload = useCallback(async (file: File) => {
    if (!file.name.endsWith('.zip')) {
      setError('Please upload a .zip file');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch('/api/import-project', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Import failed');
      }

      const data = await res.json();
      onImport(data.files);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import ZIP');
    } finally {
      setLoading(false);
    }
  }, [onImport, onClose]);

  const handleGithubImport = useCallback(async () => {
    if (!githubUrl.trim()) return;

    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/import-project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ githubUrl: githubUrl.trim() }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || 'Import failed');
      }

      const data = await res.json();
      onImport(data.files);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to import from GitHub');
    } finally {
      setLoading(false);
    }
  }, [githubUrl, onImport, onClose]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleZipUpload(file);
  }, [handleZipUpload]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative w-[480px] bg-[#0e0e20] border border-[#2a2a4a] rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#2a2a4a]">
          <h2 className="text-base font-semibold text-gray-200">Import Project</h2>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[#2a2a4a] text-gray-400 hover:text-gray-200 transition-colors"
          >
            <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex px-5 pt-3 gap-1">
          {([['zip', 'ZIP File'], ['github', 'GitHub']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => { setTab(key); setError(''); }}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors ${
                tab === key
                  ? 'bg-[#1a1a3a] text-gray-200 border-b-2 border-purple-500'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-5">
          {tab === 'zip' ? (
            <div>
              <input
                ref={fileRef}
                type="file"
                accept=".zip"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleZipUpload(e.target.files[0])}
              />
              <div
                onClick={() => !loading && fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                  dragOver
                    ? 'border-purple-500 bg-purple-500/10'
                    : 'border-[#2a2a4a] hover:border-[#3a3a5a] hover:bg-[#12122a]'
                } ${loading ? 'opacity-50 pointer-events-none' : ''}`}
              >
                <svg width="40" height="40" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="mx-auto mb-3 text-gray-500">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-gray-300 font-medium">
                  Drop a ZIP file here or click to browse
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Supports standard project ZIP files
                </p>
              </div>
            </div>
          ) : (
            <div>
              <label className="text-xs text-gray-400 font-medium">GitHub Repository URL</label>
              <input
                type="text"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/user/repo"
                className="w-full mt-1.5 px-3 py-2.5 bg-[#12122a] border border-[#2a2a4a] rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-colors"
                disabled={loading}
                onKeyDown={(e) => e.key === 'Enter' && handleGithubImport()}
              />
              <p className="text-[11px] text-gray-500 mt-2">
                Public repositories only. The repo will be cloned and loaded into the editor.
              </p>
              <button
                onClick={handleGithubImport}
                disabled={loading || !githubUrl.trim()}
                className="mt-4 w-full py-2.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Importing...
                  </span>
                ) : (
                  'Import Repository'
                )}
              </button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mt-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
