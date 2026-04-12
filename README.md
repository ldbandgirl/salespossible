# SalesPossible

**OpenClaw × Hermes Hybrid AI Sales Agent**

A personal AI sales assistant that combines two leading open-source agent architectures:

| Component | From | What it does |
|-----------|------|-------------|
| SOUL.md identity system | [OpenClaw](https://github.com/openclaw/openclaw) | Persistent personality, style, and memory files |
| SKILL.md skill library | OpenClaw | Reusable, markdown-defined agentic workflows |
| Multi-platform gateway | OpenClaw | CLI, Telegram, Discord from a single process |
| SQLite + FTS5 memory | [Hermes Agent](https://github.com/NousResearch/hermes-agent) | Cross-session recall via full-text search |
| Self-improving skills | Hermes | Skills improve after successful sessions |
| Subagent spawning | Hermes | Parallel tool execution for research tasks |
| Cron scheduling | Hermes | Daily digests, follow-up reminders |

---

## Quick Start

### 1. Install

```bash
# With UV (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .

# Or with pip
pip install -e .
```

### 2. Configure

```bash
salespossible setup
# or manually:
cp .env.example .env
# edit .env with your ANTHROPIC_API_KEY
```

### 3. Run

```bash
salespossible                    # Interactive CLI
salespossible --gateway telegram # Telegram bot
salespossible run "Research Acme Corp"  # One-shot
```

---

## Architecture

```
salespossible/
├── agent/
│   ├── core.py           # Main hybrid agent loop
│   ├── config.py         # Configuration (YAML + env)
│   ├── llm.py            # Anthropic Claude client (with prompt caching)
│   ├── gateway/          # Messaging platforms
│   │   ├── cli.py        # Interactive terminal
│   │   └── telegram.py   # Telegram bot
│   ├── memory/           # Hermes-style memory
│   │   ├── persistent.py # SQLite + FTS5 session store
│   │   └── context_loader.py  # SOUL.md → system prompt
│   ├── skills/           # OpenClaw/Hermes skill system
│   │   ├── loader.py     # Parse SKILL.md files
│   │   └── manager.py    # Trigger matching + self-improvement
│   └── tools/            # Tool implementations
│       ├── registry.py   # Tool dispatcher
│       ├── crm.py        # HubSpot / Salesforce / mock
│       ├── email_tool.py # Draft + send emails
│       ├── search_tool.py# DuckDuckGo web search
│       └── code_exec.py  # Python sandbox
├── soul/                 # OpenClaw identity files
│   ├── SOUL.md           # Who the agent is
│   ├── STYLE.md          # How it communicates
│   └── MEMORY.md         # Persistent user facts (auto-updated)
└── skills/               # SKILL.md library
    ├── prospecting/      # Company & contact research
    ├── crm_lookup/       # Pipeline queries
    ├── email_outreach/   # Cold/warm email drafting
    ├── followup/         # Stalled deal re-engagement
    ├── meeting_prep/     # Call brief generation
    └── pipeline_analysis/# Revenue forecasting
```

---

## How the Hybrid Loop Works

```
User message
     │
     ▼
ContextLoader ──── SOUL.md + STYLE.md + MEMORY.md + triggered SKILL.md
     │                         (OpenClaw identity pattern)
     ▼
PersistentMemory ── FTS5 search across past sessions → recall block
     │                         (Hermes cross-session memory)
     ▼
HybridAgent._agent_loop
     │
     ├── LLM call (Claude, prompt-cached system prompt)
     │
     ├── Tool calls → CRM / email / web search / code exec
     │       (executed in parallel via asyncio.gather)
     │
     └── Repeat until end_turn
     │
     ▼
Response → Gateway (CLI / Telegram / Discord)
     │
     ▼
Save to SQLite memory
     │
     ▼
Self-improvement (background task)
     ├── Memory nudge: update MEMORY.md with new user facts
     ├── Skill improvement: improve triggered SKILL.md
     └── Skill creation: save new skill if session was complex
              (Hermes self-improving loop)
```

---

## Configuration

Edit `config.yaml` to change:
- LLM model (primary + fast)
- CRM provider (hubspot / salesforce / mock)
- Enabled tools
- Active gateways
- Self-improvement settings

See `.env.example` for all environment variables.

---

## Adding Skills

Create a new directory under `skills/` with a `SKILL.md`:

```markdown
---
name: my_skill
description: What this skill does
triggers:
  - keyword1
  - keyword2
tools:
  - web_search
  - crm_lookup
version: 1
auto_improve: true
---

# My Skill

Instructions for executing this skill...
```

Skills are loaded automatically on the next session.

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `salespossible` | Start interactive CLI |
| `salespossible setup` | Run setup wizard |
| `salespossible run "<msg>"` | One-shot message |
| `salespossible skills list` | List installed skills |
| `salespossible memory show` | Show MEMORY.md |
| `salespossible memory search "<query>"` | FTS search sessions |

**In-session slash commands:**

| Command | Description |
|---------|-------------|
| `/new` | Fresh conversation |
| `/skills` | List skills |
| `/memory` | Show MEMORY.md |
| `/model <name>` | Switch LLM |
| `/usage` | Token usage |
| `/quit` | Exit |

---

## LLM Providers

| Provider | How to configure |
|----------|-----------------|
| Anthropic Claude (default) | `ANTHROPIC_API_KEY` in .env |
| OpenRouter (200+ models) | `OPENROUTER_API_KEY` + set `llm.provider: openrouter` in config.yaml |

---

## Credits

- [OpenClaw](https://github.com/openclaw/openclaw) — Peter Steinberger — identity, skills, gateway patterns
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) — Nous Research — memory, self-improvement, scheduling
- [Anthropic Claude](https://anthropic.com) — LLM backbone

MIT License
