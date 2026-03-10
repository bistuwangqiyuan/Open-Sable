/**
 * Sable Dev - Project Templates
 * 
 * Defines the available project templates that users can choose from.
 * Each template configures the sandbox setup, file structure, and AI system prompt.
 */

export type TemplateId = 'react-spa' | 'fullstack' | 'static-site' | 'node-api' | 'nextjs';

export interface ProjectTemplate {
  id: TemplateId;
  name: string;
  description: string;
  icon: string; // emoji for simplicity
  category: 'frontend' | 'fullstack' | 'backend';
  tags: string[];
  /** Files to create when setting up the sandbox */
  getFiles: (port: number) => Record<string, string>;
  /** npm install command (default: 'npm install --loglevel warn') */
  installCommand?: string;
  /** Command to start the dev server */
  getDevCommand: (port: number) => string;
  /** The system prompt addition for the AI */
  systemPromptAddition: string;
  /** File format instructions for the AI */
  fileFormatInstructions: string;
}

// ─── React SPA (Vite + React + Tailwind) ─────────────────────────────────────

const reactSpaTemplate: ProjectTemplate = {
  id: 'react-spa',
  name: 'React App',
  description: 'Single-page application with React, Vite, and Tailwind CSS',
  icon: '⚛️',
  category: 'frontend',
  tags: ['react', 'vite', 'tailwind', 'spa'],
  getDevCommand: (port) => `vite --host --port ${port}`,
  systemPromptAddition: `You are MODIFYING an existing React SPA with Vite and Tailwind CSS.
The sandbox already has a complete working app with these components:
- src/App.jsx (imports and renders Header, Hero, Features, Footer)
- src/components/Header.jsx (responsive nav with mobile menu)
- src/components/Hero.jsx (hero section with CTA)
- src/components/Features.jsx (3-column feature grid)
- src/components/Footer.jsx (footer with links and copyright)
- src/index.css (Tailwind directives + smooth scrolling)

CRITICAL: The app is ALREADY WORKING. Your job is to MODIFY the existing files, NOT regenerate from scratch.
- READ the user request and determine which file(s) need changes
- Output ONLY the files that need modification
- Preserve all existing code in files you modify,  only change what the user asked for
- If the user says "make a candy website", modify the content/colors in the EXISTING components, do NOT create new ones
- If the user asks for a new section, create ONE new component and add its import to App.jsx
- Use standard Tailwind classes ONLY (bg-white, text-black, etc.)
- DO NOT create tailwind.config.js, vite.config.js, or package.json
- The ONLY CSS file is src/index.css with @tailwind directives`,
  fileFormatInstructions: `Use this XML format for files:
<file path="src/App.jsx">
// Modified React component code
</file>
<file path="src/components/Hero.jsx">
// Modified component code
</file>

ONLY output files that you CHANGED. Do not output unchanged files.`,
  getFiles: (port) => ({
    'package.json': JSON.stringify({
      name: 'sandbox-app',
      version: '1.0.0',
      type: 'module',
      scripts: {
        dev: `vite --host --port ${port}`,
        build: 'vite build',
        preview: 'vite preview'
      },
      dependencies: {
        react: '^18.2.0',
        'react-dom': '^18.2.0'
      },
      devDependencies: {
        '@vitejs/plugin-react': '^4.0.0',
        vite: '^4.3.9',
        tailwindcss: '^3.3.0',
        postcss: '^8.4.31',
        autoprefixer: '^10.4.16'
      }
    }, null, 2),

    'vite.config.js': `import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: ${port},
    strictPort: true,
    hmr: true
  }
})`,

    'tailwind.config.js': `/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}`,

    'postcss.config.js': `export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}`,

    'index.html': `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Sandbox App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>`,

    'src/main.jsx': `import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)`,

    'src/App.jsx': `import Header from './components/Header.jsx'
import Hero from './components/Hero.jsx'
import Features from './components/Features.jsx'
import Footer from './components/Footer.jsx'

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Header />
      <Hero />
      <Features />
      <Footer />
    </div>
  )
}

export default App`,

    'src/components/Header.jsx': `import { useState } from 'react'

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 bg-gray-950/80 backdrop-blur-md border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <a href="#" className="text-xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            MyApp
          </a>
          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-sm text-gray-300 hover:text-white transition-colors">Features</a>
            <a href="#about" className="text-sm text-gray-300 hover:text-white transition-colors">About</a>
            <a href="#contact" className="text-sm text-gray-300 hover:text-white transition-colors">Contact</a>
            <a href="#" className="px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors">
              Get Started
            </a>
          </nav>
          <button
            className="md:hidden p-2 text-gray-400 hover:text-white"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {menuOpen
                ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />}
            </svg>
          </button>
        </div>
        {menuOpen && (
          <div className="md:hidden pb-4 space-y-2">
            <a href="#features" className="block px-3 py-2 text-gray-300 hover:text-white rounded-lg hover:bg-gray-800">Features</a>
            <a href="#about" className="block px-3 py-2 text-gray-300 hover:text-white rounded-lg hover:bg-gray-800">About</a>
            <a href="#contact" className="block px-3 py-2 text-gray-300 hover:text-white rounded-lg hover:bg-gray-800">Contact</a>
          </div>
        )}
      </div>
    </header>
  )
}`,

    'src/components/Hero.jsx': `export default function Hero() {
  return (
    <section className="relative overflow-hidden py-24 sm:py-32 lg:py-40">
      <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 via-purple-600/10 to-transparent" />
      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight mb-6">
          Build Something{' '}
          <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Amazing
          </span>
        </h1>
        <p className="max-w-2xl mx-auto text-lg sm:text-xl text-gray-400 mb-10">
          A modern, fast, and beautiful starting point for your next project.
          Powered by React, Vite, and Tailwind CSS.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a href="#features" className="px-8 py-3 text-base font-semibold bg-blue-600 hover:bg-blue-700 rounded-xl transition-all hover:scale-105 shadow-lg shadow-blue-600/25">
            Explore Features
          </a>
          <a href="#contact" className="px-8 py-3 text-base font-semibold border border-gray-700 hover:border-gray-500 rounded-xl transition-colors">
            Contact Us
          </a>
        </div>
      </div>
    </section>
  )
}`,

    'src/components/Features.jsx': `const features = [
  {
    title: 'Lightning Fast',
    description: 'Built with Vite for instant hot module replacement and blazing fast builds.',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    title: 'Modern Stack',
    description: 'React 18 with hooks, Tailwind CSS for styling, and ES modules throughout.',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    title: 'Fully Responsive',
    description: 'Looks great on every screen size, from mobile phones to ultra-wide monitors.',
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
]

export default function Features() {
  return (
    <section id="features" className="py-20 sm:py-28">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl sm:text-4xl font-bold mb-4">Features</h2>
          <p className="text-gray-400 max-w-2xl mx-auto">
            Everything you need to build modern web applications, right out of the box.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feature, i) => (
            <div
              key={i}
              className="group p-8 rounded-2xl bg-gray-900 border border-gray-800 hover:border-blue-500/50 transition-all hover:shadow-lg hover:shadow-blue-500/5"
            >
              <div className="w-14 h-14 flex items-center justify-center rounded-xl bg-blue-600/10 text-blue-400 mb-6 group-hover:bg-blue-600/20 transition-colors">
                {feature.icon}
              </div>
              <h3 className="text-xl font-semibold mb-3">{feature.title}</h3>
              <p className="text-gray-400 leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}`,

    'src/components/Footer.jsx': `export default function Footer() {
  return (
    <footer className="border-t border-gray-800 py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-sm text-gray-500">
            &copy; {new Date().getFullYear()} MyApp. All rights reserved.
          </span>
          <div className="flex gap-6">
            <a href="#" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">Privacy</a>
            <a href="#" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">Terms</a>
            <a href="#contact" className="text-sm text-gray-500 hover:text-gray-300 transition-colors">Contact</a>
          </div>
        </div>
      </div>
    </footer>
  )
}`,

    'src/index.css': `@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    font-synthesis: none;
    text-rendering: optimizeLegibility;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { scroll-behavior: smooth; }
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
  background-color: rgb(3 7 18);
}`
  })
};

