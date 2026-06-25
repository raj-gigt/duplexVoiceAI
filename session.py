from __future__ import annotations

import asyncio
import time
from typing import AsyncIterator

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from config import AppConfig
from protocols import STTProvider, LLMProvider, TTSProvider
from vad import SileroVAD
from stt import DeepgramStreamingSTT
from llm import GroqLLM
from tts import ElevenLabsTTS


def _log(msg: str) -> None:
    t = time.time()
    ts = time.strftime("%H:%M:%S", time.localtime(t)) + f".{int(t * 1000) % 1000:03d}"
    print(f"[{ts}] {msg}")


def _ms(value: float | None) -> str:
    return f"{value:.0f}ms" if value is not None else "n/a"


class VoiceSession:
    """Per-connection facade orchestrating a fully streaming duplex pipeline:

    receive loop  -> forwards audio to STT + runs VAD for barge-in
    transcript loop -> assembles turns from Deepgram events
    pipeline task -> streams LLM tokens -> sentence chunks -> TTS -> client
    """

    def __init__(
        self,
        websocket: WebSocket,
        vad: SileroVAD,
        stt: STTProvider,
        llm: LLMProvider,
        tts: TTSProvider,
        config: AppConfig,
    ) -> None:
        self._ws = websocket
        self._vad = vad
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._cfg = config

        self._history = self._llm.create_history()
        self._turn_id = 0
        self._pipeline_task: asyncio.Task | None = None
        self._cancel_event = asyncio.Event()

        # VAD barge-in state
        self._vad_leftover = b""
        self._barge_in_count = 0
        self._bytes_per_chunk = config.vad_chunk_samples * 2  # 16-bit mono

        # Estimated wall-clock (perf_counter) time the client will finish playing
        # all audio we've sent. The assistant is "audible" until this point even
        # after the server-side pipeline finishes, so barge-in stays armed.
        self._playing_until = 0.0
        self._out_bytes_per_sec = config.sample_rate * 2  # 16-bit mono PCM

    # ------------------------------------------------------------------ run

    async def run(self) -> None:
        _log("[ws] Client connected.")
        await self._stt.start()

        recv = asyncio.create_task(self._receive_loop())
        trans = asyncio.create_task(self._transcript_loop())
        try:
            await asyncio.wait({recv, trans}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (recv, trans):
                t.cancel()
            await asyncio.gather(recv, trans, return_exceptions=True)
            await self.aclose()

    async def aclose(self) -> None:
        await self._cancel_pipeline()
        await self._stt.stop()
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- receive

    async def _receive_loop(self) -> None:
        try:
            while True:
                data = await self._ws.receive_bytes()
                await self._stt.send_audio(data)
                if self._cfg.interrupt_enabled and self._assistant_speaking():
                    await self._detect_barge_in(data)
        except WebSocketDisconnect:
            _log("[ws] Client disconnected.")

    async def _detect_barge_in(self, data: bytes) -> None:
        raw = self._vad_leftover + data
        self._vad_leftover = b""
        offset = 0
        while offset + self._bytes_per_chunk <= len(raw):
            chunk = raw[offset : offset + self._bytes_per_chunk]
            offset += self._bytes_per_chunk
            chunk_np = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
            if await self._vad.is_speech(chunk_np):
                self._barge_in_count += 1
                if self._barge_in_count >= self._cfg.interrupt_vad_chunks:
                    await self._on_barge_in()
                    self._barge_in_count = 0
            else:
                self._barge_in_count = 0
        if offset < len(raw):
            self._vad_leftover = raw[offset:]

    async def _on_barge_in(self) -> None:
        if not self._assistant_speaking():
            return
        _log("[interrupt] Barge-in detected -- cancelling assistant.")
        self._cancel_event.set()
        self._playing_until = 0.0
        await self._send_control({"type": "interrupt"})

    # ------------------------------------------------------------ transcript

    async def _transcript_loop(self) -> None:
        current = ""
        # Wall-clock time the most recent is_final arrived. Used as a robust
        # proxy for "user stopped speaking" -- immune to gaps in the audio stream
        # (mic toggles, idle periods) that desync Deepgram's audio timeline.
        last_final_t: float | None = None
        async for ev in self._stt.events():
            if ev.is_utterance_end:
                if current.strip():
                    gap = (time.perf_counter() - last_final_t) * 1000 if last_final_t else -1
                    _log(
                        f"[turn] trigger=UtteranceEnd "
                        f"gap_since_last_final={gap:.0f}ms text='{current.strip()}'"
                    )
                    await self._start_turn(current.strip(), last_final_t)
                    current = ""
                    last_final_t = None
                continue
            if ev.is_final:
                if ev.text:
                    current = (current + " " + ev.text).strip()
                    last_final_t = time.perf_counter()
                    _log(f"[stt] is_final='{ev.text}' speech_final={ev.speech_final}")
                if ev.speech_final and current.strip():
                    _log(f"[turn] trigger=speech_final text='{current.strip()}'")
                    await self._start_turn(current.strip(), last_final_t)
                    current = ""
                    last_final_t = None

    async def _start_turn(self, transcript: str, speech_end_t: float | None) -> None:
        # If the assistant is still audible (server still streaming OR the client
        # is draining its buffer), flush the client so the new turn doesn't talk
        # over leftover audio. Covers barge-ins Deepgram caught but local VAD didn't.
        if self._assistant_speaking():
            await self._send_control({"type": "interrupt"})
        # Supersede any in-flight pipeline cleanly.
        await self._cancel_pipeline()
        self._cancel_event.clear()
        self._playing_until = 0.0
        self._reset_barge_in()
        self._turn_id += 1
        tid = self._turn_id
        self._pipeline_task = asyncio.create_task(
            self._run_pipeline(transcript, tid, speech_end_t)
        )

    # -------------------------------------------------------------- pipeline

    async def _run_pipeline(
        self, transcript: str, turn_id: int, speech_end_t: float | None = None
    ) -> None:
        t0 = time.perf_counter()
        # Time spent in STT (endpointing silence wait + transcription lag) between
        # the user finishing speaking and this turn being triggered.
        endpoint_wait_ms = (t0 - speech_end_t) * 1000 if speech_end_t is not None else None
        _log(
            f"[pipeline] turn={turn_id} START stt_wait={_ms(endpoint_wait_ms)} "
            f"user='{transcript}'"
        )
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._cfg.tts_queue_maxsize)
        collected: list[str] = []
        interrupted = False
        first_token_ms: float | None = None
        first_sentence_ms: float | None = None
        first_audio_ms: float | None = None
        first_audio_from_speech_ms: float | None = None
        synth_total_ms = 0.0

        async def produce() -> None:
            nonlocal first_token_ms, first_sentence_ms
            try:

                async def timed_tokens() -> AsyncIterator[str]:
                    nonlocal first_token_ms
                    async for tok in self._llm.stream_response(transcript, self._history):
                        if first_token_ms is None:
                            first_token_ms = (time.perf_counter() - t0) * 1000
                            _log(
                                f"[pipeline] turn={turn_id} LLM first token "
                                f"in {first_token_ms:.0f}ms"
                            )
                        yield tok

                async for sentence in self._sentence_chunker(timed_tokens()):
                    if self._is_stale(turn_id):
                        return
                    if first_sentence_ms is None:
                        first_sentence_ms = (time.perf_counter() - t0) * 1000
                        _log(
                            f"[pipeline] turn={turn_id} first sentence "
                            f"in {first_sentence_ms:.0f}ms: '{sentence}'"
                        )
                    collected.append(sentence)
                    await queue.put(sentence)
            finally:
                await queue.put(None)

        async def consume() -> None:
            nonlocal interrupted, first_audio_ms, first_audio_from_speech_ms
            nonlocal synth_total_ms
            idx = 0
            while True:
                sentence = await queue.get()
                if sentence is None:
                    break
                if self._is_stale(turn_id):
                    interrupted = True
                    break
                idx += 1
                s_t0 = time.perf_counter()
                ttfb_ms: float | None = None
                sent_bytes = 0
                async for audio in self._tts.synthesize_stream(sentence):
                    if self._is_stale(turn_id):
                        interrupted = True
                        break
                    if ttfb_ms is None:
                        ttfb_ms = (time.perf_counter() - s_t0) * 1000
                    await self._ws.send_bytes(audio)
                    sent_bytes += len(audio)
                    # Advance the estimated client playback end-time. Audio plays
                    # back-to-back, so each chunk extends the buffer from whichever
                    # is later: now (buffer drained) or the prior end-time.
                    now_send = time.perf_counter()
                    chunk_secs = len(audio) / self._out_bytes_per_sec
                    self._playing_until = (
                        max(self._playing_until, now_send) + chunk_secs
                    )
                    if first_audio_ms is None:
                        now = time.perf_counter()
                        first_audio_ms = (now - t0) * 1000
                        if speech_end_t is not None:
                            first_audio_from_speech_ms = (now - speech_end_t) * 1000
                        _log(
                            f"[pipeline] turn={turn_id} >>> FIRST AUDIO to client "
                            f"in {first_audio_ms:.0f}ms (from speech end: "
                            f"{_ms(first_audio_from_speech_ms)}) <<<"
                        )
                synth_ms = (time.perf_counter() - s_t0) * 1000
                synth_total_ms += synth_ms
                _log(
                    f"[pipeline] turn={turn_id} TTS #{idx} {len(sentence)}ch "
                    f"-> {sent_bytes}B ttfb={_ms(ttfb_ms)} total={synth_ms:.0f}ms"
                )
                if interrupted:
                    break

        try:
            await asyncio.gather(produce(), consume())
        except asyncio.CancelledError:
            interrupted = True
            raise
        finally:
            end = time.perf_counter()
            total_ms = (end - t0) * 1000
            perceived_ms = (end - speech_end_t) * 1000 if speech_end_t is not None else None
            self._commit_history(transcript, collected, interrupted)
            _log(
                f"[pipeline] turn={turn_id} DONE sentences={len(collected)} "
                f"interrupted={interrupted} | stt_wait={_ms(endpoint_wait_ms)} "
                f"first_token={_ms(first_token_ms)} first_sentence={_ms(first_sentence_ms)} "
                f"first_audio={_ms(first_audio_ms)} "
                f"first_audio_from_speech={_ms(first_audio_from_speech_ms)} "
                f"tts_total={synth_total_ms:.0f}ms wall={total_ms:.0f}ms "
                f"perceived_total={_ms(perceived_ms)}"
            )

    def _commit_history(
        self, transcript: str, collected: list[str], interrupted: bool
    ) -> None:
        reply = " ".join(collected).strip()
        if interrupted or self._cancel_event.is_set():
            if reply:
                reply += " [interrupted by user]"
        if reply:
            self._history.append({"role": "user", "content": transcript})
            self._history.append({"role": "assistant", "content": reply})

    async def _sentence_chunker(
        self, token_stream: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        buffer = ""
        async for token in token_stream:
            buffer += token
            start = 0
            while True:
                idx = self._first_delim(buffer, start)
                if idx == -1:
                    break
                candidate = buffer[: idx + 1].strip()
                if len(candidate) >= self._cfg.min_sentence_chars:
                    yield candidate
                    buffer = buffer[idx + 1 :]
                    start = 0
                else:
                    start = idx + 1
        tail = buffer.strip()
        if tail:
            yield tail

    def _first_delim(self, s: str, start: int = 0) -> int:
        idx = -1
        for d in self._cfg.sentence_delimiters:
            p = s.find(d, start)
            if p != -1 and (idx == -1 or p < idx):
                idx = p
        return idx

    # ----------------------------------------------------------------- utils

    def _pipeline_active(self) -> bool:
        return self._pipeline_task is not None and not self._pipeline_task.done()

    def _assistant_speaking(self) -> bool:
        """True while the server is producing audio OR the client is still
        playing previously-sent audio. Keeps barge-in armed across the gap
        between the server finishing and the client's buffer draining."""
        return self._pipeline_active() or time.perf_counter() < self._playing_until

    def _is_stale(self, turn_id: int) -> bool:
        return self._cancel_event.is_set() or turn_id != self._turn_id

    def _reset_barge_in(self) -> None:
        self._barge_in_count = 0
        self._vad_leftover = b""
        self._vad.reset()

    async def _cancel_pipeline(self) -> None:
        if self._pipeline_task is not None and not self._pipeline_task.done():
            self._cancel_event.set()
            try:
                await self._pipeline_task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001
                pass
        self._pipeline_task = None

    async def _send_control(self, obj: dict) -> None:
        try:
            await self._ws.send_json(obj)
        except Exception:  # noqa: BLE001
            pass


class SessionFactory:
    """Creates VoiceSession instances. API clients for LLM/TTS are shared
    (stateless); STT and VAD are created per session (stateful)."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._llm = GroqLLM(config)
        self._tts = ElevenLabsTTS(config)

    def create_session(self, websocket: WebSocket) -> VoiceSession:
        return VoiceSession(
            websocket=websocket,
            vad=SileroVAD(self._config),
            stt=DeepgramStreamingSTT(self._config),
            llm=self._llm,
            tts=self._tts,
            config=self._config,
        )
