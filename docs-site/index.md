# Open-Sable

**Your personal AI that actually does things — autonomous, local, and yours forever.**

[![CI](https://github.com/IdeoaLabs/Open-Sable/actions/workflows/ci.yml/badge.svg)](https://github.com/IdeoaLabs/Open-Sable/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

---

## What is Open-Sable?

Open-Sable is a fully autonomous, privacy-first agentic AI framework that runs locally on your machine. Unlike cloud-only solutions, **your data stays on your hardware**.

### Key Features

- **🧠 Agentic Loop** — Multi-step reasoning with tool calling, guardrails, and human-in-the-loop
- **🔧 100+ Built-in Tools** — Browser, files, code execution, social media, trading, and more
- **🔒 Privacy First** — Runs on Ollama (local LLMs) or connects to 13+ cloud providers
- **🤝 Multi-Agent Crews** — CrewAI-style orchestration with shared blackboard and role-based agents
- **📊 Token & Cost Tracking** — Real-time usage monitoring across all providers
- **🔐 Encrypted Memory** — Fernet-encrypted structured memory at rest
- **🔌 Interfaces** — Telegram, WhatsApp, REST API, CLI, Web Dashboard

## Quick Start

```bash
# Clone and install
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable
pip install -e .

# Start with Ollama (local)
ollama pull llama3
python main.py
```

See the [Installation Guide](getting-started/installation.md) for detailed setup instructions.

## Architecture

```
opensable/
├── core/
│   ├── agent.py          # SableAgent — brain of the system
│   ├── llm.py            # AdaptiveLLM + CloudLLM with token tracking
│   ├── tools/            # 100+ tools (modular mixin architecture)
│   ├── memory.py          # ChromaDB vectors + encrypted JSON
│   ├── multi_agent.py     # Crew API, orchestrator, distributed coordinator
│   └── ...
├── interfaces/           # Telegram, WhatsApp, REST, CLI
└── skills/               # X, Instagram, Facebook, LinkedIn, TikTok, YouTube
```
