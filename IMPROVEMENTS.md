# MARK XL — Improved Edition
## What Was Added (from JARVIS v4.2)

This document describes every module integrated from `certifiedclaw/jarvis-v4.2`
and exactly where each file lives in the new project structure.

---

## New Files Added

| File | Source | What It Does |
|------|--------|--------------|
| `memory/semantic_memory.py` | `memory_engine.py` | SQLite-backed episodic memory with sentence-transformer embeddings. Stores every exchange and retrieves relevant past context for each new message. |
| `memory/rag.py` | `rag.py` | Local RAG engine — index your Obsidian vault, PDF folders, or any `.md/.txt/.csv` files. Query them by asking JARVIS. |
| `core/smart_context.py` | `smart_context.py` | Auto-compresses conversation history when it approaches the LLM token limit. Keeps system messages, drops oldest turns first. |
| `core/plugins.py` | `plugins.py` | Drop-in plugin system. Place any `.py` file in `plugins/` with `PLUGIN_NAME` and `PLUGIN_TOOLS` defined — JARVIS auto-loads it at startup. |
| `core/plugin_watcher.py` | `plugin_watcher.py` | Watches `plugins/` with `watchdog`. Reloads plugins automatically when you add/edit/delete a file — no restart needed. |
| `core/task_scheduler.py` | `task_scheduler.py` | Background task scheduler. Register recurring tasks (e.g. "summarise news every hour"). Also exposed as an LLM tool. |
| `core/hotkey_manager.py` | `hotkey_commands.py` | Global hotkey (`Ctrl+Alt+J`) to show/hide the window from anywhere. Requires `keyboard` package. |
| `core/safety.py` | `safety.py` | Path ACL + high-risk tool confirmation layer. `run_shell` / `shell` are always blocked. Destructive tools (`delete`, `write_file`) require confirmation. |
| `core/mcp_bridge.py` | `mcp_bridge.py` | MCP (Model Context Protocol) bridge. Connect external MCP servers (Obsidian, GitHub, Postgres, etc.) via config. No restart needed. |
| `core/diagnostics.py` | `diagnostics.py` | Full system health check: Python version, Ollama status, GPU, all packages, browser CDP. Type `status` in chat to run. |
| `actions/osint_tools.py` | `osint_tools.py` | OSINT toolkit: WHOIS, DNS, subdomain enum, email breach check, port scan, Google dorks, IP geolocation, username search, SSL cert info, tech stack detection. |
| `actions/pdf_tools.py` | `pdf_tools.py` | PDF utilities: extract text, summarise, extract tables, search within document. Requires `pip install pymupdf`. |
| `actions/extra_tools.py` | `extra_tools.py` | Expanded utility tools from JARVIS (clipboard manager, process list, network info, etc.) |

---

## Changes to Existing Files

### `main.py` — Fully Rewritten
- All original tool dispatching preserved exactly
- Added imports for all new modules
- `_build_system_prompt()` now injects semantic memory context + MCP/plugin tool lists
- `_process_message()` now:
  - Handles `/clear` and `status` commands
  - Stores exchanges to semantic memory
  - Runs `compress_if_needed()` on history before each LLM call
  - Appends new tools: `osint_lookup`, `pdf_tool`, `rag_query`, `diagnostics`
  - Falls through to plugin tools if tool name not found in built-ins
  - Falls through to MCP bridge for `mcp.call`
- `_execute_tool()` extended with 5 new tool handlers
- New `_init_new_subsystems()` method — runs in background thread at startup
- All new subsystems start in parallel, non-blocking

### `memory/config_manager.py` — Extended
- Added `_MarkConfigAdapter` class with `.get("dotted.key")` interface
- Added `get_mark_config()` singleton — bridges Mark-XL's JSON config to the
  dict-style API that all JARVIS-borrowed modules expect

---

## New Tool Declarations (callable by the LLM)

| Tool | Trigger phrases |
|------|----------------|
| `osint_lookup` | "who owns domain X", "check if email was breached", "open ports on Y", "DNS records for Z" |
| `pdf_tool` | "summarize this PDF", "extract text from file.pdf", "search my PDF for X" |
| `rag_query` | "search my notes about X", "index this folder", "what does my Obsidian say about Y" |
| `diagnostics` | "status", "system check", "health check", "jarvis status" |

---

## New Chat Commands

| Command | Action |
|---------|--------|
| `status` | Run full system diagnostics |
| `/clear` | Clear chat history and semantic memory session |

---

## New Runtime Directories

```
Mark-XL/
├── plugins/          ← drop .py plugin files here (hot-reloaded)
├── data/
│   ├── memory.db     ← semantic memory (auto-created)
│   └── rag_index/    ← RAG document index (auto-created)
└── logs/
    └── markxl.log    ← rotating log, 5 MB cap
```

---

## Quick Setup

```bash
# Install new dependencies
pip install sentence-transformers watchdog keyboard PyMuPDF python-whois dnspython

# Run as normal — all new systems initialise in the background
python main.py
```

---

## Writing a Plugin

Drop a `.py` file in `plugins/`:

```python
PLUGIN_NAME = "my_tool"

def greet(name: str = "world") -> str:
    return f"Hello, {name}!"

PLUGIN_TOOLS = {
    "greet": greet,
}
```

JARVIS will pick it up instantly (no restart). Ask it: *"use my_tool to greet Alice"*.

---

## Configuring MCP Servers

Add to `config/api_keys.json`:

```json
{
  "mcp_enabled": true,
  "mcp_servers": [
    {
      "name": "obsidian",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-obsidian", "/path/to/vault"]
    }
  ]
}
```

Then ask: *"search my Obsidian notes about project X"*.
