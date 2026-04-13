import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

import vad
import stt
import llm
import tts
from config import SAMPLE_RATE, VAD_CHUNK_SAMPLES, SILENCE_DURATION_MS

app = FastAPI()

# Number of consecutive silent chunks needed to trigger the pipeline.
# Each chunk is VAD_CHUNK_SAMPLES samples at SAMPLE_RATE.
_chunk_duration_ms = (VAD_CHUNK_SAMPLES / SAMPLE_RATE) * 1000
SILENCE_CHUNKS_NEEDED = int(SILENCE_DURATION_MS / _chunk_duration_ms)


async def process_pipeline(
    audio_buffer: bytearray, history: list[dict], websocket: WebSocket
) -> None:
    """Run the full STT -> LLM -> TTS pipeline and send audio back."""
    audio_bytes = bytes(audio_buffer)

    print(f"[pipeline] Transcribing {len(audio_bytes)} bytes of audio...")
    transcript = await stt.transcribe(audio_bytes)
    if not transcript:
        print("[pipeline] Empty transcript, skipping.")
        return

    print(f"[pipeline] User said: {transcript}")

    print("[pipeline] Getting LLM response...")
    reply = await llm.get_response(transcript, history)
    print(f"[pipeline] Assistant: {reply}")

    print("[pipeline] Synthesizing speech...")
    response_audio = await tts.synthesize(reply)
    print(f"[pipeline] Sending {len(response_audio)} bytes of audio back.")

    await websocket.send_bytes(response_audio)


@app.websocket("/voice")
async def voice_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[ws] Client connected.")

    audio_buffer = bytearray()
    history = llm.create_history()
    speech_active = False
    silence_chunks = 0
    # Leftover bytes from the previous receive that didn't fill a full VAD chunk
    leftover = b""

    # TODO: Add interruption handling -- when user speaks while assistant
    #       audio is playing, cancel the current TTS playback and restart
    #       the pipeline with the new user input.

    try:
        while True:
            data = await websocket.receive_bytes()
            raw = leftover + data
            leftover = b""

            bytes_per_chunk = VAD_CHUNK_SAMPLES * 2  # 16-bit = 2 bytes/sample
            offset = 0

            while offset + bytes_per_chunk <= len(raw):
                chunk_bytes = raw[offset : offset + bytes_per_chunk]
                chunk_np = np.frombuffer(chunk_bytes, dtype=np.int16).astype(
                    np.float32
                )
                offset += bytes_per_chunk

                speech_detected = await vad.is_speech(chunk_np)

                if speech_detected:
                    speech_active = True
                    silence_chunks = 0
                    audio_buffer.extend(chunk_bytes)
                elif speech_active:
                    # Still buffer audio during short silences within speech
                    audio_buffer.extend(chunk_bytes)
                    silence_chunks += 1

                    if silence_chunks >= SILENCE_CHUNKS_NEEDED:
                        print("[ws] End of speech detected, processing...")
                        await process_pipeline(audio_buffer, history, websocket)

                        audio_buffer.clear()
                        speech_active = False
                        silence_chunks = 0
                        vad.reset()

            # Save any remaining bytes for the next iteration
            if offset < len(raw):
                leftover = raw[offset:]

    except WebSocketDisconnect:
        print("[ws] Client disconnected.")
    except Exception as e:
        print(f"[ws] Error: {e}")
        await websocket.close()
