"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { appConfig } from "@/config/app.config";

interface ModelEntry {
  id: string;
  name: string;
  provider: string;
}

interface SidebarInputProps {
  onSubmit: (url: string, style: string, model: string, instructions?: string) => void;
  disabled?: boolean;
}

export default function SidebarInput({ onSubmit, disabled = false }: SidebarInputProps) {
  const [url, setUrl] = useState<string>("");
  const [selectedStyle, setSelectedStyle] = useState<string>("1");
  const [selectedModel, setSelectedModel] = useState<string>(appConfig.ai.defaultModel);
  const [additionalInstructions, setAdditionalInstructions] = useState<string>("");
  const [isValidUrl, setIsValidUrl] = useState<boolean>(false);
  const [dynamicModels, setDynamicModels] = useState<ModelEntry[]>([]);

  // Fetch dynamic models on mount
  useEffect(() => {
    let cancelled = false;
    const fetchModels = async () => {
      try {
        const res = await fetch('/api/available-models');
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && data.models) {
          setDynamicModels(data.models);
        }
      } catch (err) {
        console.log('[SidebarInput] Failed to fetch models:', err);
      }
    };
    fetchModels();
    return () => { cancelled = true; };
  }, []);

  // Simple URL validation - currently unused but keeping for future use
  // const validateUrl = (urlString: string) => {
  //   if (!urlString) return false;
  //   const urlPattern = /^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$/;
  //   return urlPattern.test(urlString.toLowerCase());
  // };

  const styles = [
    { id: "1", name: "Glassmorphism", description: "Frosted glass effect" },
    { id: "2", name: "Neumorphism", description: "Soft 3D shadows" },
    { id: "3", name: "Brutalism", description: "Bold and raw" },
    { id: "4", name: "Minimalist", description: "Clean and simple" },
    { id: "5", name: "Dark Mode", description: "Dark theme design" },
    { id: "6", name: "Gradient Rich", description: "Vibrant gradients" },
    { id: "7", name: "3D Depth", description: "Dimensional layers" },
    { id: "8", name: "Retro Wave", description: "80s inspired" },
  ];

  const models = dynamicModels.length > 0
    ? dynamicModels
    : appConfig.ai.availableModels.map(model => ({
        id: model,
        name: appConfig.ai.modelDisplayNames[model] || model,
        provider: 'cloud',
      }));

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!url.trim() || disabled) return;

    onSubmit(url.trim(), selectedStyle, selectedModel, additionalInstructions || undefined);

    // Reset form
    setUrl("");
    setAdditionalInstructions("");
    setIsValidUrl(false);
  };

  return (
    <div className="w-full">
      <div >
        <div className="p-4 border-b border-[#2a2a4a]">
         {/* link to home page with button */}
         <Link href="/">
          <button className="w-full px-3 py-2 text-xs font-medium text-gray-200 bg-[#12122a] rounded border border-[#2a2a4a] focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500">
            Generate a new website
          </button>
         </Link>
        </div>

        {/* Options Section - Show when valid URL */}
        {isValidUrl && (
          <div className="p-4 space-y-4">
            {/* Style Selector */}
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-2">Style</label>
              <div className="grid grid-cols-2 gap-1.5">
                {styles.map((style) => (
                  <button
                    key={style.id}
                    onClick={() => setSelectedStyle(style.id)}
                    disabled={disabled}
                    className={`
                      py-2 px-2 rounded text-xs font-medium border transition-all text-center
                      ${selectedStyle === style.id
                        ? 'border-orange-500 bg-orange-50 text-orange-900'
                        : 'border-[#2a2a4a] hover:border-[#3a3a5a] bg-[#12122a] text-gray-300'
                      }
                      ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                  >
                    {style.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Model Selector */}
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-2">AI Model</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={disabled}
                className="w-full px-3 py-2 text-xs font-medium text-gray-200 bg-[#12122a] rounded border border-[#2a2a4a] focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500"
              >
                {/* Cloud AI */}
                <optgroup label="☁️ Cloud AI">
                  {models.filter(m => !['ollama', 'openwebui'].includes(m.provider)).map((model) => (
                    <option key={model.id} value={model.id}>{model.name}</option>
                  ))}
                </optgroup>
                {/* Ollama */}
                {models.some(m => m.provider === 'ollama') && (
                  <optgroup label="🦙 Ollama (Local)">
                    {models.filter(m => m.provider === 'ollama').map((model) => (
                      <option key={model.id} value={model.id}>{model.name}</option>
                    ))}
                  </optgroup>
                )}
                {/* OpenWebUI */}
                {models.some(m => m.provider === 'openwebui') && (
                  <optgroup label="🌐 OpenWebUI">
                    {models.filter(m => m.provider === 'openwebui').map((model) => (
                      <option key={model.id} value={model.id}>{model.name}</option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>

            {/* Additional Instructions */}
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-2">Additional Instructions (optional)</label>
              <input
                type="text"
                value={additionalInstructions}
                onChange={(e) => setAdditionalInstructions(e.target.value)}
                disabled={disabled}
                className="w-full px-3 py-2 text-xs text-gray-200 bg-[#12122a] rounded border border-[#2a2a4a] focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500 placeholder:text-gray-500"
                placeholder="e.g., make it more colorful, add animations..."
              />
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                onClick={handleSubmit}
                disabled={!isValidUrl || disabled}
                className={`
                  w-full py-2.5 px-4 rounded-lg text-sm font-medium transition-all
                  ${isValidUrl && !disabled
                    ? 'bg-orange-500 hover:bg-orange-600 text-white'
                    : 'bg-[#2a2a4a] text-gray-500 cursor-not-allowed'
                  }
                `}
              >
                {disabled ? 'Scraping...' : 'Scrape Site'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}