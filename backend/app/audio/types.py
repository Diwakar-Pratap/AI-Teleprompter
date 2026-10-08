"""
Audio types, data structures, and enumeration.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Literal


class AudioSourceType(str, Enum):
    SYSTEM = "system"
    MICROPHONE = "microphone"
    BOTH = "both"


class VADState(str, Enum):
    SILENCE = "SILENCE"
    SPEECH_STARTED = "SPEECH_STARTED"
    SPEAKING = "SPEAKING"
    POSSIBLE_END = "POSSIBLE_END"
    SPEECH_ENDED = "SPEECH_ENDED"


SpeakerRole = Literal["interviewer", "interviewee", "system", "other"]


@dataclass
class AudioDevice:
    id: int
    name: str
    hostapi: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_default_input: bool = False
    is_default_output: bool = False
    is_loopback: bool = False


@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int
    channels: int
    timestamp: float
    source: AudioSourceType
    rms_energy: float
    is_speech: bool = False
    speaker: SpeakerRole = "other"
