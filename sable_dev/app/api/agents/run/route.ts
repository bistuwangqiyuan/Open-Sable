import { NextRequest, NextResponse } from 'next/server';
import { createOpenAI } from '@ai-sdk/openai';
import { createGoogleGenerativeAI } from '@ai-sdk/google';
import { createAnthropic } from '@ai-sdk/anthropic';
import { createGroq } from '@ai-sdk/groq';
import { generateText } from 'ai';
import { appConfig } from '@/config/app.config';
import {
  type AgentRole,
  type Agent,
  analyzeTaskForAgents,
  selectAgentModel,
  createAgent,
  getAgentSystemPrompt,
  getAgentDefinition,
} from '@/lib/agents/agent-orchestrator';

export const dynamic = 'force-dynamic';

// Reuse the same providers as generate-ai-code-stream
const isUsingAIGateway = !!process.env.AI_GATEWAY_API_KEY;
const aiGatewayBaseURL = 'https://ai-gateway.vercel.sh/v1';

const groq = createGroq({
  apiKey: process.env.AI_GATEWAY_API_KEY ?? process.env.GROQ_API_KEY,
  baseURL: isUsingAIGateway ? aiGatewayBaseURL : undefined,
});

const anthropic = createAnthropic({
  apiKey: process.env.AI_GATEWAY_API_KEY ?? process.env.ANTHROPIC_API_KEY,
  baseURL: isUsingAIGateway ? aiGatewayBaseURL : (process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com/v1'),
});

const googleAI = createGoogleGenerativeAI({
  apiKey: process.env.AI_GATEWAY_API_KEY ?? process.env.GEMINI_API_KEY,
  baseURL: isUsingAIGateway ? aiGatewayBaseURL : undefined,
});

const openai = createOpenAI({
  apiKey: process.env.AI_GATEWAY_API_KEY ?? process.env.OPENAI_API_KEY,
  baseURL: isUsingAIGateway ? aiGatewayBaseURL : process.env.OPENAI_BASE_URL,
});

const ollamaProvider = createOpenAI({
  apiKey: 'ollama',
  baseURL: `${appConfig.ai.ollama.baseUrl}/v1`,
});

const openWebUIProvider = createOpenAI({
  apiKey: appConfig.ai.openWebUI.apiKey || 'dummy',
  baseURL: `${appConfig.ai.openWebUI.baseUrl}/api`,
});

function getModelForProvider(modelId: string) {
  if (modelId.startsWith('ollama/')) {
    return ollamaProvider(modelId.replace('ollama/', ''));
  }
  if (modelId.startsWith('openwebui/')) {
    return openWebUIProvider(modelId.replace('openwebui/', ''));
  }
  if (modelId.startsWith('anthropic/')) {
    return anthropic(modelId.replace('anthropic/', ''));
  }
  if (modelId.startsWith('google/')) {
    return googleAI(modelId.replace('google/', ''));
  }
  if (modelId.startsWith('openai/')) {
    return openai(modelId.replace('openai/', ''));
  }
  // Groq models (default provider)
  const groqConfig = (appConfig.ai.modelApiConfig as Record<string, any>)[modelId];
  if (groqConfig?.provider === 'groq') {
    return groq(groqConfig.model);
  }
  return groq(modelId);
}

// Store active agents globally so the status endpoint can read them
declare global {
  var activeAgents: Agent[];
}
if (!global.activeAgents) {
  global.activeAgents = [];
}

/**
 * POST /api/agents/run
 * Analyzes the task and spawns appropriate agents
 */
export async function POST(request: NextRequest) {
  try {
    const { 
      prompt, 
      primaryModel, 
      isEdit = false, 
      hasErrors = false, 
      generatedCode = '',
      availableModels = [],
      codeContext = ''
    } = await request.json();

    // Analyze what agents are needed
    const tasks = analyzeTaskForAgents(prompt, isEdit, hasErrors, generatedCode.length);

    if (tasks.length === 0) {
      return NextResponse.json({ agents: [], message: 'No agents needed for this task' });
    }

    console.log(`[agents] Spawning ${tasks.length} agents for: "${prompt.substring(0, 60)}..."`);

    // Create agent instances
    const agents: Agent[] = tasks.map(task => {
      const model = selectAgentModel(task.role, primaryModel, availableModels);
      return createAgent(task.role, model, task.prompt);
    });

    // Store agents globally for status polling
    global.activeAgents = [...global.activeAgents.filter(a => 
      // Keep recent completed agents for 30 seconds
      a.status !== 'completed' && a.status !== 'error' || 
      (a.completedAt && Date.now() - a.completedAt < 30000)
    ), ...agents];

    // Run agents in parallel (fire and forget - status is polled)
    const agentPromises = agents.map(async (agent, i) => {
      const task = tasks[i];
      const def = getAgentDefinition(task.role);

      try {
        // Mark as working
        agent.status = 'working';

        const userPrompt = [
          task.prompt,
          codeContext ? `\n\nCode context:\n${codeContext.substring(0, 4000)}` : '',
          generatedCode ? `\n\nGenerated code:\n${generatedCode.substring(0, 4000)}` : '',
        ].join('');

        console.log(`[agents] Running ${def.name} (${agent.model})...`);

        const result = await generateText({
          model: getModelForProvider(agent.model),
          system: getAgentSystemPrompt(task.role),
          prompt: userPrompt,
          temperature: 0.3,
        });

        agent.status = 'completed';
        agent.result = result.text;
        agent.completedAt = Date.now();
        agent.tokensUsed = result.usage?.totalTokens;

        console.log(`[agents] ${def.name} completed in ${Date.now() - agent.startedAt}ms`);
      } catch (err: any) {
        agent.status = 'error';
        agent.error = err.message || 'Agent failed';
        agent.completedAt = Date.now();
        console.error(`[agents] ${def.name} failed:`, err.message);
      }
    });

    // Don't await - let them run in background
    Promise.allSettled(agentPromises).then(() => {
      console.log('[agents] All agents completed');
    });

    // Return immediately with agent IDs for polling
    return NextResponse.json({
      agents: agents.map(a => ({
        id: a.id,
        role: a.role,
        model: a.model,
        status: a.status,
        task: a.task,
        name: getAgentDefinition(a.role).name,
        icon: getAgentDefinition(a.role).icon,
      })),
      message: `Spawned ${agents.length} agents`,
    });
  } catch (error: any) {
    console.error('[agents] Orchestrator error:', error);
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
