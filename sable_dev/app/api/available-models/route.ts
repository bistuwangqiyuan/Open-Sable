import { NextResponse } from 'next/server';
import { appConfig } from '@/config/app.config';

export const dynamic = 'force-dynamic';

interface ModelEntry {
  id: string;
  name: string;
  provider: 'ollama' | 'openwebui' | 'openai' | 'anthropic' | 'groq' | 'google';
}

/**
 * Fetch available models from Ollama local server
 */
async function fetchOllamaModels(): Promise<ModelEntry[]> {
  if (!appConfig.ai.ollama.enabled) return [];
  const baseUrl = appConfig.ai.ollama.baseUrl;
  try {
    const res = await fetch(`${baseUrl}/api/tags`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return [];
    const data = await res.json();
    const models: ModelEntry[] = (data.models || []).map((m: { name: string }) => ({
      id: `ollama/${m.name}`,
      name: `${m.name} (Ollama)`,
      provider: 'ollama' as const,
    }));
    return models;
  } catch {
    console.log('[available-models] Ollama not reachable at', baseUrl);
    return [];
  }
}

/**
 * Fetch available models from OpenWebUI instance
 */
async function fetchOpenWebUIModels(): Promise<ModelEntry[]> {
  if (!appConfig.ai.openWebUI.enabled || !appConfig.ai.openWebUI.apiKey) return [];
  const baseUrl = appConfig.ai.openWebUI.baseUrl;
  try {
    const res = await fetch(`${baseUrl}/api/models`, {
      headers: {
        Authorization: `Bearer ${appConfig.ai.openWebUI.apiKey}`,
        'Content-Type': 'application/json',
      },
      signal: AbortSignal.timeout(8000),
    });
    if (!res.ok) {
      console.log('[available-models] OpenWebUI returned', res.status);
      return [];
    }
    const data = await res.json();
    // OpenWebUI /api/models returns { data: [{id, name, ...}] } (OpenAI-compatible)
    const modelList = data.data || data.models || data || [];
    const models: ModelEntry[] = (Array.isArray(modelList) ? modelList : []).map(
      (m: { id: string; name?: string }) => ({
        id: `openwebui/${m.id}`,
        name: `${m.name || m.id} (OpenWebUI)`,
        provider: 'openwebui' as const,
      }),
    );
    return models;
  } catch (err) {
    console.log('[available-models] OpenWebUI not reachable at', baseUrl, err);
    return [];
  }
}

export async function GET() {
  // Static models from config
  const staticModels: ModelEntry[] = appConfig.ai.availableModels.map((id) => ({
    id,
    name: appConfig.ai.modelDisplayNames?.[id] || id,
    provider: (id.startsWith('openai/')
      ? 'openai'
      : id.startsWith('anthropic/')
        ? 'anthropic'
        : id.startsWith('google/')
          ? 'google'
          : 'groq') as ModelEntry['provider'],
  }));

  // Fetch dynamic models in parallel
  const [ollamaModels, openWebUIModels] = await Promise.all([
    fetchOllamaModels(),
    fetchOpenWebUIModels(),
  ]);

  return NextResponse.json({
    models: [...staticModels, ...ollamaModels, ...openWebUIModels],
    providers: {
      ollama: { enabled: appConfig.ai.ollama.enabled, reachable: ollamaModels.length > 0 },
      openwebui: {
        enabled: appConfig.ai.openWebUI.enabled,
        reachable: openWebUIModels.length > 0,
      },
    },
  });
}
