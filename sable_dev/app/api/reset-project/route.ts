import { NextResponse } from 'next/server';
import { clearSession } from '@/lib/persistence';

declare global {
  var activeSandboxProvider: any;
  var sandboxData: { sandboxId: string; url: string } | null;
  var existingFiles: Set<string>;
  var conversationState: any;
  var activeAgents: any[];
  var activeTemplateId: string | null;
  var sandboxState: any;
  var activeSandbox: any;
}

/**
 * POST /api/reset-project
 * Fully resets all server-side state: kills sandbox, clears conversation,
 * clears agents, clears file cache, clears persistence.
 */
export async function POST() {
  try {
    console.log('[reset-project] Starting full project reset...');

    // 1. Kill the sandbox process
    if (global.activeSandboxProvider) {
      try {
        await global.activeSandboxProvider.terminate();
        console.log('[reset-project] Sandbox terminated');
      } catch (e) {
        console.error('[reset-project] Error terminating sandbox:', e);
      }
      global.activeSandboxProvider = null;
    }
    global.sandboxData = null;
    global.activeSandbox = null;

    // 2. Clear file tracking
    if (global.existingFiles) {
      global.existingFiles.clear();
    }

    // 3. Clear conversation state
    global.conversationState = null;

    // 4. Clear agents
    global.activeAgents = [];

    // 5. Clear template
    global.activeTemplateId = null;

    // 6. Clear sandbox file cache
    if (global.sandboxState) {
      global.sandboxState = null;
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
