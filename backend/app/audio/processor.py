"""
Audio processing pipeline:
- Resampling to target rate (default 16000Hz for STT)
- Stereo / multi-channel to mono conversion
- PCM 16-bit encoding
- Energy / RMS computation
"""

import numpy as np
from scipy import signal
from typing import Tuple


class AudioProcessor:
    """Handles audio normalization, mono conversion, and resampling."""

    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate

    def to_mono(self, audio: np.ndarray) -> np.ndarray:
        """Convert multi-channel audio to mono by averaging channels."""
        if audio.ndim == 1:
            return audio
        elif audio.ndim == 2:
            return np.mean(audio, axis=1)
        else:
            return audio.flatten()

    def resample(self, audio: np.ndarray, orig_sr: int) -> np.ndarray:
        """Resample audio array to target sample rate using polyphase filtering."""
        if orig_sr == self.target_sample_rate:
            return audio
        if len(audio) == 0:
            return audio
        num_target_samples = int(round(len(audio) * float(self.target_sample_rate) / orig_sr))
        resampled = signal.resample(audio, num_target_samples)
        return resampled.astype(np.float32)

    def compute_rms(self, audio: np.ndarray) -> float:
        """Compute root-mean-square energy of the signal."""
        if len(audio) == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(audio))))

    def to_pcm16(self, audio: np.ndarray) -> bytes:
        """Convert float32 audio [-1.0, 1.0] to 16-bit signed PCM bytes."""
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        return pcm.tobytes()

    def process(self, raw_audio: np.ndarray, orig_sr: int) -> Tuple[np.ndarray, bytes, float]:
        """
        Runs complete pipeline: mono -> resample -> RMS -> PCM16.
        Returns: (float32_mono_resampled, pcm16_bytes, rms_energy)
        """
        mono = self.to_mono(raw_audio)
        resampled = self.resample(mono, orig_sr)
        rms = self.compute_rms(resampled)
        pcm16 = self.to_pcm16(resampled)
        return resampled, pcm16, rms
