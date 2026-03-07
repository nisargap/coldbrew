"""
Simple in-process pub/sub for SSE (Server-Sent Events).

Background tasks (sync threads) call publish() to push feed status updates.
SSE endpoint clients call subscribe()/unsubscribe() to receive them.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_subscribers: list[asyncio.Queue] = []


async def subscribe() -> asyncio.Queue:
    """Create a new subscriber queue and register it."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(q)
    logger.info(f"[SSE] New subscriber. Total: {len(_subscribers)}")
    return q


async def unsubscribe(q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    try:
        _subscribers.remove(q)
    except ValueError:
        pass
    logger.info(f"[SSE] Subscriber removed. Total: {len(_subscribers)}")


def publish(data: dict[str, Any]) -> None:
    """
    Publish an event to all subscribers.
    Safe to call from sync background threads (CPython GIL protects deque ops).
    """
    for q in list(_subscribers):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("[SSE] Subscriber queue full, dropping message")
        except Exception:
            pass
