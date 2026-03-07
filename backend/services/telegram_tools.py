"""
Tool functions + schemas for the ColdBrew Telegram agent.

Each tool queries/modifies coldbrew.db and returns a JSON string.
These are called by Claude via the agentic loop in telegram_bot.py.
"""

import os
import json
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldbrew.db")

TOOLS = [
    {
        "name": "list_events",
        "description": "List detected warehouse events. Can filter by category, severity, or status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["Safety", "Equipment", "Shipment", "Operational", "Environmental"],
                    "description": "Filter by event category",
                },
                "severity": {
                    "type": "string",
                    "enum": ["Critical", "High", "Medium", "Low"],
                    "description": "Filter by severity level",
                },
                "status": {
                    "type": "string",
                    "enum": ["new", "acknowledged", "dismissed"],
                    "description": "Filter by event status",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max events to return (default 10)",
                },
            },
        },
    },
    {
        "name": "get_event",
        "description": "Get full details of a specific event by ID (supports prefix match).",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event UUID or prefix"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "acknowledge_event",
        "description": "Acknowledge an event — marks it as seen and being handled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event UUID to acknowledge"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "dismiss_event",
        "description": "Dismiss an event as false positive or not relevant.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event UUID to dismiss"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "list_feeds",
        "description": "List all video feeds and their processing status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_summary",
        "description": "Get a summary of current warehouse activity — total events, breakdowns by category, severity, and status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def execute_tool(name: str, args: dict) -> str:
    handler = _HANDLERS.get(name)
    if not handler:
        return json.dumps({"error": f"Unknown tool: {name}"})
    conn = _get_db()
    try:
        return handler(conn, args)
    finally:
        conn.close()


def _list_events(conn: sqlite3.Connection, args: dict) -> str:
    query = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if args.get("category"):
        query += " AND category = ?"
        params.append(args["category"])
    if args.get("severity"):
        query += " AND severity = ?"
        params.append(args["severity"])
    if args.get("status"):
        query += " AND status = ?"
        params.append(args["status"])
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(args.get("limit", 10)))
    rows = conn.execute(query, params).fetchall()
    return json.dumps({"events": [dict(r) for r in rows], "count": len(rows)})


def _get_event(conn: sqlite3.Connection, args: dict) -> str:
    eid = args["event_id"]
    row = conn.execute("SELECT * FROM events WHERE id = ?", (eid,)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM events WHERE id LIKE ?", (eid + "%",)).fetchone()
    if not row:
        return json.dumps({"error": f"No event found matching '{eid}'"})
    return json.dumps(dict(row))


def _acknowledge_event(conn: sqlite3.Connection, args: dict) -> str:
    eid = args["event_id"]
    row = conn.execute("SELECT id, title FROM events WHERE id = ? OR id LIKE ?", (eid, eid + "%")).fetchone()
    if not row:
        return json.dumps({"error": f"No event found matching '{eid}'"})
    conn.execute("UPDATE events SET status = 'acknowledged' WHERE id = ?", (row["id"],))
    conn.commit()
    return json.dumps({"success": True, "event_id": row["id"], "title": row["title"], "new_status": "acknowledged"})


def _dismiss_event(conn: sqlite3.Connection, args: dict) -> str:
    eid = args["event_id"]
    row = conn.execute("SELECT id, title FROM events WHERE id = ? OR id LIKE ?", (eid, eid + "%")).fetchone()
    if not row:
        return json.dumps({"error": f"No event found matching '{eid}'"})
    conn.execute("UPDATE events SET status = 'dismissed' WHERE id = ?", (row["id"],))
    conn.commit()
    return json.dumps({"success": True, "event_id": row["id"], "title": row["title"], "new_status": "dismissed"})


def _list_feeds(conn: sqlite3.Connection, _args: dict) -> str:
    rows = conn.execute("SELECT * FROM feeds ORDER BY created_at DESC").fetchall()
    return json.dumps({"feeds": [dict(r) for r in rows], "count": len(rows)})


def _get_summary(conn: sqlite3.Connection, _args: dict) -> str:
    total = conn.execute("SELECT COUNT(*) as c FROM events").fetchone()["c"]
    by_cat = conn.execute("SELECT category, COUNT(*) as c FROM events GROUP BY category").fetchall()
    by_sev = conn.execute("SELECT severity, COUNT(*) as c FROM events GROUP BY severity").fetchall()
    by_status = conn.execute("SELECT status, COUNT(*) as c FROM events GROUP BY status").fetchall()
    return json.dumps({
        "total_events": total,
        "by_category": {r["category"]: r["c"] for r in by_cat},
        "by_severity": {r["severity"]: r["c"] for r in by_sev},
        "by_status": {r["status"]: r["c"] for r in by_status},
    })


_HANDLERS = {
    "list_events": _list_events,
    "get_event": _get_event,
    "acknowledge_event": _acknowledge_event,
    "dismiss_event": _dismiss_event,
    "list_feeds": _list_feeds,
    "get_summary": _get_summary,
}