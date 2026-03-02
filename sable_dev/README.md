# Sable Dev

**AI-powered application builder by MaliosDark.** Describe what you want, and Sable Dev generates, deploys, and iterates on full-stack applications in real-time, powered by local or cloud LLMs.

Part of the **SableCore** ecosystem. Runs as a standalone dev tool or embedded inside the Sable Desktop app.

---

## Architecture Overview

```mermaid
graph TB
    subgraph Client["Browser Client"]
        UI[Next.js Frontend<br/>Dark Theme IDE]
        Chat[AI Chat Panel]
        Preview[Live Preview<br/>iframe]
        CodeView[Code Editor<br/>File Tree]
    end

    subgraph Server["Next.js API Routes"]
        GenStream["/api/generate-ai-code-stream<br/>Streaming Code Generation"]
        ApplyCode["/api/apply-ai-code-stream<br/>Code Application"]
        SandboxAPI["/api/create-ai-sandbox-v2<br/>Sandbox Management"]
        Models["/api/available-models<br/>Model Discovery"]
        Reset["/api/reset-project<br/>Project Reset"]
        History["/api/project-history<br/>Project History"]
        ViteErr["/api/check-vite-errors<br/>Auto Error Detection"]
    end

    subgraph AI["AI Providers"]
        Ollama[Ollama<br/>Local Models]
        OpenWebUI[OpenWebUI<br/>Model Hub]
        OpenAI[OpenAI<br/>GPT-5]
        Anthropic[Anthropic<br/>Claude 4]
        Google[Google<br/>Gemini 3]
        Groq[Groq<br/>Kimi K2]
    end

    subgraph Sandbox["Sandbox Providers"]
        Local[Local Process<br/>/tmp/sable-dev-sandbox-*]
        Vercel[Vercel Sandbox<br/>Cloud Runtime]
        E2B[E2B Sandbox<br/>Cloud Runtime]
    end

    UI --> GenStream
    Chat --> GenStream
    GenStream --> AI
    GenStream --> ApplyCode
    ApplyCode --> Sandbox
    Sandbox --> Preview
    SandboxAPI --> Sandbox
    Models --> AI
```

## Code Generation Flow

```mermaid
sequenceDiagram
    actor User
    participant Chat as Chat Panel
    participant API as /api/generate-ai-code-stream
    participant LLM as AI Provider
    participant Apply as /api/apply-ai-code-stream
    participant Sandbox as Sandbox Runtime
    participant Preview as Live Preview

    User->>Chat: Describe app or edit
    Chat->>API: POST prompt + context
    API->>API: Build system prompt<br/>+ template context
    API->>LLM: streamText() via AI SDK v5
    
    loop Streaming Response
        LLM-->>API: Token chunks
        API-->>Chat: SSE: stream events
        Chat-->>Chat: Parse file tags<br/>Update progress UI
    end
    
    API-->>Chat: SSE: complete event
    Chat->>Apply: POST generated files
    Apply->>Sandbox: Write files to disk
    Sandbox->>Sandbox: Vite HMR auto-reload
    Sandbox-->>Preview: Updated app
    Preview-->>User: See result instantly
    
    Note over Chat,Sandbox: Auto Error Fix Loop
    Chat->>Chat: Poll /api/check-vite-errors
    alt Compile error detected
        Chat->>API: Auto-send fix request<br/>(isErrorFix: true)
        API->>LLM: Focused single-file fix prompt
        LLM-->>API: Fixed code
        API-->>Chat: Apply fix
        Chat->>Apply: Write fixed file
    end
```

## Sandbox Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Creating: User sends first prompt
    Creating --> Installing: Template scaffolded
    Installing --> Starting: npm install complete
    Starting --> Ready: Vite dev server running
    Ready --> Editing: User sends edit prompt
    Editing --> Ready: Files applied via HMR
    Ready --> AutoFix: Compile error detected
    AutoFix --> Ready: Error auto-fixed (max 3 retries)
    Ready --> Reset: User clicks New Project
    Reset --> [*]: Sandbox terminated
    Ready --> [*]: Session timeout
```

## Project Templates

```mermaid
graph LR
    subgraph Templates
        React[React SPA<br/>Vite + Tailwind]
        Fullstack[Full-Stack App<br/>React + Express]
        Static[Static Website<br/>Vanilla HTML/CSS/JS]
        NodeAPI[API Server<br/>Express.js REST]
        NextJS[Next.js App<br/>App Router + RSC]
    end

    Templates --> Scaffold[Template Scaffolding<br/>package.json + vite.config.js<br/>+ pre-built components]
    Scaffold --> Sandbox[Sandbox Creation]
