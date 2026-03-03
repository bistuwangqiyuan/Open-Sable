# Installing Open-Sable

## Automated Install (Recommended — Any OS)

```bash
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable
python3 install.py
```

The installer handles **everything** automatically:
- Python 3.11+ check
- Virtual environment creation
- All pip dependencies (requirements.txt + opensable package)
- Node.js check/install
- npm sub-projects (Dev Studio, Dashboard, Desktop App, Aggr Charts)
- Playwright browsers (for web scraping)
- Ollama install + optimal LLM model selection
- `.env` configuration from template
- Directory structure setup

```bash
python3 install.py --full      # Install everything, no prompts
python3 install.py --core      # Python core only (minimal, no JS sub-projects)
python3 install.py --status    # Show what's installed / missing
python3 install.py --fix       # Auto-detect and repair broken installs
```

## Manual Install

### Prerequisites

- **Python 3.11+**
- **Ollama** (for local LLM): https://ollama.com
- **Node.js 18+** (optional — for dashboard, marketplace, desktop app)

### Steps

```bash
# 1. Clone
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install -e ".[core]"

# 4. Set up environment
cp .env.example .env
# Edit .env — at minimum set TELEGRAM_BOT_TOKEN if using Telegram

# 5. Create required directories
mkdir -p data logs config

# 6. Install Ollama and pull a model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b

# 7. Run
./start.sh start          # Background (recommended)
# or: python -m opensable  # Foreground
```

### Optional Extras

Install additional features as needed:

```bash
pip install -e ".[core]"         # Telegram + browser automation (recommended)
pip install -e ".[voice]"        # Voice input/output
pip install -e ".[vision]"       # Image analysis + OCR
pip install -e ".[automation]"   # Browser automation (Playwright)
pip install -e ".[monitoring]"   # Prometheus metrics
pip install -e ".[dev]"          # Development tools (pytest, black, ruff)
```

### Dashboard & Sub-projects (Node.js)

These are installed automatically by `python3 install.py`. To install manually:

```bash
# React Dashboard (served at /dashboard on the gateway)
cd dashboard && npm install && npm run build && cd ..

# Dev Studio (AI app builder)
cd sable_dev && npm install && cd ..

# Aggr Charts (crypto market visualization)
cd aggr && npm install && npx vite build --base /aggr/ && cd ..
```

### Desktop App (Electron)

```bash
cd desktop && npm install && npm run dev
```

See [desktop/README.md](desktop/README.md) for details.

### Mobile App

See [mobile/README.md](mobile/README.md) for the SETP protocol and pairing flow.

## Running with `start.sh`

The recommended way to run in production:

```bash
./start.sh start                    # Start default agent (sable)
./start.sh start --profile analyst  # Start a different profile
./start.sh status                   # Check if running
./start.sh logs                     # Follow live logs
./start.sh stop                     # Stop the agent
./start.sh restart                  # Restart
./start.sh profiles                 # List all configured agents
```

## Multi-Agent Profiles

Each agent profile lives in `agents/<name>/` with its own `soul.md`, `profile.env`, `tools.json`, and `data/` directory. See the README.md Multi-Agent Profiles section for full details.

```bash
# Create a new agent
cp -r agents/_template agents/my_agent
# Edit agents/my_agent/soul.md, profile.env, tools.json
./start.sh start --profile my_agent
```

## Docker Install

```bash
docker-compose up -d
```

See the [Dockerfile](Dockerfile) and [docker-compose.yml](docker-compose.yml) for details.

## Verify Installation

```bash
# Check the CLI works
python -m opensable --help

# Check agent status
./start.sh status
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Activate your venv: `source venv/bin/activate` |
| Python version error | Upgrade to Python 3.11+ |
| Ollama not found | Install from https://ollama.com |
| ChromaDB errors | `pip install --upgrade chromadb` |
| Empty responses | Check `logs/sable-sable.log` for errors |
| Desktop app no response | Ensure gateway is running on port 8789 |
| Model not found | Run `ollama pull llama3.1:8b` |

For more help, open an [issue](https://github.com/IdeoaLabs/Open-Sable/issues).
