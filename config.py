import os

# --- API Keys (loaded from environment) ---
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# --- Audio Format ---
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes per sample

# --- VAD ---
VAD_THRESHOLD = 0.5
SILENCE_DURATION_MS = 700  # ms of silence after speech to trigger pipeline
VAD_CHUNK_SAMPLES = 512  # Silero expects 512 samples at 16kHz

# --- LLM ---
LLM_MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = (
    "You are a helpful voice assistant. Keep your responses concise and natural, "
    "as they will be spoken aloud. Avoid markdown, bullet points, or long lists."
)

# --- TTS ---
TTS_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # ElevenLabs "George" voice
TTS_MODEL_ID = "eleven_flash_v2_5"
TTS_OUTPUT_FORMAT = "pcm_16000"  # raw PCM 16-bit mono 16kHz
