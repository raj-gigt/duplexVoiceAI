from __future__ import annotations

import asyncio

from deepgram import AsyncDeepgramClient

from config import AppConfig
from protocols import TranscriptEvent

_SENTINEL = object()


class DeepgramStreamingSTT:
    """Per-session live speech-to-text using the Deepgram v7 async WebSocket API.

    Audio is pushed in via send_audio(); transcript events are consumed via the
    async generator events(). The connection is held open by an internal task
    running the async context manager, so there is no separate thread to bridge.
    """

    def __init__(self, config: AppConfig) -> None:
        self._cfg = config
        self._client = AsyncDeepgramClient(api_key=config.deepgram_api_key)
        self._socket = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._ready = asyncio.Event()
        self._error: BaseException | None = None
        self._listen_task: asyncio.Task | None = None
        self._keepalive_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._listen_task = asyncio.create_task(self._run())
        await self._ready.wait()
        if self._error is not None:
            raise self._error
        self._keepalive_task = asyncio.create_task(self._keepalive())

    async def _run(self) -> None:
        try:
            async with self._client.listen.v1.connect(
                model=self._cfg.stt_model,
                encoding="linear16",
                sample_rate=self._cfg.sample_rate,
                channels=self._cfg.channels,
                interim_results="true" if self._cfg.stt_interim_results else "false",
                endpointing=self._cfg.stt_endpointing_ms,
                utterance_end_ms=self._cfg.stt_utterance_end_ms,
                punctuate="true",
                smart_format="true",
            ) as socket:
                self._socket = socket
                self._ready.set()
                async for message in socket:
                    if isinstance(message, bytes):
                        continue
                    event = self._to_event(message)
                    if event is not None:
                        await self._queue.put(event)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            self._error = e
        finally:
            self._ready.set()
            await self._queue.put(_SENTINEL)

    def _to_event(self, message) -> TranscriptEvent | None:
        mtype = getattr(message, "type", None)
        if mtype == "Results":
            text = ""
            try:
                alts = message.channel.alternatives
                if alts:
                    text = (alts[0].transcript or "").strip()
            except (AttributeError, IndexError):
                text = ""
            return TranscriptEvent(
                text=text,
                is_final=bool(getattr(message, "is_final", False)),
                speech_final=bool(getattr(message, "speech_final", False)),
                is_utterance_end=False,
            )
        if mtype == "UtteranceEnd":
            return TranscriptEvent(
                text="",
                is_final=False,
                speech_final=False,
                is_utterance_end=True,
            )
        # SpeechStarted / Metadata are ignored; barge-in uses local VAD.
        return None

    async def _keepalive(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._cfg.stt_keepalive_secs)
                if self._socket is not None:
                    await self._socket.send_keep_alive()
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            return

    async def send_audio(self, chunk: bytes) -> None:
        if self._socket is not None:
            await self._socket.send_media(chunk)

    async def events(self):
        while True:
            item = await self._queue.get()
            if item is _SENTINEL:
                return
            yield item

    async def stop(self) -> None:
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
        try:
            if self._socket is not None:
                await self._socket.send_close_stream()
        except Exception:  # noqa: BLE001
            pass
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except BaseException:  # noqa: BLE001
                pass
