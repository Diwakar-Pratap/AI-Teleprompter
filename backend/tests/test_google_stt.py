"""
Tests for Google Speech-to-Text and Unified STT Engine.
"""

import numpy as np
import pytest
from app.stt.transcriber import (
    GoogleSpeechTranscriber,
    LocalTranscriber,
    UnifiedTranscriber,
    get_transcriber,
)


def test_google_transcriber_initialization():
    google_stt = GoogleSpeechTranscriber()
    assert google_stt is not None
    assert google_stt.language == "en-IN"
    assert google_stt.language_code == "en-IN"
    assert google_stt.recognizer is not None


def test_google_transcriber_handles_short_audio():
    google_stt = GoogleSpeechTranscriber()
    short_audio = np.zeros(500, dtype=np.float32)
    assert google_stt.transcribe(short_audio) == ""


def test_google_transcriber_handles_silence():
    google_stt = GoogleSpeechTranscriber()
    silence = np.zeros(16000, dtype=np.float32)
    result = google_stt.transcribe(silence)
    assert result == ""


def test_unified_transcriber_singleton():
    t1 = get_transcriber()
    t2 = UnifiedTranscriber.get_instance()
    assert t1 is t2


def test_unified_transcriber_default_provider():
    unified = get_transcriber()
    assert unified.provider in ("google", "whisper")
