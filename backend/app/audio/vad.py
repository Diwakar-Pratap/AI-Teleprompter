"""
Voice Activity Detection (VAD) module.
Implements a state machine:
SILENCE -> SPEECH_STARTED -> SPEAKING -> POSSIBLE_END -> SPEECH_ENDED
"""

import time
from typing import Optional, Tuple
from app.audio.types import VADState


class VoiceActivityDetector:
    """
    Adaptive energy-based Voice Activity Detector.
    Tracks background noise floor and identifies speech transitions.
    """

    def __init__(
        self,
        energy_threshold: float = 0.005,
        min_speech_duration_ms: float = 120.0,
        silence_timeout_ms: float = 500.0,
        adaptation_rate: float = 0.03,
    ):
        self.energy_threshold = energy_threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.adaptation_rate = adaptation_rate

        self.state: VADState = VADState.SILENCE
        self.speech_start_time: Optional[float] = None
        self.silence_start_time: Optional[float] = None
        self.background_energy: float = 0.002

    def update(self, rms_energy: float) -> Tuple[VADState, bool]:
        """
        Process current frame energy.
        Returns: (current_vad_state, state_changed_bool)
        """
        now = time.time()
        prev_state = self.state

        # Dynamic threshold based on background noise
        dynamic_threshold = max(self.energy_threshold, self.background_energy * 2.5)
        is_above_threshold = rms_energy > dynamic_threshold

        if not is_above_threshold and self.state == VADState.SILENCE:
            # Adapt noise floor slowly during silence
            self.background_energy = (
                (1.0 - self.adaptation_rate) * self.background_energy
                + self.adaptation_rate * rms_energy
            )

        if self.state == VADState.SILENCE:
            if is_above_threshold:
                self.state = VADState.SPEECH_STARTED
                self.speech_start_time = now
                self.silence_start_time = None

        elif self.state == VADState.SPEECH_STARTED:
            if is_above_threshold:
                duration_ms = (now - (self.speech_start_time or now)) * 1000.0
                if duration_ms >= self.min_speech_duration_ms:
                    self.state = VADState.SPEAKING
            else:
                # Glitch/click: return to silence
                self.state = VADState.SILENCE
                self.speech_start_time = None

        elif self.state == VADState.SPEAKING:
            if not is_above_threshold:
                self.state = VADState.POSSIBLE_END
                self.silence_start_time = now

        elif self.state == VADState.POSSIBLE_END:
            if is_above_threshold:
                # Resumed speaking
                self.state = VADState.SPEAKING
                self.silence_start_time = None
            else:
                silence_duration_ms = (now - (self.silence_start_time or now)) * 1000.0
                if silence_duration_ms >= self.silence_timeout_ms:
                    self.state = VADState.SPEECH_ENDED

        elif self.state == VADState.SPEECH_ENDED:
            # Reset back to silence on next step
            self.state = VADState.SILENCE
            self.speech_start_time = None
            self.silence_start_time = None

        state_changed = self.state != prev_state
        return self.state, state_changed

    def reset(self) -> None:
        """Reset state machine."""
        self.state = VADState.SILENCE
        self.speech_start_time = None
        self.silence_start_time = None
