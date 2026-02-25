# Quickstart

Get Open-Sable running in under 5 minutes.

## 1. Install Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3
```

## 2. Clone & Install

```bash
git clone https://github.com/IdeoaLabs/Open-Sable.git
cd Open-Sable
python3 -m venv venv && source venv/bin/activate
pip install -e .
```

## 3. Configure

```bash
cp .env.example .env
# Edit .env with your settings (API keys, Telegram token, etc.)
```

## 4. Run

```bash
# Interactive CLI
python main.py

# Or use the CLI
opensable chat "Hello, what can you do?"
```

## 5. Optional: Telegram Bot

```bash
# Set TELEGRAM_BOT_TOKEN in .env, then:
python main.py --telegram
```

## Next Steps

- [API Reference](../guides/api-reference.md) — Full SDK documentation
- [Trading Guide](../guides/trading.md) — Set up automated trading
- [Web Scraping](../guides/web-scraping.md) — Browser automation tools
- [Production Deployment](../architecture/production.md) — Docker & Kubernetes
