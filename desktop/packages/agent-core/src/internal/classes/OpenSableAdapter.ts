/**
 * OpenSableAdapter — Bridges the Electron desktop app to the OpenSable gateway
 * via WebSocket, translating gateway protocol messages to OpenCodeAdapterEvents.
 *
 * Instead of spawning a CLI via PTY (like OpenCodeAdapter), this connects to
 * the OpenSable gateway at ws://127.0.0.1:8789 (or SSH-tunneled endpoint)
 * and maps the streaming protocol to the same event interface.
 */

import { EventEmitter } from 'events';
import * as crypto from 'crypto';
import type { TaskConfig, Task, TaskMessage, TaskResult } from '../../common/types/task.js';
import type { OpenCodeMessage } from '../../common/types/opencode.js';
import type { PermissionRequest } from '../../common/types/permission.js';
import type { TodoItem } from '../../common/types/todo.js';
import type { OpenCodeAdapterEvents, AdapterOptions } from './OpenCodeAdapter.js';

// Use Node.js 22+ native WebSocket (globalThis.WebSocket)
const NativeWebSocket = globalThis.WebSocket;

const RECONNECT_DELAY = 3000;
const PING_INTERVAL = 25000;

export interface OpenSableConfig {
  /** Gateway WebSocket URL, e.g. ws://127.0.0.1:8789 */
  gatewayUrl: string;
  /** Auth token for the gateway (optional, from SABLE_TOKEN env) */
  authToken?: string;
  /** User ID for session management */
  userId?: string;
}

export class OpenSableAdapter extends EventEmitter<OpenCodeAdapterEvents> {
  private ws: WebSocket | null = null;
  private config: OpenSableConfig;
  private currentSessionId: string | null = null;
  private currentTaskId: string | null = null;
  private messages: TaskMessage[] = [];
  private hasCompleted = false;
  private isDisposed = false;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pendingText = '';
  private taskStartTime = 0;

  constructor(config: OpenSableConfig) {
    super();
    this.config = {
      gatewayUrl: config.gatewayUrl || 'ws://127.0.0.1:8789',
      authToken: config.authToken || process.env.SABLE_TOKEN,
      userId: config.userId || 'desktop',
    };
  }

  // ── Connection ───────────────────────────────────────────────────────

  private async connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = new URL(this.config.gatewayUrl);
      if (this.config.authToken) {
        url.searchParams.set('token', this.config.authToken);
      }

      this.ws = new NativeWebSocket(url.toString());

      const timeout = setTimeout(() => {
        reject(new Error('WebSocket connection timeout'));
        this.ws?.close();
      }, 10000);

