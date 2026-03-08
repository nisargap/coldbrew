# Telegram Push Notifications

## Overview

When the analysis pipeline detects events, automatically push alerts to all subscribed Telegram users. Workers get notified on their phone without asking.

## Flow

```
Video analyzed
    │
    ▼
Events stored in DB
    │
    ├──▶ SSE push to web dashboard (existing)
    │
    └──▶ Telegram push to all subscribed users (new)
            │
            ▼
        Worker's phone buzzes with alert
```

## Alert Format

```
🔴 CRITICAL — Forklift near-miss in Zone B
Safety · Dock Camera 3 · Confidence: 0.94
```

Severity icons: 🔴 Critical, 🟠 High, 🟡 Medium, 🔵 Low

## How Users Subscribe

1. User opens the bot, sends `/start` or any message
2. Bot saves their `chat_id` to `telegram_chats` table
3. They now receive push alerts automatically
4. `/unsubscribe` to stop

## Changes

### 1. `backend/database.py`

Add to `create_tables()`:

```sql
CREATE TABLE IF NOT EXISTS telegram_chats (
    chat_id       INTEGER PRIMARY KEY,
    subscribed_at TEXT NOT NULL
);
```

### 2. `backend/services/telegram.py`

- **Auto-save chat IDs** — on any incoming message, INSERT OR IGNORE the `chat_id` into `telegram_chats`
- **`/unsubscribe` command** — deletes the chat ID from the table
- **`send_alerts(events: list[dict])`** — new function:
  - Queries all chat IDs from `telegram_chats`
  - Formats each event as a short alert message
  - Calls `bot.send_message(chat_id, text)` for each subscriber
  - Runs async; called from the sync analysis thread via `asyncio.run_coroutine_threadsafe`

### 3. `backend/services/analysis.py`

After events are stored in DB (~line 312, after `conn.commit()`):

```python
from services.telegram import send_alerts
send_alerts(events)
```

## File Summary

| File | Change |
|------|--------|
| `backend/database.py` | Add `telegram_chats` table |
| `backend/services/telegram.py` | Auto-save chat IDs, add `send_alerts()`, add `/unsubscribe` |
| `backend/services/analysis.py` | Call `send_alerts(events)` after storing events |