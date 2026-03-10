/**
 * Multi-Agent Orchestrator
 * 
 * Auto-creates and manages secondary AI agents that assist the primary model.
 * Agents are spawned dynamically based on the task requirements.
 */

export type AgentRole = 
  | 'code-reviewer'      // Reviews generated code for bugs, best practices
  | 'design-advisor'     // Suggests UI/UX improvements
  | 'package-resolver'   // Figures out required npm packages
  | 'error-fixer'        // Diagnoses and fixes runtime errors
  | 'test-writer'        // Generates tests for code
  | 'refactorer'         // Optimizes and refactors code
  | 'architect';         // Plans file structure and component hierarchy

export type AgentStatus = 'idle' | 'spawning' | 'working' | 'completed' | 'error';

export interface Agent {
  id: string;
  role: AgentRole;
  model: string;
  status: AgentStatus;
  task: string;
  result?: string;
  error?: string;
  startedAt: number;
  completedAt?: number;
  tokensUsed?: number;
}

export interface AgentTask {
  role: AgentRole;
  prompt: string;
  context?: string;
  priority: number; // 1 = highest
}

export interface OrchestratorState {
  primaryModel: string;
  agents: Agent[];
  isOrchestrating: boolean;
  taskQueue: AgentTask[];
}

// Agent role definitions with descriptions and model preferences
const AGENT_DEFINITIONS: Record<AgentRole, {
  name: string;
  icon: string;
  description: string;
  systemPrompt: string;
  preferSmallModel: boolean; // Use smaller/faster model when possible
}> = {
  'code-reviewer': {
    name: 'Code Reviewer',
    icon: '🔍',
    description: 'Reviews code for bugs and best practices',
    systemPrompt: `You are an expert code reviewer. Analyze the provided code and identify:
1. Bugs or potential runtime errors
2. Performance issues
3. Security concerns
4. Best practice violations
Be concise. Output only actionable feedback in a bulleted list. If the code is good, say "LGTM" and nothing else.`,
    preferSmallModel: true,
  },
  'design-advisor': {
    name: 'Design Advisor',
    icon: '🎨',
    description: 'Suggests UI/UX improvements',
    systemPrompt: `You are a UI/UX design expert. Review the provided code/component and suggest:
1. Visual improvements (spacing, colors, typography)
2. Accessibility issues (ARIA, contrast, keyboard nav)
3. Responsive design problems
4. User experience enhancements
Be concise. Output a short bulleted list of suggestions.`,
    preferSmallModel: true,
  },
  'package-resolver': {
    name: 'Package Resolver',
    icon: '📦',
    description: 'Identifies required npm packages',
    systemPrompt: `You are a Node.js package expert. Given the code, identify:
1. All npm packages that need to be installed
2. The correct package names and versions
Output ONLY a JSON array of package names, e.g.: ["react-router-dom", "axios", "framer-motion"]
If no packages are needed, output: []`,
    preferSmallModel: true,
  },
  'error-fixer': {
    name: 'Error Fixer',
    icon: '🔧',
    description: 'Diagnoses and fixes runtime errors',
    systemPrompt: `You are a debugging expert. Given an error message and the relevant code:
1. Identify the root cause
2. Provide the exact fix
3. Explain why the error occurred in one sentence
Output the fixed code wrapped in <file path="...">...</file> tags.`,
    preferSmallModel: false,
  },
  'test-writer': {
    name: 'Test Writer',
    icon: '🧪',
    description: 'Generates test cases',
    systemPrompt: `You are a testing expert. Write comprehensive tests for the provided code using:
- Vitest or Jest syntax
- React Testing Library for components
Be pragmatic - test the important behaviors, not implementation details.`,
    preferSmallModel: true,
  },
  'refactorer': {
    name: 'Refactorer',
    icon: '♻️',
    description: 'Optimizes and cleans up code',
    systemPrompt: `You are a code optimization expert. Refactor the provided code to:
1. Reduce complexity
2. Improve readability
3. Extract reusable logic
4. Eliminate code duplication
Output the refactored code. Keep the same functionality.`,
    preferSmallModel: false,
  },
  'architect': {
    name: 'Architect',
    icon: '🏗️',
    description: 'Plans file structure and components',
    systemPrompt: `You are a software architect. Given the user's request, plan:
1. What files/components need to be created
2. The component hierarchy
3. Data flow between components
4. Which existing files need modification
Output a concise plan as a bulleted list.`,
    preferSmallModel: true,
  },
};

/**
 * Analyze a user prompt and determine which agents should be spawned
 */
