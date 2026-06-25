from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class TranscriptEvent:
    """Normalized transcript event emitted by a streaming STT provider."""

    text: str
    is_final: bool
    speech_final: bool
    is_utterance_end: bool


class STTProvider(Protocol):
    async def start(self) -> None: ...
    async def send_audio(self, chunk: bytes) -> None: ...
    def events(self) -> AsyncIterator[TranscriptEvent]: ...
    async def stop(self) -> None: ...


class LLMProvider(Protocol):
    def create_history(self) -> list[dict]: ...
    def stream_response(
        self, transcript: str, history: list[dict]
    ) -> AsyncIterator[str]: ...


class TTSProvider(Protocol):
    def synthesize_stream(self, text: str) -> AsyncIterator[bytes]: ...
