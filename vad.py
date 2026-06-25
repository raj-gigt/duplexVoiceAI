from __future__ import annotations

import asyncio

import numpy as np
import torch
from silero_vad import load_silero_vad

from config import AppConfig

torch.set_num_threads(1)


class SileroVAD:
    def __init__(self, config: AppConfig) -> None:
        self._model = load_silero_vad()
        self._sample_rate = config.sample_rate
        self._threshold = config.vad_threshold

    def _is_speech_sync(self, audio_chunk: np.ndarray) -> bool:
        """Run VAD on a single chunk. Expects 512 samples at 16 kHz."""
        tensor = torch.from_numpy(audio_chunk).float()
        if tensor.abs().max() > 1.0:
            tensor = tensor / 32768.0
        prob = self._model(tensor, self._sample_rate).item()
        return prob > self._threshold

    async def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Async wrapper -- runs torch inference in a thread to avoid blocking."""
        return await asyncio.to_thread(self._is_speech_sync, audio_chunk)

    def reset(self) -> None:
        """Reset the VAD model state between utterances."""
        self._model.reset_states()