```

---

## Features

| Feature | Description |
|---|---|
| **Multi-Provider AI** | Ollama (local), OpenWebUI, OpenAI, Anthropic, Google, Groq |
| **AI SDK v5** | Uses `streamText()` with `.chat()` for OpenAI-compatible providers |
| **Live Preview** | Instant feedback via Vite HMR in sandboxed iframe |
| **Local Sandbox** | No cloud required, runs Vite in `/tmp` with full npm support |
| **Cloud Sandbox** | Optional Vercel or E2B sandbox providers |
| **Auto Error Fix** | Detects Vite compile errors and auto-sends fix requests (up to 3 retries) |
| **Auto Continue** | Detects incomplete generation and auto-requests remaining files |
| **Pre-built Templates** | React SPA comes with Header, Hero, Features, Footer, AI modifies instead of generating from scratch |
| **5 Templates** | React SPA, Full-Stack (React + Express), Static Site, Node API, Next.js |
| **Project History** | Save/restore projects, New Project resets all state |
| **Edit Mode** | Targeted file edits with context-aware prompts |
| **Code Recovery** | Extracts code from markdown fences if LLM doesn't use file tags |
| **Dark Theme** | Full dark IDE interface |
| **Persistence** | Chat history and session state saved to `.sable-dev/` |
| **Desktop Integration** | Embeddable inside the Sable Desktop Electron app |

---

## Setup

Sable Dev is part of the SableCore monorepo. It lives in the `sable_dev/` directory.

### Prerequisites

- **Node.js** >= 18
- **pnpm** (recommended) or npm
- At least one AI provider configured

### 1. Install

```bash
cd sable_dev
pnpm install
```

### 2. Configure Environment

Create `.env.local` in the `sable_dev/` directory:

```env
# ──────────────────────────────────────────────
# SANDBOX PROVIDER (required)
# ──────────────────────────────────────────────
SANDBOX_PROVIDER=local          # 'local' | 'vercel' | 'e2b'

# ──────────────────────────────────────────────
# AI PROVIDERS, configure at least one
# ──────────────────────────────────────────────

# Local AI (Ollama), no API key needed
OLLAMA_BASE_URL=http://localhost:11434

# OpenWebUI (optional)
OPENWEBUI_BASE_URL=https://your-openwebui-instance.com
OPENWEBUI_API_KEY=sk-your-openwebui-key

# Cloud providers (optional)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# ──────────────────────────────────────────────
# OPTIONAL
# ──────────────────────────────────────────────
MORPH_API_KEY=your_morph_key           # Fast apply for edits

# Vercel Sandbox (if SANDBOX_PROVIDER=vercel)
# VERCEL_TOKEN=your_vercel_token
# VERCEL_TEAM_ID=team_xxx
# VERCEL_PROJECT_ID=prj_xxx

