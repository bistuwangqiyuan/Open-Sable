import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const PERSISTENCE_DIR = path.join(process.cwd(), '.sable-dev');
const HISTORY_FILE = path.join(PERSISTENCE_DIR, 'project-history.json');

export interface ProjectHistoryEntry {
  id: string;
  name: string;
  prompt: string;
  template: string;
  model: string;
  createdAt: number;
  updatedAt: number;
  fileCount: number;
  sandboxId?: string;
  thumbnail?: string; // base64 small screenshot
}

interface ProjectHistoryData {
  version: number;
  projects: ProjectHistoryEntry[];
}

function ensureDir() {
  if (!fs.existsSync(PERSISTENCE_DIR)) {
    fs.mkdirSync(PERSISTENCE_DIR, { recursive: true });
  }
}

function loadHistory(): ProjectHistoryData {
  try {
    if (!fs.existsSync(HISTORY_FILE)) {
      return { version: 1, projects: [] };
    }
    const raw = fs.readFileSync(HISTORY_FILE, 'utf-8');
    return JSON.parse(raw);
  } catch {
    return { version: 1, projects: [] };
  }
}

function saveHistory(data: ProjectHistoryData) {
  ensureDir();
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * GET /api/project-history — list all saved projects
 */
export async function GET() {
  try {
    const history = loadHistory();
    // Sort by most recently updated
    history.projects.sort((a, b) => b.updatedAt - a.updatedAt);
    return NextResponse.json({ success: true, projects: history.projects });
  } catch (error) {
    console.error('[project-history] GET error:', error);
    return NextResponse.json({ success: false, error: (error as Error).message }, { status: 500 });
  }
}

/**
 * POST /api/project-history — add or update a project entry
 * body: { action: 'add' | 'update' | 'delete', project: ProjectHistoryEntry }
 */
export async function POST(request: NextRequest) {
  try {
    const { action, project } = await request.json();
    const history = loadHistory();

    switch (action) {
      case 'add': {
        // Prevent duplicates by id
        const existing = history.projects.findIndex(p => p.id === project.id);
        if (existing >= 0) {
          history.projects[existing] = { ...history.projects[existing], ...project, updatedAt: Date.now() };
        } else {
          history.projects.push({ ...project, createdAt: Date.now(), updatedAt: Date.now() });
        }
        // Keep max 50 projects
        if (history.projects.length > 50) {
          history.projects = history.projects
            .sort((a, b) => b.updatedAt - a.updatedAt)
            .slice(0, 50);
        }
        saveHistory(history);
        return NextResponse.json({ success: true, message: 'Project saved' });
      }

      case 'update': {
        const idx = history.projects.findIndex(p => p.id === project.id);
        if (idx >= 0) {
          history.projects[idx] = { ...history.projects[idx], ...project, updatedAt: Date.now() };
          saveHistory(history);
        }
        return NextResponse.json({ success: true, message: 'Project updated' });
      }

      case 'delete': {
        history.projects = history.projects.filter(p => p.id !== project.id);
        saveHistory(history);
        return NextResponse.json({ success: true, message: 'Project deleted' });
      }

      default:
        return NextResponse.json({ success: false, error: 'Unknown action' }, { status: 400 });
    }
  } catch (error) {
    console.error('[project-history] POST error:', error);
    return NextResponse.json({ success: false, error: (error as Error).message }, { status: 500 });
  }
}
