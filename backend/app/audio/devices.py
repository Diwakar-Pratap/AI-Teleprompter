"""
Audio device enumerator.
Discovers available microphones and WASAPI loopback output devices.
"""

from typing import List, Optional

try:
    import sounddevice as sd
except (ImportError, OSError):
    sd = None

from app.audio.types import AudioDevice
from app.logging.logger import get_logger

logger = get_logger(__name__)


class AudioDeviceManager:
    """Enumerates and queries input/output audio hardware."""

    @staticmethod
    def get_devices() -> List[AudioDevice]:
        """List all discovered audio devices across host APIs."""
        devices: List[AudioDevice] = []
        if sd is None:
            logger.debug("sounddevice/PortAudio library is not available in this environment")
            return devices

        try:
            device_list = sd.query_devices()
            host_apis = sd.query_hostapis()
            default_input, default_output = sd.default.device

            for idx, d in enumerate(device_list):
                host_api_name = host_apis[d["hostapi"]]["name"] if d["hostapi"] < len(host_apis) else "Unknown"
                is_loopback = ("wasapi" in host_api_name.lower()) and (d["max_output_channels"] > 0)

                device = AudioDevice(
                    id=idx,
                    name=d["name"],
                    hostapi=host_api_name,
                    max_input_channels=d["max_input_channels"],
                    max_output_channels=d["max_output_channels"],
                    default_samplerate=d["default_samplerate"],
                    is_default_input=(idx == default_input),
                    is_default_output=(idx == default_output),
                    is_loopback=is_loopback,
                )
                devices.append(device)
        except Exception as e:
            logger.error("Failed to query audio devices", error=str(e))
        return devices

    @staticmethod
    def get_default_input_device() -> Optional[AudioDevice]:
        """Get system default microphone input device."""
        devices = AudioDeviceManager.get_devices()
        for d in devices:
            if d.is_default_input and d.max_input_channels > 0:
                return d
        for d in devices:
            if d.max_input_channels > 0:
                return d
        return None

    @staticmethod
    def get_default_loopback_device() -> Optional[AudioDevice]:
        """Get system default WASAPI loopback audio output device."""
        devices = AudioDeviceManager.get_devices()
        # Prefer default output device under WASAPI
        for d in devices:
            if "wasapi" in d.hostapi.lower() and d.is_default_output and d.max_output_channels > 0:
                return d
        for d in devices:
            if "wasapi" in d.hostapi.lower() and d.max_output_channels > 0:
                return d
        return None
