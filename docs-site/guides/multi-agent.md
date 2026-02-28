# Multi-Agent Orchestration

Open-Sable includes a full multi-agent system that can split complex work across specialised agents operating in parallel or in sequence, sharing context via a **SharedBlackboard**.

---

## Concepts

| Concept | Description |
|---------|-------------|
| **AgentRole** | `COORDINATOR`, `RESEARCHER`, `ANALYST`, `WRITER`, `CODER`, `REVIEWER`, `PLANNER` |
| **AgentTask** | A unit of work assigned to one role, with optional dependencies |
| **SharedBlackboard** | Thread-safe key-value store that all agents read/write during a workflow |
| **MultiAgentOrchestrator** | Low-level engine: builds a dependency graph and executes tasks in topological order |
| **Crew** | High-level CrewAI-style builder: declare members + tasks → `await crew.kickoff()` |
| **WorkflowBuilder** | Helpers for common patterns (research → write, code → review) |

---

## Crew API (recommended)

The `Crew` class is the easiest way to orchestrate multiple agents.

```python
from opensable.core.config import Config
from opensable.core.multi_agent import (
    AgentRole, Crew, CrewMember, CrewTask, SharedBlackboard,
)

config = Config()

crew = Crew(
    config=config,
    members=[
        CrewMember(
            role=AgentRole.RESEARCHER,
            goal="Find relevant papers on the topic",
            backstory="You are a senior research scientist.",
        ),
        CrewMember(
            role=AgentRole.WRITER,
            goal="Draft a clear, engaging article",
            backstory="You are a technical writer with 10 years of experience.",
        ),
        CrewMember(
            role=AgentRole.REVIEWER,
            goal="Ensure accuracy and readability",
        ),
    ],
    tasks=[
        CrewTask(
            description="Research quantum computing advances in 2026",
            assigned_to=AgentRole.RESEARCHER,
            label="research",
        ),
        CrewTask(
            description="Write a 500-word article based on the research",
            assigned_to=AgentRole.WRITER,
            depends_on=["research"],
            label="draft",
        ),
        CrewTask(
            description="Review the draft for correctness and style",
            assigned_to=AgentRole.REVIEWER,
            depends_on=["draft"],
        ),
    ],
)

result = await crew.kickoff()
print(result["results"])        # per-task outputs
print(result["blackboard"])     # shared memory snapshot
```

### Seeding the Blackboard

Pass initial data that any task can reference via `context_keys`:

```python
result = await crew.kickoff(inputs={
    "target_audience": "software engineers",
    "max_length": 500,
})
```

```python
CrewTask(
    description="Write article",
    assigned_to=AgentRole.WRITER,
    context_keys=["target_audience", "max_length"],
    depends_on=["research"],
)
```

### Task hooks

Run a callback after each task completes:

```python
async def on_done(task, result):
    print(f"✅ {task.role.value} finished: {task.task_id}")

crew = Crew(
    config=config,
    members=[...],
    tasks=[...],
    on_task_complete=on_done,
)
```

---

## SharedBlackboard

A thread-safe async key-value store shared by all agents in a workflow.

```python
from opensable.core.multi_agent import SharedBlackboard

bb = SharedBlackboard()

# Write (author is logged for audit)
await bb.write("findings", ["paper1", "paper2"], author="researcher")

# Read
findings = await bb.read("findings", default=[])

# Append to a list
await bb.append_list("sources", "https://arxiv.org/...", author="researcher")

# Snapshot (sync , for logging)
print(bb.snapshot())

# Full audit history
print(bb.history)
# [{"action": "write", "key": "findings", "author": "researcher", "ts": 1708...}, ...]
```

---

## WorkflowBuilder (presets)

For common patterns, use the built-in workflow builders:

### Research & Write

```python
from opensable.core.multi_agent import WorkflowBuilder, MultiAgentOrchestrator
from opensable.core.config import Config

tasks = WorkflowBuilder.research_and_write("The future of local AI agents")
# Creates: RESEARCHER → ANALYST → WRITER → REVIEWER

orchestrator = MultiAgentOrchestrator(Config())
result = await orchestrator.execute_workflow(tasks)
```

### Code Development

```python
tasks = WorkflowBuilder.code_development("Build a REST API for user management")
# Creates: ANALYST → CODER → REVIEWER

result = await orchestrator.execute_workflow(tasks)
```

---

## Auto-routing

For conversational use, the orchestrator can auto-detect whether a task needs multi-agent treatment:

```python
result = await orchestrator.route_complex_task(
    "Write a Python function to parse CSV files and review it for edge cases"
)
# Automatically routes to: CODER + REVIEWER
```

**Routing heuristics:**

| Keywords detected | Agents assigned |
|-------------------|----------------|
| write code, implement, debug, refactor… | `CODER` + `REVIEWER` |
| research, investigate, analyse, compare… | `RESEARCHER` + `ANALYST` |
| write article, draft, essay, summary… | `WRITER` + `REVIEWER` |
| _(none matched)_ | Returns `None` , handled by single agent |

---

## Agent Roles

Each role has a specialised system prompt. You can override it per `CrewMember`:

```python
CrewMember(
    role=AgentRole.CODER,
    goal="Implement the solution in Rust",
    custom_prompt="You are a senior Rust engineer. Always use safe Rust.",
)
```

| Role | Default behaviour |
|------|------------------|
| `COORDINATOR` | Synthesises results from multiple specialists |
| `RESEARCHER` | Finds information, cites sources |
| `ANALYST` | Breaks down problems, provides structured insights |
| `WRITER` | Creates clear, well-structured content |
| `CODER` | Writes clean code with error handling |
| `REVIEWER` | Evaluates quality, suggests improvements |
| `PLANNER` | Decomposes goals into ordered sub-tasks |

---

## Architecture

```
User request
    │
    ▼
MultiAgentOrchestrator
    │
    ├── AgentPool (lazy agent creation per role)
    │     └── SableAgent instances (each with own LLM context)
    │
    ├── SharedBlackboard (async key-value store)
    │     └── audit log of all reads/writes
    │
    └── Dependency graph (topological sort)
          └── parallel execution within each level
```

All agents share the same `Config` (LLM provider, model, etc.) but maintain independent conversation histories.

---

## See Also

- [Skills & Capabilities](skills.md) , Tools available to each agent
- [API Reference](api-reference.md) , Full `MultiAgentOrchestrator` API
- [Self-Modification](self-modification.md) , Agents that improve themselves