// ─── Full-Stack (React + Express) ─────────────────────────────────────────────

const fullstackTemplate: ProjectTemplate = {
  id: 'fullstack',
  name: 'Full-Stack App',
  description: 'React frontend + Express.js API backend with Tailwind CSS',
  icon: '🔄',
  category: 'fullstack',
  tags: ['react', 'express', 'node', 'api', 'fullstack'],
  getDevCommand: (port) => `npx concurrently "vite --host --port ${port}" "node server/index.js"`,
  systemPromptAddition: `You are building a full-stack application with React (Vite) frontend and Express.js backend.

FRONTEND (src/):
- React SPA in src/ with Vite and Tailwind CSS
- Entry: src/main.jsx → src/App.jsx
- Components: src/components/
- Use Tailwind CSS for all styling
- Make API calls to /api/* endpoints (they proxy to the Express server)

BACKEND (server/):
- Express.js server in server/index.js
- Routes in server/routes/
- Put API endpoints under /api/* prefix
- Use express.json() for body parsing
- Server runs on port 3001 by default

IMPORTANT:
- Frontend fetches from relative URLs like '/api/users'
- Vite proxy is configured to forward /api/* to the Express server
- DO NOT hardcode localhost URLs in the frontend
- For database, use in-memory storage or JSON files (no external DB)`,
  fileFormatInstructions: `Use this XML format for files:
<file path="src/App.jsx">
// React frontend code
</file>
<file path="server/routes/users.js">
// Express route code
</file>`,
  getFiles: (port) => ({
    'package.json': JSON.stringify({
      name: 'sandbox-fullstack',
      version: '1.0.0',
      type: 'module',
      scripts: {
        dev: `concurrently "vite --host --port ${port}" "node server/index.js"`,
        build: 'vite build',
        start: 'node server/index.js'
      },
      dependencies: {
        react: '^18.2.0',
        'react-dom': '^18.2.0',
        express: '^4.18.2',
        cors: '^2.8.5'
      },
      devDependencies: {
        '@vitejs/plugin-react': '^4.0.0',
        vite: '^4.3.9',
        tailwindcss: '^3.3.0',
        postcss: '^8.4.31',
        autoprefixer: '^10.4.16',
        concurrently: '^8.2.0'
      }
    }, null, 2),

    'vite.config.js': `import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: ${port},
    strictPort: true,
    hmr: true,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      }
    }
  }
})`,

    'tailwind.config.js': `/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}`,

    'postcss.config.js': `export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}`,

    'index.html': `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Full-Stack App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>`,

    'src/main.jsx': `import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)`,

    'src/App.jsx': `import { useState, useEffect } from 'react'

function App() {
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => setMessage(data.message))
      .catch(() => setMessage('API server starting...'))
  }, [])

  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="text-center max-w-2xl">
        <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-green-400 to-blue-500 bg-clip-text text-transparent">
          Full-Stack Ready
        </h1>
        <p className="text-lg text-gray-400 mb-4">
          React + Express.js + Tailwind CSS
        </p>
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <p className="text-sm text-gray-500 mb-1">API Response:</p>
          <p className="text-green-400 font-mono">{message}</p>
        </div>
      </div>
    </div>
  )
}

export default App`,

    'src/index.css': `@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: rgb(17 24 39);
}`,

    'server/index.js': `import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// Health check
app.get('/api/health', (req, res) => {
  res.json({ message: 'API server running!', timestamp: new Date().toISOString() });
});

// Example: In-memory data store
const items = [];

app.get('/api/items', (req, res) => {
  res.json(items);
});

app.post('/api/items', (req, res) => {
  const item = { id: Date.now(), ...req.body, createdAt: new Date().toISOString() };
  items.push(item);
  res.status(201).json(item);
});

app.listen(PORT, () => {
  console.log(\`API server running on port \${PORT}\`);
});
`
  })
};

