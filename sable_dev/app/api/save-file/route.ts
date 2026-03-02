import { NextRequest, NextResponse } from 'next/server';

/* globals declared in other route files */
const g = globalThis as any;

/**
 * POST /api/save-file
 * Save a single file to the active sandbox (for Monaco editor edits)
 */
export async function POST(req: NextRequest) {
  try {
    const { path: filePath, content } = await req.json();

    if (!filePath || typeof filePath !== 'string') {
      return NextResponse.json({ error: 'Missing file path' }, { status: 400 });
    }

    if (typeof content !== 'string') {
      return NextResponse.json({ error: 'Missing file content' }, { status: 400 });
    }

    const provider = g.activeSandboxProvider;
    if (!provider) {
      return NextResponse.json({ error: 'No active sandbox' }, { status: 400 });
    }

    // Normalize path
    let normalizedPath = filePath;
    if (normalizedPath.startsWith('/')) {
      normalizedPath = normalizedPath.substring(1);
    }

    // Write file to sandbox
    await provider.writeFile(normalizedPath, content);

    // Update file cache
    if (g.sandboxState?.fileCache) {
      g.sandboxState.fileCache.files[normalizedPath] = {
        content,
        lastModified: Date.now(),
      };
    }

    console.log(`[save-file] Saved: ${normalizedPath}`);

    return NextResponse.json({ success: true, path: normalizedPath });
  } catch (error: any) {
    console.error('[save-file] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to save file' },
      { status: 500 }
    );
  }
}
