# Telegram Bot Integration — Agentic

## Overview

An AI-powered Telegram bot that lets warehouse operators interact with ColdBrew using natural language. Users chat normally — Claude interprets intent, calls the right tools, and responds.

```
User: "any safety issues?"
Bot:  "Found 2 safety events:
       🔴 Forklift near-miss in Zone B
       🟠 PPE violation in Aisle 7"
User: "acknowledge the forklift one"
Bot:  "Done — acknowledged Forklift near-miss in Zone B"
```

---

## Architecture

```
Warehouse worker's phone
  │
  │ "any safety issues?"
  ▼
Telegram cloud servers
  │
  │ polling — our bot pulls new messages
  ▼
Our Python bot (runs inside FastAPI process)
  │
  ├──▶ Claude API: "user said X, here are tools you can call"
  │◀── Claude: "call list_events(category='Safety')"
  │
  ├──▶ coldbrew.db: executes the query
  │◀── returns results
  │
  ├──▶ Claude API: "here are the tool results"
  │◀── Claude: "Found 2 safety events: ..."
  │
  ▼
Bot sends Claude's response back to Telegram → user's phone
```

### The Agentic Loop

The bot doesn't parse commands. For every message:

1. Send user's message + tool definitions to Claude API
2. Claude returns either **text** (done) or **tool_use** (needs data)
3. If tool_use: execute the tool, send result back to Claude, go to step 2
4. Claude may chain multiple tools in one turn before responding

Claude decides what to call. We just execute.

---

## Setup

### 1. Create the Telegram bot

- Open Telegram, message **@BotFather**
- Send `/newbot`, follow prompts
- Copy the token

### 2. Environment variables

```
TELEGRAM_BOT_TOKEN=your_token_from_botfather
ANTHROPIC_API_KEY=your_anthropic_api_key
```

Add to `backend/.env`.

### 3. Install dependencies

```
pip install python-telegram-bot==21.10 anthropic
```

Add to `backend/requirements.txt`:
```
python-telegram-bot==21.10
anthropic>=0.39.0
```

---

## Implementation Plan

### Step 1: Tool functions — `backend/services/telegram_tools.py`

Pure functions that query/modify `coldbrew.db`. No Telegram or Claude logic here.

| Function | Args | What it does |
|----------|------|-------------|
| `list_events` | category?, severity?, status?, limit? | SELECT from events table with optional filters, returns JSON |
| `get_event` | event_id | Get one event by ID (supports prefix match) |
| `acknowledge_event` | event_id | SET status='acknowledged', returns confirmation |
| `dismiss_event` | event_id | SET status='dismissed', returns confirmation |
| `list_feeds` | (none) | SELECT from feeds table |
| `get_summary` | (none) | COUNT events grouped by category, severity, status |

Each function:
- Opens its own sqlite3 connection to `coldbrew.db`
- Returns a JSON string (Claude needs text, not Python dicts)
- Handles errors (event not found, etc.)

Also defines `TOOLS` — the list of tool schemas (name, description, input_schema) that gets sent to the Claude API.

And an `execute_tool(name, args)` dispatcher that routes to the right function.

### Step 2: Agentic message handler — `backend/services/telegram_bot.py`

The Telegram bot + Claude API integration.

**System prompt:**
> "You are ColdBrew, a warehouse intelligence assistant on Telegram. Keep responses concise — these are busy warehouse workers. Use severity icons (🔴🟠🟡🔵). Always use tools to get real data. Never make up events."

**Conversation memory:**
- In-memory dict: `{chat_id: [messages]}`
- Keeps last 20 messages per chat so Claude has context
- `/clear` command resets it

**`_call_claude(history)`** — the agentic loop:
```
messages = history
loop (max 10 rounds):
    response = claude.messages.create(messages, tools)
    if response is text → return text
    if response is tool_use:
        execute each tool
        append assistant message + tool results to messages
        continue loop
```

**Telegram handlers:**
- `_handle_message` — for any text message: append to history, call Claude, send reply
- `_start_command` — `/start`: intro message
- `_clear_command` — `/clear`: reset conversation

**Lifecycle:**
- `start_bot()` — build Application, register handlers, start polling
- `stop_bot()` — graceful shutdown

### Step 3: Wire into FastAPI — `backend/main.py`

```python
from services.telegram_bot import start_bot, stop_bot

@app.on_event("startup")
async def on_startup():
    create_tables()
    await start_bot()  # starts Telegram polling in background

@app.on_event("shutdown")
async def on_shutdown():
    await stop_bot()
```

### Step 4: Update dependencies — `backend/requirements.txt`

Add:
```
python-telegram-bot==21.10
anthropic>=0.39.0
```

---

## File Summary

| File | Action | Purpose |
|------|--------|---------|
| `backend/services/telegram_tools.py` | Create | Tool functions + schemas (DB queries) |
| `backend/services/telegram_bot.py` | Create | Telegram handlers + Claude agentic loop |
| `backend/main.py` | Modify | Add start_bot/stop_bot to lifecycle |
| `backend/requirements.txt` | Modify | Add python-telegram-bot, anthropic |

---

## Example Interactions

**Querying events:**
```
User: what happened today?
Bot:  4 events detected across 2 feeds:
      🔴 Forklift near-miss in Zone B (Safety)
      🟠 PPE violation in Aisle 7 (Safety)
      🟡 Conveyor belt jam on Line 3 (Equipment)
      🔵 Idle zone in Staging Area C (Operational)
```

**Filtering:**
```
User: just the critical stuff
Bot:  1 critical event:
      🔴 Forklift near-miss in Zone B
      Confidence: 0.94 · Status: new · Camera: Dock 3
```

**Taking action:**
```
User: acknowledge that one
Bot:  Acknowledged: Forklift near-miss in Zone B
```

**Multi-step:**
```
User: acknowledge the forklift event and give me a summary
Bot:  Done — acknowledged Forklift near-miss in Zone B.

      Summary: 4 total events
      By severity: 1 Critical, 1 High, 1 Medium, 1 Low
      By status: 3 new, 1 acknowledged
```

**Conversation context:**
```
User: show safety events
Bot:  2 safety events: ...
User: acknowledge both
Bot:  Acknowledged both: Forklift near-miss, PPE violation
```