import asyncio

from deepgram import DeepgramClient

from config import DEEPGRAM_API_KEY, SAMPLE_RATE


_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)


def _transcribe_sync(audio_bytes: bytes) -> str:
    """Send raw PCM audio to Deepgram prerecorded API and return transcript."""
    response = _client.listen.rest.v("1").transcribe_file(
        {"buffer": audio_bytes, "mimetype": "audio/l16"},
        {"model": "nova-3", "encoding": "linear16", "sample_rate": SAMPLE_RATE},
    )
    transcript = (
        response.results.channels[0].alternatives[0].transcript
    )
    return transcript.strip()


async def transcribe(audio_bytes: bytes) -> str:
    """Async wrapper -- runs Deepgram SDK call in a thread."""
    # TODO: Switch to Deepgram streaming API for real-time partial transcripts
    return await asyncio.to_thread(_transcribe_sync, audio_bytes)
