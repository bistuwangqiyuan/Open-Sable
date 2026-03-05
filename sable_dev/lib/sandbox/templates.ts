// ─── Sandbox Templates ────────────────────────────────────────────────────────
// Defines the project templates available in Sable Dev Studio.
// Each template sets the initial environment/framework for AI code generation.

export interface Template {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export const templateList: Template[] = [
  {
    id: 'react',
    name: 'React',
    icon: '⚛️',
    description: 'React app with Vite, hooks, and component-based architecture.',
  },
  {
    id: 'nextjs',
    name: 'Next.js',
    icon: '▲',
    description: 'Full-stack Next.js app with App Router and server components.',
  },
  {
    id: 'vue',
    name: 'Vue',
    icon: '💚',
    description: 'Vue 3 app with Composition API and Vite.',
  },
  {
    id: 'vanilla',
    name: 'Vanilla JS',
    icon: '🟨',
    description: 'Plain HTML, CSS and JavaScript — no framework.',
  },
  {
    id: 'node',
    name: 'Node.js',
    icon: '🟩',
    description: 'Node.js backend with Express or plain HTTP server.',
  },
  {
    id: 'python',
    name: 'Python',
    icon: '🐍',
    description: 'Python script or Flask/FastAPI web app.',
  },
];

export type TemplateId = (typeof templateList)[number]['id'];

export const DEFAULT_TEMPLATE: TemplateId = 'react';

/** Look up a template by id — returns undefined if not found. */
export function getTemplate(id: string): Template | undefined {
  return templateList.find((t) => t.id === id);
}
