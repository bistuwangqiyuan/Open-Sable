/**
 * Format a timestamp into a human-readable HH:MM string.
 * Accepts a Unix timestamp (ms or s), an ISO string, or a Date object.
 *
 * @param {number|string|Date} ts
 * @returns {string}  e.g. "14:32"
 */
export function fmtTime(ts) {
  if (!ts) return '';
  let date;
  if (ts instanceof Date) {
    date = ts;
  } else if (typeof ts === 'number') {
    // Handle both millisecond and second timestamps
    date = new Date(ts > 1e10 ? ts : ts * 1000);
  } else {
    date = new Date(ts);
  }
  if (isNaN(date.getTime())) return '';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Format an uptime value (in seconds) into a human-readable string.
 * e.g. 3661 → "1h 01m"  |  90 → "1m 30s"  |  45 → "45s"
 *
 * @param {number} sec - uptime in seconds
 * @returns {string}
 */
export function fmtUptime(sec) {
  if (!sec || sec < 0) return '0s';
  const s = Math.floor(sec);
  const hours = Math.floor(s / 3600);
  const mins  = Math.floor((s % 3600) / 60);
  const secs  = s % 60;
  if (hours > 0) return `${hours}h ${String(mins).padStart(2, '0')}m`;
  if (mins  > 0) return `${mins}m ${String(secs).padStart(2, '0')}s`;
  return `${secs}s`;
}

/**
 * Supported AI provider definitions.
 * Each entry: { id, name, models[], local? }
 */
export const PROVIDERS = [
  {
    id: 'openai',
    name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o1', 'o1-mini', 'o3-mini'],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    models: ['claude-opus-4-5', 'claude-sonnet-4-5', 'claude-haiku-4-5', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'],
  },
  {
    id: 'google',
    name: 'Google',
    models: ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro', 'gemini-1.5-flash'],
  },
  {
    id: 'groq',
    name: 'Groq',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  },
  {
    id: 'mistral',
    name: 'Mistral',
    models: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest', 'open-mixtral-8x22b'],
  },
  {
    id: 'ollama',
    name: 'Ollama',
    local: true,
    models: ['llama3.2', 'llama3.1', 'mistral', 'phi3', 'gemma2', 'qwen2.5'],
  },
  {
    id: 'lmstudio',
    name: 'LM Studio',
    local: true,
    models: ['local-model'],
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    models: ['openai/gpt-4o', 'anthropic/claude-3.5-sonnet', 'google/gemini-pro-1.5', 'meta-llama/llama-3.1-70b-instruct'],
  },
  {
    id: 'xai',
    name: 'xAI',
    models: ['grok-2-latest', 'grok-beta'],
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
];

/**
 * Emoji / logo for each provider id.
 */
export const PROVIDER_LOGOS = {
  openai:     '🟢',
  anthropic:  '🟠',
  google:     '🔵',
  groq:       '⚡',
  mistral:    '🌊',
  ollama:     '🦙',
  lmstudio:   '🖥️',
  openrouter: '🔀',
  xai:        '✖️',
  deepseek:   '🐋',
};
