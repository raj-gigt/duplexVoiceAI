# Setup & Local Development

A real-time, full-duplex voice AI assistant. Speak into the browser, get a spoken
AI response, and interrupt it mid-sentence (barge-in).

- **Backend**: Python + FastAPI + WebSockets (STT → LLM → TTS streaming pipeline)
- **Frontend**: React + TypeScript + Vite (Web Audio API)

## Prerequisites

- **Python** 3.10+
- **Node.js** 18+ and **npm**
- API keys for:
  - [Deepgram](https://console.deepgram.com/) (speech-to-text)
  - [Groq](https://console.groq.com/) (LLM)
  - [ElevenLabs](https://elevenlabs.io/) (text-to-speech)

## 1. Backend

From the project root (`duplexVoiceAI/`):

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows (PowerShell)

# Install dependencies
pip install -r requirements.txt
```

> Note: the app loads API keys via `python-dotenv`. If it is not already
> pulled in as a dependency, install it with `pip install python-dotenv`.

### Environment variables

Create a `.env` file in the project root with your API keys:

```bash
DEEPGRAM_API_KEY=your_deepgram_key
GROQ_API_KEY=your_groq_key
ELEVENLABS_API_KEY=your_elevenlabs_key
```

### Run the backend

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

The WebSocket endpoint will be available at `ws://localhost:8000/voice`.

## 2. Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite serves the app (default `http://localhost:5173`). Open it in your browser.

> The frontend connects to `ws://localhost:8000/voice` (hardcoded in
> `src/hooks/useVoiceAgent.ts`). If you change the backend host/port, update
> `WS_URL` there.

## 3. Using the app

1. Click **Connect** to open the WebSocket and grant microphone access.
2. Click the **microphone** button to start speaking.
3. Speak — the assistant transcribes, thinks, and responds with voice.
4. Talk over the assistant to **interrupt** it (barge-in).
5. Click **Disconnect** to end the session.

## Troubleshooting

- **Mic not working**: browsers require a secure context. `localhost` is treated
  as secure, so `http://localhost:5173` works; a raw LAN IP may not.
- **No audio / assistant silent**: browsers auto-suspend the `AudioContext`.
  Interacting with the page (the Connect click) resumes it.
- **Backend fails on startup with a KeyError**: a required API key is missing
  from your `.env` file.
- **Deepgram connection issues**: confirm your key is valid and the
  `deepgram-sdk==7.0.0` version from `requirements.txt` is installed.

## Production build (frontend)

```bash
cd frontend
npm run build      # outputs to frontend/dist
npm run preview    # serve the production build locally
```
