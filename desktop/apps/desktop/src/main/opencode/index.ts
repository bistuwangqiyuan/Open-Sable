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

let taskManagerInstance: TaskManagerAPI | null = null;

/**
 * Detects whether we should use OpenSable gateway mode.
 * Uses gateway if OPENSABLE_API_URL or SABLE_TOKEN is set, or if the
 * default gateway URL is configured (non-production accomplish URL).
 */
function shouldUseOpenSableMode(): boolean {
  return !!(process.env.OPENSABLE_API_URL || process.env.SABLE_TOKEN);
}

export function getTaskManager(): TaskManagerAPI {
  if (!taskManagerInstance) {
    if (shouldUseOpenSableMode()) {
      // Use OpenSable gateway adapter (WebSocket)
      const config = getDesktopConfig();
      const opts = createElectronTaskManagerOptions();
      taskManagerInstance = createTaskManager({
        ...opts,
        adapterMode: 'opensable',
        opensableConfig: {
          gatewayUrl: process.env.OPENSABLE_API_URL || config.apiUrl.replace('http', 'ws'),
          authToken: process.env.SABLE_TOKEN,
          userId: 'desktop',
        },
      });
      console.log('[OpenSable] Using gateway adapter:', process.env.OPENSABLE_API_URL || config.apiUrl);
    } else {
      // Fall back to OpenCode CLI adapter (original behavior)
      taskManagerInstance = createTaskManager(createElectronTaskManagerOptions());
    }
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
