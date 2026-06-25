from __future__ import annotations

import asyncio
import threading
from typing import AsyncIterator

from elevenlabs.client import ElevenLabs

from config import AppConfig

_DONE = object()


class ElevenLabsTTS:
    """Text-to-speech using ElevenLabs.

    synthesize_stream() sends the full sentence to ElevenLabs but relays each
    audio chunk to the caller as soon as it arrives, instead of buffering the
    whole sentence -- this minimizes time-to-first-audio. The ElevenLabs SDK
    call is synchronous and streams via a generator, so we run it in a worker
    thread and bridge chunks onto the event loop through an asyncio.Queue.
    """

    def __init__(self, config: AppConfig) -> None:
        self._client = ElevenLabs(api_key=config.elevenlabs_api_key)
        self._voice_id = config.tts_voice_id
        self._model_id = config.tts_model_id
        self._output_format = config.tts_output_format

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()

        def worker() -> None:
            try:
                audio_iter = self._client.text_to_speech.convert(
                    text=text,
                    voice_id=self._voice_id,
                    model_id=self._model_id,
                    output_format=self._output_format,
                )
                for chunk in audio_iter:
                    if stop.is_set():
                        break
                    if isinstance(chunk, bytes) and chunk:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:  # noqa: BLE001
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

        fut = loop.run_in_executor(None, worker)
        try:
            while True:
                item = await queue.get()
                if item is _DONE:
                    break
                if isinstance(item, Exception):
                    raise item
                yield item
        finally:
            # Signal the worker to stop (e.g. on interruption) and let it finish.
            stop.set()
            await fut
