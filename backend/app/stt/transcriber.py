"""
Speech-to-Text Transcribers:
- GoogleSpeechTranscriber: Google Cloud / Web Speech Recognition API (best starting point, fast, high accuracy)
- LocalTranscriber: faster-whisper (runs 100% locally on CPU, offline backup)
- UnifiedTranscriber: Hybrid auto-switching engine with Google STT and offline Whisper fallback
"""

import os
from typing import Optional
import numpy as np

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

from app.logging.logger import get_logger

logger = get_logger(__name__)


class GoogleSpeechTranscriber:
    """
    Google Speech-to-Text transcriber using Google's Speech Recognition API.
    Zero-config, fast cloud transcription, high accuracy across all accents.
    Supports optional custom API key or standard Google Speech recognition service.
    """

    def __init__(self, api_key: Optional[str] = None, language: str = "en-IN"):
        self.api_key = api_key or os.getenv("GOOGLE_SPEECH_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.language = os.getenv("STT_LANGUAGE", language)
        self.language_code = self.language
        if sr is not None:
            self.recognizer = sr.Recognizer()
        else:
            self.recognizer = None
            logger.warning("speech_recognition library not installed, STT fallback active")
        logger.info("Google Speech-to-Text engine initialized", language=self.language, language_code=self.language_code, has_custom_key=bool(self.api_key))

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Synchronously transcribe float32 mono 16kHz audio array using Google Speech API.
        Returns transcribed text string.
        """
        if len(audio) < 1600 or self.recognizer is None:
            return ""

        try:
            # Convert float32 [-1.0, 1.0] to signed 16-bit PCM bytes
            clipped = np.clip(audio, -1.0, 1.0)
            pcm16 = (clipped * 32767.0).astype(np.int16).tobytes()
            audio_data = sr.AudioData(pcm16, sample_rate=16000, sample_width=2)

            text = self.recognizer.recognize_google(
                audio_data,
                key=self.api_key,
                language=self.language,
            )
            return text.strip()
        except sr.UnknownValueError:
            # Audio was received, but no words / unintelligible speech was detected
            return ""
        except sr.RequestError as e:
            logger.warning("Google Speech API request error, falling back to local Whisper", error=str(e))
            # Fallback to local whisper on network error or quota limits
            local = LocalTranscriber.get_instance()
            return local.transcribe(audio)
        except Exception as e:
            logger.error("Error during Google Speech transcription", error=str(e))
            return ""


class LocalTranscriber:
    """
    Local Speech-to-Text Transcriber using faster-whisper.
    Runs 100% locally on CPU, ultra-fast and completely free.
    """
    _instance: Optional["LocalTranscriber"] = None

    def __init__(self, model_size: str = "tiny.en", device: str = "cpu", compute_type: str = "int8"):
        logger.info("Initializing faster-whisper STT engine...", model=model_size, device=device)
        if WhisperModel is not None:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("faster-whisper STT engine ready.")
        else:
            self.model = None
            logger.warning("faster_whisper not installed")

    @classmethod
    def get_instance(cls, model_size: str = "tiny.en") -> "LocalTranscriber":
        if cls._instance is None:
            cls._instance = cls(model_size=model_size)
        return cls._instance

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Synchronously transcribe float32 mono 16kHz audio array.
        Returns transcribed text string.
        """
        if len(audio) < 1600 or self.model is None:  # Less than 0.1s or no model
            return ""

        try:
            segments, info = self.model.transcribe(
                audio,
                beam_size=1,
                language="en",
                condition_on_previous_text=False,
                vad_filter=False,
            )
            text = " ".join(s.text.strip() for s in segments if s.text.strip())
            return text.strip()
        except Exception as e:
            logger.error("Error during transcription", error=str(e))
            return ""


class UnifiedTranscriber:
    """
    Unified STT Manager:
    Selects Google Speech-to-Text by default (best starting point) with automatic
    fallback to local faster-whisper when offline or when configured.
    """
    _instance: Optional["UnifiedTranscriber"] = None

    def __init__(self):
        provider = os.getenv("STT_PROVIDER", "google").lower().strip()
        self.provider = provider
        self.google_stt = GoogleSpeechTranscriber()
        self.local_stt = LocalTranscriber.get_instance()
        logger.info("UnifiedTranscriber initialized", active_provider=self.provider)

    @classmethod
    def get_instance(cls) -> "UnifiedTranscriber":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe audio with selected provider and automatic fallback."""
        provider = os.getenv("STT_PROVIDER", self.provider).lower().strip()

        if provider in ("google", "google_speech", "gcs"):
            text = self.google_stt.transcribe(audio)
            if not text and len(audio) >= 4800:
                # If Google returned empty on longer audio, verify with local whisper
                text = self.local_stt.transcribe(audio)
            return text
        else:
            return self.local_stt.transcribe(audio)


def get_transcriber() -> UnifiedTranscriber:
    """Return the global unified speech transcriber."""
    return UnifiedTranscriber.get_instance()
