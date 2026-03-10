'use client';

import { useRef, useState, useCallback } from 'react';

interface ImageUploadProps {
  onImageSelect: (images: ImageData[]) => void;
  disabled?: boolean;
}

export interface ImageData {
  name: string;
  base64: string;
  mimeType: string;
  size: number;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml'];

export default function ImageUpload({ onImageSelect, disabled }: ImageUploadProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const processFiles = useCallback(async (files: FileList | File[]) => {
    const validFiles = Array.from(files).filter(f => {
      if (!ACCEPTED_TYPES.includes(f.type)) return false;
      if (f.size > MAX_FILE_SIZE) return false;
      return true;
    });

    if (validFiles.length === 0) return;

    const images: ImageData[] = await Promise.all(
      validFiles.map(file => new Promise<ImageData>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(',')[1];
          resolve({
            name: file.name,
            base64,
            mimeType: file.type,
            size: file.size,
          });
        };
        reader.readAsDataURL(file);
      }))
    );

    onImageSelect(images);
  }, [onImageSelect]);

  const handleClick = () => {
    if (!disabled) fileRef.current?.click();
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (!disabled) processFiles(e.dataTransfer.files);
  }, [disabled, processFiles]);

  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        multiple
        className="hidden"
        onChange={(e) => e.target.files && processFiles(e.target.files)}
      />
      <button
        onClick={handleClick}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        disabled={disabled}
        className={`p-1.5 rounded-lg transition-all ${
          dragOver
            ? 'bg-purple-500/20 text-purple-400'
            : 'text-gray-500 hover:text-gray-300 hover:bg-[#2a2a4a]'
        } ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        title="Upload image"
      >
        <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </button>
    </>
  );
}

// Paste handler hook,  use in chat input
export function useImagePaste(onImageSelect: (images: ImageData[]) => void) {
  const handlePaste = useCallback((e: ClipboardEvent) => {
    const items = Array.from(e.clipboardData?.items || []);
    const imageItems = items.filter(item => item.type.startsWith('image/'));

    if (imageItems.length === 0) return;

    e.preventDefault();

    const files = imageItems.map(item => item.getAsFile()).filter(Boolean) as File[];
    
    Promise.all(
      files.map(file => new Promise<ImageData>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          const base64 = (reader.result as string).split(',')[1];
          resolve({
            name: file.name || `pasted-${Date.now()}.png`,
            base64,
            mimeType: file.type,
            size: file.size,
          });
        };
        reader.readAsDataURL(file);
      }))
    ).then(onImageSelect);
  }, [onImageSelect]);

  return handlePaste;
}
