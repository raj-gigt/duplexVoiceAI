import asyncio

import numpy as np
import torch
from silero_vad import load_silero_vad

from config import SAMPLE_RATE, VAD_THRESHOLD

torch.set_num_threads(1)

_model = load_silero_vad()


def _is_speech_sync(audio_chunk: np.ndarray) -> bool:
    """Run VAD on a single chunk. Expects 512 samples at 16kHz."""
    tensor = torch.from_numpy(audio_chunk).float()
    # Silero expects float32 in [-1, 1] range; int16 -> float conversion
    if tensor.abs().max() > 1.0:
        tensor = tensor / 32768.0
    prob = _model(tensor, SAMPLE_RATE).item()
    return prob > VAD_THRESHOLD


async def is_speech(audio_chunk: np.ndarray) -> bool:
    """Async wrapper -- runs torch inference in a thread to avoid blocking."""
    return await asyncio.to_thread(_is_speech_sync, audio_chunk)


def reset():
    """Reset the VAD model state between utterances."""
    _model.reset_states()
