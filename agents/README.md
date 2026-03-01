# Agent Profiles

**All agents** live under `agents/`. There is no special "base agent" — every agent, including the primary one (`sable`), has its own folder with its own soul, config, tools, and data.

## Directory Structure

```
agents/
  _template/          ← copy this to create a new profile
    soul.md           ← agent's immutable identity / personality foundation
    profile.env       ← FULL environment configuration for this agent
    tools.json        ← which tools/skills this agent can use
    data/             ← profile-specific memory, consciousness, checkpoints
  sable/              ← the PRIMARY agent (default when no --profile given)
  analyst/            ← analytical intelligence agent
```

## Quick Start

```bash
# Start sable (default — no --profile needed)
./start.sh start

# Start a specific agent
./start.sh start --profile analyst

# List all agents and their status
./start.sh profiles

# Stop / restart / logs
./start.sh stop --profile analyst
./start.sh restart --profile my_agent
./start.sh logs --profile sable
```

## Creating a New Agent

```bash
# 1. Create from template
cp -r agents/_template agents/my_agent

# 2. Edit the full config
nano agents/my_agent/soul.md         # who is this agent?
nano agents/my_agent/profile.env     # FULL config (LLM, Telegram, X, etc.)
nano agents/my_agent/tools.json      # which tools can it use?

# 3. Launch it
./start.sh start --profile my_agent
```

## Profile Files

### `soul.md`
The agent's immutable identity. This is injected into the system prompt and defines
who the agent *is*. Each profile must have a unique soul.

### `profile.env`
**Complete** environment configuration for this agent. Every variable the system
supports is defined here — LLM, Telegram, X/Twitter, gateway port, behavior,
database, monitoring, etc. Each agent is self-contained.
AGENT_PERSONALITY=professional
WEBCHAT_PORT=8790
X_USERNAME=my_other_account
X_EMAIL=other@email.com
X_PASSWORD=secret
X_STYLE=news
X_TOPICS=finance,markets
X_ENABLED=true
X_AUTOPOSTER_ENABLED=true
```

### `tools.json`
Controls which tools/skills this agent has access to. Three modes:

```json
{"mode": "all", "tools": []}
```

```json
{
  "mode": "allowlist",
  "tools": ["web_search", "execute_command", "x_post_tweet", "x_reply", "grok_chat"]
}
```

```json
{
  "mode": "denylist",
  "tools": ["trading_place_trade", "email_send", "desktop_click"]
}
```

### `data/`
Profile-specific data directory. Memory, consciousness journal, checkpoints, and
vector DB are stored here so agents don't interfere with each other.

> **Note:** The `sable` agent's `data/` is a symlink to the root `data/` to preserve
> the original agent's existing memory and consciousness.

## Multiple Agents on X

Each X agent needs **different credentials** (different `X_USERNAME`/`X_EMAIL`/`X_PASSWORD`
or different cookies) and a **different gateway port** (`WEBCHAT_PORT`).

## Architecture

```
./start.sh start                             ← sable (default)
./start.sh start --profile analyst           ← agents/analyst/
./start.sh start --profile my_agent           ← agents/my_agent/
     │                                         │                    │
     ▼                                         ▼                    ▼
  SableAgent                            SableAgent             SableAgent
  port 8789                             port 8790              port 8791
  /tmp/sable-sable.sock                 /tmp/sable-analyst.sock  /tmp/sable-my_agent.sock
  agents/sable/data/                    agents/analyst/data/   agents/my_agent/data/
```

Each agent runs as a **completely independent process** with its own PID file,
log file, gateway socket, and data directory. Every agent is equal — no special treatment.
