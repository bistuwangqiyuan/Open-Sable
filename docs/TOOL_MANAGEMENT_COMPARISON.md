# Tool Management Comparison: Open-Sable vs OpenClaw

> **Date:** March 2026
> **Purpose:** Architectural comparison of how Open-Sable and OpenClaw handle tool registration, filtering, and delivery to LLMs — with actionable takeaways for Open-Sable.

---

## Table of Contents

1. [Background](#background)
2. [Architecture Overview](#architecture-overview)
3. [Tool Filtering Strategies](#tool-filtering-strategies)
4. [Skills & Lazy Loading](#skills--lazy-loading)
5. [System Prompt Construction](#system-prompt-construction)
6. [Context Management](#context-management)
7. [What OpenClaw Does Better](#what-openclaw-does-better)
8. [What Open-Sable Does Better](#what-open-sable-does-better)
9. [Actionable Improvements](#actionable-improvements)
10. [References](#references)

---

## Background

Open-Sable's agent system registers **~124 tools** across 7 mixin classes (Core, Desktop, Social, Productivity, Trading, Marketplace, Mobile), with schemas spread across 20 domain modules. When all schemas are sent to a local LLM (e.g., Ollama with llama3.1:8b), inference becomes extremely slow — often exceeding the 120-second timeout.

To benchmark our approach, we examined **OpenClaw** (`github.com/openclaw/openclaw`), a 265k-star TypeScript-based personal AI assistant. OpenClaw exposes ~20 core tools plus a plugin/skills ecosystem, managed through a Gateway → Pi-agent RPC architecture.

This document captures the comparison and identifies concrete improvements for Open-Sable.

---

## Architecture Overview

| Aspect | **OpenClaw** | **Open-Sable** |
|--------|-------------|----------------|
| Language | TypeScript (86.7%) | Python (asyncio) |
| Stars | ~265,000 | — |
| LLM integration | Cloud APIs (OpenAI, Anthropic, Google, etc.) | Ollama (local models) |
| Tool count | ~20 core + plugins | ~124 across 7 mixins |
| Tool delivery | JSON schema **+** text list in system prompt | JSON schema only (Ollama function calling) |
| Filtering | Static profile-based allowlists | Dynamic intent-based regex filtering |
| Skill system | Lazy-loaded SKILL.md files (read on demand) | All schemas embedded at startup |
| Configuration | Declarative `openclaw.json` | Hardcoded Python constants |
| Architecture | Gateway (WS) → Pi-agent (RPC) → Tools | Single-process monolith |

### OpenClaw High-Level Flow

```
User Message
  → Gateway (WebSocket control plane)
    → Session queue (serialized runs)
      → System prompt assembly (base + skills list + bootstrap files)
        → Model inference (cloud API)
          → Tool execution (typed, RPC-based)
            → Streaming response
```

### Open-Sable High-Level Flow

```
User Message
  → IntentClassifier (zero-latency regex, 17 intents)
    → Greeting fast-path? → Minimal prompt, zero tools → LLM → Done
    → Full path:
      → Memory retrieval
      → System prompt assembly (intent-conditional blocks)
      → Tool schema filtering (_filter_schemas_for_intent)
      → LLM inference (Ollama, local)
        → Tool execution (async, mixin-based)
          → Multi-step agentic loop
```

---

## Tool Filtering Strategies

### OpenClaw: Profile + Policy Layering (Static)

OpenClaw uses a **4-layer static filtering pipeline**, configured entirely in `openclaw.json`:

```
tools.profile → tools.byProvider → tools.allow/deny → per-agent override
```

#### Tool Profiles (Base Allowlist)

| Profile | Tools Included |
|---------|---------------|
| `minimal` | `session_status` only |
| `coding` | `group:fs`, `group:runtime`, `group:sessions`, `group:memory`, `image` |
| `messaging` | `group:messaging`, `sessions_list`, `sessions_history`, `sessions_send`, `session_status` |
| `full` | No restriction (all tools) |

#### Tool Groups (Shorthands)

Groups expand to multiple tools, simplifying policy composition:

| Group | Expands To |
|-------|-----------|
| `group:runtime` | `exec`, `bash`, `process` |
| `group:fs` | `read`, `write`, `edit`, `apply_patch` |
| `group:sessions` | `sessions_list`, `sessions_history`, `sessions_send`, `sessions_spawn`, `session_status` |
| `group:memory` | `memory_search`, `memory_get` |
| `group:web` | `web_search`, `web_fetch` |
| `group:ui` | `browser`, `canvas` |
| `group:automation` | `cron`, `gateway` |
| `group:messaging` | `message` |

#### Example Configuration

```json
{
  "tools": {
    "profile": "coding",
    "deny": ["group:runtime"],
    "byProvider": {
      "google-antigravity": { "profile": "minimal" }
    }
  },
  "agents": {
    "list": [
      {
        "id": "support",
        "tools": { "profile": "messaging", "allow": ["slack"] }
      }
    ]
  }
}
```

**Key characteristic:** Filtering is decided at **deploy/config time**, not at request time. Each agent gets a fixed tool set. No runtime adaptation.

### Open-Sable: Intent-Based Dynamic Filtering (Runtime)

Open-Sable uses a **runtime pipeline** that adapts per message:

```
User message → IntentClassifier.classify() → _filter_schemas_for_intent() → filtered schemas
```

#### Intent Classifier

- **17 intents** detected via zero-latency regex patterns (no LLM call)
- Intents: `self_modify`, `desktop_screenshot`, `desktop_click`, `desktop_type`, `desktop_hotkey`, `window_list`, `window_focus`, `navigate_url`, `open_app`, `system_command`, `code_question`, `file_operation`, `image_request`, `web_search`, `trading`, `social_media`, `general_chat`

#### Filtering Logic

```python
# ~54 core tools always included
_CORE_SCHEMA_NAMES = frozenset({
    "execute_command", "read_file", "write_file", "browser_search",
    "email_send", "calendar_list_events", "generate_image", ...
})

# Intent → extra tool prefixes
_INTENT_EXTRA_PREFIXES = {
    "desktop_screenshot": ("desktop_", "screen_", "open_app", ...),
    "trading":            ("trading_",),
    "social_media":       ("x_", "grok_", "ig_", "fb_", "linkedin_", ...),
}
```

| Intent | Tools Sent to LLM | Reduction |
|--------|-------------------|-----------|
| `general_chat` | ~54 (core only) | **56% reduction** |
| `social_media` | ~54 + ~60 social = ~114 | ~8% reduction |
| `desktop_*` | ~54 + ~13 desktop = ~67 | ~46% reduction |
| `trading` | ~54 + ~10 trading = ~64 | ~48% reduction |

#### Greeting Fast-Path

For trivial greetings (`hello`, `hi`, `hey`, etc.):
- Detected via `_GREETING_RE` regex
- **Skips entirely:** memory retrieval, tool schemas, bloated system prompt
- Sends only: personality line + current date + LLM call with **zero tools**
- Result: sub-second responses for greetings

**Key characteristic:** Filtering is decided at **request time** based on what the user actually said. The same agent dynamically adjusts its tool set per message.

---

## Skills & Lazy Loading

### OpenClaw: Lazy-Loaded Skills

OpenClaw's skills system is its most architecturally distinct feature:

1. **Skills are directories** containing a `SKILL.md` with YAML frontmatter + instructions
2. **Three locations** (precedence order): workspace > managed (`~/.openclaw/skills`) > bundled
3. **System prompt only includes a compact list:**

```xml
<available_skills>
  <skill>
    <name>nano-banana-pro</name>
    <description>Generate or edit images via Gemini 3 Pro Image</description>
    <location>~/.openclaw/skills/nano-banana-pro/SKILL.md</location>
  </skill>
</available_skills>
```

4. **The model `read`s the SKILL.md only when it decides to use that skill** — instructions are not injected upfront
5. **Token cost:** ~195 chars base + ~97 chars per skill (compared to full schema injection)

#### Gating (Load-Time Filters)

Skills are filtered at load time based on conditions in `metadata.openclaw`:

```yaml
---
name: nano-banana-pro
description: Generate or edit images via Gemini 3 Pro Image
metadata:
  {"openclaw": {"requires": {"bins": ["uv"], "env": ["GEMINI_API_KEY"]}}}
---
```

- `requires.bins` — binaries must exist on PATH
- `requires.env` — environment variables must be set
- `requires.config` — config paths must be truthy
- `os` — platform filter (darwin/linux/win32)

#### Session Snapshots

Skills are snapshot when a session starts and reused for subsequent turns. Changes take effect on the next new session (or via hot-reload watcher).

### Open-Sable: Eager Schema Loading

Open-Sable loads **all tool schemas at startup** from 20 domain modules:

```python
# opensable/core/tools/_schemas/__init__.py
def get_all_schemas():
    return (browser_schemas + system_schemas + core_schemas +
            marketplace_schemas + mobile_schemas + desktop_schemas +
            vision_schemas + x_twitter_schemas + grok_schemas +
            instagram_schemas + facebook_schemas + linkedin_schemas +
            tiktok_schemas + youtube_schemas + documents_schemas +
            email_schemas + calendar_schemas + clipboard_schemas +
            ocr_schemas + trading_schemas)
```

All schemas are JSON objects with full parameter definitions — every parameter, type, description, and enum value is sent to the LLM on every tool-capable request.

**Token impact comparison (estimated):**

| | OpenClaw (12 skills) | Open-Sable (124 tools) |
|---|---|---|
| Skills/tools in prompt | ~546 tokens (name+desc only) | ~8,000+ tokens (full JSON schemas) |
| On-demand cost | Model reads SKILL.md when needed | N/A — always present |
| Wasted tokens | Near zero for unused skills | High for unused tools |

---

## System Prompt Construction

### OpenClaw

The system prompt is rebuilt each run with fixed sections:

1. **Tooling** — current tool list + short descriptions
2. **Safety** — guardrail reminders
3. **Skills** — compact XML list (name + description + location)
4. **Workspace** — working directory
5. **Documentation** — local docs path
6. **Bootstrap files** — `AGENTS.md`, `SOUL.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md` (injected, truncated at 20k chars/file)
7. **Current Date & Time** — timezone only (cache-stable)
8. **Runtime** — host, OS, model, repo root
9. **Sandbox** — when enabled

**Prompt modes** for sub-agents:
- `full` — all sections
- `minimal` — omits skills, memory, self-update, messaging, heartbeats
- `none` — base identity line only

### Open-Sable

The system prompt is built in `_agentic_loop()` with **intent-conditional blocks**:

```python
# Social media instructions (~250 tokens) — only if intent == "social_media"
if _intent.intent == "social_media":
    system_parts.append(social_media_instructions)

# Trading instructions (~200 tokens) — only if intent == "trading"
if _intent.intent == "trading":
    system_parts.append(trading_instructions)

# Desktop control (~400 tokens) — only if intent is desktop-related
if _intent.intent in desktop_intents:
    system_parts.append(desktop_instructions)

# Marketplace, Mobile — keyword-conditional
```

This saves ~1,250 tokens for general messages by omitting irrelevant instruction blocks.

---

## Context Management

### OpenClaw

- **`/context list`** — shows per-file and per-tool schema sizes
- **`/context detail`** — detailed breakdown of biggest contributors
- **Compaction** — summarizes older history to free window space
- **Pruning** — removes old tool results from in-memory prompt
- **Bootstrap cap** — 20k chars/file, 150k chars total
- **Tool schema overhead is visible** and quantified (e.g., `browser: 9,812 chars (~2,453 tok)`)

### Open-Sable

- No built-in context diagnostics
- No compaction mechanism
- Tool schema sizes are not tracked or exposed
- Memory retrieval adds to context but isn't budgeted against a window limit

---

## What OpenClaw Does Better

### 1. Lazy Skill Loading
The most impactful architectural difference. Skills are listed by name in the prompt, and the model reads the full instructions **only when needed**. This keeps the base prompt small while supporting an extensible skill ecosystem.

### 2. Declarative Configuration
Tool policies are configured in JSON — no code changes needed to add/remove/restrict tools:
```json
{ "tools": { "profile": "coding", "deny": ["group:runtime"] } }
```

### 3. Context Transparency
Users can inspect exactly how much each tool/skill/file costs in tokens via `/context detail`. This enables informed optimization.

### 4. Tool Groups
Shorthand groups (`group:fs`, `group:web`, etc.) make policy composition clean and readable, rather than listing individual tool names.

### 5. Provider-Specific Policies
Weaker models can automatically get fewer tools:
```json
{ "tools": { "byProvider": { "google-antigravity": { "profile": "minimal" } } } }
```

### 6. Loop Detection Guardrails
Tracks repeated tool calls and breaks cycles (generic repeat, poll-no-progress, ping-pong patterns) — prevents stuck agent loops.

### 7. Session Snapshots
Skills are snapshot at session start and reused across turns, avoiding redundant re-computation.

---

## What Open-Sable Does Better

### 1. Dynamic Per-Request Adaptation
OpenClaw's profiles are static — the same agent always gets the same tool set. Open-Sable dynamically adjusts tools per message based on intent classification. A user who says "tweet this" gets social tools; "check my files" gets only core tools. No configuration changes or agent switching needed.

### 2. Greeting Fast-Path
Trivial messages like "hello" skip memory, tools, and bloated system prompt entirely — returning in sub-second time. OpenClaw still sends the full system prompt + tool schemas for every message.

### 3. Zero-Latency Intent Classification
The regex-based `IntentClassifier` adds zero latency (no LLM call, no API request). OpenClaw relies on the LLM itself to decide which tools/skills to use.

### 4. Single-Process Simplicity
No gateway, no RPC, no container orchestration. Open-Sable runs as a single Python process with direct Ollama integration — simpler to deploy, debug, and extend.

### 5. Local-First Design
Optimized for local LLMs (Ollama) where token overhead directly impacts inference speed. OpenClaw primarily targets cloud APIs where token overhead affects cost but not latency as dramatically.

---

## Actionable Improvements

Based on this comparison, these are concrete improvements Open-Sable could adopt:

### High Impact

| # | Improvement | Description | Estimated Effort |
|---|------------|-------------|-----------------|
| 1 | **Lazy tool loading** | List tool names + descriptions in system prompt; only include full schemas for tools the intent classifier selects. For remaining tools, let the model request them explicitly. | Medium |
| 2 | **Tool profiles in config** | Define `minimal`, `coding`, `social`, `full` profiles in `config/tools.json`. Users choose a profile; intent classifier narrows further at runtime. | Low |
| 3 | **`tools.allow`/`tools.deny` in config** | Let users whitelist/blacklist tools without code changes. | Low |

### Medium Impact

| # | Improvement | Description | Estimated Effort |
|---|------------|-------------|-----------------|
| 4 | **Tool groups** | Define `group:desktop`, `group:social`, `group:trading`, `group:fs` as shorthands for policy composition. | Low |
| 5 | **Per-model tool policy** | Detect model size (7B/13B/70B) and automatically reduce tool count for smaller models. | Low |
| 6 | **Session-level schema cache** | Cache the filtered schema list per session instead of recomputing every turn. | Low |
| 7 | **Context diagnostics** | Add a `/context` command showing token cost per tool schema, system prompt size, and memory usage. | Low |

### Lower Priority

| # | Improvement | Description | Estimated Effort |
|---|------------|-------------|-----------------|
| 8 | **Loop detection** | Track repeated tool calls with identical params/results and break cycles after N repetitions. | Medium |
| 9 | **Compaction** | Summarize older conversation history to free context window space for long sessions. | Medium |
| 10 | **Prompt modes** | Implement `full`/`minimal`/`none` prompt modes for sub-agent spawning (if multi-agent is added). | Low |

### Recommended Implementation Order

```
Phase 1 (Quick Wins):
  → Tool profiles in config (#2)
  → tools.allow/deny in config (#3)
  → Tool groups (#4)

Phase 2 (Performance):
  → Per-model tool policy (#5)
  → Session-level schema cache (#6)
  → Context diagnostics (#7)

Phase 3 (Architecture):
  → Lazy tool loading (#1)
  → Loop detection (#8)
  → Compaction (#9)
```

---

## References

- **OpenClaw GitHub:** https://github.com/openclaw/openclaw
- **OpenClaw Tools Docs:** https://docs.openclaw.ai/tools
- **OpenClaw Agent Loop:** https://docs.openclaw.ai/concepts/agent-loop
- **OpenClaw System Prompt:** https://docs.openclaw.ai/concepts/system-prompt
- **OpenClaw Skills:** https://docs.openclaw.ai/tools/skills
- **OpenClaw Context:** https://docs.openclaw.ai/concepts/context
- **Open-Sable Agent:** `opensable/core/agent.py`
- **Open-Sable Tool Registry:** `opensable/core/tools/__init__.py`
- **Open-Sable Intent Classifier:** `opensable/core/intent_classifier.py`
- **Open-Sable Tool Schemas:** `opensable/core/tools/_schemas/__init__.py`
