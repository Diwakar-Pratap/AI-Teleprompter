"""
Phase 2 Audio Engine Tests

Tests for:
- AudioDevice enumeration and discovery
- AudioProcessor (mono conversion, resampling, RMS, PCM16)
- VoiceActivityDetector state transitions
- AudioBuffer circular queue
- Audio device API endpoint
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.audio.types import AudioSourceType, VADState, AudioChunk
from app.audio.devices import AudioDeviceManager
from app.audio.processor import AudioProcessor
from app.audio.vad import VoiceActivityDetector
from app.audio.buffer import AudioBuffer


@pytest.fixture
def app() -> FastAPI:
    import os
    os.environ["TESTING"] = "1"
    from app.main import create_app
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


class TestAudioDevices:
    def test_get_devices_returns_list(self) -> None:
        devices = AudioDeviceManager.get_devices()
        assert isinstance(devices, list)
        assert len(devices) > 0

    def test_devices_have_expected_fields(self) -> None:
        devices = AudioDeviceManager.get_devices()
        first = devices[0]
        assert hasattr(first, "id")
        assert hasattr(first, "name")
        assert hasattr(first, "hostapi")
        assert hasattr(first, "is_loopback")

    def test_api_list_audio_devices(self, client: TestClient) -> None:
        response = client.get("/api/v1/audio/devices")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "name" in data[0]
        assert "is_loopback" in data[0]


class TestAudioProcessor:
    def test_to_mono_from_stereo(self) -> None:
        processor = AudioProcessor(target_sample_rate=16000)
        # Create stereo signal with channels [1.0, 0.0]
        stereo = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
        mono = processor.to_mono(stereo)
        assert mono.ndim == 1
        assert np.allclose(mono, [0.5, 0.5])

    def test_resample_reduces_or_expands_length(self) -> None:
        processor = AudioProcessor(target_sample_rate=16000)
        # 1 second of 48000Hz audio
        audio_48k = np.zeros(48000, dtype=np.float32)
        resampled = processor.resample(audio_48k, orig_sr=48000)
        assert len(resampled) == 16000

    def test_compute_rms(self) -> None:
        processor = AudioProcessor(target_sample_rate=16000)
        silence = np.zeros(1000, dtype=np.float32)
        assert processor.compute_rms(silence) == 0.0

        signal_ones = np.ones(1000, dtype=np.float32)
        assert np.isclose(processor.compute_rms(signal_ones), 1.0)

    def test_to_pcm16_clipping(self) -> None:
        processor = AudioProcessor(target_sample_rate=16000)
        audio = np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32)
        pcm = processor.to_pcm16(audio)
        assert isinstance(pcm, bytes)
        assert len(pcm) == len(audio) * 2  # 16-bit = 2 bytes per sample

    def test_process_pipeline(self) -> None:
        processor = AudioProcessor(target_sample_rate=16000)
        raw = np.random.uniform(-0.5, 0.5, (44100, 2)).astype(np.float32)
        f32, pcm16, rms = processor.process(raw, orig_sr=44100)
        assert len(f32) == 16000
        assert len(pcm16) == 16000 * 2
        assert rms > 0.0


class TestVoiceActivityDetector:
    def test_vad_starts_in_silence(self) -> None:
        vad = VoiceActivityDetector()
        assert vad.state == VADState.SILENCE

    def test_vad_detects_speech_start_on_energy(self) -> None:
        vad = VoiceActivityDetector(energy_threshold=0.01)
        state, changed = vad.update(rms_energy=0.05)
        assert state == VADState.SPEECH_STARTED
        assert changed is True

    def test_vad_speech_ended_after_silence(self) -> None:
        vad = VoiceActivityDetector(
            energy_threshold=0.01,
            min_speech_duration_ms=0.0,
            silence_timeout_ms=10.0,
        )
        vad.update(rms_energy=0.05)
        vad.update(rms_energy=0.05)
        # Now drop energy to silence
        vad.update(rms_energy=0.001)
        import time
        time.sleep(0.02)
        state, _ = vad.update(rms_energy=0.001)
        assert state == VADState.SPEECH_ENDED


class TestAudioBuffer:
    def test_push_and_length(self) -> None:
        buf = AudioBuffer(max_chunks=5)
        chunk = AudioChunk(
            data=b"\x00\x00",
            sample_rate=16000,
            channels=1,
            timestamp=0.0,
            source=AudioSourceType.SYSTEM,
            rms_energy=0.0,
        )
        for _ in range(3):
            buf.push(chunk)
        assert len(buf) == 3

    def test_buffer_respects_max_chunks(self) -> None:
        buf = AudioBuffer(max_chunks=3)
        chunk = AudioChunk(
            data=b"\x01\x02",
            sample_rate=16000,
            channels=1,
            timestamp=0.0,
            source=AudioSourceType.SYSTEM,
            rms_energy=0.0,
        )
        for _ in range(10):
            buf.push(chunk)
        assert len(buf) == 3

    def test_concatenated_pcm(self) -> None:
        buf = AudioBuffer(max_chunks=5)
        chunk = AudioChunk(
            data=b"test",
            sample_rate=16000,
            channels=1,
            timestamp=0.0,
            source=AudioSourceType.SYSTEM,
            rms_energy=0.0,
        )
        buf.push(chunk)
        buf.push(chunk)
        assert buf.get_concatenated_pcm() == b"testtest"
