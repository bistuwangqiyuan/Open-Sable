import { NextResponse } from 'next/server';
import { getAgentDefinition } from '@/lib/agents/agent-orchestrator';

export const dynamic = 'force-dynamic';

// Uses global.activeAgents declared in agents/run/route.ts

/**
 * GET /api/agents/status
 * Returns current status of all active agents
 */
export async function GET() {
  const agents = (global.activeAgents || []).map(a => ({
    id: a.id,
    role: a.role,
    model: a.model,
    status: a.status,
    task: a.task,
    result: a.result,
    error: a.error,
    startedAt: a.startedAt,
    completedAt: a.completedAt,
    tokensUsed: a.tokensUsed,
    name: getAgentDefinition(a.role)?.name || a.role,
    icon: getAgentDefinition(a.role)?.icon || '🤖',
    durationMs: a.completedAt ? a.completedAt - a.startedAt : Date.now() - a.startedAt,
  }));

  // Clean up agents older than 2 minutes
  if (global.activeAgents) {
    global.activeAgents = global.activeAgents.filter(a => 
      Date.now() - a.startedAt < 120000
    );
  }

  return NextResponse.json({ agents });
}
