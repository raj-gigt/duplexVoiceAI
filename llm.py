from __future__ import annotations

from typing import AsyncIterator

from groq import AsyncGroq

from config import AppConfig


class GroqLLM:
    """Streaming LLM completions via Groq."""

    def __init__(self, config: AppConfig) -> None:
        self._client = AsyncGroq(api_key=config.groq_api_key)
        self._model = config.llm_model
        self._system_prompt = config.system_prompt

    def create_history(self) -> list[dict]:
        """Create a fresh conversation history with the system prompt."""
        return [{"role": "system", "content": self._system_prompt}]

    async def stream_response(
        self, transcript: str, history: list[dict]
    ) -> AsyncIterator[str]:
        """Stream the assistant reply token-by-token.

        Does NOT mutate *history* -- the caller commits the turn once it knows
        whether the response completed or was interrupted.
        """
        messages = history + [{"role": "user", "content": transcript}]
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
