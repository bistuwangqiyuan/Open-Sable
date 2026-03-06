/**
 * File-based persistence layer for Sable Dev
 * Saves critical state to disk so it survives server restarts.
 * 
 * Stored at: .sable-dev/session.json
 */

import fs from 'fs';
import path from 'path';
import type { ConversationState } from '@/types/conversation';
import type { Agent } from '@/lib/agents/agent-orchestrator';

const PERSISTENCE_DIR = path.join(process.cwd(), '.sable-dev');
const SESSION_FILE = path.join(PERSISTENCE_DIR, 'session.json');
const CHAT_HISTORY_FILE = path.join(PERSISTENCE_DIR, 'chat-history.json');

interface PersistedSession {
  version: number;
  savedAt: number;
  conversationState: ConversationState | null;
  sandboxData: {
    sandboxId: string;
    url: string;
  } | null;
  activeTemplateId: string | null;
  activeAgents: Array<{
    id: string;
    role: string;
    model: string;
    status: string;
    task?: string;
    result?: string;
    startedAt: number;
    completedAt?: number;
  }>;
  projectFiles?: Record<string, string>;
}

interface PersistedChatHistory {
  version: number;
  savedAt: number;
  messages: Array<{
    content: string;
    type: string;
    timestamp: string;
    metadata?: any;
  }>;
}

function ensureDir() {
  if (!fs.existsSync(PERSISTENCE_DIR)) {
    fs.mkdirSync(PERSISTENCE_DIR, { recursive: true });
    // Add to .gitignore if not already there
    const gitignorePath = path.join(process.cwd(), '.gitignore');
    if (fs.existsSync(gitignorePath)) {
      const content = fs.readFileSync(gitignorePath, 'utf-8');
      if (!content.includes('.sable-dev')) {
        fs.appendFileSync(gitignorePath, '\n# Sable Dev persistence\n.sable-dev/\n');
      }
    }
  }
}

/**
 * Save the current session state to disk
 */
export function saveSession(): boolean {
  try {
    ensureDir();
    
    const session: PersistedSession = {
      version: 1,
      savedAt: Date.now(),
      conversationState: global.conversationState || null,
      sandboxData: global.sandboxData || null,
      activeTemplateId: global.activeTemplateId || null,
      activeAgents: (global.activeAgents || []).map((a: any) => ({
        id: a.id,
        role: a.role,
        model: a.model,
        status: a.status,
        task: a.task,
        result: a.result,
        startedAt: a.startedAt,
        completedAt: a.completedAt,
      })),
    };
    
    fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2), 'utf-8');
    console.log('[persistence] Session saved to disk');
    return true;
  } catch (error) {
    console.error('[persistence] Failed to save session:', error);
    return false;
  }
}

/**
 * Load the persisted session from disk
 */
export function loadSession(): PersistedSession | null {
  try {
    if (!fs.existsSync(SESSION_FILE)) {
      console.log('[persistence] No persisted session found');
      return null;
    }
    
    const raw = fs.readFileSync(SESSION_FILE, 'utf-8');
    const session: PersistedSession = JSON.parse(raw);
    
    // Check if the session is too old (24 hours)
    const ageMs = Date.now() - session.savedAt;
    if (ageMs > 24 * 60 * 60 * 1000) {
      console.log('[persistence] Session too old, discarding');
      clearSession();
      return null;
    }
    
    console.log('[persistence] Session loaded from disk (age: ' + Math.round(ageMs / 1000) + 's)');
    return session;
  } catch (error) {
    console.error('[persistence] Failed to load session:', error);
    return null;
  }
}

/**
 * Restore global state from a persisted session
 */
export function restoreSession(): boolean {
  const session = loadSession();
  if (!session) return false;
  
  try {
    if (session.conversationState) {
      global.conversationState = session.conversationState;
      console.log('[persistence] Restored conversation state');
    }
    
    if (session.sandboxData) {
      global.sandboxData = session.sandboxData;
      console.log('[persistence] Restored sandbox data:', session.sandboxData.sandboxId);
    }
    
    if (session.activeTemplateId) {
      global.activeTemplateId = session.activeTemplateId;
      console.log('[persistence] Restored template:', session.activeTemplateId);
    }
    
    if (session.activeAgents?.length) {
      // Restore agents with required fields filled in
      global.activeAgents = session.activeAgents.map(a => ({
        ...a,
        task: a.task || a.role, // Ensure task field exists
      })) as Agent[];
      console.log('[persistence] Restored', session.activeAgents.length, 'agents');
    }
    
    return true;
  } catch (error) {
    console.error('[persistence] Failed to restore session:', error);
    return false;
  }
}

/**
 * Clear persisted session data
 */
export function clearSession(): boolean {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      fs.unlinkSync(SESSION_FILE);
    }
    if (fs.existsSync(CHAT_HISTORY_FILE)) {
      fs.unlinkSync(CHAT_HISTORY_FILE);
    }
    console.log('[persistence] Session cleared');
    return true;
  } catch (error) {
    console.error('[persistence] Failed to clear session:', error);
    return false;
  }
}

/**
 * Save chat history to disk (called from client-facing APIs)
 */
export function saveChatHistory(messages: PersistedChatHistory['messages']): boolean {
  try {
    ensureDir();
    
    const history: PersistedChatHistory = {
      version: 1,
      savedAt: Date.now(),
      messages: messages.slice(-100), // Keep last 100 messages
    };
    
    fs.writeFileSync(CHAT_HISTORY_FILE, JSON.stringify(history, null, 2), 'utf-8');
    return true;
  } catch (error) {
    console.error('[persistence] Failed to save chat history:', error);
    return false;
  }
}

/**
 * Load persisted chat history
 */
export function loadChatHistory(): PersistedChatHistory['messages'] | null {
  try {
    if (!fs.existsSync(CHAT_HISTORY_FILE)) return null;
    
    const raw = fs.readFileSync(CHAT_HISTORY_FILE, 'utf-8');
    const history: PersistedChatHistory = JSON.parse(raw);
    
    // Check if too old
    const ageMs = Date.now() - history.savedAt;
    if (ageMs > 24 * 60 * 60 * 1000) {
      return null;
    }
    
    return history.messages;
  } catch (error) {
    console.error('[persistence] Failed to load chat history:', error);
    return null;
  }
}

// Declare globals used by persistence
declare global {
  var sandboxData: { sandboxId: string; url: string } | null;
  var activeTemplateId: string | null;
  var activeAgents: Agent[];
}
