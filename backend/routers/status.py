"""
Dependency status checks — NomadicML, Claude (Anthropic), Telegram.
"""

import os
import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/status", tags=["status"])


def _check_nomadicml() -> dict:
    """Ping the NomadicML SDK by attempting a lightweight operation."""
    api_key = os.environ.get("NOMADIC_SDK_API_KEY", "")
    if not api_key:
        return {
            "name": "NomadicML",
            "status": "misconfigured",
            "message": "NOMADIC_SDK_API_KEY environment variable is not set.",
            "latency_ms": None,
        }
    try:
        start = time.time()
        from nomadicml import NomadicML
        client = NomadicML(api_key=api_key)
        # Use the SDK's auth verification endpoint
        client.verify_auth()
        latency = round((time.time() - start) * 1000)
        return {
            "name": "NomadicML",
            "status": "connected",
            "message": "SDK authenticated and reachable.",
            "latency_ms": latency,
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        err_str = str(e)[:200]
        # Distinguish auth errors from network errors
        if "401" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower():
            status = "auth_error"
            message = f"Authentication failed: {err_str}"
        elif "timeout" in err_str.lower() or "connect" in err_str.lower():
            status = "unreachable"
            message = f"Network error: {err_str}"
        else:
            status = "error"
            message = err_str
        return {
            "name": "NomadicML",
            "status": status,
            "message": message,
            "latency_ms": latency,
        }


def _check_anthropic() -> dict:
    """Check if the Anthropic (Claude) API key is set and reachable."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "name": "Claude (Anthropic)",
            "status": "misconfigured",
            "message": "ANTHROPIC_API_KEY environment variable is not set.",
            "latency_ms": None,
        }
    try:
        start = time.time()
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        # Lightweight call — count tokens for a tiny message to verify auth
        resp = client.messages.count_tokens(
            model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            messages=[{"role": "user", "content": "ping"}],
        )
        latency = round((time.time() - start) * 1000)
        return {
            "name": "Claude (Anthropic)",
            "status": "connected",
            "message": f"Authenticated. Model: {os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-20250514')}",
            "latency_ms": latency,
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        err_str = str(e)[:200]
        if "401" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower():
            status = "auth_error"
            message = f"Authentication failed: {err_str}"
        elif "timeout" in err_str.lower() or "connect" in err_str.lower():
            status = "unreachable"
            message = f"Network error: {err_str}"
        else:
            status = "error"
            message = err_str
        return {
            "name": "Claude (Anthropic)",
            "status": status,
            "message": message,
            "latency_ms": latency,
        }


def _check_telegram() -> dict:
    """Check Telegram bot token and connectivity."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return {
            "name": "Telegram Bot",
            "status": "disabled",
            "message": "TELEGRAM_BOT_TOKEN not set. Bot is disabled.",
            "latency_ms": None,
        }
    try:
        start = time.time()
        import httpx
        resp = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
        latency = round((time.time() - start) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            bot_name = data.get("result", {}).get("username", "unknown")
            return {
                "name": "Telegram Bot",
                "status": "connected",
                "message": f"Bot @{bot_name} is online.",
                "latency_ms": latency,
            }
        elif resp.status_code == 401:
            return {
                "name": "Telegram Bot",
                "status": "auth_error",
                "message": "Invalid bot token.",
                "latency_ms": latency,
            }
        else:
            return {
                "name": "Telegram Bot",
                "status": "error",
                "message": f"Telegram API returned HTTP {resp.status_code}.",
                "latency_ms": latency,
            }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        return {
            "name": "Telegram Bot",
            "status": "unreachable",
            "message": f"Network error: {str(e)[:200]}",
            "latency_ms": latency,
        }


def _check_elevenlabs() -> dict:
    """Check ElevenLabs API key and TTS connectivity.

    Uses a minimal TTS call to verify the key works for speech synthesis,
    since scoped API keys may not have user_read or voices_read permissions
    but can still generate audio.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return {
            "name": "ElevenLabs",
            "status": "disabled",
            "message": "ELEVENLABS_API_KEY not set. Voice alerts disabled.",
            "latency_ms": None,
            "hint": "Set ELEVENLABS_API_KEY in backend/.env to enable voice alerts.",
        }
    start = time.time()
    try:
        from elevenlabs import ElevenLabs as ElevenLabsClient
        client = ElevenLabsClient(api_key=api_key)
        # Use TTS endpoint with minimal text — this is the actual capability we need.
        # Default voice "Rachel" (21m00Tcm4TlvDq8ikWAM) is always available.
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            text="ok",
            model_id="eleven_monolingual_v1",
        )
        # Consume generator to confirm we got bytes
        audio_bytes = b"".join(audio) if hasattr(audio, "__iter__") else audio
        latency = round((time.time() - start) * 1000)
        return {
            "name": "ElevenLabs",
            "status": "connected",
            "message": f"TTS verified. Voice: {voice_id[:8]}…",
            "latency_ms": latency,
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000)
        err_str = str(e)[:300]
        logger.warning(f"ElevenLabs check failed: {err_str}")
        if "missing_permissions" in err_str:
            return {
                "name": "ElevenLabs",
                "status": "auth_error",
                "message": "API key lacks TTS permissions.",
                "latency_ms": latency,
                "hint": "Regenerate your API key at https://elevenlabs.io/app/settings/api-keys with Text-to-Speech permission enabled.",
            }
        if "401" in err_str or "auth" in err_str.lower() or "invalid" in err_str.lower() or "Unauthorized" in err_str:
            return {
                "name": "ElevenLabs",
                "status": "auth_error",
                "message": "Authentication failed. Check your ELEVENLABS_API_KEY.",
                "latency_ms": latency,
                "hint": "Get a valid API key from https://elevenlabs.io/app/settings/api-keys",
            }
        return {
            "name": "ElevenLabs",
            "status": "error",
            "message": err_str[:200],
            "latency_ms": latency,
        }


@router.get("")
def get_dependency_status():
    """Check connectivity to all external dependencies."""
    checks = [
        _check_nomadicml(),
        _check_anthropic(),
        _check_elevenlabs(),
        _check_telegram(),
    ]

    # Overall status: healthy if all connected/disabled, degraded if some fail
    active = [c for c in checks if c["status"] not in ("disabled",)]
    all_ok = all(c["status"] == "connected" for c in active)
    any_ok = any(c["status"] == "connected" for c in active)

    if all_ok:
        overall = "healthy"
    elif any_ok:
        overall = "degraded"
    else:
        overall = "unhealthy"

    return {
        "overall": overall,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "dependencies": checks,
    }
