import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs/promises';
import * as path from 'path';
import * as os from 'os';
import { exec } from 'child_process';

/* globals: activeSandboxProvider, sandboxState,  declared in other route files */

const TEXT_EXTENSIONS = new Set([
  '.js', '.jsx', '.ts', '.tsx', '.json', '.html', '.css', '.scss', '.less',
  '.md', '.txt', '.yaml', '.yml', '.toml', '.xml', '.svg', '.vue', '.astro',
  '.env', '.gitignore', '.prettierrc', '.eslintrc', '.babelrc',
  '.mjs', '.cjs', '.mts', '.cts',
]);

/**
 * POST /api/import-project
 * 
 * Supports two modes:
 * 1. Form data with a ZIP file
 * 2. JSON body with { githubUrl: string }
 */
export async function POST(req: NextRequest) {
  try {
    const contentType = req.headers.get('content-type') || '';

    if (contentType.includes('multipart/form-data')) {
      return handleZipUpload(req);
    } else {
      return handleGithubImport(req);
    }
  } catch (error: any) {
    console.error('[import-project] Error:', error);
    return NextResponse.json(
      { error: error.message || 'Import failed' },
      { status: 500 }
    );
  }
}

async function handleZipUpload(req: NextRequest): Promise<NextResponse> {
  const formData = await req.formData();
  const file = formData.get('file') as File | null;

  if (!file || !file.name.endsWith('.zip')) {
    return NextResponse.json({ error: 'Please upload a .zip file' }, { status: 400 });
  }

  // Save to temp file
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'sable-import-'));
  const zipPath = path.join(tmpDir, 'upload.zip');
  const extractDir = path.join(tmpDir, 'extracted');
  await fs.mkdir(extractDir, { recursive: true });

  const buffer = Buffer.from(await file.arrayBuffer());
  await fs.writeFile(zipPath, buffer);

  // Extract ZIP using system unzip
  await new Promise<void>((resolve, reject) => {
    exec(`unzip -o "${zipPath}" -d "${extractDir}"`, (err: any) => {
      if (err) reject(new Error('Failed to extract ZIP'));
      else resolve();
    });
  });

  // Read all files from extracted directory
  const files = await readDirectoryRecursive(extractDir, extractDir);

  // Clean up
  await fs.rm(tmpDir, { recursive: true, force: true }).catch(() => {});

  // Write files to sandbox if active
  const provider = (globalThis as any).activeSandboxProvider;
  if (provider) {
    for (const [filePath, content] of Object.entries(files)) {
      try {
        await provider.writeFile(filePath, content);
        if ((globalThis as any).sandboxState?.fileCache) {
          (globalThis as any).sandboxState.fileCache.files[filePath] = {
            content,
            lastModified: Date.now(),
          };
        }
      } catch (e) {
        console.warn(`[import-project] Failed to write ${filePath}:`, e);
      }
    }
  }

  console.log(`[import-project] ZIP import complete: ${Object.keys(files).length} files`);
  return NextResponse.json({ files, count: Object.keys(files).length });
}

async function handleGithubImport(req: NextRequest): Promise<NextResponse> {
  const { githubUrl } = await req.json();

  if (!githubUrl || typeof githubUrl !== 'string') {
    return NextResponse.json({ error: 'Missing GitHub URL' }, { status: 400 });
  }

  // Validate GitHub URL
  const match = githubUrl.match(/github\.com\/([^\/]+)\/([^\/\?#]+)/);
  if (!match) {
    return NextResponse.json({ error: 'Invalid GitHub repository URL' }, { status: 400 });
  }

  const [, owner, repo] = match;
  const repoName = repo.replace(/\.git$/, '');

  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'sable-github-'));
  const cloneDir = path.join(tmpDir, repoName);

  // Clone the repo (shallow, no history)
  await new Promise<void>((resolve, reject) => {
    exec(
      `git clone --depth 1 "${githubUrl}" "${cloneDir}"`,
      { timeout: 60000 },
      (err: any) => {
        if (err) reject(new Error(`Failed to clone repository: ${err.message}`));
        else resolve();
      }
    );
  });

  // Read files (skip .git and node_modules)
  const files = await readDirectoryRecursive(cloneDir, cloneDir, ['.git', 'node_modules', '.next', 'dist', 'build']);

  // Clean up
  await fs.rm(tmpDir, { recursive: true, force: true }).catch(() => {});

  // Write files to sandbox if active
  const provider = (globalThis as any).activeSandboxProvider;
  if (provider) {
    for (const [filePath, content] of Object.entries(files)) {
      try {
        await provider.writeFile(filePath, content);
        if ((globalThis as any).sandboxState?.fileCache) {
          (globalThis as any).sandboxState.fileCache.files[filePath] = {
            content,
            lastModified: Date.now(),
          };
        }
      } catch (e) {
        console.warn(`[import-project] Failed to write ${filePath}:`, e);
      }
    }
  }

  console.log(`[import-project] GitHub import complete: ${Object.keys(files).length} files from ${owner}/${repoName}`);
  return NextResponse.json({ files, count: Object.keys(files).length });
}

async function readDirectoryRecursive(
  dir: string,
  baseDir: string,
  skipDirs: string[] = ['.git', 'node_modules', '.next', 'dist', 'build', '__pycache__']
): Promise<Record<string, string>> {
  const files: Record<string, string> = {};
  const entries = await fs.readdir(dir, { withFileTypes: true });

  for (const entry of entries) {
    if (skipDirs.includes(entry.name)) continue;

    const fullPath = path.join(dir, entry.name);
    const relativePath = path.relative(baseDir, fullPath);

    if (entry.isDirectory()) {
      const subFiles = await readDirectoryRecursive(fullPath, baseDir, skipDirs);
      Object.assign(files, subFiles);
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      // Only read text files
      if (TEXT_EXTENSIONS.has(ext) || entry.name.startsWith('.')) {
        try {
          const content = await fs.readFile(fullPath, 'utf-8');
          // Skip very large files (> 500KB)  
          if (content.length < 500000) {
            files[relativePath] = content;
          }
        } catch {
          // Skip binary or unreadable files
        }
      }
    }
  }

  return files;
}
