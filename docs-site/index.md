# Open-Sable

**Your personal AI that actually does things , autonomous, local, and yours forever.**

[![CI](https://github.com/IdeoaLabs/Open-Sable/actions/workflows/ci.yml/badge.svg)](https://github.com/IdeoaLabs/Open-Sable/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-297%20passing-brightgreen.svg)](https://github.com/IdeoaLabs/Open-Sable)
[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://github.com/IdeoaLabs/Open-Sable)

---

## What is Open-Sable?

Open-Sable is a fully autonomous, privacy-first agentic AI framework that runs locally on your machine. Unlike cloud-only solutions, **your data stays on your hardware**.

### Key Features

- **🧠 Agentic Loop** , Multi-step reasoning with tool calling, guardrails, and human-in-the-loop
- **🔧 100+ Built-in Tools** , Browser, files, code execution, social media, trading, and more
- **🔒 Privacy First** , Runs on Ollama (local LLMs) or connects to 13+ cloud providers
- **🤝 Multi-Agent Crews** , CrewAI-style orchestration with shared blackboard and role-based agents
- **📊 Token & Cost Tracking** , Real-time usage monitoring across all providers
- **🔐 Encrypted Memory** , Fernet-encrypted structured memory at rest
- **🔌 Interfaces** , Telegram, WhatsApp, REST API, CLI, Web Dashboard

### What's New in v1.1.0

- Token & cost tracking (`TokenTracker`) with per-model pricing
- Encrypted memory at rest (Fernet)
- Crew API for multi-agent orchestration + `SharedBlackboard`
- Proper tool-use protocol (no regex parsing)
- Skills reorganised into `social/`, `media/`, `data/`, `automation/`
- Tools split into modular mixin package
- MkDocs documentation site
- 297 tests (up from 9)

## Quick Start

```bash
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable
python3 -m venv venv && source venv/bin/activate
pip install -e .
ollama pull llama3
python main.py
```

See the [Quickstart](getting-started/quickstart.md) for a guided walkthrough or the [Installation Guide](getting-started/installation.md) for advanced options.

## Architecture

```
opensable/
├── core/
│   ├── agent.py          # SableAgent , brain of the system
│   ├── llm.py            # AdaptiveLLM + CloudLLM with token tracking
│   ├── tools/            # 100+ tools (modular mixin architecture)
│   ├── memory.py         # ChromaDB vectors + encrypted JSON
│   ├── multi_agent.py    # Crew API, orchestrator, SharedBlackboard
│   └── ...
├── interfaces/           # Telegram, WhatsApp, REST, CLI, Web Dashboard
└── skills/
    ├── social/           # X, Grok, Instagram, Facebook, LinkedIn, TikTok, YouTube
    ├── media/            # Image generation, Voice, OCR
    ├── data/             # Database, RAG, File Manager, Documents, Clipboard
    ├── automation/       # Code Executor, API Client, Browser, Scraper, Email, Calendar
    ├── trading/          # Multi-exchange trading engine
    └── community/        # 16 community-contributed skills
```