export function analyzeTaskForAgents(
  prompt: string,
  isEdit: boolean,
  hasErrors: boolean,
  codeLength: number
): AgentTask[] {
  const tasks: AgentTask[] = [];
  const lower = prompt.toLowerCase();

  // Always spawn architect for complex new projects
  if (!isEdit && (
    lower.includes('build') || lower.includes('create') || lower.includes('make') ||
    lower.includes('app') || lower.includes('website') || lower.includes('dashboard') ||
    lower.length > 100
  )) {
    tasks.push({
      role: 'architect',
      prompt: `Plan the architecture for: "${prompt}"`,
      priority: 1,
    });
  }

  // Package resolver for new code or when packages are mentioned
  if (!isEdit || lower.includes('install') || lower.includes('package') || lower.includes('import') ||
      lower.includes('library') || lower.includes('use ')) {
    tasks.push({
      role: 'package-resolver',
      prompt: `Identify packages needed for: "${prompt}"`,
      priority: 2,
    });
  }

  // Error fixer when there are known errors
  if (hasErrors || lower.includes('error') || lower.includes('fix') || lower.includes('bug') ||
      lower.includes('broken') || lower.includes('not working')) {
    tasks.push({
      role: 'error-fixer',
      prompt: `Fix the error: "${prompt}"`,
      priority: 1,
    });
  }

  // Code reviewer after significant code generation
  if (codeLength > 500 || isEdit) {
    tasks.push({
      role: 'code-reviewer',
      prompt: `Review the generated code for: "${prompt}"`,
      priority: 3,
    });
  }

  // Design advisor for UI-related tasks
  if (lower.includes('ui') || lower.includes('design') || lower.includes('layout') ||
      lower.includes('button') || lower.includes('form') || lower.includes('page') ||
      lower.includes('component') || lower.includes('style') || lower.includes('css') ||
      lower.includes('responsive') || lower.includes('look') || lower.includes('beautiful')) {
    tasks.push({
      role: 'design-advisor',
      prompt: `Review the UI for: "${prompt}"`,
      priority: 3,
    });
  }

  // Refactorer for complex edits
  if (isEdit && codeLength > 1000 && (
    lower.includes('refactor') || lower.includes('clean') || lower.includes('optimize') ||
    lower.includes('improve') || lower.includes('simplify')
  )) {
    tasks.push({
      role: 'refactorer',
      prompt: `Refactor code for: "${prompt}"`,
      priority: 2,
    });
  }

  return tasks;
}

// Patterns that identify embedding / non-chat models,  these CANNOT generate text
const EMBEDDING_MODEL_PATTERNS = [
  'embed', 'nomic', 'bge-', 'e5-', 'gte-', 'instructor',
  'all-minilm', 'sentence-', 'text-embedding', 'mxbai-embed',
];

function isChatModel(modelId: string): boolean {
  const lower = modelId.toLowerCase();
  return !EMBEDDING_MODEL_PATTERNS.some(p => lower.includes(p));
}

// Simple round-robin counter so consecutive agent calls rotate models
let _roundRobinIdx = 0;

/**
 * Select the best available model for an agent role.
 * Filters out embedding models and rotates between available chat models
 * for diverse, parallel development.
 */
export function selectAgentModel(
  role: AgentRole,
  primaryModel: string,
  availableModels: Array<{ id: string; provider: string }>
): string {
  const def = AGENT_DEFINITIONS[role];

  // Filter to chat-capable models only
  const chatModels = availableModels.filter(m => isChatModel(m.id));
  if (chatModels.length === 0) return primaryModel; // absolute fallback

  // Separate pools
  const ollamaChat = chatModels.filter(m => m.provider === 'ollama');
  const openwebuiChat = chatModels.filter(m => m.provider === 'openwebui');
  const localModels = [...ollamaChat, ...openwebuiChat];
  const cloudModels = chatModels.filter(m => !['ollama', 'openwebui'].includes(m.provider));

  // For tasks that prefer a small / fast model, pick from local models first
  if (def.preferSmallModel && localModels.length > 0) {
    const pick = localModels[_roundRobinIdx % localModels.length];
    _roundRobinIdx++;
    return pick.id;
  }

  // For critical tasks (preferSmallModel = false), prefer a capable model
  // but still rotate so agents don't all hit the same endpoint
  const pool = cloudModels.length > 0 ? cloudModels : localModels;

  // Try to avoid the same model as the primary for diversity
  const nonPrimary = pool.filter(m => m.id !== primaryModel);
  const candidates = nonPrimary.length > 0 ? nonPrimary : pool;

  const pick = candidates[_roundRobinIdx % candidates.length];
  _roundRobinIdx++;
  return pick.id;
}

/**
 * Get agent definition info
 */
export function getAgentDefinition(role: AgentRole) {
  return AGENT_DEFINITIONS[role];
}

/**
 * Create an agent instance
 */
export function createAgent(
  role: AgentRole,
  model: string,
  task: string
): Agent {
  return {
    id: `agent-${role}-${Date.now()}`,
    role,
    model,
    status: 'spawning',
    task,
    startedAt: Date.now(),
  };
}

/**
 * Get the system prompt for an agent
 */
export function getAgentSystemPrompt(role: AgentRole): string {
  return AGENT_DEFINITIONS[role].systemPrompt;
}
