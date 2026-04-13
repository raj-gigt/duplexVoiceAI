import asyncio

from elevenlabs.client import ElevenLabs

from config import ELEVENLABS_API_KEY, TTS_VOICE_ID, TTS_MODEL_ID, TTS_OUTPUT_FORMAT


_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


def _synthesize_sync(text: str) -> bytes:
    """Convert text to raw PCM audio using ElevenLabs."""
    audio_iter = _client.text_to_speech.convert(
        text=text,
        voice_id=TTS_VOICE_ID,
        model_id=TTS_MODEL_ID,
        output_format=TTS_OUTPUT_FORMAT,
    )
    # Collect all chunks into a single bytes object
    chunks = []
    for chunk in audio_iter:
        if isinstance(chunk, bytes):
            chunks.append(chunk)
    return b"".join(chunks)


async def synthesize(text: str) -> bytes:
    """Async wrapper -- runs ElevenLabs call in a thread."""
    # TODO: Use streaming TTS to send audio chunks as they arrive,
    #       reducing time-to-first-byte for the user.
    return await asyncio.to_thread(_synthesize_sync, text)