// ─── Static Site (Vanilla HTML/CSS/JS) ────────────────────────────────────────

const staticSiteTemplate: ProjectTemplate = {
  id: 'static-site',
  name: 'Static Website',
  description: 'Vanilla HTML, CSS, and JavaScript,  no framework, no build step',
  icon: '🌐',
  category: 'frontend',
  tags: ['html', 'css', 'javascript', 'vanilla', 'static'],
  getDevCommand: (port) => `vite --host --port ${port}`,
  systemPromptAddition: `You are building a static website with vanilla HTML, CSS, and JavaScript.
- No React, no frameworks,  pure HTML/CSS/JS
- The entry point is index.html
- Put styles in styles/main.css
- Put scripts in js/main.js
- Use modern CSS (flexbox, grid, custom properties)
- Use ES6+ JavaScript (modules, arrow functions, template literals)
- Vite serves the files with hot reload
- You CAN use npm packages via ES module imports from node_modules
- For icons, use inline SVGs or a CDN like Font Awesome`,
  fileFormatInstructions: `Use this XML format for files:
<file path="index.html">
<!-- HTML code -->
</file>
<file path="styles/main.css">
/* CSS styles */
</file>
<file path="js/main.js">
// JavaScript code
</file>`,
  getFiles: (port) => ({
    'package.json': JSON.stringify({
      name: 'sandbox-static',
      version: '1.0.0',
      type: 'module',
      scripts: {
        dev: `vite --host --port ${port}`,
        build: 'vite build',
        preview: 'vite preview'
      },
      devDependencies: {
        vite: '^4.3.9'
      }
    }, null, 2),

    'vite.config.js': `import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: ${port},
    strictPort: true,
    hmr: true
  }
})`,

    'index.html': `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Static Site</title>
    <link rel="stylesheet" href="/styles/main.css" />
  </head>
  <body>
    <div id="app">
      <div class="hero">
        <h1>Static Site Ready</h1>
        <p>Pure HTML, CSS, and JavaScript,  no framework needed.</p>
      </div>
    </div>
    <script type="module" src="/js/main.js"></script>
  </body>
</html>`,

    'styles/main.css': `*, *::before, *::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --color-bg: #111827;
  --color-text: #f9fafb;
  --color-accent: #3b82f6;
  --color-muted: #9ca3af;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: var(--color-bg);
  color: var(--color-text);
  min-height: 100vh;
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  text-align: center;
  padding: 2rem;
}

.hero h1 {
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 1rem;
  background: linear-gradient(to right, var(--color-accent), #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero p {
  font-size: 1.125rem;
  color: var(--color-muted);
}
`,

    'js/main.js': `// Your JavaScript code here
console.log('Static site loaded!');
`
  })
};