# E2B Sandbox (if SANDBOX_PROVIDER=e2b)
# E2B_API_KEY=your_e2b_key
```

### 3. Run

```bash
pnpm dev
```

Opens on **http://localhost:5700**.

Or start via the SableCore main launcher:

```bash
# From the SableCore root
./start.sh --all
```

---

## Provider Configuration

```mermaid
graph TD
    subgraph Sandbox["Sandbox Provider"]
        SP{SANDBOX_PROVIDER}
        SP -->|local| LP[Local Process<br/>No setup needed<br/>Runs in /tmp]
        SP -->|vercel| VP[Vercel Sandbox<br/>Needs VERCEL_TOKEN]
        SP -->|e2b| EP[E2B Sandbox<br/>Needs E2B_API_KEY]
    end

    subgraph AI["AI Provider Selection"]
        Model{Model Prefix}
        Model -->|ollama/*| OL[Ollama<br/>OLLAMA_BASE_URL]
        Model -->|openwebui/*| OW[OpenWebUI<br/>OPENWEBUI_BASE_URL]
        Model -->|openai/*| OA[OpenAI<br/>OPENAI_API_KEY]
        Model -->|anthropic/*| AN[Anthropic<br/>ANTHROPIC_API_KEY]
        Model -->|google/*| GO[Google<br/>GEMINI_API_KEY]
        Model -->|groq/*| GR[Groq<br/>GROQ_API_KEY]
    end
```

### Local AI Setup (Ollama)

For fully offline operation:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a code-capable model
ollama pull qwen2.5:14b-instruct-q4_K_M

# Sable Dev auto-discovers Ollama models at startup
```

---

## Auto Error Fix & Auto Continue

Sable Dev includes two self-healing mechanisms that run automatically after code generation:

### Auto Error Fix
After applying generated code, the frontend polls `/api/check-vite-errors` to detect compile errors captured from Vite's stderr. If an error is found, it automatically sends a focused fix request to the AI with:
- The exact error message from the Vite compiler
- The content of the broken file
- A laser-focused system prompt for single-file fixes (skips the full agentic workflow)

This loop retries up to **3 times** before stopping and showing the error to the user.

### Auto Continue
When the first generation is incomplete (e.g., the AI ran out of tokens mid-generation), the system detects missing component files and automatically requests the remaining files in a follow-up generation pass.

---

## Project Structure

```
sable_dev/
├── app/
│   ├── layout.tsx                    # Root layout + metadata
│   ├── page.tsx                      # Landing page
│   ├── generation/page.tsx           # Main IDE interface (builder + chat)
│   └── api/
│       ├── generate-ai-code-stream/  # Core: streaming code generation
│       ├── apply-ai-code-stream/     # Writes generated files to sandbox
│       ├── create-ai-sandbox-v2/     # Sandbox provisioning
│       ├── available-models/         # Model discovery (static + Ollama + OpenWebUI)
│       ├── check-vite-errors/        # Auto error detection endpoint
│       ├── get-sandbox-files/        # File tree from sandbox
│       ├── reset-project/            # Full project reset
│       ├── project-history/          # Project history CRUD
│       ├── detect-and-install-packages/ # Auto npm install
│       ├── sandbox-status/           # Sandbox health check
│       ├── sandbox-logs/             # Sandbox log retrieval
│       ├── restart-vite/             # Restart Vite dev server
│       └── ...
├── components/
│   ├── HMRErrorDetector.tsx          # Runtime HMR error detection
│   ├── SandboxPreview.tsx            # Live preview iframe
│   ├── CodeApplicationProgress.tsx   # Code apply progress UI
│   ├── HeroInput.tsx                 # Landing page input
│   └── ui/                           # Reusable UI components (shadcn)
├── lib/
│   ├── sandbox/
│   │   ├── providers/
│   │   │   ├── local-provider.ts     # Local process sandbox (captures Vite errors)
│   │   │   ├── vercel-provider.ts    # Vercel sandbox
│   │   │   └── e2b-provider.ts       # E2B sandbox
│   │   ├── templates/index.ts        # 5 project templates
│   │   ├── factory.ts                # Sandbox provider factory
│   │   └── sandbox-manager.ts        # Sandbox lifecycle management
│   ├── ai/                           # AI provider configuration
│   ├── persistence.ts                # Session persistence (.sable-dev/)
│   ├── context-selector.ts           # File selection for edit context
│   ├── edit-intent-analyzer.ts       # Classifies user edit requests
│   ├── file-parser.ts                # Component tree analysis
│   ├── build-validator.ts            # Build validation utilities
│   └── morph-fast-apply.ts           # Morph fast apply integration
├── config/
│   └── app.config.ts                 # All configurable settings
├── .sable-dev/                       # Auto-created, gitignored
│   ├── session.json                  # Persisted session state
│   ├── chat-history.json             # Chat message history
│   └── project-history.json          # Saved project entries
└── .env.local                        # Your configuration (not committed)
```

---

## Key Technical Details

### AI SDK v5 Compatibility

Sable Dev uses `@ai-sdk/openai` v2.x which defaults to the OpenAI **Responses API** (`/v1/responses`). Since Ollama and OpenWebUI only support the **Chat Completions API** (`/v1/chat/completions`), the code uses `provider.chat(modelId)` instead of `provider(modelId)` for these providers.

### Template-First Generation

The default React SPA template ships with pre-built components (Header, Hero, Features, Footer) using Tailwind CSS. When a user describes an app, the AI **modifies the existing template** rather than generating everything from scratch. This dramatically improves output quality and reduces errors.

### Code Output Format

The LLM is instructed to output **only** XML file tags:

```xml
<file path="src/App.jsx">
import React from 'react';
export default function App() {
  return <div className="text-white">Hello World</div>;
}
</file>
```

If the LLM fails to use file tags, a recovery mechanism attempts to extract code from markdown fences or raw output.

### Error Fix Fast Path

When auto-error-fix triggers, the backend receives an `isErrorFix: true` flag. This activates a focused code path that:
- Replaces the full system prompt with a minimal single-file-fix prompt
- Skips the agentic search workflow
- Injects the broken file content and exact compiler error
- Produces faster, more accurate fixes

### Persistence

Session state is automatically saved to `.sable-dev/` (gitignored):
- Chat history survives page refreshes
- Project history allows switching between projects
- New Project button saves current work before resetting

---

## License

MIT