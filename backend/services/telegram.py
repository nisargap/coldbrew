"""
Agentic Telegram bot for ColdBrew.

Users chat naturally — Claude interprets intent, calls tools, responds.
"""

import os
import logging
import sqlite3
from datetime import datetime, timezone

import anthropic
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from database import DB_PATH
from services.telegram_tools import TOOLS, execute_tool

logger = logging.getLogger(__name__)

# Per-chat conversation history (in-memory)
_conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20


def _save_chat(chat_id: int, username: str | None, first_name: str | None):
    """Persist a Telegram chat_id so we can send notifications later."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO telegram_chats (chat_id, username, first_name, created_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name",
            (chat_id, username, first_name, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

SYSTEM_PROMPT = (
    "You are ColdBrew, a warehouse intelligence assistant on Telegram. "
    "You help warehouse operators monitor and respond to events detected from CCTV footage.\n\n"
    "Keep responses concise — these are busy warehouse workers on their phones. "
    "Use severity icons: 🔴 Critical, 🟠 High, 🟡 Medium, 🔵 Low.\n\n"
    "FORMATTING: Use Telegram HTML for formatting. "
    "Supported tags: <b>bold</b>, <i>italic</i>, <code>code</code>. "
    "Do NOT use markdown syntax like **bold** or *italic*. "
    "Escape &, <, > as &amp; &lt; &gt; when they appear in plain text (not as tags).\n\n"
    "Always use your tools to get real data. Never make up events or IDs. "
    "When referring to events, include the title so the user can identify them. "
    "Confirm actions taken."
)


def _call_claude(history: list[dict]) -> str:
    client = anthropic.Anthropic()
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    messages = list(history)

    for _ in range(10):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Final text response — done
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if hasattr(b, "text")) or "Done."

        # Tool calls — execute and loop
        assistant_content = []
        tool_results = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                result = execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "assistant", "content": assistant_content})
        messages.append({"role": "user", "content": tool_results})

    return "Hit my processing limit — try a simpler question."


async def _handle_message(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_text = update.message.text

    if chat_id not in _conversations:
        _conversations[chat_id] = []
    history = _conversations[chat_id]
    history.append({"role": "user", "content": user_text})

    if len(history) > MAX_HISTORY:
        _conversations[chat_id] = history[-MAX_HISTORY:]
        history = _conversations[chat_id]

    try:
        reply = _call_claude(history)
        history.append({"role": "assistant", "content": reply})

        for i in range(0, len(reply), 4000):
            chunk = reply[i : i + 4000]
            try:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(chunk)
    except Exception as e:
        logger.error(f"[Telegram] Error: {e}", exc_info=True)
        await update.message.reply_text("Something went wrong — please try again.")


async def _start_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    _save_chat(
        update.message.chat_id,
        user.username if user else None,
        user.first_name if user else None,
    )
    await update.message.reply_text(
        "ColdBrew — Warehouse Intelligence\n\n"
        "Just ask me anything:\n"
        '• "What happened today?"\n'
        '• "Any critical safety events?"\n'
        '• "Acknowledge the forklift incident"\n'
        '• "Give me a summary"\n\n'
        "/clear to reset our conversation"
    )


async def _clear_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    _conversations.pop(update.message.chat_id, None)
    await update.message.reply_text("Conversation cleared.")


# Bot lifecycle

_bot_app: Application | None = None


async def start_bot():
    global _bot_app

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("[Telegram] TELEGRAM_BOT_TOKEN not set — bot disabled")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.warning("[Telegram] ANTHROPIC_API_KEY not set — bot disabled")
        return

    try:
        _bot_app = Application.builder().token(token).build()
        _bot_app.add_handler(CommandHandler("start", _start_command))
        _bot_app.add_handler(CommandHandler("clear", _clear_command))
        _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

        await _bot_app.initialize()
        await _bot_app.start()
        await _bot_app.updater.start_polling(drop_pending_updates=True)

        logger.info("[Telegram] Bot started (polling mode)")
    except Exception as e:
        logger.error(f"[Telegram] Bot startup failed: {e}")
        _bot_app = None


async def send_to_all_chats(message: str):
    """Send a message to all registered Telegram chats."""
    if not _bot_app:
        logger.warning("[Telegram] Bot not running — cannot send notifications")
        return 0

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT chat_id FROM telegram_chats").fetchall()
    finally:
        conn.close()

    sent = 0
    for row in rows:
        try:
            await _bot_app.bot.send_message(
                chat_id=row[0], text=message, parse_mode=ParseMode.HTML
            )
            sent += 1
        except Exception as e:
            logger.error(f"[Telegram] Failed to send to {row[0]}: {e}")
    return sent


async def stop_bot():
    global _bot_app
    if _bot_app:
        await _bot_app.updater.stop()
        await _bot_app.stop()
        await _bot_app.shutdown()
        _bot_app = None
        logger.info("[Telegram] Bot stopped")