// ─── Node.js API Server ───────────────────────────────────────────────────────

const nodeApiTemplate: ProjectTemplate = {
  id: 'node-api',
  name: 'API Server',
  description: 'Express.js REST API with Node.js,  backend only, no frontend',
  icon: '🖥️',
  category: 'backend',
  tags: ['express', 'node', 'api', 'rest', 'backend'],
  getDevCommand: (port) => `node --watch index.js`,
  systemPromptAddition: `You are building a Node.js REST API with Express.js.
- This is a BACKEND-ONLY project,  no frontend, no React, no HTML pages
- Main entry: index.js
- Routes go in routes/ directory
- Middleware goes in middleware/ directory
- Use express.json() for body parsing
- Use cors for cross-origin requests
- For data storage, use in-memory objects/arrays or JSON files
- API responses should be JSON
- Follow RESTful conventions (GET, POST, PUT, DELETE)
- The server listens on port ${'{PORT}'} (provided by environment)
- For testing, the user can see JSON responses in the preview iframe

OUTPUT FORMAT: Since there's no frontend, the root route (GET /) should return an HTML page
that documents the available API endpoints as a nice developer-friendly page.`,
  fileFormatInstructions: `Use this XML format for files:
<file path="index.js">
// Express server code
</file>
<file path="routes/users.js">
// Route handler code
</file>`,
  getFiles: (port) => ({
    'package.json': JSON.stringify({
      name: 'sandbox-api',
      version: '1.0.0',
      type: 'module',
      scripts: {
        dev: 'node --watch index.js',
        start: 'node index.js'
      },
      dependencies: {
        express: '^4.18.2',
        cors: '^2.8.5'
      }
    }, null, 2),

    'index.js': `import express from 'express';
import cors from 'cors';

const app = express();
const PORT = process.env.PORT || ${port};

app.use(cors());
app.use(express.json());

// API Documentation page
app.get('/', (req, res) => {
  res.send(\`
    <!DOCTYPE html>
    <html>
      <head>
        <title>API Server</title>
        <style>
          body { font-family: -apple-system, sans-serif; background: #111827; color: #f9fafb; padding: 2rem; }
          h1 { background: linear-gradient(to right, #10b981, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
          .endpoint { background: #1f2937; padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0; border: 1px solid #374151; }
          .method { font-weight: bold; color: #10b981; }
          code { color: #60a5fa; }
        </style>
      </head>
      <body>
        <h1>API Server Ready</h1>
        <p style="color: #9ca3af;">Express.js REST API</p>
        <h2 style="margin-top: 1.5rem;">Endpoints</h2>
        <div class="endpoint"><span class="method">GET</span> <code>/api/health</code>,  Health check</div>
        <div class="endpoint"><span class="method">GET</span> <code>/api/items</code>,  List all items</div>
        <div class="endpoint"><span class="method">POST</span> <code>/api/items</code>,  Create item</div>
      </body>
    </html>
  \`);
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// In-memory data store
const items = [];

app.get('/api/items', (req, res) => {
  res.json(items);
});

app.post('/api/items', (req, res) => {
  const item = { id: Date.now(), ...req.body, createdAt: new Date().toISOString() };
  items.push(item);
  res.status(201).json(item);
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(\`API server running on http://localhost:\${PORT}\`);
});
`
  })
};

