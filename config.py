from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    # API Keys
    deepgram_api_key: str
    groq_api_key: str
    elevenlabs_api_key: str

    # Audio format
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit = 2 bytes per sample

    # VAD (used only for barge-in / interrupt detection in streaming mode)
    vad_threshold: float = 0.7
    silence_duration_ms: int = 700
    vad_chunk_samples: int = 512  # Silero expects 512 samples at 16 kHz

    # STT (Deepgram live streaming)
    stt_model: str = "nova-3"
    stt_interim_results: bool = True
    stt_endpointing_ms: int = 300  # silence (ms) before speech_final fires
    stt_utterance_end_ms: int = 1500  # gap (ms) after last is_final -> UtteranceEnd
    stt_keepalive_secs: float = 5.0  # send KeepAlive to avoid idle disconnect

    # LLM
    llm_model: str = "llama-3.1-8b-instant"
    system_prompt: str = (
        "You are a helpful voice assistant. Keep your responses concise and natural, "
        "as they will be spoken aloud. Avoid markdown, bullet points, or long lists."
    )

    # TTS
    tts_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs "George" voice
    tts_model_id: str = "eleven_flash_v2_5"
    tts_output_format: str = "pcm_16000"  # raw PCM 16-bit mono 16 kHz

    # Streaming pipeline
    tts_queue_maxsize: int = 3  # backpressure: max sentences awaiting synthesis
    sentence_delimiters: str = ".!?\n"
    min_sentence_chars: int = 2  # avoid synthesizing tiny fragments

    # Interruption / barge-in
    interrupt_enabled: bool = True
    interrupt_vad_chunks: int = 2  # consecutive speech chunks to confirm barge-in

    @classmethod
    def from_env(cls) -> AppConfig:
        """Load API keys from environment variables; all other fields use defaults."""
        load_dotenv()
        return cls(
            deepgram_api_key=os.environ["DEEPGRAM_API_KEY"],
            groq_api_key=os.environ["GROQ_API_KEY"],
            elevenlabs_api_key=os.environ["ELEVENLABS_API_KEY"],
        )
