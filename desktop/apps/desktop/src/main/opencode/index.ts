// Factory functions from agent-core
export { OpenCodeCliNotFoundError, createTaskManager } from '@opensable/agent-core';

// Types from agent-core
export type {
  TaskManagerOptions,
  TaskCallbacks,
  TaskProgressEvent,
  TaskManagerAPI,
} from '@opensable/agent-core';

export {
  createElectronTaskManagerOptions,
  buildEnvironment,
  buildCliArgs,
  getCliCommand,
  isCliAvailable,
  onBeforeStart,
  onBeforeTaskStart,
  recoverDevBrowserServer,
  getOpenCodeCliPath,
  isOpenCodeCliAvailable,
  getBundledOpenCodeVersion,
  cleanupVertexServiceAccountKey,
} from './electron-options';

export {
  generateOpenCodeConfig,
  getMcpToolsPath,
  syncApiKeysToOpenCodeAuth,
  OPENSABLE_AGENT_NAME,
} from './config-generator';

export { loginOpenAiWithChatGpt } from './auth-browser';

import { createTaskManager, type TaskManagerAPI } from '@opensable/agent-core';
import {
  createElectronTaskManagerOptions,
  isCliAvailable,
  getBundledOpenCodeVersion,
} from './electron-options';
import { getDesktopConfig } from '../config';
import fs from 'fs';
import path from 'path';
import os from 'os';

let taskManagerInstance: TaskManagerAPI | null = null;

/**
 * Reads WEBCHAT_TOKEN from the SableCore .env file.
 * Tries ~/SableCore_/.env first, then the directory two levels up from this file (monorepo).
 */
function readSableCoreToken(): string | undefined {
  const candidates = [
    path.join(os.homedir(), 'SableCore_', '.env'),
    path.resolve(__dirname, '..', '..', '..', '..', '.env'),
  ];
  for (const envPath of candidates) {
    try {
      if (!fs.existsSync(envPath)) continue;
      const content = fs.readFileSync(envPath, 'utf-8');
      const match = content.match(/^WEBCHAT_TOKEN=(.+)$/m);
      if (match) return match[1].trim();
    } catch {
      // ignore read errors, try next candidate
    }
  }
  return undefined;
}

/**
 * Resolve the WebSocket gateway URL.
 * Converts http(s) to ws(s) if needed.
 */
function resolveGatewayUrl(): string {
  const raw = process.env.OPENSABLE_API_URL || getDesktopConfig().apiUrl;
  return raw.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
}

export function getTaskManager(): TaskManagerAPI {
  if (!taskManagerInstance) {
    // Always use the OpenSable gateway adapter — connects to the local SableCore agent.
    const gatewayUrl = resolveGatewayUrl();
    const authToken = process.env.SABLE_TOKEN || readSableCoreToken();
    const opts = createElectronTaskManagerOptions();
    taskManagerInstance = createTaskManager({
      ...opts,
      onBeforeTaskStart: undefined, // Not needed in OpenSable mode — gateway handles AI
      adapterMode: 'opensable',
      opensableConfig: {
        gatewayUrl,
        authToken,
        userId: 'desktop',
      },
    });
    console.log('[OpenSable] Using gateway adapter:', gatewayUrl);
  }
  return taskManagerInstance;
}

export function disposeTaskManager(): void {
  if (taskManagerInstance) {
    taskManagerInstance.dispose();
    taskManagerInstance = null;
  }
}

export async function isOpenCodeCliInstalled(): Promise<boolean> {
  return isCliAvailable();
}

export async function getOpenCodeCliVersion(): Promise<string | null> {
  return getBundledOpenCodeVersion();
}
