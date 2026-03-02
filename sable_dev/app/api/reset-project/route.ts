import { NextResponse } from 'next/server';
import { clearSession } from '@/lib/persistence';

/* globals declared in other route files */
const g = globalThis as any;

/**
 * POST /api/reset-project
 * Fully resets all server-side state: kills sandbox, clears conversation,
 * clears agents, clears file cache, clears persistence.
 */
export async function POST() {
  try {
    console.log('[reset-project] Starting full project reset...');

    // 1. Kill the sandbox process
    if (g.activeSandboxProvider) {
      try {
        await g.activeSandboxProvider.terminate();
        console.log('[reset-project] Sandbox terminated');
      } catch (e) {
        console.error('[reset-project] Error terminating sandbox:', e);
      }
      g.activeSandboxProvider = null;
    }
    g.sandboxData = null;
    g.activeSandbox = null;

    // 2. Clear file tracking
    if (g.existingFiles) {
      g.existingFiles.clear();
    }

    // 3. Clear conversation state
    g.conversationState = null;

    // 4. Clear agents
    g.activeAgents = [];

    // 5. Clear template
    g.activeTemplateId = null;

    // 6. Clear sandbox file cache
    if (g.sandboxState) {
      g.sandboxState = null;
    }

    // 7. Clear persistence on disk
    clearSession();

    console.log('[reset-project] Full reset complete');

    return NextResponse.json({
      success: true,
      message: 'Project fully reset. Ready for a new project.',
    });
  } catch (error) {
    console.error('[reset-project] Error:', error);
    return NextResponse.json(
      { success: false, error: (error as Error).message },
      { status: 500 },
    );
  }
}
