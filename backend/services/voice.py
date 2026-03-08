"""
ElevenLabs TTS — Voice alert generation for high-risk warehouse events.

Generates MP3 audio files from Claude-written voice alert scripts.
Audio is stored locally and served via FastAPI's static file mount.
"""

import os
import logging

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
VOICE_DIR = os.path.join(UPLOAD_DIR, "voice")


def generate_voice_alert(enrichment_id: str, event_id: str, script: str) -> str:
    """
    Generate an MP3 voice alert from a text script using ElevenLabs TTS.

    Returns the URL path to the generated audio file (e.g. /uploads/voice/{event_id}.mp3).
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set")

    from elevenlabs import ElevenLabs

    client = ElevenLabs(api_key=api_key)

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "Rachel")

    logger.info(f"[Voice] Generating TTS for event {event_id} (voice={voice_id}, {len(script)} chars)")

    # Generate speech
    audio_generator = client.text_to_speech.convert(
        text=script,
        voice_id=voice_id,
        model_id="eleven_turbo_v2_5",
        output_format="mp3_44100_128",
    )

    # Save to disk
    os.makedirs(VOICE_DIR, exist_ok=True)
    file_path = os.path.join(VOICE_DIR, f"{event_id}.mp3")

    with open(file_path, "wb") as f:
        for chunk in audio_generator:
            f.write(chunk)

    file_size = os.path.getsize(file_path)
    logger.info(f"[Voice] Saved {file_size} bytes to {file_path}")

    return f"/uploads/voice/{event_id}.mp3"
