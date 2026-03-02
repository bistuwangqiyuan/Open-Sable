'use client';

import { useCallback, useRef, useEffect, useState } from 'react';
import dynamic from 'next/dynamic';

const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false });

interface CodeEditorProps {
  filePath: string;
  content: string;
  language?: string;
  readOnly?: boolean;
  onChange?: (value: string) => void;
  onSave?: (filePath: string, content: string) => void;
}

function getLanguageFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'js': return 'javascript';
    case 'jsx': return 'javascript';
    case 'ts': return 'typescript';
    case 'tsx': return 'typescript';
    case 'css': return 'css';
    case 'html': return 'html';
    case 'json': return 'json';
    case 'md': return 'markdown';
    case 'svg': return 'xml';
    default: return 'plaintext';
  }
}

export default function CodeEditor({ filePath, content, language, readOnly = false, onChange, onSave }: CodeEditorProps) {
  const editorRef = useRef<any>(null);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const handleMount = useCallback((editor: any) => {
    editorRef.current = editor;
    
    // Add Ctrl+S save shortcut
    editor.addAction({
      id: 'save-file',
      label: 'Save File',
      keybindings: [2048 | 49], // Ctrl+S (Monaco KeyMod.CtrlCmd | KeyCode.KeyS)
      run: () => {
        const value = editor.getValue();
        onSave?.(filePath, value);
      }
    });
  }, [filePath, onSave]);

  const handleChange = useCallback((value: string | undefined) => {
    if (value !== undefined) {
      onChange?.(value);
    }
  }, [onChange]);

  const resolvedLanguage = language || getLanguageFromPath(filePath);

  if (!isMounted) {
    return (
      <div className="w-full h-full bg-[#1e1e1e] flex items-center justify-center">
        <div className="text-gray-500 text-sm">Loading editor...</div>
      </div>
    );
  }

  return (
    <MonacoEditor
      height="100%"
      language={resolvedLanguage}
      value={content}
      theme="vs-dark"
      onChange={handleChange}
      onMount={handleMount}
      options={{
        readOnly,
        minimap: { enabled: false },
        fontSize: 13,
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        wordWrap: 'on',
        tabSize: 2,
        automaticLayout: true,
        padding: { top: 8, bottom: 8 },
        renderLineHighlight: 'line',
        cursorBlinking: 'smooth',
        smoothScrolling: true,
        bracketPairColorization: { enabled: true },
        guides: { bracketPairs: true },
        scrollbar: {
          verticalScrollbarSize: 8,
          horizontalScrollbarSize: 8,
        },
        suggest: { showWords: false },
        quickSuggestions: false,
      }}
    />
  );
}
