"""
Agentic Telegram bot for ColdBrew.

Users chat naturally — Claude interprets intent, calls tools, responds.
"""

import os
import logging
import asyncio
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

from services.telegram_tools import TOOLS, execute_tool

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldbrew.db")

logger = logging.getLogger(__name__)

# Per-chat conversation history (in-memory)
_conversations: dict[int, list[dict]] = {}
MAX_HISTORY = 20

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


def _save_chat_id(chat_id: int) -> None:
    """Auto-save a chat ID so the user receives push alerts."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO telegram_chats (chat_id, subscribed_at) VALUES (?, ?)",
            (chat_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _remove_chat_id(chat_id: int) -> None:
    """Remove a chat ID so the user stops receiving push alerts."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()


async def _unsubscribe_command(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    _remove_chat_id(update.message.chat_id)
    await update.message.reply_text("Unsubscribed — you won't receive push alerts anymore. Send any message to re-subscribe.")


async def _handle_message(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user_text = update.message.text

    _save_chat_id(chat_id)

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
    _save_chat_id(update.message.chat_id)
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
        _bot_app.add_handler(CommandHandler("unsubscribe", _unsubscribe_command))
        _bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))

        await _bot_app.initialize()
        await _bot_app.start()
        await _bot_app.updater.start_polling(drop_pending_updates=True)

        logger.info("[Telegram] Bot started (polling mode)")
    except Exception as e:
        logger.error(f"[Telegram] Bot startup failed: {e}")
        _bot_app = None


async def stop_bot():
    global _bot_app
    if _bot_app:
        await _bot_app.updater.stop()
        await _bot_app.stop()
        await _bot_app.shutdown()
        _bot_app = None
        logger.info("[Telegram] Bot stopped")


# --- Push alerts ---

_SEVERITY_ICONS = {
    "Critical": "\U0001f534",
    "High": "\U0001f7e0",
    "Medium": "\U0001f7e1",
    "Low": "\U0001f535",
}


def _format_alert(event: dict) -> str:
    icon = _SEVERITY_ICONS.get(event.get("severity", ""), "\U0001f535")
    severity = event.get("severity", "Unknown")
    title = event.get("title", "Unnamed Event")
    category = event.get("category", "")
    source = event.get("source_feed", "")
    confidence = event.get("confidence", 0)
    return f"{icon} {severity.upper()} — {title}\n{category} · {source} · Confidence: {confidence:.2f}"


async def _push_alerts(events: list[dict]) -> None:
    """Send alert messages to all subscribed Telegram chats."""
    if not _bot_app or not events:
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT chat_id FROM telegram_chats").fetchall()
    finally:
        conn.close()

    if not rows:
        return

    bot = _bot_app.bot
    for event in events:
        text = _format_alert(event)
        for (chat_id,) in rows:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logger.warning(f"[Telegram] Failed to send alert to {chat_id}: {e}")


def send_alerts(events: list[dict]) -> None:
    """
    Send push alerts to all subscribed Telegram chats.
    Safe to call from sync background threads.
    """
    if not _bot_app or not events:
        return
    asyncio.run(_push_alerts(events))


async def _push_analysis_complete(feed_name: str, feed_id: str, event_count: int, events: list[dict], analysis_mode: str) -> None:
    """Send a summary message to all subscribed chats when analysis finishes."""
    if not _bot_app:
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT chat_id FROM telegram_chats").fetchall()
    finally:
        conn.close()

    if not rows:
        return

    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for ev in events:
        sev = ev.get("severity", "Unknown")
        cat = ev.get("category", "Unknown")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1

    severity_line = ", ".join(
        f"{_SEVERITY_ICONS.get(s, '')} {s}: {c}" for s, c in sorted(severity_counts.items(), key=lambda x: ["Critical", "High", "Medium", "Low"].index(x[0]) if x[0] in ["Critical", "High", "Medium", "Low"] else 99)
    )
    category_line = ", ".join(f"{cat}: {c}" for cat, c in sorted(category_counts.items()))

    text = (
        f"\u2705 <b>Analysis Complete</b>\n\n"
        f"<b>Feed:</b> {feed_name}\n"
        f"<b>Mode:</b> {analysis_mode}\n"
        f"<b>Events detected:</b> {event_count}\n"
    )
    if severity_line:
        text += f"<b>Severity:</b> {severity_line}\n"
    if category_line:
        text += f"<b>Categories:</b> {category_line}\n"

    bot = _bot_app.bot
    for (chat_id,) in rows:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"[Telegram] Failed to send analysis-complete to {chat_id}: {e}")


def send_analysis_complete(feed_name: str, feed_id: str, event_count: int, events: list[dict], analysis_mode: str) -> None:
    """
    Notify all subscribed Telegram chats that analysis has finished.
    Safe to call from sync background threads.
    """
    if not _bot_app:
        return
    asyncio.run(_push_analysis_complete(feed_name, feed_id, event_count, events, analysis_mode))