      this.ws.onopen = () => {
        clearTimeout(timeout);
        console.log('[OpenSable] Connected to gateway');
        this.emit('debug', { type: 'info', message: 'Connected to OpenSable gateway' });
        this.startPing();
        resolve();
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const msg = JSON.parse(typeof event.data === 'string' ? event.data : event.data.toString());
          this.handleGatewayMessage(msg);
        } catch (err) {
          console.warn('[OpenSable] Failed to parse message:', err);
        }
      };

      this.ws.onclose = () => {
        clearTimeout(timeout);
        this.stopPing();
        if (!this.isDisposed && !this.hasCompleted) {
          console.log('[OpenSable] Connection closed, scheduling reconnect');
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = (event: Event) => {
        clearTimeout(timeout);
        const errMsg = 'WebSocket error';
        console.error('[OpenSable]', errMsg);
        this.emit('debug', { type: 'error', message: errMsg });
        if (this.ws?.readyState !== NativeWebSocket.OPEN) {
          reject(new Error(errMsg));
        }
      };
    });
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      this.send({ type: 'ping' });
    }, PING_INTERVAL);
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(async () => {
      this.reconnectTimer = null;
      try {
        await this.connect();
        // Re-request session state if we had an active task
        if (this.currentSessionId) {
          this.send({
            type: 'sessions.history',
            session_id: this.currentSessionId,
          });
        }
      } catch {
        console.log('[OpenSable] Reconnect failed, will retry');
        this.scheduleReconnect();
      }
    }, RECONNECT_DELAY);
  }

  private send(msg: Record<string, unknown>): void {
    if (this.ws?.readyState === NativeWebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  // ── Gateway Protocol → OpenCodeAdapterEvents ─────────────────────────

  private handleGatewayMessage(msg: Record<string, unknown>): void {
    const type = msg.type as string;

    switch (type) {
      case 'connected':
        this.emit('debug', {
          type: 'info',
          message: `Gateway v${msg.version}`,
        });
        break;

      case 'message.start': {
        const sessionId = (msg.session_id as string) || this.currentSessionId || '';
        this.currentSessionId = sessionId;
        this.pendingText = '';

        // Emit step_start as OpenCodeMessage
        const stepStart: OpenCodeMessage = {
          type: 'step_start',
          sessionID: sessionId,
          part: {
            id: crypto.randomUUID(),
            sessionID: sessionId,
            messageID: crypto.randomUUID(),
            type: 'step-start',
          },
        };
        this.emit('message', stepStart);
        this.emit('progress', { stage: 'running', message: 'Processing...', modelName: undefined });
        break;
      }

      case 'message.chunk': {
        const text = (msg.text as string) || '';
        this.pendingText += text;

        const textMsg: OpenCodeMessage = {
          type: 'text',
          sessionID: this.currentSessionId || '',
          part: {
            id: crypto.randomUUID(),
            sessionID: this.currentSessionId || '',
            messageID: crypto.randomUUID(),
            type: 'text',
            text,
          },
        };
        this.emit('message', textMsg);
        break;
      }

      case 'message.done': {
        const fullText = (msg.text as string) || this.pendingText;
        const sessionId = (msg.session_id as string) || this.currentSessionId || '';

        // Emit the complete text as a TaskMessage
        const taskMsg: TaskMessage = {
          id: crypto.randomUUID(),
          type: 'assistant',
          content: fullText,
          timestamp: new Date().toISOString(),
        };
        this.messages.push(taskMsg);

        // Emit step_finish
        const stepFinish: OpenCodeMessage = {
          type: 'step_finish',
          sessionID: sessionId,
          part: {
            id: crypto.randomUUID(),
            sessionID: sessionId,
            messageID: crypto.randomUUID(),
            type: 'step-finish',
            reason: 'end_turn',
          },
        };
        this.emit('message', stepFinish);
        this.emit('step-finish', {
          reason: 'end_turn',
          model: undefined,
          tokens: undefined,
          cost: undefined,
        });

        this.pendingText = '';

        // Mark task as complete
        this.hasCompleted = true;
        const durationMs = Date.now() - this.taskStartTime;
        this.emit('complete', {
          status: 'success',
          sessionId,
          durationMs,
        });
        this.emit('progress', { stage: 'complete' });
        break;
      }

      case 'command.result': {
        const text = (msg.text as string) || '';
        const success = msg.success as boolean;

        const taskMsg: TaskMessage = {
          id: crypto.randomUUID(),
          type: 'system',
          content: text,
          timestamp: new Date().toISOString(),
        };
        this.messages.push(taskMsg);

        if (!success) {
          this.emit('debug', { type: 'error', message: text });
        }
        break;
      }

      case 'error': {
        const errorText = (msg.text as string) || 'Unknown gateway error';
        const errorMsg: OpenCodeMessage = {
          type: 'error',
          error: errorText,
        };
        this.emit('message', errorMsg);
        this.emit('error', new Error(errorText));

        if (!this.hasCompleted) {
          this.hasCompleted = true;
          this.emit('complete', {
            status: 'error',
            sessionId: this.currentSessionId || undefined,
            error: errorText,
          });
        }
        break;
      }

      case 'status': {
        // Forward status updates
        this.emit('debug', { type: 'status', message: JSON.stringify(msg), data: msg });
        break;
      }

      case 'heartbeat':
      case 'pong':
        break;

      case 'sessions.list.result': {
        this.emit('debug', {
          type: 'sessions',
          message: `Found ${(msg.sessions as unknown[])?.length || 0} sessions`,
          data: msg.sessions,
        });
        break;
      }

      case 'sessions.history.result': {
        const messages = (msg.messages as Array<Record<string, unknown>>) || [];
        for (const m of messages) {
          const taskMsg: TaskMessage = {
            id: crypto.randomUUID(),
            type: (m.role as 'assistant' | 'user') || 'system',
            content: (m.content as string) || '',
            timestamp: (m.timestamp as string) || new Date().toISOString(),
          };
          this.messages.push(taskMsg);
        }
        break;
      }

      // Node protocol messages (for skill execution / tool use)
      case 'node.invoke': {
        const capability = msg.capability as string;
        const args = msg.args as Record<string, unknown>;
        this.emit('tool-use', capability, args);

        const toolMsg: OpenCodeMessage = {
          type: 'tool_call',
          sessionID: this.currentSessionId || '',
          part: {
            id: crypto.randomUUID(),
            sessionID: this.currentSessionId || '',
            messageID: crypto.randomUUID(),
            type: 'tool-call',
            tool: capability,
            input: args,
          },
        };
        this.emit('message', toolMsg);
        break;
      }

      case 'node.result': {
        const output = (msg.output as string) || '';
        this.emit('tool-result', output);

        const toolResult: OpenCodeMessage = {
          type: 'tool_result',
          sessionID: this.currentSessionId || '',
          part: {
            id: crypto.randomUUID(),
            sessionID: this.currentSessionId || '',
            messageID: crypto.randomUUID(),
            type: 'tool-result',
            toolCallID: (msg.request_id as string) || '',
            output,
          },
        };
        this.emit('message', toolResult);
        break;
      }

      default:
        this.emit('debug', {
          type: 'unknown',
          message: `Unhandled message type: ${type}`,
          data: msg,
        });
    }
  }

  // ── Task Lifecycle ───────────────────────────────────────────────────

  async startTask(config: TaskConfig): Promise<Task> {
    if (this.isDisposed) {
      throw new Error('Adapter has been disposed and cannot start new tasks');
    }

    const taskId = config.taskId || crypto.randomUUID();
    this.currentTaskId = taskId;
    this.currentSessionId = config.sessionId || null;
    this.messages = [];
    this.hasCompleted = false;
    this.pendingText = '';
    this.taskStartTime = Date.now();

    this.emit('progress', { stage: 'connecting', message: 'Connecting to OpenSable...' });

    // Connect to gateway if not connected
    if (!this.ws || this.ws.readyState !== NativeWebSocket.OPEN) {
      try {
        await this.connect();
      } catch (err) {
        const error = err instanceof Error ? err : new Error(String(err));
        this.emit('error', error);
        throw error;
      }
    }

    this.emit('progress', { stage: 'running', message: 'Sending task...' });

    // Check if the prompt is a command (starts with /)
    const isCommand = config.prompt.startsWith('/');
    const messageType = isCommand ? 'command' : 'message';

    // Send the task prompt to the gateway
    this.send({
      type: messageType,
      session_id: this.currentSessionId || taskId,
      user_id: this.config.userId,
      text: config.prompt,
    });

    // Store user message
    this.messages.push({
      id: crypto.randomUUID(),
      type: 'user',
      content: config.prompt,
      timestamp: new Date().toISOString(),
    });

    const task: Task = {
      id: taskId,
      prompt: config.prompt,
      status: 'running',
      sessionId: this.currentSessionId || taskId,
      messages: this.messages,
      createdAt: new Date().toISOString(),
      startedAt: new Date().toISOString(),
    };

    return task;
  }

  async resumeSession(sessionId: string, prompt: string): Promise<Task> {
    this.currentSessionId = sessionId;
    return this.startTask({
      prompt,
      sessionId,
    });
  }

  async interrupt(): Promise<void> {
    if (this.currentSessionId) {
      this.send({
        type: 'command',
        session_id: this.currentSessionId,
        user_id: this.config.userId,
        text: '/stop',
      });
    }

    this.hasCompleted = true;
    this.emit('complete', {
      status: 'interrupted',
      sessionId: this.currentSessionId || undefined,
    });
  }

  /** Alias for interrupt — used by TaskManager */
  async cancelTask(): Promise<void> {
    return this.interrupt();
  }

  /** Alias for interrupt — used by TaskManager */
  async interruptTask(): Promise<void> {
    return this.interrupt();
  }

  /** Send a follow-up response / permission answer to the gateway */
  async sendResponse(response: string): Promise<void> {
    this.send({
      type: 'message',
      session_id: this.currentSessionId || this.currentTaskId,
      user_id: this.config.userId,
      text: response,
    });
  }

  /** Get current session ID — used by TaskManager */
  getSessionId(): string | null {
    return this.currentSessionId;
  }

  /** Whether a task is currently running — used by TaskManager */
  get running(): boolean {
    return !this.hasCompleted && !this.isDisposed && this.ws?.readyState === NativeWebSocket.OPEN;
  }

  getMessages(): TaskMessage[] {
    return [...this.messages];
  }

  getCurrentSessionId(): string | null {
    return this.currentSessionId;
  }

  isConnected(): boolean {
    return this.ws?.readyState === NativeWebSocket.OPEN;
  }

  // ── Cleanup ──────────────────────────────────────────────────────────

  dispose(): void {
    this.isDisposed = true;
    this.stopPing();

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }

    if (this.ws) {
      if (this.ws.readyState === NativeWebSocket.OPEN) {
        this.ws.close();
      }
      this.ws = null;
    }

    this.removeAllListeners();
  }
}

/**
 * Factory to create an OpenSableAdapter with default config from environment.
 */
export function createOpenSableAdapter(overrides?: Partial<OpenSableConfig>): OpenSableAdapter {
  const config: OpenSableConfig = {
    gatewayUrl: process.env.OPENSABLE_API_URL || 'ws://127.0.0.1:8789',
    authToken: process.env.SABLE_TOKEN,
    userId: 'desktop',
    ...overrides,
  };
  return new OpenSableAdapter(config);
}
