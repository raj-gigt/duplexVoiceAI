from openai import AsyncOpenAI

from config import OPENAI_API_KEY, LLM_MODEL, SYSTEM_PROMPT


_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def create_history() -> list[dict]:
    """Create a fresh conversation history with the system prompt."""
    return [{"role": "system", "content": SYSTEM_PROMPT}]


async def get_response(transcript: str, history: list[dict]) -> str:
    """Send transcript to OpenAI and return the assistant's reply.

    Mutates `history` in-place to maintain conversation context.
    """
    history.append({"role": "user", "content": transcript})

    # TODO: Switch to streaming (stream=True) and yield partial tokens
    #       so TTS can start synthesizing before the full response is ready.
    response = await _client.chat.completions.create(
        model=LLM_MODEL,
        messages=history,
    )

    reply = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": reply})
    return reply