// ─── Next.js App ──────────────────────────────────────────────────────────────

const nextjsTemplate: ProjectTemplate = {
  id: 'nextjs',
  name: 'Next.js App',
  description: 'Full-featured Next.js with App Router, React Server Components, and Tailwind',
  icon: '▲',
  category: 'fullstack',
  tags: ['nextjs', 'react', 'ssr', 'fullstack', 'tailwind'],
  getDevCommand: (port) => `npx next dev -p ${port} -H 0.0.0.0`,
  systemPromptAddition: `You are building a Next.js application with the App Router.
- Use the app/ directory for routing (App Router)
- app/layout.js is the root layout (REQUIRED)
- app/page.js is the home page
- Create routes as app/[route]/page.js
- API routes go in app/api/[route]/route.js
- Use 'use client' directive for client-side components
- Server Components are the default (no directive needed)
- Style with Tailwind CSS utility classes
- Global styles in app/globals.css
- For data fetching, use fetch() in Server Components or Route Handlers
- images go in public/ directory

IMPORTANT:
- ALWAYS include app/layout.js with html, body tags and globals.css import
- ALWAYS include app/globals.css with @tailwind directives
- DO NOT create next.config.js,  it already exists
- DO NOT create package.json,  it already exists
- DO NOT create tailwind.config.js,  it already exists`,
  fileFormatInstructions: `Use this XML format for files:
<file path="app/page.js">
// Next.js page component
</file>
<file path="app/api/hello/route.js">
// API route handler
</file>`,
  getFiles: (port) => ({
    'package.json': JSON.stringify({
      name: 'sandbox-nextjs',
      version: '1.0.0',
      scripts: {
        dev: `next dev -p ${port} -H 0.0.0.0`,
        build: 'next build',
        start: 'next start'
      },
      dependencies: {
        next: '^14.0.0',
        react: '^18.2.0',
        'react-dom': '^18.2.0'
      },
      devDependencies: {
        tailwindcss: '^3.3.0',
        postcss: '^8.4.31',
        autoprefixer: '^10.4.16'
      }
    }, null, 2),

    'next.config.js': `/** @type {import('next').NextConfig} */
const nextConfig = {};
export default nextConfig;`,

    'tailwind.config.js': `/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}`,

    'postcss.config.js': `module.exports = {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}`,

    'app/layout.js': `import './globals.css'

export const metadata = {
  title: 'Next.js App',
  description: 'Built with Sable Dev',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}`,

    'app/page.js': `export default function Home() {
  return (
    <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-4">
      <div className="text-center max-w-2xl">
        <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent">
          Next.js Ready
        </h1>
        <p className="text-lg text-gray-400">
          App Router + React Server Components + Tailwind CSS
        </p>
      </div>
    </div>
  )
}`,

    'app/globals.css': `@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background-color: rgb(17 24 39);
}`,

    'app/api/health/route.js': `import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ status: 'ok', timestamp: new Date().toISOString() });
}
`
  })
};

// ─── Template Registry ────────────────────────────────────────────────────────

export const templates: Record<TemplateId, ProjectTemplate> = {
  'react-spa': reactSpaTemplate,
  'fullstack': fullstackTemplate,
  'static-site': staticSiteTemplate,
  'node-api': nodeApiTemplate,
  'nextjs': nextjsTemplate,
};

export const templateList = Object.values(templates);

export const DEFAULT_TEMPLATE: TemplateId = 'react-spa';

export function getTemplate(id: string): ProjectTemplate {
  return templates[id as TemplateId] || templates[DEFAULT_TEMPLATE];
}
