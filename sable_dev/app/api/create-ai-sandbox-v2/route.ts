import { NextResponse } from 'next/server';
import { SandboxFactory } from '@/lib/sandbox/factory';
import type { SandboxState } from '@/types/sandbox';
import { sandboxManager } from '@/lib/sandbox/sandbox-manager';
import { LocalProcessProvider } from '@/lib/sandbox/providers/local-provider';
import { getTemplate, DEFAULT_TEMPLATE } from '@/lib/sandbox/templates';
import { saveSession } from '@/lib/persistence';

// Store active sandbox globally
declare global {
  var activeSandbox: any;
  var activeSandboxProvider: any;
  var sandboxData: { sandboxId: string; url: string } | null;
  var existingFiles: Set<string>;
  var sandboxState: SandboxState;
  var activeTemplateId: string | null;
}

export async function POST(request: Request) {
  try {
    // Parse template from request body (default: react-spa)
    let templateId = DEFAULT_TEMPLATE;
    try {
      const body = await request.json();
      if (body?.template) {
        templateId = body.template;
      }
    } catch {
      // Empty body is fine, use default
    }
    
    const template = getTemplate(templateId);
    console.log(`[create-ai-sandbox-v2] Creating sandbox with template: ${template.name} (${template.id})`);
    
    // Clean up all existing sandboxes
    console.log('[create-ai-sandbox-v2] Cleaning up existing sandboxes...');
    await sandboxManager.terminateAll();
    
    // Also clean up legacy global state
    if (global.activeSandboxProvider) {
      try {
        await global.activeSandboxProvider.terminate();
      } catch (e) {
        console.error('Failed to terminate legacy global sandbox:', e);
      }
      global.activeSandboxProvider = null;
    }
    global.activeSandbox = null;
    
    // Clear existing files tracking
    if (global.existingFiles) {
      global.existingFiles.clear();
    } else {
      global.existingFiles = new Set<string>();
    }

    // Create new sandbox using factory
    const provider = SandboxFactory.create();
    const sandboxInfo = await provider.createSandbox();
    
    console.log(`[create-ai-sandbox-v2] Setting up project with template: ${template.name}`);
    await provider.setupViteApp(templateId);
    
    // Store the active template ID globally for the AI system prompt
    global.activeTemplateId = templateId;
    
    // Register with sandbox manager
    sandboxManager.registerSandbox(sandboxInfo.sandboxId, provider);
    
    // Also store in legacy global state for backward compatibility
    global.activeSandboxProvider = provider;
    global.sandboxData = {
      sandboxId: sandboxInfo.sandboxId,
      url: sandboxInfo.url
    };

    // Set up global.activeSandbox for legacy API routes that use Vercel SDK interface
    // (run-command, get-sandbox-files, sandbox-logs, create-zip, etc.)
    if (provider instanceof LocalProcessProvider) {
      global.activeSandbox = provider.createLegacyCompatWrapper();
    } else {
      // For Vercel/E2B providers, the raw sandbox is set by their own creation logic
      global.activeSandbox = (provider as any).sandbox || provider;
    }
    
    // Initialize sandbox state
    global.sandboxState = {
      fileCache: {
        files: {},
        lastSync: Date.now(),
        sandboxId: sandboxInfo.sandboxId
      },
      sandbox: provider, // Store the provider instead of raw sandbox
      sandboxData: {
        sandboxId: sandboxInfo.sandboxId,
        url: sandboxInfo.url
      }
    };
    
    console.log('[create-ai-sandbox-v2] Sandbox ready at:', sandboxInfo.url);
    
    // Persist session to disk
    saveSession();
    
    return NextResponse.json({
      success: true,
      sandboxId: sandboxInfo.sandboxId,
      url: sandboxInfo.url,
      provider: sandboxInfo.provider,
      template: templateId,
      templateName: template.name,
      message: `Sandbox created with ${template.name} template`
    });

  } catch (error) {
    console.error('[create-ai-sandbox-v2] Error:', error);
    
    // Clean up on error
    await sandboxManager.terminateAll();
    if (global.activeSandboxProvider) {
      try {
        await global.activeSandboxProvider.terminate();
      } catch (e) {
        console.error('Failed to terminate sandbox on error:', e);
      }
      global.activeSandboxProvider = null;
    }
    global.activeSandbox = null;
    
    return NextResponse.json(
      { 
        error: error instanceof Error ? error.message : 'Failed to create sandbox',
        details: error instanceof Error ? error.stack : undefined
      },
      { status: 500 }
    );
  }
}