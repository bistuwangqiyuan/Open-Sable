# Quickstart

Get Open-Sable running in under 5 minutes.

!!! info "Requirements"
    - **Python 3.11+** , check with `python3 --version`
    - **8 GB RAM** minimum (16 GB recommended for voice/vision)
    - **Ollama** for local LLMs (or an OpenAI / Anthropic API key)

---

## 1. Install Ollama (local LLM)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3          # ~4 GB download
```

??? tip "Skip Ollama , use a cloud provider instead"
    If you prefer OpenAI or Anthropic, skip this step and add your API key
    in `.env` later:
    ```bash
    OPENAI_API_KEY=sk-...
    # or
    ANTHROPIC_API_KEY=sk-ant-...
    ```

## 2. Clone & Install

```bash
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable

# Create a virtual environment (keeps your system Python clean)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install Open-Sable + core dependencies
pip install -e .
```

## 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your settings. The only **required** value is an LLM provider:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OLLAMA_MODEL` | Local model to use | `llama3` |
| `OPENAI_API_KEY` | OpenAI (cloud) | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic (cloud) | `sk-ant-...` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot | `123456:ABC...` |

## 4. Run

```bash
# Interactive mode (recommended for first run)
python main.py

# Or use the CLI directly
opensable chat "Hello, what can you do?"

# Check available commands
opensable --help
```

You should see:

```
🤖 Open-Sable v1.1.0 , Autonomous AI Agent
Type your message or /help for commands.
> _
```

## 5. Optional , Connect Telegram

```bash
# 1. Talk to @BotFather on Telegram and create a bot
# 2. Add the token to .env:
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...

# 3. Start with Telegram enabled:
python main.py --telegram
```

## 6. Optional , Enable Trading (paper mode)

```bash
# Add to .env:
TRADING_ENABLED=true
TRADING_PAPER_MODE=true    # simulated $10k , no real money

# Then ask Sable:
#   "What's the price of Bitcoin?"
#   "Buy 0.5 ETH"
#   "Show me my portfolio"
```

See the [Trading Guide](../guides/trading.md) for exchange setup and live trading.

## Verify Everything Works

```bash
# Run the test suite
python -m pytest tests/ -q --ignore=tests/test_agent_real.py

# Expected output:
# 297 passed in ~35s
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Activate your venv: `source venv/bin/activate` |
| `ollama: command not found` | Install Ollama: `curl -fsSL https://ollama.com/install.sh \| sh` |
| Python version error | Upgrade to Python 3.11+ |
| ChromaDB errors | `pip install --upgrade chromadb` |
| Permission denied | Don't use `sudo pip` , use a venv instead |

---

## Next Steps

- [Skills & Capabilities](../guides/skills.md) , Browse all 22 built-in skills
- [Multi-Agent Crews](../guides/multi-agent.md) , Orchestrate teams of agents
- [API Reference](../guides/api-reference.md) , Full SDK documentation
- [Trading Guide](../guides/trading.md) , Set up automated trading
- [Web Scraping](../guides/web-scraping.md) , Browser automation tools
- [Production Deployment](../architecture/production.md) , Docker & Kubernetes
